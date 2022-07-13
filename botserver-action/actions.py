import logging
import re
import json
import random
import copy

import arrow

from typing import Any, Dict, List, Text, Optional, Tuple
from datetime import datetime
from functools import reduce


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
from .booking_service import search_rooms
from .utils import (
    slots_for_entities,
    get_room_by_id,
    extract_page_number_payload,
    paginate,
    hash_bkinfo,
    picklize_search_result,
)
from .utils import SORTBY_POPULARITY, SORTBY_REVIEW_SCORE, SORTBY_PRICE
from .utils import parse_date_range

from .duckling_service import (
    parse_checkin_time,
    parse_bkinfo_duration,
    parse_bkinfo_price,
)

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

TEST_ENV = False


class custom_action_fallback(Action):

    def name(self) -> Text:
        return "custom_action_fallback"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        return [
            FollowupAction(name='bot_let_action_emerges'),
        ]

class action_unlikely_intent(Action):

    def name(self) -> Text:
        return "action_unlikely_intent"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        return [
            FollowupAction(name='bot_let_action_emerges'),
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
            },
            'entities': [
                {
                    'entity': 'botmind_state',
                    'value': 'transitioning',
                    'confidence_entity': 1.0,
                }
            ]
        }

        logs_fallback_loop_history = tracker.slots.get('logs_fallback_loop_history', [])
        events = [
            SlotSet('logs_fallback_loop_history', logs_fallback_loop_history + [datetime.now().timestamp()]),
            UserUttered(text="/bot_embodies_intention", parse_data=parse_data),
            BOTMIND_STATE_SLOT['TRANSITIONING'],
            FollowupAction(name="pseudo_action"),
        ]

        if len(logs_fallback_loop_history) == 0:
            return events

        last = datetime.fromtimestamp(logs_fallback_loop_history[-1])
        duration = datetime.now() - last
        if duration.seconds < THRESHOLD:
            dispatcher.utter_message(response='utter_looping_fallback')
            return [
                FollowupAction(name='action_listen'),
                AllSlotsReset(),
            ]

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
class botacts_search_hotel_rooms(Action):

    def name(self) -> Text:
        return "botacts_search_hotel_rooms"

    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        events = []
        slots = tracker.slots
        channel = tracker.get_latest_input_channel()
        pagination_intent = 'user_click_to_navigate_search_result'
        LIMIT_NUM = 3
        notes_bkinfo = slots.get('notes_bkinfo')
        bkinfo_orderby = slots.get('bkinfo_orderby', None)
        querystr = slots.get('search_result_query', '')
        notes_search_result = slots.get('notes_search_result', {})
        botmemo_booking_progress = FSMBotmemeBookingProgress(slots)
        bkinfo = botmemo_booking_progress.form

        if bkinfo_orderby:
            page_number = 1
        elif querystr:
            page_number, bkinfo_orderby = extract_page_number_payload(querystr)

        if not bkinfo_orderby:
            bkinfo_orderby = SORTBY_POPULARITY
            page_number = 1

        logger.info('[INFO] navigation, bkinfo_orderby: %s, page_number: %s', bkinfo_orderby, page_number)

        if not botmemo_booking_progress.is_form_completed():
            error_message = '[ERROR] in botacts_search_hotel_rooms action, bkinfo is incomplete'
            return [
                SlotSet('botmemo_booking_failure', 'missing_booking_info'),
                SlotSet('logs_debugging_info', slots['logs_debugging_info'] + [error_message]),
                FollowupAction(name='bot_let_action_emerges'),
            ]

        if botmemo_booking_progress == 'room_selected':
            error_message = '[ERROR] in botacts_search_hotel_rooms action, room has been selected.'
            return [
                SlotSet('logs_debugging_info', slots['logs_debugging_info'] + [error_message]),
                FollowupAction(name='botacts_confirm_room_selection'),
            ]

        # if TEST_ENV:
        # hashed_query = hash_bkinfo(bkinfo_orderby=bkinfo_orderby, **bkinfo)
        # hotels = query_available_rooms(bkinfo_orderby=bkinfo_orderby, **bkinfo)

        hashed_query = hash_bkinfo(bkinfo_orderby=bkinfo_orderby, **bkinfo)
        if notes_search_result and notes_search_result.get('hashed_query', None) == hashed_query:
            hotels = notes_search_result.get('hotels', {})
            hotels = picklize_search_result(data=hotels)
            logger.info('[INFO] Retrieve hotels from notes_search_result slot.')
        else:
            hotels = await search_rooms(bkinfo_orderby=bkinfo_orderby, **bkinfo)
            events.append(SlotSet('notes_search_result', {
                'hashed_query': hashed_query,
                'hotels': picklize_search_result(data=hotels),
            }))

            if not isinstance(hotels, dict):
                error_message = '[ERROR] in botacts_search_hotel_rooms action, search_rooms returns wrong data type: %s.' % (type(hotels))
                return [
                    SlotSet('botmemo_booking_failure', 'missing_booking_info'),
                    SlotSet('logs_debugging_info', slots['logs_debugging_info'] + [error_message]),
                    FollowupAction(name='bot_let_action_emerges'),
                ]

            logger.info('[INFO] request to booking_service, hotels: %s', hotels.keys())

        if len(hotels.keys()) == 0:
            dispatcher.utter_message(response="utter_room_not_available")
            dispatcher.utter_message(response="utter_asking_revise_booking_information")

        else:
            total_rooms = reduce(lambda x, y: x+y, hotels.values())
            room_num = len(total_rooms)

            if SORTBY_REVIEW_SCORE== bkinfo_orderby:
                dispatcher.utter_message(response="utter_about_to_show_hotel_list_by_review_score", room_num=room_num)
            elif SORTBY_PRICE == bkinfo_orderby:
                dispatcher.utter_message(response="utter_about_to_show_hotel_list_by_price", room_num=room_num)
            else:
                dispatcher.utter_message(response="utter_about_to_show_hotel_list_by_popularity", room_num=room_num)

            start, end, remains = paginate(index=page_number, limit=LIMIT_NUM, total=room_num)
            logger.info('[INFO] paginating search result by index=%s, limit=%s, total=%s -> (%s, %s, %s)', page_number, LIMIT_NUM, room_num, start, end, remains)

            fb_elements = []
            counter = start
            for room in total_rooms[start:end]:

                counter += 1
                room_bed_type = room.get('bed_type', {}).get('name', 'unknown')
                photos = [ photo.get('url_original', '') for photo in room.get('photos', [])]
                photos = photos[0:5]
                photos = ' - ' + '\n - '.join(photos)

                data = {
                    'hotel_name': room['hotel_name_trans'],
                    'address': room['address_trans'],
                    'city': room['city_trans'],
                    'country': room['country_trans'],
                    'review_score': room['review_score'],
                    'nearest_beach_name': 'near ' + room['nearest_beach_name'] if room['is_beach_front'] else '',
                    'photos': photos,
                    'room_display_index': counter,
                    'room_name': room['name_without_policy'],
                    'room_bed_type': room.get('bed_type', {}).get('name', 'unknown'),
                    'room_min_price': room['min_price'],
                    'room_price_currency': room['price_currency'],
                }

                room_description = "Room #{room_display_index}: {room_name}, {room_bed_type}, {room_min_price:.2f} {room_price_currency}, {hotel_name}. Room's photos:\n{photos}" . format(**data)
                # room_photos = "Room's photos:\n{photos}" . format(**data)
                hotel_descrition = "{hotel_name}, address: {address}, {city}, {country}. Review score: {review_score}; {nearest_beach_name}" . format(**data)

                # IMPORTANT: the json format of params is very strict, use \' instead of \" will yield silently no effect
                payload = { 'room_id': room['room_id'] }
                btn_payload = "/user_click_to_select_room%s" % (json.dumps(payload))
                if channel == 'facebook':
                    fb_button = 'Room #{room_display_index}'.format(**data)
                    fb_elements.append({
                        'title': hotel_descrition,
                        'subtitle': room_description,
                        'buttons': [
                            {
                                'title': fb_button,
                                "type":"postback",
                                'payload': btn_payload,
                            }
                        ]
                    })
                else:
                    logger.info("[INFO] channel: %s", channel)
                    btn_title = 'Room #{room_display_index}: {room_min_price} {room_price_currency}'.format(**data)
                    button = { "title": btn_title, "payload": btn_payload}

                    dispatcher.utter_message(text=room_description, buttons=[button])
                    dispatcher.utter_message(image=room['hotel_photo_url'], text=hotel_descrition)

            if channel == 'facebook':
                dispatcher.utter_message(elements=fb_elements, template_type="generic")

            query = {
                'next': json.dumps({'page_number': page_number + 1, 'order_by': bkinfo_orderby}),
                'intent': pagination_intent,
                'remains': remains,
                'limit_num': LIMIT_NUM,
            }

            buttons = []
            if page_number > 1:
                query['prev'] = json.dumps({'page_number': page_number - 1, 'order_by': bkinfo_orderby})
                # buttons.append({'title': 'back {limit_num} rooms'.format(**query), 'payload': '/{intent}{prev}'.format(**query)})
            if remains != 0:
                pass
                # buttons.append({'title': 'see more {remains} room(s)'.format(**query), 'payload': '/{intent}{next}'.format(**query)})

            # dispatcher.utter_message(response="utter_instruct_to_choose_room", buttons=buttons)
            dispatcher.utter_message(response="utter_instruct_to_choose_room")

        botmemo_booking_progress = FSMBotmemeBookingProgress(slots, additional={'search_result_flag': 'available'})
        events.append(botmemo_booking_progress.SlotSetEvent)
        events.append(SlotSet('search_result_flag', 'available'))
        events.append(SlotSet('bkinfo_orderby', None))
        events.append(SlotSet('search_result_query', None))
        events.append(SlotSet('notes_bkinfo', bkinfo))

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
            ]

    search_result = slots.get('notes_search_result')
    room = get_room_by_id(room_id=room_id, search_result=search_result)

    if not room:
        error_message = '[ERROR] in botacts_confirm_room_selection action, data is broken or clicking room handling logic is mistaken or clicking event is accidental.'
        return [
                SlotSet('botmemo_booking_failure', 'missing_room_id'),
                SlotSet('logs_debugging_info', slots['logs_debugging_info'] + [error_message]),
                FollowupAction(name='bot_let_action_emerges'),
            ]
    checkin_time = parse_checkin_time(expression=slots.get('bkinfo_checkin_time'))
    duration = parse_bkinfo_duration(expression=slots.get('bkinfo_duration'))
    checkin_date, checkout_date = parse_date_range(from_time=checkin_time.value, duration=duration.value, format='MMM DD YYYY')

    hotel_name = room['hotel_name_trans']
    data = {
        'room_name': room['name_without_policy'],
        'room_bed_type': room.get('bed_type', {}).get('name', 'unknown'),
        'room_min_price': room['min_price'],
        'room_price_currency': room['price_currency'],
    }
    room_description = "Room details: {room_name}, {room_bed_type}, {room_min_price:.2f} {room_price_currency}" . format(**data)

    dispatcher.utter_message(
        response="utter_room_selection",
        hotel_name=hotel_name,
        duration=duration.value,
        checkin_date=checkin_date,
        checkout_date=checkout_date,
        room_description=room_description,
    )

    events = [
        FollowupAction(name='action_listen'),
        AllSlotsReset(),
    ]

    return events


class botacts_start_conversation(Action):

    def name(self) -> Text:
        return "botacts_start_conversation"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        events = [
            SlotSet('botmind_context', 'chitchat'),
        ]

        return events


class botacts_utter_bye(Action):

    def name(self) -> Text:
        return "botacts_utter_bye"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        dispatcher.utter_message(response='utter_bye')

        return [
            FollowupAction(name='action_listen'),
            AllSlotsReset(),
        ]


class botacts_utter_asking_confirm_stop_booking(Action):

    def name(self) -> Text:
        return "botacts_utter_asking_confirm_stop_booking"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        botmemo_booking_progress = tracker.slots.get('botmemo_booking_progress')
        not_working_conditions = [None, 'initialized']

        if botmemo_booking_progress in not_working_conditions:
            return [FollowupAction(name='botacts_utter_bye')]

        dispatcher.utter_message(response='utter_asking_confirm_stop_booking')

        return []


class botacts_start_booking_progress(Action):

    def name(self) -> Text:
        return "botacts_start_booking_progress"

    def slots_for_entities(self, entities: List[Dict[Text, Any]], intent: Dict[Text, Any], domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return slots_for_entities(entities, intent, domain)

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        entities = tracker.latest_message['entities']
        logger.info('[INFO] entities: %s', entities)
        intent = tracker.latest_message['intent']
        mapped_slots = self.slots_for_entities(entities, intent, domain)

        search_result_flag = 'waiting'
        botmind_context = 'workingonbooking'

        additional= {'botmind_context': botmind_context, 'search_result_flag': search_result_flag}
        botmemo_booking_progress = FSMBotmemeBookingProgress(
            slots=tracker.slots,
            additional={**mapped_slots, **additional},
        )
        events = [
            SlotSet('botmind_context', botmind_context),
            botmemo_booking_progress.SlotSetEvent,
            SlotSet('botmemo_bkinfo_status', botmemo_booking_progress.bkinfo_status),
            SlotSet('search_result_flag', search_result_flag),
        ]

        for slot_name, slot_value in mapped_slots.items():
            events.append(SlotSet(slot_name, slot_value))

        return events


class botacts_express_bot_job_to_support_booking(Action):

    def name(self) -> Text:
        return "botacts_express_bot_job_to_support_booking"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        intent = tracker.latest_message['intent']['name']
        if intent == 'request_searching_hotel':
            dispatcher.utter_message(response='utter_bot_job_to_support_booking')
        else:
            dispatcher.utter_message(response='utter_bot_guess_to_booking')

        search_result_flag = 'waiting'
        botmind_context = 'workingonbooking'

        botmemo_booking_progress = FSMBotmemeBookingProgress(
            slots=tracker.slots,
            additional={'botmind_context': botmind_context, 'search_result_flag': search_result_flag},
        )
        events = [
            SlotSet('botmind_context', botmind_context),
            botmemo_booking_progress.SlotSetEvent,
            SlotSet('botmemo_bkinfo_status', botmemo_booking_progress.bkinfo_status),
            SlotSet('search_result_flag', search_result_flag),
        ]

        return events


class action_botmemo_booking_progress_mapping(Action):

    def name(self) -> Text:
        return "action_botmemo_booking_progress_mapping"

    def slots_for_entities(self, entities: List[Dict[Text, Any]], intent: Dict[Text, Any], domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return slots_for_entities(entities, intent, domain)

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        entities = tracker.latest_message['entities']
        intent = tracker.latest_message['intent']
        mapped_slots = self.slots_for_entities(entities, intent, domain)
        botmemo_booking_progress = FSMBotmemeBookingProgress(tracker.slots, additional=mapped_slots)

        logger.info("[INFO] botmemo_booking_progress.form: %s", botmemo_booking_progress.form)

        if tracker.latest_action_name == 'botacts_utter_revised_bkinfo':
            return []

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
        del slots['notes_search_result']
        del slots['notes_bkinfo']

        return [SlotSet('old', slots)]


class botacts_utter_revised_bkinfo(Action):

    def name(self) -> Text:
        return "botacts_utter_revised_bkinfo"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        events = []
        schema = FSMBotmemeBookingProgress.FORM_SCHEMA
        slots = tracker.slots
        search_result_flag = slots.get('search_result_flag')
        additional = {}

        """
        Results:
            - reflex the changes to bkinfo
            - reset the revised bkinfo
            - inform user
        """
        for slot_name in schema:
            slot_name_revised = f"{slot_name}_revised"
            slot_value_revised = slots.get(slot_name_revised, None)
            slot_value_current = slots.get(slot_name, None)
            if slot_value_revised and slot_value_revised != slot_value_current:
                response = f'utter_revised_{slot_name}'
                dispatcher.utter_message(response=response)

                events.append(SlotSet(slot_name, slot_value_revised))

                events.append(SlotSet(slot_name_revised, None))
                additional[slot_name_revised] = None

        if search_result_flag == 'available':
            events.append(SlotSet('search_result_flag', 'updating'))
            additional['search_result_flag'] = ['updating']
        else:
            events.append(SlotSet('search_result_flag', 'waiting'))
            additional['search_result_flag'] = ['waiting']

        botmemo_booking_progress = FSMBotmemeBookingProgress(slots, additional=additional)
        events.append(botmemo_booking_progress.SlotSetEvent)

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
        slot_value = botmemo_booking_progress.bkinfo_status

        if not botmemo_bkinfo_status:
            return [SlotSet('botmemo_bkinfo_status', None)]

        return [SlotSet('botmemo_bkinfo_status', slot_value)]


class action_botmind_state_mapping(Action):

    def name(self) -> Text:
        return "action_botmind_state_mapping"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        return []


class action_botmind_intention_mappings(Action):

    def name(self) -> Text:
        return "action_botmind_intention_mappings"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        intent = tracker.latest_message['intent']['name']

        slot_name = 'botmind_intention'
        mind_map = {
            'bye': 'engage_interrogative',
            'stop_doing': 'engage_interrogative',
            'affirm': 'engage_affirmative',
            'deny': 'engage_negative',
        }

        slot_value = mind_map.get(intent, None)

        return [SlotSet(slot_name, slot_value)]

class action_interlocutor_intention_mappings(Action):

    def name(self) -> Text:
        return "action_interlocutor_intention_mappings"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        intent = tracker.latest_message['intent']['name']
        slot_name = 'interlocutor_intention'
        ignored_intents = ['bot_embodies_intention']
        if intent in ignored_intents:
            logger.info('[INFO] skip mapping due to intent: %s', intent)
            return []

        mind_map = {
            'bye': 'terminate_session',
            'stop_doing': 'terminate_session',
        }

        slot_value = mind_map.get(intent, None)

        return [SlotSet(slot_name, slot_value)]

