import logging
from functools import lru_cache

from requests import get
import arrow
from arrow import Arrow

from .utils import parse_date_range


logger = logging.getLogger(__name__)

BASE_URL = 'https://booking-com.p.rapidapi.com/v1'

CURRENCY = 'USD'
LOCALE = 'en-gb'
UNITS = 'metric'

PRICE_MARGIN = 0.07

HOTEL_RESULT_LIMIT = 5

headers = {
    "X-RapidAPI-Key": "6ddab563a2mshfe98ce973810751p137295jsnd9d1bea86c0e",
    "X-RapidAPI-Host": "booking-com.p.rapidapi.com"
}

# @lru_cache
def search_rooms(bkinfo_area, bkinfo_checkin_time, bkinfo_duration, bkinfo_max_price, bkinfo_bed_type):
    """
        search_locations
        search_hotel
        get_room_list_by_hotel
        filter by price, adult_number
        ADVANCES:
        - sort by price, sort by rating
        - filter by bed_type
    """
    logger.info('[INFO] searching parameters(bkinfo_area, bkinfo_checkin_time, bkinfo_duration, bkinfo_bed_type, bkinfo_price): (%s, %s, %s, %s)',
        bkinfo_area, bkinfo_checkin_time, bkinfo_duration, bkinfo_max_price, bkinfo_bed_type)

    locations = search_locations(name=bkinfo_area)
    locations = index_location_by_dest_type(data=locations)
    destination = choose_location(data=locations)
    checkin_date, checkout_date = parse_date_range(from_time=bkinfo_checkin_time, duration=bkinfo_duration)

    hotels = search_hotel(dest_id=destination['dest_id'], dest_type=destination['dest_type'], checkin_date=checkin_date, checkout_date=checkout_date)
    hotels = hotels['result']
    hotels = sort_hotel_by_review_score(hotels)

    rooms_indexed_by_hote_id = {}
    counter = 0
    for hotel in hotels:
        room_list = get_room_list_by_hotel(hotel_id=hotel['hotel_id'], checkin_date=checkin_date, checkout_date=checkout_date)
        for item in room_list:
            blocks = item['block']
            ref_rooms = item['rooms']
            for block in blocks:
                room = curate_room_info(hotel=hotel, block=block, ref_rooms=ref_rooms)
                if verifyif_room_in_price_range(room=room, price=bkinfo_max_price) and verifyif_room_has_bed_type(room=room, bed_type=bkinfo_bed_type):
                    hotel_id = room['hotel_id']
                    if rooms_indexed_by_hote_id.get(hotel_id, None):
                        rooms_indexed_by_hote_id[hotel_id].append(room)
                    else:
                        rooms_indexed_by_hote_id[hotel_id] = [room]
                        counter += 1

        if counter >= 5:
            break

    sorted_room = {}
    for hotel_id, rooms in rooms_indexed_by_hote_id.items():
        sorted_room[hotel_id] = sorted(rooms, key=lambda x: x['min_price'])

    return sorted_room


def sort_hotel_by_review_score(hotels):
    return sorted(hotels, key=lambda x: x['review_score'], reverse=True)


def verifyif_room_has_bed_type(room, bed_type):
    if not len(room['bed_configurations']):
        return False
    room_bed_types = room['bed_configurations'][0]['bed_types']
    if not len(room_bed_types):
        return False
    room_bed_type = room_bed_types[0]
    return room_bed_type['name'].find(bed_type) != -1


def verifyif_room_in_price_range(room, price):
    max_price = price + price * PRICE_MARGIN
    room_price = room['min_price']
    return room_price < max_price


def curate_room_info(hotel, block, ref_rooms):
    room_id = str(block['room_id'])
    room = ref_rooms[room_id]

    return {
        'hotel_id': hotel['hotel_id'],
        'hotel_name_trans': hotel['hotel_name_trans'],
        'address_trans': hotel['address_trans'],
        'hotel_photo_url': hotel['max_1440_photo_url'],
        'city_trans': hotel['city_trans'],
        'city_name_en': hotel.get('city_name_en', None),
        'country_trans': hotel['country_trans'],
        'is_beach_front': hotel['is_beach_front'],
        'nearest_beach_name': hotel.get('nearest_beach_name', None),
        'review_score': float(hotel['review_score']),
        'min_price': float(block['min_price']['price']),
        'max_occupancy': int(block['max_occupancy']),
        'name_without_policy': block['name_without_policy'],
        'room_id': room_id,
        'bed_configurations': room['bed_configurations'],
        'facilities': room['facilities'],
        'description': room['description'],
        'photos': room['photos'],
    }


@lru_cache
def get_room_list_by_hotel(hotel_id, checkin_date, checkout_date):
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

    querystring = {
        "checkin_date": checkin_date,
        "checkout_date": checkout_date,
        "hotel_id": hotel_id,
        "adults_number_by_rooms": number_of_occupancy,
        "room_number": number_of_room,
        "currency": CURRENCY,
        "locale": LOCALE,
        "units": UNITS,
    }


    response = get(url, headers=headers, params=querystring)
    response.raise_for_status()

    return response.json()


@lru_cache
def search_hotel(dest_id, dest_type, checkin_date, checkout_date):
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
    order_by = 'popularity'
    number_of_occupancy = 2
    number_of_room = 1

    querystring = {
        "order_by": order_by,
        "checkin_date": checkin_date,
        "checkout_date": checkout_date,
        "dest_id": dest_id,
        "dest_type": dest_type,
        "adults_number": number_of_occupancy,
        "room_number": number_of_room,
        "filter_by_currency": CURRENCY,
        "locale": LOCALE,
        "units": UNITS,
    }


    response = get(url, headers=headers, params=querystring)
    response.raise_for_status()

    return response.json()

@lru_cache
def search_locations(name):
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


    response = get(url, headers=headers, params=querystring)
    response.raise_for_status()


    return response.json()


def index_location_by_dest_type(data):
    result = {}
    for item in data:
        dest_type = item['dest_type']
        if result.get(dest_type, None):
            result[dest_type].append(item)
        else:
            result[dest_type] = [item]

    return result

def choose_location(data):
    CITY = 'city'
    REGION = 'REGION'
    HOTEL = 'HOTEL'

    if data.get(CITY, None):
        return data.get(CITY)[0]
    if data.get( REGION, None):
        return data.get(REGION)[0]
    if data.get(HOTEL):
        return data.get(HOTEL)
    else:
        raise  NotImplementedError(f'There is dest_type has not recognized to retrieve. Info: %s' % (str(data.keys())))


def __test__():
    import pprint
    pp = pprint.PrettyPrinter(indent=4)

    # locations = search_locations(name='hawaii')
    # locations = index_location_by_dest_type(data=locations)
    # pp.pprint(locations)

    from .test_data.hotel import sample as hotel
    from .test_data.block import sample as block
    from .test_data.rooms import sample as rooms

    room_info = curate_room_info(hotel=hotel, block=block, ref_rooms=rooms)
    pp.pprint(room_info)
