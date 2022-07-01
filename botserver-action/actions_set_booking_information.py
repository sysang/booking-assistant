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
from .service import query_available_rooms, query_room_by_id
from .fsm_botmemo_booking_progress import FSMBotmemeBookingProgress


logger = logging.getLogger(__name__)
DATE_FORMAT = 'MMMM Do YYYY'

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

  def update_booking_progress(self, slot_name, slot_value, slots):
    # Coz changed working slot has not been reflexted
    additional = {
        slot_name:  slot_value,
        'botmind_context': 'workingonbooking'
    }
    botmemo_booking_progress = FSMBotmemeBookingProgress(slots, additional)

    return SlotSet("botmemo_booking_progress", botmemo_booking_progress.next_state)

  def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
    slots = tracker.slots.copy()
    events = []

    slot_name, slot_value = self.retrieve_slot_data(tracker)
    if slot_value and slot_name:
      events.append(SlotSet(slot_name, slot_value))

      # set __flag slot to None
      bkinfo_flag_slot = f"{slot_name}_flag"
      events.append(SlotSet(bkinfo_flag_slot, 'present'))
    else:
        return events

    if slots.get('botmind_context') != 'workingonbooking':
      events.append(SlotSet("botmind_context", "workingonbooking"))

    events.append(self.update_booking_progress(slot_name, slot_value, slots))

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
    return ('time', 'bkinfo_checkin_time')


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


class set_booking_information__bed_type__(ActionSetBookingInformation):

  def name(self) -> Text:
    return "set_booking_information__bed_type__"

  def slot_entity(self) -> Tuple[str, str]:
    return ('bed_type', 'bkinfo_bed_type')
