import logging
import pprint
import redis
import requests
import arrow
import asyncio
import math
import time
import copy

from arrow import Arrow
from requests import get, RequestException
from cachetools import cached, TTLCache
from cachecontrol import CacheControl
from cachecontrol import CacheControlAdapter
from cachecontrol.caches.redis_cache import RedisCache
from cachecontrol.heuristics import ExpiresAfter
from functools import reduce

from .utils import parse_date_range
from .utils import SortbyDictionary
from .utils import make_fuzzy_string_comparison

from .duckling_service import (
    parse_checkin_time,
    parse_bkinfo_duration,
    parse_bkinfo_price,
)


pp = pprint.PrettyPrinter(indent=4)
logger = logging.getLogger(__name__)

BASE_URL = 'https://booking-com.p.rapidapi.com/v1'
CURRENCY = 'USD'
LOCALE = 'en-gb'
UNITS = 'metric'
PRICE_MARGIN = 0.07
REQUESTS_CACHE_MINS = 60

# comply to https://booking-com.p.rapidapi.com/v1/hotels/locations api's dest_type field
DEST_TYPE_HOTEL = 'hotel'
DEST_TYPE_LANDMARK = 'landmark'
DEST_TYPE_AIRPORT = 'airport'
DEST_TYPE_CITY = 'city'
DEST_TYPE_DISTRICT = 'district'
DEST_TYPE_REGION = 'region'
DEST_TYPE_REGION_EXC = 'region_exc'

"""
IMPOTANT:
    - Mapping bkinfo_area_type to dest_type field
    - Refer to https://booking-com.p.rapidapi.com/v1/hotels/locations
    - Notes:
        1) `region` slot and entity which are recognize by NLU have differenct mapping: 'state', 'province', 'county' -> region
        2) 'island', 'islands', 'bay' are small, convenient region that are usaully used when searching for hotel
        3) dest_type of 'district' is also complement info (but granted more priority because more specific than 'state', 'province', 'county')
        4) dest_type of 'district' can not be mapped by bkinfo_area because in NLU sample it usually go allong with normal bkinfon_area expression, causes difficulty for annotation
        5) standing-alone 'district' is usaully ambiguous
"""
AREA_DEST_TYPE = {
    # assigned to hotel
    DEST_TYPE_HOTEL: ['hotel', 'hotels'],
    # assigned to beach, lake, cave, bridge, museum
    DEST_TYPE_LANDMARK: ['beach', 'beaches', 'lake', 'lakes', 'cave', 'caves', 'bridge', 'bridges', 'museum', 'station', 'terminal', 'university'],
    # assigned to airport
    DEST_TYPE_AIRPORT: ['airport'],
    # assigned to city
    DEST_TYPE_CITY: ['city', 'cities'],
    # assigned to  island, bay
    DEST_TYPE_REGION: ['island', 'islands', 'bay', 'bays'],
    # 'state', 'province', 'region' 'county' are not bkinfo_area_type but entities that are recognized as region
    DEST_TYPE_REGION_EXC: ['state', 'province', 'county'],
    # 'district' are not bkinfo_area_type neither implied by bkinfo_area but entities that are recognized via bkinfo_district
    DEST_TYPE_DISTRICT: ['district'],
}

headers = {
    "X-RapidAPI-Key": "6ddab563a2mshfe98ce973810751p137295jsnd9d1bea86c0e",
    "X-RapidAPI-Host": "booking-com.p.rapidapi.com"
}

pool = redis.ConnectionPool(host='redis', port=6379, db=0,  password='qwer1234')
r = redis.Redis(connection_pool=pool)
requests_sess = CacheControl(sess=requests.Session(), cache=RedisCache(r), heuristic=ExpiresAfter(minutes=REQUESTS_CACHE_MINS))


def make_request_to_bookingapi(url, headers, params):

    for i in range(3):
        try:
            response = requests_sess.get(url, headers=headers, params=params)
            response.raise_for_status()

            return response

        except RequestException:
            logger.error('[INFO] try to request_to_search_hotel, %s, API url: %s, HttpError: %s', 'RequestException', response.url, response.reason)
            time.sleep(0.1)

    # TODO: propagate the error back to action to inform user something like
    # "I got problem while communicating booking service, please try again after few minutes"
    return None


# @cached(cache=TTLCache(maxsize=128, ttl=60))
async def search_rooms(
        bkinfo_area, bkinfo_checkin_time, bkinfo_duration,
        bkinfo_bed_type, bkinfo_price, bkinfo_orderby,
        bkinfo_area_type=None, bkinfo_district=None, bkinfo_region=None,
        bkinfo_country=None,
    ):
    """
        search_locations
        search_hotel
        request_room_list_by_hotel
        filter by price, adult_number
        ADVANCES:
        - sort by price, sort by review_score
        - filter by bed_type
    """
    info_msg = f"""
        [INFO] searching parameters: (
            bkinfo_area: {bkinfo_area},
            bkinfo_area_type: {bkinfo_area_type},
            bkinfo_district: {bkinfo_district},
            bkinfo_region: {bkinfo_region},
            bkinfo_country: {bkinfo_country},
            bkinfo_checkin_time: {bkinfo_checkin_time},
            bkinfo_duration: {bkinfo_duration},
            bkinfo_bed_type: {bkinfo_bed_type},
            bkinfo_price: {bkinfo_price},
            bkinfo_orderby: {bkinfo_orderby},)
    """
    logger.info(info_msg)

    destination = choose_location(
        bkinfo_area=bkinfo_area, bkinfo_area_type=bkinfo_area_type,
        bkinfo_district=bkinfo_district, bkinfo_region=bkinfo_region,
        bkinfo_country=bkinfo_country,
    )

    if not destination:
        return {}

    logger.info('[INFO] will look for hotels in this destination: %s', destination)

    checkin_date = parse_checkin_time(expression=bkinfo_checkin_time)
    duration = parse_bkinfo_duration(expression=bkinfo_duration)
    checkin_date, checkout_date = parse_date_range(from_time=checkin_date.value, duration=duration.value)
    logger.info('[INFO] will look for hotels from %s to %s', checkin_date, checkout_date)

    max_price = parse_bkinfo_price(expression=bkinfo_price)
    logger.info('[INFO] will look for hotels in price below %s', max_price)

    if destination.get('dest_type') == DEST_TYPE_HOTEL:
        hotel = request_hotel_data(hotel_id=destination.get('dest_id'))
        # To solve the discrepancy of format of data of request_to_search_hotel and request_hotel_data
        hotels = [uniformize_hotel_data(hotel)]
    else:
        hotels = request_to_search_hotel(
            dest_id=destination['dest_id'],
            dest_type=destination['dest_type'],
            checkin_date=checkin_date,
            checkout_date=checkout_date,
            order_by=bkinfo_orderby,
            currency=max_price.unit,
        )
        hotels = hotels.get('result', [])
    logger.info('[INFO] request_to_search_hotel, found %s results.', len(hotels))

    if bkinfo_orderby == SortbyDictionary.SORTBY_REVIEW_SCORE:
        hotels = sort_hotel_by_review_score(hotels)

    hotels = { hotel['hotel_id']:hotel for hotel in hotels }
    hotel_id_list = list(hotels.keys())

    room_list = await get_room_list(hotel_id_list, checkin_date=checkin_date, checkout_date=checkout_date, currency=max_price.unit)
    logger.info('[INFO] query room by hotels %s, found %s rooms', hotel_id_list, len(room_list))

    rooms_groupby_hotel_id = {}
    for item in room_list:
        blocks = item.get('block', None)
        if not blocks:
            continue

        hotel_id = item.get('hotel_id', None)
        if not hotel_id:
            continue
        hotel = hotels[hotel_id]
        ref_rooms = item['rooms']
        for block in blocks:
            room = curate_room_info(hotel=hotel, block=block, ref_rooms=ref_rooms)

            if not verifyif_room_in_price_range(room=room, price=max_price.value):
                logger.info('[INFO] room, %s, does not match price, room_min_price: %s, max_price: %s', room['room_id'], room['min_price'], max_price.value)
                continue
            if not verifyif_room_has_bed_type(room_bed_type=room['bed_type'], bed_type=bkinfo_bed_type):
                logger.info('[INFO] room, %s, does not match bed type, room_bed_type: %s, bkinfo_bed_type: %s', room['room_id'], room['bed_type'].get('name'), bkinfo_bed_type)
                continue

            hotel_id = room['hotel_id']
            if rooms_groupby_hotel_id.get(hotel_id, None):
                rooms_groupby_hotel_id[hotel_id].append(room)
            else:
                rooms_groupby_hotel_id[hotel_id] = [room]

    if bkinfo_orderby == SortbyDictionary.SORTBY_PRICE:
        rooms_groupby_hotel_id = sort_hotel_by_min_room_price(rooms_groupby_hotel_id)

    # Regardless of sorting way rooms in a group are alwasys ascendently sorted by price
    sorted_rooms = sort_rooms_by_price(rooms_groupby_hotel_id)

    return sorted_rooms


def uniformize_hotel_data(hotel):
    mappings = [
        ('hotel_id', 'hotel_id'),
        ('hotel_name_trans', 'name'),
        ('address_trans', 'address'),
        ('max_1440_photo_url', 'main_photo_url'),
        ('city_trans', 'city'),
        ('city_name_en', 'city'),
        ('country_trans', 'country'),
        ('is_beach_front', 'unavailable'),
        ('nearest_beach_name', 'unavailable'),
        ('review_score', 'review_score'),
    ]

    uniformized = copy.copy(hotel)
    for pair in mappings:
        uniformized[pair[0]] = uniformized.get(pair[1], '')

    return uniformized


def sort_rooms_by_price(rooms):
    result = {}
    for hotel_id, rooms in rooms.items():
        result[hotel_id] = sorted(rooms, key=lambda x: x['min_price'])

    return result


def sort_hotel_by_min_room_price(rooms_groupby_hotel_id):
    tmp = {}

    for hotel_id, rooms in rooms_groupby_hotel_id.items():
        lowest_room = min(rooms, key=lambda room: room['min_price'])
        tmp[hotel_id] = lowest_room['min_price']

    sorted_hotels = sorted(tmp, key=tmp.get)
    result = {hotel_id:rooms_groupby_hotel_id[hotel_id] for hotel_id in sorted_hotels}

    return result


def sort_hotel_by_review_score(hotels):
    return sorted(hotels, key=lambda x: x['review_score'], reverse=True)


def verifyif_room_has_bed_type(room_bed_type, bed_type):
    name = room_bed_type.get('name', '')
    name = name.lower()
    return name.find(bed_type) != -1


def verifyif_room_in_price_range(room, price):
    max_price = price + price * PRICE_MARGIN
    room_price = room['min_price']
    return room_price < max_price


def curate_room_info(hotel, block, ref_rooms):
    room_id = str(block['room_id'])
    room = ref_rooms[room_id]

    return {
        'hotel_id': hotel.get('hotel_id', ''),
        'hotel_name_trans': hotel.get('hotel_name_trans', ''),
        'address_trans': hotel.get('address_trans', ''),
        'hotel_photo_url': hotel.get('max_1440_photo_url', ''),
        'city_trans': hotel.get('city_trans', ''),
        'city_name_en': hotel.get('city_name_en', None),
        'country_trans': hotel.get('country_trans', ''),
        'is_beach_front': hotel.get('is_beach_front', False),
        'nearest_beach_name': hotel.get('nearest_beach_name', ''),
        'review_score': float(hotel.get('review_score')) if hotel.get('review_score') else -1.0,
        'min_price': float(block.get('product_price_breakdown', {}).get('gross_amount_per_night', {}).get('value', -1.0)),
        'price_currency': block.get('product_price_breakdown', {}).get('gross_amount_per_night', {}).get('currency', 'unknown'),
        'max_occupancy': int(block.get('max_occupancy', 2)),
        'name_without_policy': block.get('name_without_policy', ''),
        'room_id': room_id,
        'bed_type': extract_bed_type(room),
        'facilities': room.get('facilities', []),
        'description': room.get('description', ''),
        'photos': room.get('photos', []),
    }


def extract_bed_type(room):
    bed_configurations = room.get('bed_configurations', None)
    if not bed_configurations:
        return {}

    if len(bed_configurations) == 0:
        return {}

    bed_types = bed_configurations[0]['bed_types']
    if len(bed_types) == 0:
        return {}

    return bed_types[0]

async def get_room_list(hotel_id_list, checkin_date, checkout_date, currency=CURRENCY):
    total_num = len(hotel_id_list)
    reqnum_limit = 4
    total_page = math.ceil(total_num / reqnum_limit)
    schedule = []
    for idx in range(total_page):
        start = idx * reqnum_limit
        end = start + reqnum_limit
        schedule.append(hotel_id_list[start:end])

    loop = asyncio.get_running_loop()

    result = []
    for tasks in schedule:
        futures = []
        for hotel_id in tasks:
            futures.append(loop.run_in_executor( None, request_room_list_by_hotel, hotel_id, checkin_date, checkout_date, currency))
        for response in await asyncio.gather(*futures):
            for item in response:
                result.append(item)

    return result


def request_room_list_by_hotel(hotel_id, checkin_date, checkout_date, currency=CURRENCY):
    """
    >>> rooms = response.json()
    >>> rooms[0].keys()
    dict_keys([
        'is_cpv2_property', 'max_rooms_in_reservation', 'b_legal_use_neutral_color_for_persuasion_legal', 'is_exclusive', 'qualifies_for_no_cc_reservation',
        'duplicate_rates_removed', 'min_room_distribution', 'top_ufi_benefits', 'arrival_date', 'total_blocks', 'soldout_rooms', 'preferences',
        'use_new_bui_icon_highlight', 'block', 'hotel_id', 'b_max_los_data', 'address_required', 'room_recommendation', 'cc_required', 'departure_date',
        'tax_exceptions', 'rooms', 'cvc_required', 'last_matching_block_index'])
    """

    url = f"{BASE_URL}/hotels/room-list"
    number_of_occupancy = 2
    number_of_room = 1
    currency_code = convert_currency_symbol_to_code(currency)

    querystring = {
        "checkin_date": checkin_date,
        "checkout_date": checkout_date,
        "hotel_id": hotel_id,
        "adults_number_by_rooms": number_of_occupancy,
        "room_number": number_of_room,
        "currency": currency_code,
        "locale": LOCALE,
        "units": UNITS,
    }

    response = make_request_to_bookingapi(url, headers=headers, params=querystring)
    logger.info('[INFO] request_room_list_by_hotel, API url: %s', response.url)

    if not response.ok:
        return []

    result = response.json()

    # logger.info('[INFO] query room by hotel id: %s, found %s rooms', hotel_id, sum(len(item['block']) for item in result))

    return result


def request_to_search_hotel(dest_id, dest_type, checkin_date, checkout_date, order_by, currency=CURRENCY):
    """
    >>> hotels = response.json()
    >>> hotels.keys()
    dict_keys(['primary_count', 'count', 'room_distribution', 'map_bounding_box', 'total_count_with_filters',
        'unfiltered_count', 'extended_count', 'unfiltered_primary_count', 'search_radius', 'sort', 'result'])
    >>> hotels.result[0].keys()
    dict_keys(['hotel_include_breakfast', 'in_best_district', 'latitude', 'extended', 'class_is_estimated',
        'review_score_word', 'is_free_cancellable', 'is_wholesaler_candidate', 'checkout', 'native_ads_tracking',
        'badges', 'composite_price_breakdown', 'is_smart_deal', 'timezone', 'cc1', 'accommodation_type_name',
        'district_id', 'is_mobile_deal', 'hotel_has_vb_boost', 'city', 'soldout', 'districts', 'city_name_en',
        'is_beach_front', 'review_nr', 'city_in_trans', 'is_geo_rate', 'price_breakdown', 'nearest_beach_name',
        'longitude', 'main_photo_id', 'city_trans', 'preferred_plus', 'countrycode', 'review_score',
        'default_language', 'rewards', 'block_ids', 'checkin', 'hotel_id', 'district', 'is_city_center',
        'address_trans', 'id', 'distance_to_beach_in_meters', 'hotel_name', 'is_genius_deal', 'type',
        'unit_configuration_label', 'children_not_allowed', 'address', 'hotel_facilities', 'zip', 'preferred',
        'url', 'is_no_prepayment_block', 'accommodation_type', 'cc_required', 'min_total_price', 'distance',
        'ufi', 'mobile_discount_percentage', 'genius_discount_percentage', 'native_ads_cpc', 'review_recommendation',
        'price_is_final', 'distance_to_cc', 'default_wishlist_name', 'distances', 'selected_review_topic', 'class',
        'cant_book', 'hotel_name_trans', 'currency_code', 'currencycode', 'country_trans', 'main_photo_url',
        'native_ad_id', 'bwallet', 'wishlist_count', 'max_photo_url', 'max_1440_photo_url'])
    """

    url = f"{BASE_URL}/hotels/search"
    number_of_occupancy = 2
    number_of_room = 1
    currency_code = convert_currency_symbol_to_code(currency)

    querystring = {
        "order_by": order_by,
        "checkin_date": checkin_date,
        "checkout_date": checkout_date,
        "dest_id": dest_id,
        "dest_type": dest_type,
        "adults_number": number_of_occupancy,
        "room_number": number_of_room,
        "filter_by_currency": currency_code,
        "locale": LOCALE,
        "units": UNITS,
    }

    response = make_request_to_bookingapi(url, headers=headers, params=querystring)

    logger.info('[INFO] request_to_search_hotel, API url: %s', response.url)

    if response:
        return response.json()
    return {}


def request_hotel_data(hotel_id):
    """
    >>> details = response.json()
    >>> type(details)
    <class 'dict'>
    >>> details.keys()
    dict_keys(['ranking', 'countrycode', 'class', 'zip', 'name', 'main_photo_url', 'minrate', 'checkout', 'checkin', 'city', 'currencycode', 'hoteltype_id', 'hotel_facilities_filtered', 'review_score', 'class_is_estimated', 'is_single_unit_vr', 'is_vacation_rental', 'main_photo_id', 'district_id', 'languages_spoken', 'maxrate', 'booking_home', 'review_nr', 'country', 'hotel_id', 'location', 'hotel_facilities', 'address', 'city_id', 'url', 'email', 'description_translations', 'review_score_word', 'district', 'preferred_plus', 'preferred'])
    """

    global BASE_URL
    global headers
    global LOCALE

    url = f"{BASE_URL}/hotels/data"
    querystring = {
        "hotel_id": hotel_id,
        "locale": LOCALE,
    }

    response = make_request_to_bookingapi(url, headers=headers, params=querystring)
    logger.info('[INFO] request_hotel_data, API url: %s', response.url)

    return response.json()


@cached(cache=TTLCache(maxsize=32, ttl=300))
def request_to_search_locations(name):
    """
    >>> locations = response.json()
    >>> locations[0].keys()
    dict_keys(['longitude', 'city_ufi', 'hotels', 'region', 'rtl', 'city_name', 'country', 'b_max_los_data', 'name', 'latitude', 'type', 'cc1', 'label', 'image_url', 'dest_type', 'nr_hotels', 'dest_id', 'lc'])
    """

    url = f"{BASE_URL}/hotels/locations"

    querystring = {
        "name": name,
        "locale": LOCALE,
    }

    response = make_request_to_bookingapi(url, headers=headers, params=querystring)
    logger.info('[INFO] request_to_search_locations, API url: %s', response.url)

    return response.json()


def index_location_by_dest_type(locations):
    result = {}
    for item in locations:
        dest_type = item['dest_type']
        if result.get(dest_type, None):
            result[dest_type].append(item)
        else:
            result[dest_type] = [item]

    return result


def compose_location_name(bkinfo_area, bkinfo_area_type=None, bkinfo_district=None, bkinfo_region=None, bkinfo_country=None):
    SPACE_CHAR = "\u0020"

    # to reduce unnecessary inforamtion to make search more precise
    # if bkinfo_area_type is of landmark so bkinfo_district is unnecessary
    remarkable_dest_types = AREA_DEST_TYPE[DEST_TYPE_HOTEL] + AREA_DEST_TYPE[DEST_TYPE_LANDMARK] + AREA_DEST_TYPE[DEST_TYPE_AIRPORT]
    bkinfo_district = bkinfo_district if bkinfo_area_type not in remarkable_dest_types else None

    params = [bkinfo_area, bkinfo_area_type, bkinfo_district, bkinfo_region, bkinfo_country]
    params = list(filter(lambda x: x, params))

    return SPACE_CHAR.join(params)


def choose_location(bkinfo_area, bkinfo_area_type=None, bkinfo_district=None, bkinfo_region=None, bkinfo_country=None):
    name = compose_location_name(
        bkinfo_area,
        bkinfo_area_type=bkinfo_area_type,
        bkinfo_district=bkinfo_district,
        bkinfo_region=bkinfo_region,
        bkinfo_country=bkinfo_country,
    )

    logger.info('[DEV] request_to_search_locations -> %s', name)
    locations = request_to_search_locations(name=name)
    logger.info('[INFO] request_to_search_locations, found %s location(s) in respective to query: %s', len(locations), name)

    if len(locations) == 0:
        return None

    return find_most_likely_locations(
        locations=locations,
        bkinfo_area=bkinfo_area,
        bkinfo_area_type=bkinfo_area_type,
        bkinfo_district=bkinfo_district,
        bkinfo_region=bkinfo_region,
        bkinfo_country=bkinfo_country,
    )


def find_most_likely_locations(locations, bkinfo_area, bkinfo_area_type=None, bkinfo_district=None, bkinfo_region=None, bkinfo_country=None):
    """
    Logic of priority:
        1: explicit area_type -> dest_type
        2: bkinfo_area and hotel_name are matched strictly
        3: if bkinfo_district is present, take dest_type -> district
        4: dest_type >> landmark >> city >> region >> hotel

    Notes:
        - It seems that the api is applying full text search on many fiels such as name, city_name, region, country, dest_type
        - When complement information (area_type, district...) is absent, filter is applied by matching destination's name,
        thus dest_types of landmark, city, region are preferred more than 'hotel' unless 93% matching
    """
    locations = index_location_by_dest_type(locations)
    result = None

    if bkinfo_area_type:
        result = find_location_by_area_type(locations=locations, bkinfo_area=bkinfo_area, bkinfo_area_type=bkinfo_area_type)
        if result:
            # print('[INFO] Location is matched firstly in respective to bkinfo_area_type.')
            return result

    # finding with district is forced to compare bkinfo_area to city_name
    # since matching of bkinfo_area and `name` is take care by many other mechanisms
    result = find_district_locations(locations=locations, bkinfo_area=bkinfo_area, bkinfo_district=bkinfo_district)

    if result:
        # print('[INFO] Location is matched secondly in respective to bkinfo_district.')
        return result

    result = find_exact_location_name(locations, bkinfo_area, bkinfo_region=bkinfo_region, bkinfo_country=bkinfo_country)

    if result:
        # print('[INFO] Location is matched exactly in respective to bkinfo_area.')
        return result

    result = choose_destination_over_dest_types(
        locations=locations,
        bkinfo_area=bkinfo_area,
        bkinfo_region=bkinfo_region,
        bkinfo_country=bkinfo_country,
    )

    if result:
        # print('[INFO] Location is matched finally in respective to api-data-field dest_type.')
        return result

    return None

def find_location_by_area_type(locations, bkinfo_area, bkinfo_area_type):
    threshold = 0.25
    result = None

    if bkinfo_area_type in AREA_DEST_TYPE[DEST_TYPE_HOTEL]:
        result = find_by_dest_type(dest_type=DEST_TYPE_HOTEL, threshold=threshold, locations=locations, bkinfo_area=bkinfo_area)
    if bkinfo_area_type in AREA_DEST_TYPE[DEST_TYPE_LANDMARK]:
        result = find_by_dest_type(dest_type=DEST_TYPE_LANDMARK, threshold=threshold, locations=locations, bkinfo_area=bkinfo_area)
    if bkinfo_area_type in AREA_DEST_TYPE[DEST_TYPE_AIRPORT]:
        result = find_by_dest_type(dest_type=DEST_TYPE_AIRPORT, threshold=threshold, locations=locations, bkinfo_area=bkinfo_area)
    if bkinfo_area_type in AREA_DEST_TYPE[DEST_TYPE_CITY]:
        result = find_by_dest_type(dest_type=DEST_TYPE_CITY, threshold=threshold, locations=locations, bkinfo_area=bkinfo_area)

    return result

def find_district_locations(locations, bkinfo_area, bkinfo_district):
    district_threshold = 0.51
    city_threshold = 0.85
    excluded = AREA_DEST_TYPE[DEST_TYPE_CITY]

    if not bkinfo_district:
        return None

    destination_list = locations.get(DEST_TYPE_DISTRICT, None)
    if not destination_list:
        return None

    result = None
    best_score = 0.0
    for dest in destination_list:
        total_score = -1.0

        # compare bkinfo_district to destination name which is district name (in case of dest_type being district)
        district_similarity_ratio = make_fuzzy_string_comparison(querystr=bkinfo_district, keystr=dest.get('name', ''))
        # compare bkinfo_area to city name. Here we just handle very specific case, bkinfo_area is (implicitly) mentioned as city name
        city_similarity_ratio = make_fuzzy_string_comparison(querystr=bkinfo_area, keystr=dest.get('city_name', ''), excluded=excluded)

        if district_similarity_ratio > district_threshold and city_similarity_ratio > city_threshold:
            total_score = district_similarity_ratio + city_similarity_ratio
        if total_score > best_score:
            best_score = total_score
            result = dest

    return result


def find_exact_location_name(locations, bkinfo_area, bkinfo_region=None, bkinfo_country=None):
    """
    if area_type is explicitly expressed as hotel, comparing will less strict
    otherwise increase threshold to strict level: 0.93
    """
    AREA_THRESHOLD = 0.87
    destination_list = reduce(lambda x, y: x+y, locations.values())

    if not destination_list:
        return None

    best_matched = []
    for dest in destination_list:
        dest_name = dest.get('name', '')
        similarity_ratio = make_fuzzy_string_comparison(querystr=bkinfo_area, keystr=dest_name)
        if similarity_ratio > AREA_THRESHOLD:
            best_matched.append(dest)

    if len(best_matched) == 0:
        return None

    if len(best_matched) == 1:
        return best_matched[0]

    result = choose_destination_over_dest_types(
        locations=index_location_by_dest_type(best_matched),
        bkinfo_area=bkinfo_area,
        bkinfo_region=bkinfo_region,
        bkinfo_country=bkinfo_country,
        threshold=AREA_THRESHOLD,
    )

    return result


def choose_destination_over_dest_types(locations, bkinfo_area, bkinfo_region=None, bkinfo_country=None, threshold=0.35):
    for dest_type in [DEST_TYPE_LANDMARK, DEST_TYPE_AIRPORT, DEST_TYPE_CITY, DEST_TYPE_DISTRICT, DEST_TYPE_REGION, DEST_TYPE_HOTEL]:
        result = find_by_dest_type(dest_type, threshold, locations, bkinfo_area, bkinfo_region, bkinfo_country)
        if result:
            return result

    return None


def find_by_dest_type(dest_type, threshold, locations, bkinfo_area, bkinfo_region=None, bkinfo_country=None):
    REGION_THRESHOLD = 0.75
    destination_list = locations.get(dest_type, None)

    excluded = AREA_DEST_TYPE[dest_type]
    if dest_type == DEST_TYPE_REGION:
        excluded = excluded + AREA_DEST_TYPE[DEST_TYPE_REGION_EXC]

    if not destination_list:
        return None

    # check if there is complement info, do not do that if comming from find_region_locations function
    # if complement info is available take solely destinations that match
    if bkinfo_region and dest_type != DEST_TYPE_REGION:
        destination_list = list(filter(
            lambda dest: make_fuzzy_string_comparison(querystr=bkinfo_region, keystr=dest.get('region', ''), threshold=REGION_THRESHOLD),
            destination_list
        ))
    elif bkinfo_country:
        destination_list = list(filter(
            lambda dest: make_fuzzy_string_comparison(querystr=bkinfo_country, keystr=dest.get('country', ''), threshold=REGION_THRESHOLD),
            destination_list,
        ))

    # if complement info do not pick out any destination, normally compare bkinfo_area with destination name
    if len(destination_list) == 0:
        destination_list = locations.get(dest_type, None)

    _threshold = threshold
    result = None
    for dest in destination_list:
        # compare with general destination name, because dest_type could be landmark, city, region
        similarity_ratio = make_fuzzy_string_comparison(querystr=bkinfo_area, keystr=dest.get('name', ''), excluded=excluded)
        if similarity_ratio > _threshold:
            _threshold = similarity_ratio
            result = dest

    return result


def convert_currency_symbol_to_code(symbol):
    table = {
        '$': 'USD',
        '£': 'GBP',
        '₫': 'VND',
        '₩': 'KRW',
        '¥': 'JPY',
        '€': 'EUR',
    }

    return table.get(symbol, symbol)


"""
__pytest__
import os;from actions.booking_service import eval_test;eval_test(tfunc=os.environ.get('TEST_FUNC', None));
"""


def eval_test(tfunc):
    __test__fn = f'__test__{tfunc}'
    eval(__test__fn)()


def __test__search_locations():
    global pp
    locations = request_to_search_locations(name='hawaii')
    locations = index_location_by_dest_type(data=locations)
    pp.pprint(locations)


def __test__curate_room_info():
    global pp
    from .test_data.hotel import sample as hotel
    from .test_data.block import sample as block
    from .test_data.rooms import sample as rooms

    room_info = curate_room_info(hotel=hotel, block=block, ref_rooms=rooms)
    pp.pprint(room_info)


def __test__search_rooms():
    args = {
        'bkinfo_area': 'hawaii',
        'bkinfo_checkin_time': 'september 5th',
        'bkinfo_duration': '3 days',
        'bkinfo_bed_type': 'double',
        'bkinfo_price': '700 usd',
    }
    hotels = search_rooms(**args)
    print(hotels.keys())


def __test__sort_rooms_by_price():
    rooms = {
        '1': [
            {'room_id': 3, 'min_price': 100},
            {'room_id': 4, 'min_price': 125},
            {'room_id': 1, 'min_price': 50},
            {'room_id': 2, 'min_price': 75},
        ],
        '2': [
            {'room_id': 2, 'min_price': 75},
            {'room_id': 3, 'min_price': 100},
            {'room_id': 4, 'min_price': 125},
            {'room_id': 1, 'min_price': 50},
        ]
    }

    print(sort_rooms_by_price(rooms))


def __test__sort_hotel_by_min_price():
    rooms = {
        '1': [
            {'room_id': 1, 'min_price': 25},
        ],
        '4': [
            {'room_id': 2, 'min_price': 75},
            {'room_id': 3, 'min_price': 100},
        ],
        '3': [
            {'room_id': 4, 'min_price': 125},
            {'room_id': 5, 'min_price': 50},
        ],
        '2': [
            {'room_id': 4, 'min_price': 125},
            {'room_id': 5, 'min_price': 50},
        ],
    }

    print(sort_hotel_by_min_room_price(rooms))


def __test__sort_hotel_by_review_score():
    hotels = [
        {'hotel_id': 2, 'review_score': 7.0},
        {'hotel_id': 5, 'review_score': 8.8},
        {'hotel_id': 4, 'review_score': 8.7},
        {'hotel_id': 1, 'review_score': 6.7},
        {'hotel_id': 3, 'review_score': 7.7},
    ]

    print(sort_hotel_by_review_score(hotels))

def __test__find_most_likely_location():
    from .test_data.locations import (
        area_type_hotel, area_type_city, area_type_landmark,
        area_district, area_exact, area_country,
        area_region, area_notype_notexact_landmark,
        area_notype_notexact_hotel, area_notype_notexact_region,
    )

    print('[CASE 1] when bkinfo_area_type -> hotel')
    locations = area_type_hotel['search_location_result_essex']
    expected_dest_id = '55777'
    destination = find_most_likely_locations(locations, bkinfo_area='essex', bkinfo_area_type='hotel')
    actual = destination['dest_id']
    assert actual == expected_dest_id, f'[FAIL] actual: {actual}'

    print('[CASE 2] when bkinfo_area_type -> landmark')
    locations = area_type_landmark['search_location_result_bullock']
    expected_dest_id = '21283'
    destination = find_most_likely_locations(locations, bkinfo_area='bullock', bkinfo_area_type='cave')
    actual = destination['dest_id']
    assert actual == expected_dest_id, f'[FAIL] actual: {actual}'

    print('[CASE 3] when bkinfo_area_type -> city')
    locations = area_type_city['search_location_result_essex']
    expected_dest_id = '20018793'
    destination = find_most_likely_locations(locations, bkinfo_area='essex', bkinfo_area_type='city')
    actual = destination['dest_id']
    assert actual == expected_dest_id, f'[FAIL] actual: {actual}'

    locations = area_type_city['search_location_result_little_corn']
    expected_dest_id = '900051838'
    destination = find_most_likely_locations(locations, bkinfo_area='little corn', bkinfo_area_type='city')
    actual = destination['dest_id']
    assert actual == expected_dest_id, f'[FAIL] actual: {actual}'

    locations = area_exact['search_location_result_mexico_city_new_york']
    expected_dest_id = '20088027'
    destination = find_most_likely_locations(locations, bkinfo_area='mexico', bkinfo_area_type='city', bkinfo_region='new york')
    actual = destination['dest_id']
    assert actual == expected_dest_id, f'[FAIL] actual: {actual}'

    print('[CASE 4] when bkinfo_district')
    locations = area_district['search_location_result_san_francisco_north']
    expected_dest_id = '1432'
    destination = find_most_likely_locations(locations, bkinfo_area='san francisco', bkinfo_district='north point')
    actual = destination['dest_id']
    assert actual == expected_dest_id, f'[FAIL] actual: {actual}'

    locations = area_district['search_location_result_ho_chi_minh_city_district_1']
    expected_dest_id = '2088'
    destination = find_most_likely_locations(locations, bkinfo_area='ho chi minh', bkinfo_area_type='city', bkinfo_district='district 1')
    actual = destination['dest_id']
    assert actual == expected_dest_id, f'[FAIL] actual: {actual}'

    print('[CASE 5] when bkinfo_area -> exact')
    locations = area_exact['search_location_result_rocky_mountain_resort']
    expected_dest_id = '185458'
    destination = find_most_likely_locations(locations, bkinfo_area='rocky mountain resort')
    actual = destination['dest_id']
    assert actual == expected_dest_id, f'[FAIL] actual: {actual}'

    locations = area_exact['search_location_result_hambug']
    expected_dest_id = '-1785434'
    destination = find_most_likely_locations(locations, bkinfo_area='hamburg')
    actual = destination['dest_id']
    assert actual == expected_dest_id, f'[FAIL] actual: {actual}'

    locations = area_exact['search_location_result_boston_us']
    expected_dest_id = '20061717'
    destination = find_most_likely_locations(locations, bkinfo_area='boston', bkinfo_country='us')
    actual = destination['dest_id']
    assert actual == expected_dest_id, f'[FAIL] actual: {actual}'

    print('[CASE 6] when bkinfo_area -> exact, bkinfo_country -> united states')
    locations = area_country['search_location_result_essex']
    expected_dest_id = '20018793'
    destination = find_most_likely_locations(locations, bkinfo_area='essex', bkinfo_country='united states')
    actual = destination['dest_id']
    assert actual == expected_dest_id, f'[FAIL] actual: {actual}'

    print('[CASE 7] when bkinfo_area -> exact, bkinfo_region -> massachusetts')
    locations = area_region['search_location_result_essex']
    expected_dest_id = '20062172'
    destination = find_most_likely_locations(locations, bkinfo_area='essex', bkinfo_region='massachusetts')
    actual = destination['dest_id']
    assert actual == expected_dest_id, f'[FAIL] actual: {actual}'

    print('[CASE 8] when bkinfo_area -> not exact, bkinfo_area_type -> absent, dest_type -> landmark')
    locations = area_notype_notexact_landmark['search_location_result_phra_nang']
    expected_dest_id = '20414'
    destination = find_most_likely_locations(locations, bkinfo_area='phra nang')
    actual = destination['dest_id']
    assert actual == expected_dest_id, f'[FAIL] actual: {actual}'

    print('[CASE 9] when bkinfo_area -> not exact, bkinfo_area_type -> absent, dest_type -> region, country')
    locations = area_notype_notexact_region['search_location_result_tameside']
    expected_dest_id = '2439'
    destination = find_most_likely_locations(locations, bkinfo_area='tameside')
    actual = destination['dest_id']
    assert actual == expected_dest_id, f'[FAIL] actual: {actual}'

    locations = area_notype_notexact_region['search_location_result_continental_vietnam']
    expected_dest_id = '184750'
    destination = find_most_likely_locations(locations, bkinfo_area='continental', bkinfo_country='vietnam')
    actual = destination['dest_id']
    assert actual == expected_dest_id, f'[FAIL] actual: {actual}'

    print('[CASE 10] when bkinfo_area -> not exact, bkinfo_area_type -> absent, dest_type -> district')
    locations = area_notype_notexact_hotel['search_location_result_san_francisco_north']
    expected_dest_id = '1432'
    destination = find_most_likely_locations(locations, bkinfo_area='san francisco north')
    actual = destination['dest_id']
    assert actual == expected_dest_id, f'[FAIL] actual: {actual}'

    print('All done.')


def __test__compose_location_name():
    bkinfo_area = 'bkinfo_area'
    bkinfo_area_type = 'bkinfo_area_type'
    bkinfo_district = 'bkinfo_district'
    bkinfo_region = 'bkinfo_region'
    bkinfo_country = 'bkinfo_country'

    print('[CASE 1] bkinfo_area')
    expected = 'bkinfo_area'
    actual = compose_location_name(bkinfo_area=bkinfo_area)
    assert actual == expected, f'[FAIL] actual: {actual}'

    print('[CASE 2] bkinfo_area, bkinfo_area_type')
    expected = 'bkinfo_area bkinfo_area_type'
    actual = compose_location_name(bkinfo_area=bkinfo_area, bkinfo_area_type=bkinfo_area_type)
    assert actual == expected, f'[FAIL] actual: {actual}'

    print('[CASE 3] bkinfo_area, bkinfo_district')
    expected = 'bkinfo_area bkinfo_district'
    actual = compose_location_name(bkinfo_area=bkinfo_area, bkinfo_district=bkinfo_district)
    assert actual == expected, f'[FAIL] actual: {actual}'

    print('[CASE 4] bkinfo_area, hotel, bkinfo_district')
    expected = 'bkinfo_area hotel'
    actual = compose_location_name(bkinfo_area=bkinfo_area, bkinfo_area_type='hotel', bkinfo_district=bkinfo_district)
    assert actual == expected, f'[FAIL] actual: {actual}'

    print('[CASE 5] bkinfo_area, airport, bkinfo_district')
    expected = 'bkinfo_area airport'
    actual = compose_location_name(bkinfo_area=bkinfo_area, bkinfo_area_type='airport', bkinfo_district=bkinfo_district)
    assert actual == expected, f'[FAIL] actual: {actual}'

    print('[CASE 6] bkinfo_area, beach, bkinfo_district')
    expected = 'bkinfo_area beach'
    actual = compose_location_name(bkinfo_area=bkinfo_area, bkinfo_area_type='beach', bkinfo_district=bkinfo_district)
    assert actual == expected, f'[FAIL] actual: {actual}'

    print('[CASE 7] bkinfo_area, bkinfo_country')
    expected = 'bkinfo_area bkinfo_country'
    actual = compose_location_name(bkinfo_area=bkinfo_area, bkinfo_country=bkinfo_country)
    assert actual == expected, f'[FAIL] actual: {actual}'

    print('[CASE 8] bkinfo_area, bkinfo_area_type, bkinfo_district, bkinfo_region, bkinfo_country')
    expected = 'bkinfo_area bkinfo_area_type bkinfo_district bkinfo_region bkinfo_country'
    actual = compose_location_name(bkinfo_area=bkinfo_area, bkinfo_area_type=bkinfo_area_type, bkinfo_district=bkinfo_district, bkinfo_region=bkinfo_region, bkinfo_country=bkinfo_country)
    assert actual == expected, f'[FAIL] actual: {actual}'

    print('All done.')
