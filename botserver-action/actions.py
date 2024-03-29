import logging
import re
import json
import random
import copy

import arrow
import requests

from typing import Any, Dict, List, Text, Optional, Tuple
from datetime import datetime
from functools import reduce
from urllib import parse

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
    paginate_button_payload,
    paginate,
    hash_bkinfo,
    picklize_search_result,
)
from .utils import SortbyDictionary
from .utils import parse_date_range
from .utils import DictUpdatingMemmQueue
from .utils import request_botfrontend_url
from .slot_default_values import INTERLOCUTOR_INTENTION_DEFAULT

from .duckling_service import (
    parse_checkin_time,
    parse_bkinfo_duration,
    parse_bkinfo_price,
)
from .redis_service import set_cache, get_cache
from .slot_default_values import BOTMIND_INTENTION_DEFAULT


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
        dispatcher.utter_message(response='utter_resonse_unlikely_intent')
        return []

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


class botacts_utter_inform_searching_inprogress(Action):

    def name(self) -> Text:
        return "botacts_utter_inform_searching_inprogress"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        slots = tracker.slots
        query_payload = slots.get('search_result_query', '')
        if not query_payload:
            botmemo_booking_progress = FSMBotmemeBookingProgress(slots)
            bkinfo = botmemo_booking_progress.form
            data = {
                'destination': bkinfo.get('bkinfo_area'),
                'checkin': bkinfo.get('bkinfo_checkin_time'),
                'staying': bkinfo.get('bkinfo_duration') if bkinfo.get('bkinfo_checkin_time') != bkinfo.get('bkinfo_duration') else '',
                'bed_type': bkinfo.get('bkinfo_bed_type'),
                'max_price': bkinfo.get('bkinfo_price'),
            }
            message = """
                I'm going to search for hotel room based on your information, destination: {destination}, check-in: {checkin}, staying: {staying}, bed type: {bed_type}, max price: {max_price}. It takes for a while, hold on!
            """.format(**data)

            dispatcher.utter_message(text=message)
            # dispatcher.utter_message(response='utter_inform_searching_inprogress')

        return [FollowupAction(name='botacts_search_hotel_rooms')]


class botacts_search_hotel_rooms(Action):

    def name(self) -> Text:
        return "botacts_search_hotel_rooms"

    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        BASE_URL = request_botfrontend_url('room_photos')
        events = []
        slots = tracker.slots
        channel = tracker.get_latest_input_channel()
        pagination_intent = 'user_click_to_navigate_search_result'
        notes_bkinfo = slots.get('notes_bkinfo')
        bkinfo_orderby = slots.get('bkinfo_orderby', None)
        bkinfo_area_type = slots.get('bkinfo_area_type', None)
        bkinfo_district = slots.get('bkinfo_district', None)
        bkinfo_region = slots.get('bkinfo_region', None)
        bkinfo_country = slots.get('bkinfo_country', None)
        query_payload = slots.get('search_result_query', '')
        notes_search_result = slots.get('notes_search_result', None)
        botmemo_booking_progress = FSMBotmemeBookingProgress(slots)
        bkinfo = botmemo_booking_progress.form

        web_channels = ['socketio', 'rasa', 'cwwebsite']
        telegram_channels = ['telegram', 'cwtelegram']
        fb_channels = ['facebook', 'cwfacebook']
        whatsapp_channels = ['whatsapp', 'cwwhatsapp']

        limit_num = 5 if channel in fb_channels else 2 if channel in web_channels else 1


        if bkinfo_orderby:
            page_number = 1
        elif query_payload:
            page_number, bkinfo_orderby = paginate_button_payload(payload=query_payload)

        if not bkinfo_orderby:
            bkinfo_orderby = SortbyDictionary.SORTBY_POPULARITY
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
        if notes_search_result == hashed_query:
            hotels = picklize_search_result(get_cache(notes_search_result))
            logger.info('[INFO] Retrieve hotels from redis cache, key: notes_search_result.')
        else:
            hotels = await search_rooms(
                **bkinfo,
                bkinfo_orderby=bkinfo_orderby,
                bkinfo_area_type=bkinfo_area_type,
                bkinfo_district=bkinfo_district,
                bkinfo_region=bkinfo_region,
                bkinfo_country=bkinfo_country,
            )

            if not isinstance(hotels, dict):
                error_message = '[ERROR] in botacts_search_hotel_rooms action, search_rooms returns wrong data type: %s.' % (type(hotels))
                return [
                    SlotSet('botmemo_booking_failure', 'missing_booking_info'),
                    SlotSet('logs_debugging_info', slots['logs_debugging_info'] + [error_message]),
                    FollowupAction(name='bot_let_action_emerges'),
                ]

            set_cache(hashed_query, picklize_search_result(hotels))
            events.append(SlotSet('notes_search_result', hashed_query))

            logger.info('[INFO] request to booking_service, hotels: %s', hotels.keys())

        if not hotels or len(hotels.keys()) == 0:
            dispatcher.utter_message(response="utter_room_not_available")
            dispatcher.utter_message(response="utter_asking_revise_booking_information")

        else:
            total_rooms = reduce(lambda x, y: x+y, hotels.values())
            room_num = len(total_rooms)

            # do not repeat if user keep exploring the same filter
            if page_number == 1:
                if SortbyDictionary.SORTBY_REVIEW_SCORE == bkinfo_orderby:
                    dispatcher.utter_message(response="utter_about_to_show_hotel_list_by_review_score", room_num=room_num)
                elif SortbyDictionary.SORTBY_PRICE == bkinfo_orderby:
                    dispatcher.utter_message(response="utter_about_to_show_hotel_list_by_price", room_num=room_num)
                else:
                    dispatcher.utter_message(response="utter_about_to_show_hotel_list_by_popularity", room_num=room_num)

            start, end, remains = paginate(index=page_number, limit=limit_num, total=room_num)
            logger.info('[INFO] paginating search result by index=%s, limit=%s, total=%s -> (%s, %s, %s)', page_number, limit_num, room_num, start, end, remains)

            fb_elements = []
            counter = start
            for room in total_rooms[start:end]:

                counter += 1
                room_bed_type = room.get('bed_type', {}).get('name', 'unknown')

                images = [room['hotel_photo_url']] if room.get('hotel_photo_url', None) else []
                for photo in room.get('photos', []):
                    if photo.get('url_original', None):
                        images.append(photo.get('url_original'))

                if len(images) != 0 and BASE_URL:
                    checkin_time = parse_checkin_time(expression=bkinfo.get('bkinfo_checkin_time'))
                    duration = parse_bkinfo_duration(expression=bkinfo.get('bkinfo_duration'))
                    checkin_date, checkout_date = parse_date_range(from_time=checkin_time.value, duration=duration.value, format='YYYY-MM-DD')
                    img_query = {'hoid': room['hotel_id'], 'roid': room['room_id'], 'chkin': checkin_date, 'chkout': checkout_date}
                    photos_presentation_url = BASE_URL + '?' + parse.urlencode(img_query)
                else:
                    photos_presentation_url = None

                data = {
                    'hotel_name': room['hotel_name_trans'],
                    'address': room['address_trans'],
                    'city': room['city_trans'],
                    'country': room['country_trans'],
                    'review_score': room['review_score'],
                    'nearest_beach_name': 'near ' + room['nearest_beach_name'] if room['is_beach_front'] else '',
                    'photos_url': photos_presentation_url,
                    'room_display_index': counter,
                    'room_name': room['name_without_policy'],
                    'room_bed_type': room.get('bed_type', {}).get('name', 'unknown'),
                    'room_min_price': room['min_price'],
                    'room_price_currency': room['price_currency'],
                }

                # IMPORTANT: the json format of params is very strict, use \' instead of \" will yield silently no effect
                payload = { 'room_id': room['room_id'] }
                btn_payload = "/user_click_to_select_room%s" % (json.dumps(payload))
                btn_payload = btn_payload.replace(' ', '')

                fb_buttons = []
                teleg_buttons = []

                if channel in fb_channels:

                    if photos_presentation_url:
                        fb_buttons.append({
                            'title': 'View Photos',
                            "type":"web_url",
                            'url': photos_presentation_url,
                        })

                    fb_buttons.append({
                        'title': 'Pick Room',
                        "type":"postback",
                        'payload': btn_payload,
                    })

                    fb_elements.append({
                        'title': '{room_name}, {room_bed_type}, ☝ {room_min_price:.2f} {room_price_currency}'.format(**data),
                        'subtitle': '❖ {hotel_name}  ★★★ Score: {review_score} ★★★ Address: {address}, {nearest_beach_name}'.format(**data),
                        'buttons': fb_buttons,
                    })

                    dispatcher.utter_message(elements=fb_elements, template_type="generic")

                    logger.info("[INFO] send message to facebook channel, fb_elements: %s ", fb_elements)

                elif channel in web_channels:
                    room_description = "⚑ {room_display_index}: {room_name}, {room_bed_type}, ☝ {room_min_price:.2f} {room_price_currency}." . format(**data)
                    room_photos = "To view room photos: \n{photos_url}" . format(**data)
                    hotel_description = "❖ Hotel information: {hotel_name}  ★★★ Score: {review_score} ★★★ Address: {address}, {city}, {country}, {nearest_beach_name}" . format(**data)
                    # button = { "title": 'Pick Room ⚑ {room_display_index}'.format(**data), "payload": btn_payload}
                    button = { "title": room_description, "payload": btn_payload}

                    # dispatcher.utter_message(text=room_description, buttons=[button])
                    dispatcher.utter_message(text='♫ ♫ ♫'.format(**data), buttons=[button])
                    dispatcher.utter_message(text=room_photos)
                    dispatcher.utter_message(text=hotel_description, image=room['hotel_photo_url'])

                    logger.info("[INFO] send message to web channel, hotel_description: %s", hotel_description)

                elif channel in telegram_channels or channel in whatsapp_channels:
                    hotel_description = "❖ Hotel information: {hotel_name}  ★★★ Score: {review_score} ★★★ Address: {address}, {city}, {country}, {nearest_beach_name}" . format(**data)

                    button = { "title": 'Pick Room ⚑ {room_display_index}'.format(**data), "payload": btn_payload}
                    teleg_buttons.append(button)

                    if photos_presentation_url:
                        room_description = "Room ⚑ {room_display_index}: {room_name}, {room_bed_type}, ☝ {room_min_price:.2f} {room_price_currency}. To view room photos: \n{photos_url}" . format(**data)
                    else:
                        room_description = "Room ⚑ {room_display_index}: {room_name}, {room_bed_type}, ☝ {room_min_price:.2f} {room_price_currency}" . format(**data)

                    dispatcher.utter_message(text=room_description)

                    hotel_image_url = room['hotel_photo_url']
                    r = requests.get(hotel_image_url)
                    if room.get('hotel_photo_url') and r.status_code == 200:
                        dispatcher.utter_message(text=hotel_description, image=hotel_image_url)
                    else:
                        dispatcher.utter_message(text=hotel_description)

                    logger.info("[INFO] send message to telegram/whatsapp channel, room_description: %s", room_description)

            # End of `for room in total_rooms[start:end]:`

            next_page = page_number + 1
            prev_page = page_number - 1
            query = {
                'intent': pagination_intent,
                'remains': remains,
                'limit_num': limit_num,
                'next': paginate_button_payload(page_number=next_page, bkinfo_orderby=bkinfo_orderby) if remains != 0 else None,
                'prev': paginate_button_payload(page_number=prev_page, bkinfo_orderby=bkinfo_orderby) if page_number > 1 else None,
            }
            prev_button_title = '❮❮ previous {limit_num} rooms'.format(**query)
            prev_button_payload = '/{intent}{prev}'.format(**query)
            next_button_title = '❯❯ next {remains} room(s)'.format(**query)
            next_button_payload = '/{intent}{next}'.format(**query)

            if channel in fb_channels:
                fb_buttons = []

                if query.get('prev'):
                    fb_buttons.append({'title': prev_button_title, 'payload': prev_button_payload, 'type': 'postback'})
                if query.get('next'):
                    fb_buttons.append({'title': next_button_title, 'payload': next_button_payload, 'type': 'postback'})
                dispatcher.utter_message(response="utter_instruct_to_choose_room", buttons=fb_buttons)

            elif channel in web_channels:
                buttons = []
                if query.get('prev'):
                    buttons.append({'title': prev_button_title, 'payload': prev_button_payload})
                if query.get('next'):
                    buttons.append({'title': next_button_title, 'payload': next_button_payload})
                dispatcher.utter_message(response="utter_instruct_to_choose_room", buttons=buttons)

            elif channel in telegram_channels or channel in whatsapp_channels:
                if query.get('prev'):
                    teleg_buttons.append({'title': prev_button_title, 'payload':  prev_button_payload})
                if query.get('next'):
                    teleg_buttons.append({'title': next_button_title, 'payload': next_button_payload})
                logger.info("[INFO] button: %s", teleg_buttons)
                dispatcher.utter_message(response="utter_instruct_to_choose_room", buttons=teleg_buttons, button_type='vertical')

        # End of `if len(hotels.keys()) == 0:`

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
    room_description = "Room details: {room_name}, {room_bed_type}, ☝ {room_min_price:.2f} {room_price_currency}" . format(**data)

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


class botacts_utter_bye(Action):

    def name(self) -> Text:
        return "botacts_utter_bye"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        dispatcher.utter_message(response='utter_bye')

        return [
            FollowupAction(name='action_listen'),
            AllSlotsReset(),
        ]


class botacts_start_booking_progress(Action):

    def name(self) -> Text:
        return "botacts_start_booking_progress"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        entities = tracker.latest_message['entities']
        intent = tracker.latest_message['intent']
        requested_slot = tracker.slots.get('requested_slot', None)
        mapped_slots = slots_for_entities(entities=entities, intent=intent, domain=domain, requested_slot=requested_slot)

        logger.info('[INFO] entities: %s', entities)
        logger.info('[INFO] intent: %s', intent)
        logger.info('[INFO] mapped_slots: %s', mapped_slots)

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
            # default values
            SlotSet('botmind_state', 'attentive'),
            SlotSet('botmind_intention', BOTMIND_INTENTION_DEFAULT),
            SlotSet('bkinfo_orderby', None),
            SlotSet('search_result_query', None),
            SlotSet('interlocutor_intention', INTERLOCUTOR_INTENTION_DEFAULT),
            SlotSet('bkinfo_room_id', None),
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

        additional= {'botmind_context': botmind_context, 'search_result_flag': search_result_flag}
        botmemo_booking_progress = FSMBotmemeBookingProgress(
            slots=tracker.slots,
            additional={**additional},
        )
        events = [
            SlotSet('botmind_context', botmind_context),
            botmemo_booking_progress.SlotSetEvent,
            SlotSet('botmemo_bkinfo_status', botmemo_booking_progress.bkinfo_status),
            SlotSet('search_result_flag', search_result_flag),
            # default values
            SlotSet('botmind_state', 'attentive'),
            SlotSet('botmind_intention', BOTMIND_INTENTION_DEFAULT),
            SlotSet('bkinfo_orderby', None),
            SlotSet('search_result_query', None),
            SlotSet('interlocutor_intention', INTERLOCUTOR_INTENTION_DEFAULT),
            SlotSet('bkinfo_room_id', None),
        ]

        return events


class action_botmemo_booking_progress_mapping(Action):

    def name(self) -> Text:
        return "action_botmemo_booking_progress_mapping"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        entities = tracker.latest_message['entities']
        intent = tracker.latest_message['intent']
        requested_slot = tracker.slots.get('requested_slot', None)
        mapped_slots = slots_for_entities(entities=entities, intent=intent, domain=domain, requested_slot=requested_slot)
        botmemo_booking_progress = FSMBotmemeBookingProgress(tracker.slots, additional=mapped_slots)

        logger.info('[INFO] intent: %s', intent)
        logger.info('[INFO] entities: %s', entities)
        logger.info('[INFO] mapped_slots: %s', mapped_slots)
        logger.info("[INFO] botmemo_booking_progress.form: %s", botmemo_booking_progress.form)

        if tracker.latest_action_name == 'botacts_utter_revised_bkinfo':
            return []

        return [botmemo_booking_progress.SlotSetEvent]


class action_old_slot_mapping(Action):

    def name(self) -> Text:
        return "action_old_slot_mapping"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        """
        - To trigger validate_old method which is a real mapping
        - To delegate storing data to validating phrase because  mapping phrase is not able access newly changed other slots, but validating phrase is
        """

        old_slot = tracker.slots.get('old', None)

        # to trigger validation
        memm_queue = DictUpdatingMemmQueue(data=old_slot)
        memm_queue.register(key='dummy_slot', value=random.random())

        return [SlotSet('old', memm_queue.data)]


class botacts_utter_revised_bkinfo(Action):

    def name(self) -> Text:
        return "botacts_utter_revised_bkinfo"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        events = []
        schema = FSMBotmemeBookingProgress.FORM_SCHEMA
        slots = tracker.slots
        search_result_flag = slots.get('search_result_flag')
        additional = {}

        def apply_change(slot_name, slot_name_revised, slot_value_revised):
            response = f'utter_revised_{slot_name}'
            dispatcher.utter_message(response=response)

            events.append(SlotSet(slot_name, slot_value_revised))
            events.append(SlotSet(slot_name_revised, None))
            additional[slot_name_revised] = None


        """
        Results:
            - reflex the changes to bkinfo
            - set bkinfo_district, bkinfo_region, bkinfo_country if bkinfo_area is in revision
            - reset the revised bkinfo
            - inform user
        """
        for slot_name in schema:
            slot_name_revised = f"{slot_name}_revised"
            slot_value_revised = slots.get(slot_name_revised, None)
            slot_value_current = slots.get(slot_name, None)

            if slot_name == 'bkinfo_area':
                bkinfo_area_type = slots.get('bkinfo_area_type', None)
                bkinfo_country = slots.get('bkinfo_country', None)
                bkinfo_region = slots.get('bkinfo_region', None)
                bkinfo_district = slots.get('bkinfo_district', None)
                bkinfo_area_type_revised = slots.get('bkinfo_area_type_revised', None)
                bkinfo_country_revised = slots.get('bkinfo_country_revised', None)
                bkinfo_region_revised = slots.get('bkinfo_region_revised', None)
                bkinfo_district_revised = slots.get('bkinfo_district_revised', None)

                if (slot_value_revised and
                    (
                        slot_value_revised != slot_value_current
                        or (bkinfo_area_type_revised and bkinfo_area_type_revised != bkinfo_area_type)
                        or (bkinfo_country_revised and bkinfo_country_revised != bkinfo_country)
                        or (bkinfo_region_revised and bkinfo_region_revised != bkinfo_region)
                        or (bkinfo_district_revised and bkinfo_district_revised != bkinfo_district)
                    )):
                        apply_change(slot_name=slot_name, slot_name_revised=slot_name_revised, slot_value_revised=slot_value_revised)

                        events.append(SlotSet('bkinfo_area_type', bkinfo_area_type_revised))
                        events.append(SlotSet('bkinfo_country', bkinfo_country_revised))
                        events.append(SlotSet('bkinfo_region', bkinfo_region_revised))
                        events.append(SlotSet('bkinfo_district', bkinfo_district_revised))

                        events.append(SlotSet('bkinfo_area_type_revised', None))
                        events.append(SlotSet('bkinfo_country_revised', None))
                        events.append(SlotSet('bkinfo_region_revised', None))
                        events.append(SlotSet('bkinfo_district_revised', None))

            else:
                if slot_value_revised and slot_value_revised != slot_value_current:
                    apply_change(slot_name=slot_name, slot_name_revised=slot_name_revised, slot_value_revised=slot_value_revised)

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

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        """
        The problem: to cancel out slot mapping if intent is rejected by active form
        """
        slots = tracker.slots
        botmemo_bkinfo_status = slots.get('botmemo_bkinfo_status', None)
        requested_slot = slots.get('requested_slot', None)

        if not botmemo_bkinfo_status:
            return [SlotSet('botmemo_bkinfo_status', None)]

        entities = tracker.latest_message['entities']
        intent = tracker.latest_message['intent']
        mapped_slots = slots_for_entities(entities=entities, intent=intent, domain=domain, requested_slot=requested_slot)

        logger.info('[INFO] intent: %s', intent)
        logger.info('[INFO] entities: %s', entities)
        logger.info('[INFO] mapped_slots: %s', mapped_slots)

        botmemo_booking_progress = FSMBotmemeBookingProgress(slots, additional=mapped_slots)
        slot_value = botmemo_booking_progress.bkinfo_status

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
        slots = tracker.slots
        intent = tracker.latest_message['intent']['name']
        slot_name = 'botmind_intention'

        interlocutor_intention = slots.get('interlocutor_intention')

        mind_mapped_intent = {
            None: {},
            'engage_conversation': {
                'bye': 'engage_interrogative',
                'stop_doing': 'engage_interrogative',
            },
            'terminate_session': {
                'affirm': 'engage_affirmative',
                'deny': 'engage_negative',
            },
        }

        slot_value = mind_mapped_intent.get(interlocutor_intention, {}).get(intent, BOTMIND_INTENTION_DEFAULT)

        return [SlotSet(slot_name, slot_value)]

class action_interlocutor_intention_mappings(Action):

    def name(self) -> Text:
        return "action_interlocutor_intention_mappings"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        IGNORED_INTENTS = [
            'bot_embodies_intention'
        ]

        intent = tracker.latest_message['intent']['name']
        slot_name = 'interlocutor_intention'
        default_intention = 'engage_conversation'

        if intent in IGNORED_INTENTS:
            logger.info('[INFO] skip mapping due to intent: %s', intent)
            return []

        secondary_intention_mapping = {
            'bye': 'terminate_session',
            'stop_doing': 'terminate_session',
        }

        slot_value = secondary_intention_mapping.get(intent, default_intention)

        return [SlotSet(slot_name, slot_value)]

