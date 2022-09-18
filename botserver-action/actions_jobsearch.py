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

from .fsm_botmemo_collecting_profile_progress import FSMBotmemoCollectingProfileProgress
from .slot_default_values import BOTMIND_INTENTION_DEFAULT


logger = logging.getLogger(__name__)

job_data = [
    {
        'title': 'Plumbing Supervisor',
        'description': 'supervisor, supervisor, supervisor, supervisor, supervisor.',
        'salary': '300000 Rupee',
        'food': 'lunch',
        'accommodation': 'yes',
        'expense': 'no',
        'code': 'JOB01',
    },
    {
        'title': 'Plumber',
        'description': 'plumber plumber plumber plumber plumber plumber plumber',
        'salary': '200000 Rupee',
        'food': 'lunch',
        'accommodation': 'yes',
        'expense': 'no',
        'code': 'JOB02',
    },
    {
        'title': 'Senior Plumber',
        'description': 'senior senior senior senior senior senior senior senior',
        'salary': '100000 Rupee',
        'food': 'lunch',
        'accommodation': 'yes',
        'expense': 'no',
        'code': 'JOB03',
    },
]


class botacts_initialize_profile_collecting(Action):

    def name(self) -> Text:
        return "botacts_initialize_profile_collecting"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        dispatcher.utter_message(response="utter_greet")
        dispatcher.utter_message(response="utter_introduction")

        BOTMIND_CONTEXT = 'workingonjobsearch'
        SEARCH_RESULT_FLAG = 'waiting'
        INTERLOCUTOR_INTENTION = 'engage_conversation'
        intent = tracker.latest_message['intent']['name']

        additional= {'botmind_context': BOTMIND_CONTEXT, 'search_result_flag': SEARCH_RESULT_FLAG}
        botmemo_collecting_info_progress = FSMBotmemoCollectingProfileProgress(
            slots=tracker.slots,
            additional={**additional},
        )
        events = [
            SlotSet('botmind_context', BOTMIND_CONTEXT),
            botmemo_collecting_info_progress.SlotSetEvent,
            SlotSet('botmemo_profileinfo_status', botmemo_collecting_info_progress.info_statuses),
            SlotSet('search_result_flag', SEARCH_RESULT_FLAG),
            # default values
            SlotSet('botmind_state', 'attentive'),
            SlotSet('botmind_intention', BOTMIND_INTENTION_DEFAULT),
            SlotSet('interlocutor_intention', INTERLOCUTOR_INTENTION),
            SlotSet('jobinfo_id', None),
        ]

        return events


class botacts_utter_inform_searching_inprogress(Action):

    def name(self) -> Text:
        return "botacts_utter_inform_searching_inprogress"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        dispatcher.utter_message(text="I'm searching, please wait...")

        return [FollowupAction(name='botacts_search_job')]


class botacts_search_job(Action):

    def name(self) -> Text:
        return "botacts_search_job"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        slots = tracker.slots
        events = []
        found = random.randrange(0, 2, 1) == 1
        profileinfo_user_name = slots.get('profileinfo_user_name')

        found = True
        if not found:
            message = f"""
Thank you {profileinfo_user_name} for providing us your information.
Currently we don’t have jobs matching your experience.
We have saved your information and we will get back to you as soon as there is a job opening matching your experience.
Do you want to apply for any other job or want to check our current job openings?
"""
            dispatcher.utter_message(text=message)

        else:
            dispatcher.utter_message(text=f"Thank you {profileinfo_user_name} for providing us your info. We have some relevant jobs:")

            for job in job_data:
                message = """
Title: {title}
Description: {description}
Salary: {salary}
Food: {food}
Accommodation: {accommodation}
Expense: {expense}
Code: {code}
"""
                payload = { 'entity_id': job['code'] }
                btn_payload = "/user_selects_entity%s" % (json.dumps(payload))
                btn_payload = btn_payload.replace(' ', '')
                button = { "title": job['title'], "payload": btn_payload}
                dispatcher.utter_message(text=message.format(**job), buttons=[button])

            search_result_flag = 'available'
            botmemo_booking_progress = FSMBotmemoCollectingProfileProgress(slots, additional={'search_result_flag': search_result_flag})
            events.append(botmemo_booking_progress.SlotSetEvent)
            events.append(SlotSet('search_result_flag', search_result_flag))

            events.append(FollowupAction('action_listen'))

        return events


class botacts_confirm_job_selection(Action):

    def name(self) -> Text:
        return "botacts_confirm_job_selection"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        entities = tracker.latest_message['entities']
        logger.error('[DEBUG] entities: %s', entities)

        return []


class botacts_utter_asking_confirm_stop_searching_job(Action):

    def name(self) -> Text:
        return "botacts_utter_asking_confirm_stop_searching_job"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        botmemo_collecting_info_progress = tracker.slots.get('botmemo_collecting_profile_progress')
        not_working_conditions = [None, 'initialized']

        if botmemo_collecting_info_progress in not_working_conditions:
            return [FollowupAction(name='botacts_utter_bye')]

        dispatcher.utter_message(response='utter_asking_confirm_stop_job_search')

        return []
