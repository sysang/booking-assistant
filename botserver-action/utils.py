import arrow
from arrow import Arrow
from typing import Any, Dict, List, Text, Optional, Tuple


DATE_FORMAT = 'YYYY-MM-DD'

def parse_date_range(from_time, duration, format=DATE_FORMAT):
  arrobj_now = arrow.now()
  arrobj_checkin = arrow.get(from_time)
  arrobj_checkout = arrobj_checkin.shift(days=duration)

  return (arrobj_checkin.format(format), arrobj_checkout.format(format))


def __test__parse_date_range():
    from_time, to_time = parse_date_range('2022-01-01', 3)
    assert from_time == '2022-01-01', "from_time is incorrect."
    assert to_time == '2022-01-04', "to_time is incorrect."

    from_time, to_time = parse_date_range('2022-01-01', 32)
    assert from_time == '2022-01-01', "from_time is incorrect."
    assert to_time == '2022-02-02', "to_time is incorrect."

    print('Success.')


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

    for rooms in search_result.values():
        for room in rooms:
            if room['room_id'] == room_id:
                return room

    raise Exception("Data is broken or clicking room handling logic is mistaken.")


def __test__():
    __test__parse_date_range()
