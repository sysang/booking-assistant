import pickle
import re
import json
import arrow

from arrow import Arrow
from typing import Any, Dict, List, Text, Optional, Tuple
# from difflib import SequenceMatcher as SM
from thefuzz import fuzz
from unidecode import unidecode
from datetime import datetime


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
                if mapping.get('type', None) != 'from_entity':
                    continue
                if mapping.get('entity', None) != entity['entity']:
                    continue
                if mapping.get('intent', None) != intent['name']:
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

    similarity_ratio = fuzz.ratio(str1, str2)
    similarity_ratio = similarity_ratio * factor
    # print(f'[DEV] {str1} : {str2} -> {similarity_ratio}')

    if threshold:
        return similarity_ratio > threshold

    return similarity_ratio


class DictUpdatingMemmQueue():
    MEMM_SIZE = 2

    def __init__(self, data):
        self.data = data if isinstance(data, dict) else {}
        self.sanitize_data()

    def sanitize_data(self):
        result = {}
        for key in self.data.keys():
            item = self.get_item(key)
            result[key] = item[0:self.MEMM_SIZE]

        self.data = result

    def get_item(self, key):
        item = self.data.get(key, [])
        item = sorted(item, key=lambda x: x[1], reverse=True)
        return item

    def register(self, key, value):
        item = self.get_item(key)
        now_st = datetime.now().timestamp()
        updated = (value, now_st)
        if len(item) < self.MEMM_SIZE:
            item.append(updated)
            self.data[key] = item
        else:
            newer = item[0:-1]
            newer.append(updated)
            self.data[key] = newer

        return self.data

    def retrieve(self, key):
        item = self.get_item(key)
        if not item:
            return None
        return item[-1][0]

"""
__pytest__
import os;from actions.utils import eval_test;eval_test(tfunc=os.environ.get('TEST_FUNC', None));
"""


def eval_test(tfunc):
    __test__fn = f'__test__{tfunc}'
    eval(__test__fn)()


def __test__parse_date_range():
    from_time, to_time = parse_date_range('2022-01-01', 3)
    assert from_time == '2022-01-01', "from_time is incorrect."
    assert to_time == '2022-01-04', "to_time is incorrect."

    from_time, to_time = parse_date_range('2022-01-01', 32)
    assert from_time == '2022-01-01', "from_time is incorrect."
    assert to_time == '2022-02-02', "to_time is incorrect."

    print('Success.')


def __test__DictUpdatingMemmQueue():
    DictUpdatingMemmQueue.MEMM_SIZE = 3
    now = datetime.now()
    now = now.replace(second=0, minute=now.minute - 1)
    data = {
        'slot1': [
            ('slot_value_1', now.replace(second=1).timestamp()),
            ('slot_value_3', now.replace(second=3).timestamp()),
            ('slot_value_2', now.replace(second=2).timestamp()),
        ],
        'slot2': [
            ('slot_value_6', now.replace(second=6).timestamp()),
            ('slot_value_5', now.replace(second=5).timestamp()),
            ('slot_value_7', now.replace(second=7).timestamp()),
        ],
    }
    print('[Case 1] retrieve() returns first value')
    expected = 'slot_value_1'
    actual = DictUpdatingMemmQueue(data=data).retrieve('slot1')
    assert actual == expected, f'[FAIL] actual: {actual}'

    expected = 'slot_value_5'
    actual = DictUpdatingMemmQueue(data=data).retrieve('slot2')
    assert actual == expected, f'[FAIL] actual: {actual}'

    print('[Case 2] register one time, retrieve() returns second value')
    updated = DictUpdatingMemmQueue(data=data).register(key='slot1', value='updated_1')
    expected = 'slot_value_2'
    actual = DictUpdatingMemmQueue(data=updated).retrieve('slot1')
    assert actual == expected, f'[FAIL] actual: {actual}'

    print('[Case 3] register three time, retrieve() returns update_1 value')
    updated = DictUpdatingMemmQueue(data=data).register(key='slot1', value='updated_1')
    updated = DictUpdatingMemmQueue(data=updated).register(key='slot1', value='updated_2')
    updated = DictUpdatingMemmQueue(data=updated).register(key='slot1', value='updated_3')
    expected = 'updated_1'
    actual = DictUpdatingMemmQueue(data=updated).retrieve('slot1')
    assert actual == expected, f'[FAIL] actual: {actual}'

    print('[Case 4] empty, register three time, retrieve() one by one')
    updated = DictUpdatingMemmQueue(data=None).register(key='slot1', value='updated_1')
    expected = 'updated_1'
    actual = DictUpdatingMemmQueue(data=updated).retrieve('slot1')
    assert actual == expected, f'[FAIL] actual: {actual}'

    updated = DictUpdatingMemmQueue(data=updated).register(key='slot1', value='updated_2')
    expected = 'updated_1'
    actual = DictUpdatingMemmQueue(data=updated).retrieve('slot1')
    assert actual == expected, f'[FAIL] actual: {actual}'

    updated = DictUpdatingMemmQueue(data=updated).register(key='slot1', value='updated_3')
    expected = 'updated_1'
    actual = DictUpdatingMemmQueue(data=updated).retrieve('slot1')
    assert actual == expected, f'[FAIL] actual: {actual}'

    updated = DictUpdatingMemmQueue(data=updated).register(key='slot1', value='updated_4')
    expected = 'updated_2'
    actual = DictUpdatingMemmQueue(data=updated).retrieve('slot1')
    assert actual == expected, f'[FAIL] actual: {actual}'

    print('[Case 5] empty, retrieve() returns None')
    actual = DictUpdatingMemmQueue(data=None).retrieve('slot1')
    assert actual == None, f'[FAIL] actual: {actual}'

    print('All done.')
