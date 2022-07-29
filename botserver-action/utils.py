import pickle
import re
import json
import arrow

from arrow import Arrow
from typing import Any, Dict, List, Text, Optional, Tuple
from difflib import SequenceMatcher as SM
from fuzzywuzzy import fuzz
from unidecode import unidecode


DATE_FORMAT = 'YYYY-MM-DD'
SUSPICIOUS_CHECKIN_DISTANCE = 60


class SortbyDictionary():
    SORTBY_POPULARITY = 'popularity'
    SORTBY_REVIEW_SCORE = 'review_score'
    SORTBY_PRICE = 'price'

    vocab_index = {
        0: SORTBY_POPULARITY,
        1: SORTBY_REVIEW_SCORE,
        2: SORTBY_PRICE,
    }

    @classmethod
    def get_index(self, sortby):
        for idx, name in self.vocab_index.items():
            if name == sortby:
                return idx

        return 0

    @classmethod
    def get_sorby_name(self, idx):
        return self.vocab_index.get(idx, self.SORTBY_POPULARITY)


def parse_date_range(from_time, duration, format=DATE_FORMAT):
  arrobj_now = arrow.now()
  arrobj_checkin = arrow.get(from_time)
  arrobj_checkout = arrobj_checkin.shift(days=duration)

  return (arrobj_checkin.format(format), arrobj_checkout.format(format))


def slots_for_entities(entities: List[Dict[Text, Any]], intent: Dict[Text, Any], domain: Dict[Text, Any]) -> Dict[Text, Any]:
    mapped_slots = {}
    for slot_name, slot_conf in domain['slots'].items():
        for entity in entities:
            for mapping in slot_conf['mappings']:
                if mapping['type'] != 'from_entity':
                    continue
                if mapping['entity'] != entity['entity']:
                    continue
                if mapping['intent'] != intent['name']:
                    continue
                mapped_slots[slot_name] = entity.get('value')

    return mapped_slots


def get_room_by_id(room_id, search_result):
    hotels = search_result.get('hotels', None)
    if not hotels:
        return None

    hotels = picklize_search_result(data=hotels)

    for rooms in hotels.values():
        for room in rooms:
            if room['room_id'] == room_id:
                return room

    return None


def calc_time_distance_in_days(checkin_time):
    now_arrobj = arrow.utcnow()
    checkin_time_arrobj = arrow.get(checkin_time)

    delta = checkin_time_arrobj - now_arrobj

    return delta.days


def paginate_button_payload(payload=None, page_number=None, bkinfo_orderby=None):
    page_number_field = 'p'
    order_by_field = 'o'

    if payload:
        matched = re.search(r'\{.+\}', payload)

        if not matched:
            return None, None

        data = json.loads(matched.group(0))
        if not isinstance(data, dict):
            return None, None

        return data.get(page_number_field, None), data.get(order_by_field, None)

    query = {page_number_field: page_number, order_by_field: bkinfo_orderby}
    jsonstr = json.dumps(query)
    jsonstr = jsonstr.replace(' ', '')

    return jsonstr


def paginate(index, limit, total):
    start = (index - 1) * limit
    end = start + limit
    end = end if end < total else total
    remains = total - end

    return start, end, remains

def hash_bkinfo(bkinfo_area, bkinfo_checkin_time, bkinfo_duration, bkinfo_bed_type, bkinfo_price, bkinfo_orderby):
    assert bkinfo_area and bkinfo_checkin_time and bkinfo_duration and bkinfo_bed_type and bkinfo_price and bkinfo_orderby, "Invalid value"

    h = bkinfo_area.encode(encoding="utf-8", errors="strict")
    h = h + bkinfo_checkin_time.encode(encoding="utf-8", errors="strict")
    h = h + bkinfo_duration.encode(encoding="utf-8", errors="strict")
    h = h + bkinfo_bed_type.encode(encoding="utf-8", errors="strict")
    h = h + bkinfo_price.encode(encoding="utf-8", errors="strict")
    h = h + bkinfo_orderby.encode(encoding="utf-8", errors="strict")

    return h.hex()


def picklize_search_result(data):
    if isinstance(data, dict):
        return pickle.dumps(data)

    if isinstance(data, bytes):
        return pickle.loads(data)

    return None


def make_fuzzy_string_comparison(querystr, keystr, excluded: List[Text] = [], threshold=None):
    factor = 0.01
    str1 = str(querystr).lower().strip()
    str1 = unidecode(str1)

    str2 = str(keystr).lower().strip()
    str2 = unidecode(str2)
    for item in excluded:
        str2 = str2.replace(item, '').strip()

    # similarity_ratio = SM(isjunk=None, a=str1, b=str2).ratio()
    similarity_ratio = fuzz.ratio(str1, str2)
    similarity_ratio = similarity_ratio * factor

    if threshold:
        return similarity_ratio > threshold

    return similarity_ratio



def __test__parse_date_range():
    from_time, to_time = parse_date_range('2022-01-01', 3)
    assert from_time == '2022-01-01', "from_time is incorrect."
    assert to_time == '2022-01-04', "to_time is incorrect."

    from_time, to_time = parse_date_range('2022-01-01', 32)
    assert from_time == '2022-01-01', "from_time is incorrect."
    assert to_time == '2022-02-02', "to_time is incorrect."

    print('Success.')


def eval_test():
    __test__parse_date_range()
