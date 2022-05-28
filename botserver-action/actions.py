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

from typing import Any, Dict, List, Text, Optional, Tuple

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import (
    SlotSet,
    UserUtteranceReverted,
    ConversationPaused,
    EventType,
)

from .entity_preprocessing_rules import mapping_table
from .service import duckling_parse, query_available_rooms

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


class ActionSetBookingInformation(Action):

  def verify_entity(self, entity_name, entity_value):
    processor = mapping_table[entity_name]
    return processor(entity_value)


  def name(self) -> Text:
    return "ActionSetBookingInformation"

  def slot_entity(self) -> Tuple[str, str]:
    raise NotImplementedError('method ActionSetBookingInformation.slot_entity')

  def retrieve_entity_value(self, tracker, entity_name):
    entities = tracker.latest_message['entities']
    entity = list(filter(lambda ent: ent['entity'] == entity_name, entities))
    logger.info(f"[INFO] retrieve_entity_value, entity: ", entity)

    if len(entity) == 0:
      return None

    return entity.pop()['value']

  def run(self, dispatcher: CollectingDispatcher,
          tracker: Tracker,
          domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

    entity_name, slot_name = self.slot_entity()
    logger.info(f"[INFO] retrieve_entity_value, entity_name: ", entity_name)
    logger.info(f"[INFO] retrieve_entity_value, slot_name: ", slot_name)

    entity_value = self.retrieve_entity_value(tracker, entity_name)
    logger.info(f"[INFO] retrieve_entity_value, entity_value: ", entity_value)

    if self.verify_entity(entity_value, entity_value):
      return [SlotSet(slot_name, entity_value)]

    return []


class set_booking_information__city__(ActionSetBookingInformation):

  def name(self) -> Text:
    return "set_booking_information__city__"

  def slot_entity(self) -> Tuple[str, str]:
    return ('city', 'bkinfo_city')


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

    tpl = "hotel {}, price ${}"
    snips = []
    for room in rooms:
      snips.append(tpl.format(room['hotel'], room['price']))

    snips = snips.join(', ')
    message = f"These are available rooms: {snips}."

    dispatcher.utter(text=message)

    return []


