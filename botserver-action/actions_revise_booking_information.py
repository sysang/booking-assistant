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
from .data_struture import BookingInfo
from .fsm_botmemo_booking_progress import FSMBotmemeBookingProgress

logger = logging.getLogger(__name__)

BOTMIND_STATE_SLOT = {
    'ATTENTIVE': SlotSet('botmind_state', 'attentive'),
    'TRANSITIONING': SlotSet('botmind_state', 'transitioning'),
    'THINKINGx1': SlotSet('botmind_state', 'thinking_boostX1'),
    'THINKINGx2': SlotSet('botmind_state', 'thinking_boostX2'),
    'PRIMEx1': SlotSet('botmind_state', 'prime_boostX1'),
    'PRIMEx2': SlotSet('botmind_state', 'prime_boostX2'),
}

DATE_FORMAT = 'MMMM Do YYYY'

from .actions_set_booking_information import ActionSetBookingInformation


class ActionReviseBookingInformation(ActionSetBookingInformation):

    def name(self) -> Text:
        return "ActionReviseBookingInformation"

    def inform(self, slot_name, slot_value, dispatcher):
        if 'bkinfo_area' == slot_name:
            dispatcher.utter_message(response='utter_inform_booking_area_revised', bkinfo_area=slot_value)
        elif 'bkinfo_checkin_time' == slot_name:
            bkinfo_checkin_time = arrow.get(slot_value).format(DATE_FORMAT)
            dispatcher.utter_message(response='utter_inform_checkin_time_revised', bkinfo_checkin_time=bkinfo_checkin_time)
        elif 'bkinfo_duration' == slot_name:
            dispatcher.utter_message(response='utter_inform_reservation_duration_revised', bkinfo_duration=slot_value)
        elif 'bkinfo_room_type' == slot_name:
            dispatcher.utter_message(response='utter_inform_hotel_room_type_revised', bkinfo_room_type=slot_value)

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        slot_name, slot_value = self.retrieve_slot_data(tracker)
        if not slot_name and not slot_value:
            return []

        events = []

        if slot_value:
            events.append(SlotSet(slot_name, slot_value))
            events.append(SlotSet('search_result_flag', None))
            events += BookingInfo.set_booking_information_flag(value='present')
        elif slot_name:
            events.append(SlotSet('botmemo_booking_progress', 'information_collecting'))
            events.append(BookingInfo.set_bkinfo_slot_flag(slot_name, 'onchange'))

        slots = tracker.slots
        # Coz changed working slot has not been reflexted
        additional = {
            slot_name:  slot_name,
            'botmind_context': 'workingonbooking',
            'search_result_flag': None,
        }
        botmemo_booking_progress = FSMBotmemeBookingProgress(slots, additional)
        events.append(SlotSet("botmemo_booking_progress", botmemo_booking_progress.next_state))

        self.inform(slot_name, slot_value, dispatcher)

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


