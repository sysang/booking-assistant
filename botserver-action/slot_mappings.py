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


from .utils import slots_for_entities
from .fsm_botmemo_collecting_profile_progress import FSMBotmemoCollectingProfileProgress

logger = logging.getLogger(__name__)


class BaseInfoStatusSlotMapping(Action):

    def name(self):
        return 'BaseInfoStatusSlotMapping'

    def _fsm(self, slots, additional={}):
        raise NotImplementedError('FSM must be instantiated')

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        """
        The problem: to cancel out slot mapping if intent is rejected by active form
        """
        slots = tracker.slots
        slot_name = self._slot_name()
        botmemo_info_status = slots.get(slot_name)
        requested_slot = slots.get('requested_slot')

        if not botmemo_info_status:
            return [SlotSet(slot_name, None)]

        entities = tracker.latest_message['entities']
        intent = tracker.latest_message['intent']
        mapped_slots = slots_for_entities(
            entities=entities,
            intent=intent,
            domain=domain,
            requested_slot=requested_slot,
        )

        logger.info('[INFO] intent: %s', intent)
        logger.info('[INFO] entities: %s', entities)
        logger.info('[INFO] mapped_slots: %s', mapped_slots)

        botmemo_info_progress = self._fsm(slots=slots, additional=mapped_slots)
        slot_value = botmemo_info_progress.info_statuses

        return [SlotSet(slot_name, slot_value)]


class botmemo_profile_status_slot_mapping(BaseInfoStatusSlotMapping):

    def name(self) -> Text:
        return "botmemo_profile_status_slot_mapping"

    def _slot_name(self):
        return 'botmemo_profileinfo_status'

    def _fsm(self, slots, additional={}):
        return FSMBotmemoCollectingProfileProgress(slots=slots, additional=additional)


class BaseBotmemeCollectingInfoProgressMapping(Action):

    def name(self) -> Text:
        return "BaseBotmemeCollectingInfoProgressMapping"

    def _revising_actions(self):
        return [
            'botacts_utter_revised_bkinfo',
        ]

    def _fsm(self, slots, additional={}):
        raise NotImplementedError('FSM must be instantiated')

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        slots = tracker.slots
        entities = tracker.latest_message['entities']
        intent = tracker.latest_message['intent']
        requested_slot = slots.get('requested_slot', None)
        mapped_slots = slots_for_entities(entities=entities, intent=intent, domain=domain, requested_slot=requested_slot)
        botmemo_info_progress = self._fsm(slots=slots, additional=mapped_slots)

        logger.info('[INFO] intent: %s', intent)
        logger.info('[INFO] entities: %s', entities)
        logger.info('[INFO] mapped_slots: %s', mapped_slots)
        logger.info("[INFO] botmemo_info_progress.form: %s", botmemo_info_progress.form)

        # To work around the problem that cancels out all SlotSet events of actions
        revising_actions = self._revising_actions()
        if tracker.latest_action_name in revising_actions:
            return []

        return [botmemo_info_progress.SlotSetEvent]


class botmemo_collecting_profile_progress_mapping(BaseBotmemeCollectingInfoProgressMapping):

    def name(self) -> Text:
        return "botmemo_collecting_profile_progress_mapping"

    def _fsm(self, slots, additional={}):
        return FSMBotmemoCollectingProfileProgress(slots=slots, additional=additional)
