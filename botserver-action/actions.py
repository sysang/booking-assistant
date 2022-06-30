import logging
import json
import random
import copy
from typing import Any, Dict, List, Text, Optional, Tuple
from datetime import datetime

import arrow

from rasa_sdk import Action, Tracker
from rasa_sdk.forms import ValidationAction
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
from rasa_sdk.types import DomainDict

from .entity_preprocessing_rules import mapping_table
from .service import query_available_rooms, query_room_by_id
from .data_struture import BookingInfo
from .fsm_botmemo_booking_progress import FSMBotmemeBookingProgress
from .actions_validate_predefined_slots import ValidatePredefinedSlots
from .actions_validate_info_form import ValidateBkinfoForm
from .utils import slots_for_entities

logger = logging.getLogger(__name__)

BOTMIND_STATE_SLOT = {
    'ATTENTIVE': SlotSet('botmind_state', 'attentive'),
    'TRANSITIONING': SlotSet('botmind_state', 'transitioning'),
    'THINKINGx1': SlotSet('botmind_state', 'thinking'),
    'THINKINGx2': SlotSet('botmind_state', 'thinking'),
    'PRIMEx1': SlotSet('botmind_state', 'prime_boostX1'),
    'PRIMEx2': SlotSet('botmind_state', 'prime_boostX2'),
}

DATE_FORMAT = 'MMMM Do YYYY'


from .actions_botacts_checkif_user_wants_booking import botacts_checkif_user_wants_booking, bot_perceive_user_wants_booking
from .actions_set_booking_information import (
    set_booking_information__area__,
    set_booking_information__checkin_time__,
    set_booking_information__duration__,
    set_booking_information__bed_type__,
    set_booking_information__room_id__,
)
from .actions_revise_booking_information import (
    revise_booking_information__area__,
    revise_booking_information__checkin_time__,
    revise_booking_information__duration__,
    revise_booking_information__bed_type__,
)


class custom_action_fallback(Action):

    def name(self) -> Text:
        return "custom_action_fallback"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        return [
            FollowupAction('bot_let_action_emerges'),
        ]

class action_unlikely_intent(Action):

    def name(self) -> Text:
        return "action_unlikely_intent"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        return [
            FollowupAction('bot_let_action_emerges'),
        ]

class bot_let_action_emerges(Action):

    def name(self) -> Text:
        return "bot_let_action_emerges"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        THRESHOLD = 10
        parse_data = {
            "intent": {
                "name": "bot_embodies_intention",
                "confidence": 1.0,
            }
        }

        logs_fallback_loop_history = tracker.slots.get('logs_fallback_loop_history', [])
        events = [
            BOTMIND_STATE_SLOT['TRANSITIONING'],
            UserUttered(text="/bot_embodies_intention", parse_data=parse_data),
            FollowupAction(name="pseudo_action"),
            SlotSet('logs_fallback_loop_history', logs_fallback_loop_history + [datetime.now().timestamp()]),
        ]

        if len(logs_fallback_loop_history) == 0:
            return events

        last = datetime.fromtimestamp(logs_fallback_loop_history[-1])
        duration = datetime.now() - last
        if duration.seconds < THRESHOLD:
            dispatcher.utter_message(response='utter_looping_fallback')
            return [AllSlotsReset()]

        return events


class pseudo_action(Action):

    def name(self) -> Text:
        return "pseudo_action"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        return [BOTMIND_STATE_SLOT['ATTENTIVE']]


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
            "name": "bot_intents_to_think",
            "confidence": 1.0,
        }
    }

    botmind_state_slot = BOTMIND_STATE_SLOT['PRIMEx1'] if random.random() > 0.5 else BOTMIND_STATE_SLOT['PRIMEx2']

    return [
        UserUttered(text="/bot_intents_to_think", parse_data=parse_data),
        botmind_state_slot,
        FollowupAction(name="bot_switchto_thinking"),
    ]


class bot_switchto_thinking(Action):

  def name(self) -> Text:
    return "bot_switchto_thinking"

  def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

    botmind_state_slot = BOTMIND_STATE_SLOT['THINKINGx1'] if random.random() > 0.5 else BOTMIND_STATE_SLOT['THINKINGx2']

    return [botmind_state_slot]


#TODO: rename to search_hotel
class bot_search_hotel_rooms(Action):

  def name(self) -> Text:
    return "bot_search_hotel_rooms"

  def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

    slots = tracker.slots
    botmemo_booking_progress = FSMBotmemeBookingProgress(slots)

    error_message = '[ERROR] in bot_search_hotel_rooms action, bkinfo in incomplete'
    if not botmemo_booking_progress.is_form_completed():
        return [
            SlotSet('botmemo_booking_failure', 'missing_booking_info'),
            SlotSet('logs_debugging_info', slots['logs_debugging_info'] + [error_message]),
            FollowupAction('bot_let_action_emerges'),
        ]

    bkinfo = botmemo_booking_progress.form
    rooms = query_available_rooms(**bkinfo)

    events = []

    if rooms is None or len(rooms) == 0:
        events.append(SlotSet('notes_search_result', []))
    else:
        events.append(SlotSet('notes_search_result', rooms))

    notes_bkinfo = {}
    for slot_name in FSMBotmemeBookingProgress.FORM_SCHEMA:
        # events.append(SlotSet(slot_name, None))
        notes_bkinfo[slot_name] = slots.get(slot_name)

    events.append(SlotSet('search_result_flag', 'available'))
    events.append(SlotSet('notes_bkinfo', notes_bkinfo))

    return events

class botacts_show_room_list(Action):

    def name(self) -> Text:
        return "botacts_show_room_list"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        events = []
        slots = tracker.slots
        notes_bkinfo = slots.get('notes_bkinfo')
        botmemo_booking_progress = slots.get('botmemo_booking_progress')
        rooms = slots.get('notes_search_result')

        if botmemo_booking_progress == 'room_selected':
            error_message = '[ERROR] in botacts_show_room_list action, room has been selected.'

            return [
                SlotSet('logs_debugging_info', slots['logs_debugging_info'] + [error_message]),
                FollowupAction('botacts_confirm_room_selection'),
            ]

        if botmemo_booking_progress != 'done_information_collecting':
            error_message = '[ERROR] in botacts_show_room_list action, bkinfo is incomplete'

            return [
                SlotSet('botmemo_booking_failure', 'missing_booking_info'),
                SlotSet('logs_debugging_info', slots['logs_debugging_info'] + [error_message]),
                FollowupAction('bot_let_action_emerges'),
            ]

        if rooms is None or len(rooms) == 0:
            dispatcher.utter_message(response="utter_room_not_available")
            dispatcher.utter_message(response="utter_asking_revise_booking_information")

        else:
            buttons = []
            for room in rooms:
                params = { 'room_id': room['id'] }
                params = json.dumps(params)

                buttons.append({
                    "title": "%s, price: $%s" % (room["hotel"], room['price']),
                    "payload": "/user_click_to_select_hotel%s" % (params)  # IMPORTANT the json format of params is very strict, use \' instead of \" will yield silently no effect
                })

            logger.info("[INFO] buttons: %s", buttons)
            dispatcher.utter_message(response="utter_about_to_show_hotel_list", buttons=buttons)

        botmemo_booking_progress = FSMBotmemeBookingProgress(slots)
        events.append(SlotSet('botmemo_booking_progress', botmemo_booking_progress.next_state))

        events.append(SlotSet('search_result_flag', None))

        return events


class botacts_confirm_room_selection(Action):

  def name(self) -> Text:
    return "botacts_confirm_room_selection"

  def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
    slots = tracker.slots

    room_id = slots.get('bkinfo_room_id')
    if not room_id:
        error_message = '[ERROR] in botacts_confirm_room_selection action, missing room id'
        return [
                SlotSet('botmemo_booking_failure', 'missing_room_id'),
                SlotSet('logs_debugging_info', slots['logs_debugging_info'] + [error_message]),
                FollowupAction('bot_let_action_emerges'),
            ]

    room = query_room_by_id(room_id)
    hotel_name = room['hotel']

    dispatcher.utter_message(response="utter_room_selection", hotel_name=hotel_name)

    events = [AllSlotsReset()]

    return events


class botacts_start_conversation(Action):

    def name(self) -> Text:
        return "botacts_start_conversation"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        events = [
            SlotSet('botmind_context', 'chitchat'),
        ]

        return events


class botacts_express_bot_job_to_support_booking(Action):

    def name(self) -> Text:
        return "botacts_express_bot_job_to_support_booking"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        dispatcher.utter_message(response='utter_bot_job_to_support_booking')

        botmemo_booking_progress = FSMBotmemeBookingProgress(
            slots=tracker.slots,
            additional={'botmind_context': 'workingonbooking', 'search_result_flag': 'waiting'},
        )
        events = [
            SlotSet('botmind_context', 'workingonbooking'),
            SlotSet('search_result_flag', 'waiting'),
            SlotSet('botmemo_booking_progress', botmemo_booking_progress.next_state),
            SlotSet('botmemo_bkinfo_status', [None] * len(FSMBotmemeBookingProgress.FORM_SCHEMA)),
        ]

        return events


class bot_determines_botmemo_booking_progress(Action):

    def name(self) -> Text:
        return "bot_determines_botmemo_booking_progress"

    def slots_for_entities(self, entities: List[Dict[Text, Any]], intent: Dict[Text, Any], domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return slots_for_entities(entities, intent, domain)

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        entities = tracker.latest_message['entities']
        intent = tracker.latest_message['intent']
        mapped_slots = self.slots_for_entities(entities, intent, domain)
        botmemo_booking_progress = FSMBotmemeBookingProgress(tracker.slots, additional=mapped_slots)

        logger.info("[INFO] botmemo_booking_progress.form: %s", botmemo_booking_progress.form)

        return [botmemo_booking_progress.SlotSetEvent]


class action_old_slot_mapping(Action):

    def name(self) -> Text:
        return "action_old_slot_mapping"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        slots = copy.copy(tracker.slots)
        del slots['old']
        del slots['requested_slot']
        del slots['logs_debugging_info']
        del slots['logs_fallback_loop_history']
        del slots['session_started_metadata']
        del slots['botmind_name']

        return [SlotSet('old', slots)]


class botacts_utter_revised_bkinfo(Action):

    def name(self) -> Text:
        return "botacts_utter_revised_bkinfo"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        events = []
        schema = FSMBotmemeBookingProgress.FORM_SCHEMA
        slots = tracker.slots
        search_result_flag = slots.get('search_result_flag')

        for slot_name in schema:
            slot_name_revised = f"{slot_name}_revised"
            slot_value_revised = slots.get(slot_name_revised, None)
            if slot_value_revised:
                response = 'utter_revised_{slot_name}'
                dispatcher.utter_message(response=response)
                events.append(SlotSet(slot_name, slot_value_revised))

        if search_result_flag == 'room_showing':
            events.append(SlotSet('botmemo_booking_progress', 'done_information_collecting'))
            events.append(SlotSet('search_result_flag', 'waiting'))

        return events


class action_bkinfo_status_slot_mapping(Action):

    def name(self) -> Text:
        return "action_bkinfo_status_slot_mapping"

    def slots_for_entities(self, entities: List[Dict[Text, Any]], intent: Dict[Text, Any], domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return slots_for_entities(entities, intent, domain)

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        slots = tracker.slots
        botmemo_bkinfo_status = slots.get('botmemo_bkinfo_status', None)

        # TODO: check for intent mapping
        entities = tracker.latest_message['entities']
        intent = tracker.latest_message['intent']
        mapped_slots = self.slots_for_entities(entities, intent, domain)
        botmemo_booking_progress = FSMBotmemeBookingProgress(slots, additional=mapped_slots)
        logger.info("[INFO] botmemo_booking_progress.form: %s", botmemo_booking_progress.form.values())
        slot_value = list(botmemo_booking_progress.form.values())

        if not botmemo_bkinfo_status:
            return [SlotSet('botmemo_bkinfo_status', None)]

        return [SlotSet('botmemo_bkinfo_status', slot_value)]
