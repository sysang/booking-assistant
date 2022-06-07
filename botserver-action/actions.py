# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions


# This is a simple example for a custom action which utters "Hello World!"

# from typing import Any, Text, Dict, List
#
# from rasa_sdk import Action, Tracker
# from rasa_sdk.executor import CollectingDispatcher
#
#
# class ActionHelloWorld(Action):
#
#     def name(self) -> Text:
#         return "action_hello_world"
#
#     def run(self, dispatcher: CollectingDispatcher,
#             tracker: Tracker,
#             domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
#
#         dispatcher.utter_message(text="Hello World!")
#
#         return []

import logging
import json
from typing import Any, Dict, List, Text, Optional, Tuple

import arrow

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import (
    SlotSet,
    UserUtteranceReverted,
    ConversationPaused,
    EventType,
)

from .entity_preprocessing_rules import mapping_table
from .service import duckling_parse, query_available_rooms, query_room_by_id

logger = logging.getLogger(__name__)


class set_booking_state__information_collecting__(Action):

  def name(self) -> Text:
    return "set_booking_state__information_collecting__"

  def run(self, dispatcher: CollectingDispatcher,
          tracker: Tracker,
          domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

    return [SlotSet("booking_state", "information_collecting")]


class set_booking_state__done_collecting_information__(Action):

  def name(self) -> Text:
    return "set_booking_state__done_collecting_information__"

  def run(self, dispatcher: CollectingDispatcher,
          tracker: Tracker,
          domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

    return [SlotSet("booking_state", "done_collecting_information")]


class set_booking_state__room_selected__(Action):

  def name(self) -> Text:
    return "set_booking_state__room_selected__"

  def run(self, dispatcher: CollectingDispatcher,
          tracker: Tracker,
          domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

    return [SlotSet("booking_state", "room_selected")]


class ActionSetBookingInformation(Action):

  def verify_entity(self, entity_name, entity_value):
    processor = mapping_table(entity_name)
    return processor(entity_value)


  def name(self) -> Text:
    return "ActionSetBookingInformation"

  def slot_entity(self) -> Tuple[str, str]:
    raise NotImplementedError('method ActionSetBookingInformation.slot_entity')

  def retrieve_entity_value(self, tracker, entity_name):
    entities = tracker.latest_message['entities']
    entity = list(filter(lambda ent: ent['entity'] == entity_name, entities))
    logger.info(f"[INFO] retrieve_entity_value, entity: %s", str(entity))

    if len(entity) == 0:
      return None

    return entity.pop()['value']

  def run(self, dispatcher: CollectingDispatcher,
          tracker: Tracker,
          domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

    entity_name, slot_name = self.slot_entity()
    logger.info(f"[INFO] retrieve_entity_value, entity_name: %s", str(entity_name))
    logger.info(f"[INFO] retrieve_entity_value, slot_name: %s", str(slot_name))

    entity_value = self.retrieve_entity_value(tracker, entity_name)
    logger.info(f"[INFO] retrieve_entity_value, entity_value: %s", str(entity_value))

    valid_entity_value = self.verify_entity(entity_name=entity_name, entity_value=entity_value)
    if valid_entity_value:
      return [SlotSet(slot_name, valid_entity_value)]

    return []


class set_booking_information__city__(ActionSetBookingInformation):

  def name(self) -> Text:
    return "set_booking_information__city__"

  def slot_entity(self) -> Tuple[str, str]:
    return ('city', 'bkinfo_city')

class set_booking_information__area__(ActionSetBookingInformation):

  def name(self) -> Text:
    return "set_booking_information__area__"

  def slot_entity(self) -> Tuple[str, str]:
    return ('area', 'bkinfo_area')




class set_booking_information__checkin_time__(ActionSetBookingInformation):

  def name(self) -> Text:
    return "set_booking_information__checkin_time__"

  def slot_entity(self) -> Tuple[str, str]:
    return ('date', 'bkinfo_checkin_time')


class set_booking_information__duration__(ActionSetBookingInformation):

  def name(self) -> Text:
    return "set_booking_information__duration__"

  def slot_entity(self) -> Tuple[str, str]:
    return ('duration', 'bkinfo_duration')


class set_booking_information__room_id__(ActionSetBookingInformation):

  def name(self) -> Text:
    return "set_booking_information__room_id__"

  def slot_entity(self) -> Tuple[str, str]:
    return ('room_id', 'bkinfo_room_id')


class set_booking_information__room_type__(ActionSetBookingInformation):

  def name(self) -> Text:
    return "set_booking_information__room_type__"

  def slot_entity(self) -> Tuple[str, str]:
    return ('room_type', 'bkinfo_room_type')


class bot_show_hotel_list(Action):

  def name(self) -> Text:
    return "bot_show_hotel_list"

  def run(self, dispatcher: CollectingDispatcher,
          tracker: Tracker,
          domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

    slots = tracker.slots
    booking_state__done_collecting_information__ = 'done_collecting_information'
    booking_failure__missing_booking_info__ = 'missing_booking_info'

    booking_state = slots['booking_state']
    if booking_state != booking_state__done_collecting_information__:
      return [SlotSet('booking_failure', booking_failure__missing_booking_info__)]

    # TODO: check slot's value, if slot is empty re-proceed appropricate info collecting step
    bkinfo_area = slots['bkinfo_area']
    bkinfo_room_type = slots['bkinfo_room_type']
    bkinfo_checkin_time = slots['bkinfo_checkin_time']
    bkinfo_duration = slots['bkinfo_duration']

    rooms = query_available_rooms(
          area=bkinfo_area,
          room_type=bkinfo_room_type,
          checkin_time=bkinfo_checkin_time,
          duration=bkinfo_duration
        )

    if len(rooms) == 0:
      dispatcher.utter_message(response="utter_room_not_available")
    else:

      buttons = []
      for room in rooms:
        params = {
              'room_id': room['id']
            }
        params = json.dumps(params)

        buttons.append(
            {
              "title": "%s, price: $%s" % (room["hotel"], room['price']),
              "payload": "/user_click_to_select_hotel%s" % (params)  # IMPORTANT the json format of params is very strict, use \' instead of \" will yield silently no effect
            })

      logger.info("[INFO] buttons: %s", buttons)
      dispatcher.utter_message(response="utter_about_to_show_hotel_list", buttons=buttons)

    return []

class confirm_room_selection(Action):

  def name(self) -> Text:
    return "confirm_room_selection"

  def run(self, dispatcher: CollectingDispatcher,
          tracker: Tracker,
          domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

    slots = tracker.slots

    # TODO: check slot's id, if id is absent restart the process (safe fallback)
    room = query_room_by_id(slots['bkinfo_room_id'])
    hotel_name = room['hotel']

    checkin_time = arrow.get(slots['bkinfo_checkin_time']).format('MMMM Do YYYY')
    duration = slots['bkinfo_duration']
    duration = str(duration) + ' days' if duration > 1 else str(duration) + ' day'

    dispatcher.utter_message(response = "utter_room_selection",
          room_type=slots['bkinfo_room_type'],
          checkin_time=checkin_time,
          duration=duration,
          hotel_name=hotel_name,
        )
