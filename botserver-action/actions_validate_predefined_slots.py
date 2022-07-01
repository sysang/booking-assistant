import logging
from typing import Any, Dict, List, Text, Optional, Tuple

import arrow

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.forms import ValidationAction
from rasa_sdk.types import DomainDict

from .duckling_service import (
    parse_checkin_time,
    parse_bkinfo_duration,
    parse_bkinfo_price,
)


logger = logging.getLogger(__name__)

class ValidatePredefinedSlots(ValidationAction):

    def old_slot_value(self, tracker, slot_name):
        slots = tracker.slots.get('old', {})
        return slots.get(slot_name, None)

    def if_changed_by_botacts_utter_revised_bkinfo(self, tracker):
        return tracker.latest_action_name == 'botacts_utter_revised_bkinfo'

    def validate_bkinfo_area_revised(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,) -> Dict[Text, Any]:

        slot_name = 'bkinfo_area_revised'

        if self.if_changed_by_botacts_utter_revised_bkinfo(tracker):
            return {slot_name: None}

        return {slot_name: slot_value}


    def validate_bkinfo_checkin_time_revised(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,) -> Dict[Text, Any]:

        slot_name = 'bkinfo_checkin_time_revised'
        result = parse_checkin_time(expression=slot_value)

        if self.if_changed_by_botacts_utter_revised_bkinfo(tracker):
            return {slot_name: None}

        if result.if_error('failed'):
            dispatcher.utter_message(response='utter_inform_invalid_info')
            return {slot_name: None}

        if result.if_error('invalid_checkin_time'):
            dispatcher.utter_message(response='utter_ask_valid_bkinfo_checkin_time')
            return {slot_name: self.old_slot_value(tracker, slot_name)}

        return {slot_name: slot_value}

    def validate_bkinfo_duration_revised(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,) -> Dict[Text, Any]:

        slot_name = 'bkinfo_duration_revised'

        if self.if_changed_by_botacts_utter_revised_bkinfo(tracker):
            return {slot_name: None}

        result = parse_bkinfo_duration(expression=slot_value)

        if result.if_error('failed'):
            dispatcher.utter_message(response='utter_inform_invalid_info')
            return {slot_name: self.old_slot_value(tracker, slot_name)}

        if result.if_error('invalid_bkinfo_duration'):
            dispatcher.utter_message(response='utter_ask_valid_bkinfo_duration')
            return {slot_name: None}

        return {slot_name: slot_value}

    def validate_bkinfo_bed_type_revised(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,) -> Dict[Text, Any]:

        slot_name = 'bkinfo_bed_type_revised'

        if self.if_changed_by_botacts_utter_revised_bkinfo(tracker):
            return {slot_name: None}

        return {slot_name: slot_value}

    def validate_bkinfo_price_revised(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,) -> Dict[Text, Any]:

        slot_name = 'bkinfo_price_revised'

        if self.if_changed_by_botacts_utter_revised_bkinfo(tracker):
            return {slot_name: None}

        result = parse_bkinfo_price(expression=slot_value)

        if result.if_error('failed'):
            dispatcher.utter_message(response='utter_ask_valid_bkinfo_price')
            return {slot_name: None}

        return {slot_name: slot_value}
