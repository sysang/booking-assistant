import logging
import json
import random
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
from .commons import BookingInfo

logger = logging.getLogger(__name__)

BOTMIND_STATE_SLOT = {
    'ATTENTIVE': SlotSet('botmind_state', 'attentive'),
    'TRANSITIONING': SlotSet('botmind_state', 'transitioning'),
    'THINKINGx1': SlotSet('botmind_state', 'thinking_boostX1'),
    'THINKINGx2': SlotSet('botmind_state', 'thinking_boostX2'),
    'PRIMEx1': SlotSet('botmind_state', 'prime_boostX1'),
    'PRIMEx2': SlotSet('botmind_state', 'prime_boostX2'),
}


class pseudo_action(Action):

  def name(self) -> Text:
    return "pseudo_action"

  def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
    return [BOTMIND_STATE_SLOT['ATTENTIVE']]


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
    parse_data = {
        "intent": {
            "name": "pseudo_user_intent_to_wait",
            "confidence": 1.0,
          }
      }

    botmind_state_slot = BOTMIND_STATE_SLOT['PRIMEx1'] if random.random() > 0.5 else BOTMIND_STATE_SLOT['PRIMEx2']

    return [
            UserUttered(text="/pseudo_user_intent_to_wait", parse_data=parse_data),
            botmind_state_slot,
            FollowupAction(name="bot_switchto_thinking"),
            ]


class bot_switchto_thinking(Action):

  def name(self) -> Text:
    return "bot_switchto_thinking"

  def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

    botmind_state_slot = BOTMIND_STATE_SLOT['THINKINGx1'] if random.random() > 0.5 else BOTMIND_STATE_SLOT['THINKINGx2']

    return [botmind_state_slot]


class bot_let_action_emerges(Action):

  def name(self) -> Text:
    return "bot_let_action_emerges"

  def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

    return [
            BOTMIND_STATE_SLOT['TRANSITIONING'],
            FollowupAction(name="pseudo_action"),
        ]


class set_botmemo_booking_progress__information_collecting__(Action):

  def name(self) -> Text:
    return "set_botmemo_booking_progress__information_collecting__"

  def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

    return [SlotSet("botmemo_booking_progress", "information_collecting")]


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

  def retrieve_slot_data(self, tracker):
    entity_name, slot_name = self.slot_entity()
    logger.info(f"[INFO] retrieve_entity_value, entity_name: %s", str(entity_name))
    logger.info(f"[INFO] retrieve_entity_value, slot_name: %s", str(slot_name))

    entity_value = self.retrieve_entity_value(tracker, entity_name)
    logger.info(f"[INFO] retrieve_entity_value, entity_value: %s", str(entity_value))

    if not entity_value:
      return None, None

    valid_entity_value = self.verify_entity(entity_name=entity_name, entity_value=entity_value)

    return slot_name, valid_entity_value

  def update_booking_progress(self, slot_name, slot_value, tracker):
    events = []

    slots = tracker.slots.copy()
    slots[slot_name] = slot_value
    if BookingInfo.checkif_done_collection_information(slots):
      events.append(SlotSet("botmemo_booking_progress", "done_information_collecting"))
    else:
      events.append(SlotSet("botmemo_booking_progress", "information_collecting"))

    if BookingInfo.checkif_room_selectd(slots):
      events.append(SlotSet("botmemo_booking_progress", "room_selected"))

    return events

  def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
    events = []

    slot_name, slot_value = self.retrieve_slot_data(tracker)
    if slot_value and slot_name:
      events.append(SlotSet(slot_name, slot_value))

      # set __flag slot to None
      bkinfo_flag_slot = f"{slot_name}_flag"
      events.append(SlotSet(bkinfo_flag_slot, 'present'))
    else:
        return events

    events = events + self.update_booking_progress(slot_name, slot_value, tracker)

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


class set_notes_bkinfo(Action):

  def name(self) -> Text:
    return "set_notes_bkinfo"

  def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

    slots = tracker.slots

    botmemo_booking_progress = slots['botmemo_booking_progress']
    error_message = '[ERROR] in set_notes_bkinfo action, missing booking info'
    if botmemo_booking_progress != 'done_information_collecting':
      return [
            SlotSet('botmemo_booking_failure', 'missing_booking_info'),
            SlotSet('logs_debugging_info', slots['logs_debugging_info'] + [error_message]),
          ]

    # TODO: check slot's value, if slot is empty re-proceed appropricate info collecting step
    bkinfo = BookingInfo(slots)

    return [SlotSet('notes_bkinfo', bkinfo)] + BookingInfo.set_booking_information_flag(value='noted')

class botacts_show_room_list(Action):

  def name(self) -> Text:
    return "botacts_show_room_list"

  def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

    slots = tracker.slots
    bkinfo = slots.get('notes_bkinfo', None)

    error_message = '[ERROR] in botacts_show_room_list action, missing booking info'
    if not bkinfo:
      return [
            SlotSet('botmemo_booking_failure', 'missing_booking_info'),
            SlotSet('logs_debugging_info', slots['logs_debugging_info'] + [error_message]),
          ]

    rooms = query_available_rooms(**bkinfo)

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

    # return [BOTMIND_STATE_SLOT['ATTENTIVE']]
    return []


class botacts_confirm_room_selection(Action):

  def name(self) -> Text:
    return "botacts_confirm_room_selection"

  def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

    slots = tracker.slots
    bkinfo = slots['notes_bkinfo']

    # TODO: check slot's id, if id is absent restart the process (safe fallback)
    room_id = slots.get('bkinfo_room_id')
    if not room_id:
        error_message = '[ERROR] in botacts_confirm_room_selection action, missing room id'
        return [
                SlotSet('botmemo_booking_failure', 'missing_room_id'),
                SlotSet('logs_debugging_info', slots['logs_debugging_info'] + [error_message]),
            ]

    room = query_room_by_id(room_id)
    hotel_name = room['hotel']
    # TODO: check slot for potental error
    checkin_time = arrow.get(bkinfo['bkinfo_checkin_time']).format('MMMM Do YYYY')
    duration = bkinfo['bkinfo_duration']
    duration = str(duration) + ' days' if duration > 1 else str(duration) + ' day'

    dispatcher.utter_message(response = "utter_room_selection",
          room_type=bkinfo['bkinfo_room_type'],
          checkin_time=checkin_time,
          duration=duration,
          hotel_name=hotel_name,
        )

    return [
            # BOTMIND_STATE_SLOT['ATTENTIVE'],
            SlotSet('bkinfo_room_id', None),
            SlotSet('bkinfo_room_id_flag', None),
            SlotSet('notes_room_id', room_id),
        ] + BookingInfo.set_booking_information_flag(value=None) + BookingInfo.set_booking_information(value=None)


class ActionReviseBookingInformation(ActionSetBookingInformation):

  def name(self) -> Text:
    return "ActionReviseBookingInformation"

  def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

    slot_name, slot_value = self.retrieve_slot_data(tracker)
    if not slot_name and not slot_value:
      return []

    events = []

    if slot_value:
      events.append(SlotSet(slot_name, slot_value))
      events.append(SlotSet('notes_bkinfo', None))
      events = events + BookingInfo.set_booking_information_flag(value='present')
    elif slot_name:
      events.append(SlotSet('botmemo_booking_progress', 'information_collecting'))
      events.append(SlotSet(f"{slot_name}_flag", 'onchange'))

    events = events + self.update_booking_progress(slot_name, slot_value, tracker)

    return events


class revise_booking_information__area__(ActionReviseBookingInformation):

  def name(self) -> Text:
    return "revise_booking_information__area__"

  def slot_entity(self) -> Tuple[str, str]:
    return ('area', 'bkinfo_area')


class revise_booking_information__checkin_time__(ActionReviseBookingInformation):

  def name(self) -> Text:
    return "revise_booking_information__checkin_time__"

  def slot_entity(self) -> Tuple[str, str]:
    return ('date', 'bkinfo_checkin_time')


class revise_booking_information__duration__(ActionReviseBookingInformation):

  def name(self) -> Text:
    return "revise_booking_information__duration__"

  def slot_entity(self) -> Tuple[str, str]:
    return ('duration', 'bkinfo_duration')


class revise_booking_information__room_type__(ActionReviseBookingInformation):

  def name(self) -> Text:
    return "revise_booking_information__room_type__"

  def slot_entity(self) -> Tuple[str, str]:
    return ('room_type', 'bkinfo_room_type')
