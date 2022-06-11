import logging
import json
from typing import Any, Dict, List, Text, Optional, Tuple

import arrow

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import (
    Restarted,
    SlotSet,
    AllSlotsReset,
    UserUtteranceReverted,
    ConversationPaused,
    FollowupAction,
    ActionExecuted,
    UserUttered,
)

from .entity_preprocessing_rules import mapping_table
from .service import duckling_parse, query_available_rooms, query_room_by_id

logger = logging.getLogger(__name__)


class custom_action_fallback(Action):

  def name(self) -> Text:
    return "custom_action_fallback"

  def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

    dispatcher.utter_message(response="utter_action_fallback")

    # return [Restarted()]
    return [FollowupAction(name="action_listen"), AllSlotsReset()]


class bot_relieves_imposition_to_think(Action):
  """
    - In combination with bot_switchto_thinking to break the force in story.
    - The rules in story always demands an action after an certain action
      whereby eventually leads to (implicit) `action_listen`.
    - This foster opportunity to make decisions based mainly on memory (slot information)
  """

  def name(self) -> Text:
    return "bot_relieves_imposition_to_think"

  def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

    return [FollowupAction(name="bot_transitioning")]


class bot_transitioning(Action):

  def name(self) -> Text:
    return "bot_transitioning"

  def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
    parse_data = {
        "intent": {
            "name": "pseudo_user_intent_to_wait",
            "confidence": 1.0,
          }
      }

    return [
          SlotSet("botmind_state", "transitioning"),
          UserUttered(text="/pseudo_user_intent_to_wait", parse_data=parse_data),
        ]


class bot_switchto_thinking(Action):

  def name(self) -> Text:
    return "bot_switchto_thinking"

  def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

    return [
          SlotSet("botmind_state", "thinking"),
        ]


class bot_let_action_emerges(Action):

  def name(self) -> Text:
    return "bot_let_action_emerges"

  def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

    return [
          FollowupAction(name='bot_output_decision')
        ]


class bot_output_decision(Action):

  def name(self) -> Text:
    return "bot_output_decision"

  def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
    parse_data = {
        "intent": {
            "name": "pseudo_user_intent_to_wait",
            "confidence": 1.0,
          }
      }

    return [
          SlotSet("botmind_state", "attentive"),
          UserUttered(text="/pseudo_user_intent_to_wait", parse_data=parse_data),
        ]


class set_botmemo_booking_progress__information_collecting__(Action):

  def name(self) -> Text:
    return "set_botmemo_booking_progress__information_collecting__"

  def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

    return [SlotSet("botmemo_booking_progress", "information_collecting")]


class set_botmemo_booking_progress__room_selected__(Action):

  def name(self) -> Text:
    return "set_botmemo_booking_progress__room_selected__"

  def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

    return [SlotSet("botmemo_booking_progress", "room_selected")]


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

  def checkif_done_collection_information(self, slots):
    bkinfo = ('bkinfo_area', 'bkinfo_checkin_time', 'bkinfo_duration', 'bkinfo_room_type')

    for name in bkinfo:
      v = slots.get(name, False)
      logger.info("[DEBUG] %s: %s", name, v)
      if not v:
        return False

    return True

  def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

    entity_name, slot_name = self.slot_entity()
    logger.info(f"[INFO] retrieve_entity_value, entity_name: %s", str(entity_name))
    logger.info(f"[INFO] retrieve_entity_value, slot_name: %s", str(slot_name))

    entity_value = self.retrieve_entity_value(tracker, entity_name)
    logger.info(f"[INFO] retrieve_entity_value, entity_value: %s", str(entity_value))

    events = []
    if not entity_value:
      return events

    valid_entity_value = self.verify_entity(entity_name=entity_name, entity_value=entity_value)
    if valid_entity_value:
      events.append(SlotSet(slot_name, valid_entity_value))
      # set __flag slot to None
      bkinfo_flag_slot = f"{slot_name}_flag"
      events.append(SlotSet(bkinfo_flag_slot, 'present'))

    slots = tracker.slots.copy()
    slots[slot_name] = valid_entity_value
    if self.checkif_done_collection_information(slots):
      events.append(SlotSet("botmemo_booking_progress", "done_information_collecting"))
    else:
      events.append(SlotSet("botmemo_booking_progress", "information_collecting"))

    return events


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


class botacts_show_room_list(Action):

  def name(self) -> Text:
    return "botacts_show_room_list"

  def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

    slots = tracker.slots

    botmemo_booking_progress = slots['botmemo_booking_progress']
    if botmemo_booking_progress != 'done_information_collecting':
      return [SlotSet('botmemo_booking_failure', 'missing_booking_info')]

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


class botacts_confirm_room_selection(Action):

  def name(self) -> Text:
    return "botacts_confirm_room_selection"

  def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

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

    return []
