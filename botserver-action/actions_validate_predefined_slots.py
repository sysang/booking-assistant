import logging
from typing import Any, Dict, List, Text, Optional, Tuple

import arrow

from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.forms import ValidationAction
from rasa_sdk import Action, Tracker
from rasa_sdk.forms import ValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from .duckling_service import (
    parse_checkin_time,
    parse_bkinfo_duration,
    parse_bkinfo_price,
)


logger = logging.getLogger(__name__)


class ValidatePredefinedSlots(ValidationAction):

    def validate_bkinfo_checkin_time(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,) -> Dict[Text, Any]:

        result = parse_checkin_time(expression=slot_value)

        if result.if_error('failed'):
            dispatcher.utter_message(response='utter_inform_invalid_info')
            return {'bkinfo_checkin_time': None}

        if result.if_error('invalid_checkin_time'):
            dispatcher.utter_message(response='utter_ask_valid_bkinfo_checkin_time')
            return {'bkinfo_checkin_time': None}

        return {'bkinfo_checkin_time': result.value}

    def validate_bkinfo_duration(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,) -> Dict[Text, Any]:

        result = parse_bkinfo_duration(expression=slot_value)

        if result.if_error('failed'):
            dispatcher.utter_message(response='utter_inform_invalid_info')
            return {'bkinfo_duration': None}

        if result.if_error('invalid_bkinfo_duration'):
            dispatcher.utter_message(response='utter_ask_valid_bkinfo_checkin_time')
            return {'bkinfo_duration': None}

        return {'bkinfo_duration': result.value}

    def validate_bkinfo_price(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,) -> Dict[Text, Any]:

        result = parse_bkinfo_price(expression=slot_value)

        if result.if_error('failed'):
            dispatcher.utter_message(response='utter_inform_invalid_info')
            return {'bkinfo_price': None}

        return {'bkinfo_price': result.value}
