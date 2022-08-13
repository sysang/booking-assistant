import redis
import requests

from cachecontrol import CacheControl
from cachecontrol.caches.redis_cache import RedisCache
from cachecontrol.heuristics import ExpiresAfter


BASE_URL = 'https://booking-com.p.rapidapi.com/v1'
CURRENCY = 'USD'
LOCALE = 'en-gb'
UNITS = 'metric'
REQUESTS_CACHE_MINS = 60

headers = {
    "X-RapidAPI-Key": "6ddab563a2mshfe98ce973810751p137295jsnd9d1bea86c0e",
    "X-RapidAPI-Host": "booking-com.p.rapidapi.com"
}

pool = redis.ConnectionPool(host='redis', port=6379, db=0,  password='qwer1234')
r = redis.Redis(connection_pool=pool)
requests_sess = CacheControl(sess=requests.Session(), cache=RedisCache(r), heuristic=ExpiresAfter(minutes=REQUESTS_CACHE_MINS))


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

    querystring = {
        "checkin_date": checkin_date,
        "checkout_date": checkout_date,
        "hotel_id": hotel_id,
        "adults_number_by_rooms": number_of_occupancy,
        "room_number": number_of_room,
        "currency": currency,
        "locale": LOCALE,
        "units": UNITS,
    }

    response = requests_sess.get(url, headers=headers, params=querystring)

    if not response.ok:
        return []

    result = response.json()

    return result
