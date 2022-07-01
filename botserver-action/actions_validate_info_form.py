import logging
from typing import Any, Dict, List, Text, Optional, Tuple

import arrow

from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.forms import ValidationAction, FormValidationAction
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from .duckling_service import (
    parse_checkin_time,
    parse_bkinfo_duration,
    parse_bkinfo_price,
)

from .utils import slots_for_entities

logger = logging.getLogger(__name__)


class ValidateBkinfoForm(FormValidationAction):

    def name(self) -> Text:
        return "validate_bkinfo_form"

    def slots_for_entities(self, entities: List[Dict[Text, Any]], domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return slots_for_entities(entities, domain)

    def old_slot_value(self, tracker, slot_name):
        slots = tracker.slots.get('old', {})
        return slots.get(slot_name, None)

    def is_slot_requested(self, tracker, slot_name):
        return tracker.slots.get('requested_slot', None) == slot_name

    def utter_if_revised_bkinfo(self, tracker, dispatcher, domain, slot_name):

        entities = tracker.latest_message['entities']
        intent = tracker.latest_message['intent']
        mapped_slots = self.slots_for_entities(entities, domain)

        if intent['name'] == 'nlu_fallback':
            return True

        if self.is_slot_requested(tracker, slot_name):
            return True

        if slot_name not in mapped_slots.keys():
            return True

        response = f"utter_revised_{slot_name}"
        dispatcher.utter_message(response=response)

    def validate_bkinfo_area(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,) -> Dict[Text, Any]:

        slot_name = 'bkinfo_area'

        # self.utter_if_revised_bkinfo(
        #     dispatcher=dispatcher,
        #     tracker=tracker,
        #     domain=domain,
        #     slot_name=slot_name,
        # )

        return {}


    def validate_bkinfo_checkin_time(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,) -> Dict[Text, Any]:

        slot_name = 'bkinfo_checkin_time'
        result = parse_checkin_time(expression=slot_value)

        logger.info('[DEV] parsing %s slot_value, result: %s', slot_value, result)

        if result.if_error('failed'):
            dispatcher.utter_message(response='utter_inform_invalid_info')
            return {slot_name: self.old_slot_value(tracker, slot_name)}

        if result.if_error('invalid_checkin_time'):
            dispatcher.utter_message(response='utter_ask_valid_bkinfo_checkin_time')
            return {slot_name: self.old_slot_value(tracker, slot_name)}

        return {}

    def validate_bkinfo_duration(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,) -> Dict[Text, Any]:

        slot_name = 'bkinfo_duration'
        result = parse_bkinfo_duration(expression=slot_value)

        if result.if_error('failed'):
            dispatcher.utter_message(response='utter_inform_invalid_info')
            return {slot_name: self.old_slot_value(tracker, slot_name)}

        if result.if_error('invalid_bkinfo_duration'):
            dispatcher.utter_message(response='utter_ask_valid_bkinfo_duration')
            return {slot_name: self.old_slot_value(tracker, slot_name)}

        return {}

    def validate_bkinfo_bed_type(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,) -> Dict[Text, Any]:

        slot_name = 'bkinfo_bed_type'

        return {}

    def validate_bkinfo_price(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,) -> Dict[Text, Any]:

        slot_name = 'bkinfo_price'
        result = parse_bkinfo_price(expression=slot_value)

        if result.if_error('failed'):
            dispatcher.utter_message(response='utter_ask_valid_bkinfo_price')
            return {slot_name: self.old_slot_value(tracker, slot_name)}

        return {}
