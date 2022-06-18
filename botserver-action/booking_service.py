import logging

from requests import get
import arrow
from arrow import Arrow


logger = logging.getLogger(__name__)

BASE_URL = 'https://booking-com.p.rapidapi.com/v1'

CURRENCY = 'USD'
LOCALE = 'en-gb'
UNITS = 'metric'

headers = {
    "X-RapidAPI-Key": "6ddab563a2mshfe98ce973810751p137295jsnd9d1bea86c0e",
    "X-RapidAPI-Host": "booking-com.p.rapidapi.com"
}

def search_rooms(bkinfo_area, bkinfo_checkin_time, bkinfo_duration):
    # search_locations
    # search_hotel
    # get_room_list_by_hotel
    # filter by price, adult_number
    # ADVANCES: sort by price, sort by rating
    pass


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

    querystring = {
        "checkin_date": checkin_date,
        "checkout_date": checkout_date,
        "hotel_id": hotel_id,
        "adults_number_by_rooms": 2,
        "room_number": "1",
        "adults_number_by_rooms": "2",
        "currency": CURRENCY,
        "locale": LOCALE,
        "units": UNITS,
    }


    response = get(url, headers=headers, params=querystring)
    response.raise_for_status()

    # print(response.text)

    return response.json()



def search_hotel(dest_id, dest_type, checkin_date, checkout_date):
    """
    >>> hotels = response.json()
    >>> hotels.keys()
    dict_keys(['primary_count', 'count', 'room_distribution', 'map_bounding_box', 'total_count_with_filters', 'unfiltered_count', 'extended_count', 'unfiltered_primary_count', 'search_radius', 'sort', 'result'])
    """

    url = f"{BASE_URL}/hotels/search"

    querystring = {
        "order_by": "popularity",
        "checkin_date": checkin_date,
        "checkout_date": checkout_date,
        "dest_id": dest_id,
        "dest_type": dest_type,
        "room_number": "1",
        "adults_number": "2",
        "filter_by_currency": CURRENCY,
        "locale": LOCALE,
        "units": UNITS,
    }


    response = get(url, headers=headers, params=querystring)
    response.raise_for_status()

    # print(response.text)

    return response.json()


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

    # print(response.text)

    return response.json()
