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
from .booking_service import choose_location

from .utils import calc_time_distance_in_days
from .utils import SUSPICIOUS_CHECKIN_DISTANCE
from .utils import DictUpdatingMemmQueue

logger = logging.getLogger(__name__)


class ValidateBkinfoForm(FormValidationAction):

    def name(self) -> Text:
        return "validate_bkinfo_form"

    def old_slot_value(self, tracker, slot_name):
        old_slot = tracker.slots.get('old', None)
        if not old_slot:
            return None

        return DictUpdatingMemmQueue(data=old_slot).retrieve(key=slot_name)

    def is_new(self, tracker, slot_name, slot_value):
        old_value = self.old_slot_value(tracker, slot_name)
        logger.info('[INFO] check if slot changed: old_value: %s, slot_value: %s', old_value, slot_value)
        return old_value is None or slot_value != old_value

    def is_slot_requested(self, tracker, slot_name):
        return tracker.slots.get('requested_slot', None) == slot_name

    def validate_bkinfo_area(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,) -> Dict[Text, Any]:

        slot_name = 'bkinfo_area'

        slots = tracker.slots
        destination = choose_location(
            bkinfo_area=slot_value, bkinfo_area_type=slots.get('bkinfo_area_type'), bkinfo_district=slots.get('bkinfo_district'),
            bkinfo_region=slots.get('bkinfo_region'), bkinfo_country=slots.get('bkinfo_country'),
        )
        if not destination:
            dispatcher.utter_message(response='utter_ask_valid_bkinfo_area')
            return {slot_name: None}

        if self.is_new(tracker, slot_name, slot_value):
            dest_label = destination.get('label', None)
            # TODO: verify if request to image_url gets 200, otherwise we're in horrible trouble by telegram
            image_url = destination.get('image_url', None)
            if dest_label and image_url:
                dispatcher.utter_message(response='utter_confirm_bkinfo_area', image=image_url, dest_label=dest_label)

            return {slot_name: slot_value}


    def validate_bkinfo_checkin_time(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,) -> Dict[Text, Any]:

        slot_name = 'bkinfo_checkin_time'
        result = parse_checkin_time(expression=slot_value)

        if result.if_error('failed'):
            dispatcher.utter_message(response='utter_ask_rephrase_checkin_time')
            return {slot_name: None}

        if result.if_error('invalid_checkin_time'):
            dispatcher.utter_message(response='utter_ask_valid_bkinfo_checkin_time')
            return {slot_name: None}

        # detect change in checkin_time, only issue alert after a new change
        old_bkinfo_checkin_time = self.old_slot_value(tracker=tracker, slot_name=slot_name)
        if old_bkinfo_checkin_time != slot_value:
            distance = calc_time_distance_in_days(result.value)
            if distance > SUSPICIOUS_CHECKIN_DISTANCE:
                dispatcher.utter_message(response='utter_aware_checkin_date', checkin_distance=distance)

        return {slot_name: slot_value}

    def validate_bkinfo_duration(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,) -> Dict[Text, Any]:

        slot_name = 'bkinfo_duration'
        result = parse_bkinfo_duration(expression=slot_value)

        if result.if_error('failed'):
            dispatcher.utter_message(response='utter_ask_rephrase_duration')
            return {slot_name: None}

        if result.if_error('invalid_bkinfo_duration'):
            dispatcher.utter_message(response='utter_ask_valid_bkinfo_duration')
            return {slot_name: None}

        current_slot = {slot_name: slot_value}

        """
         'time', 'duration' are entity, duration is mapped to bkinfo_checkin_time when:
         + text -> alike 'from exp1 to exp2'
         + text -> request_checkin_time+request_room_reservation_duration
        """
        entities = [ entity['entity'] for entity in tracker.latest_message['entities'] ]
        if 'time' not in entities and result.value_type == 'interval':
            extension_slot = self.validate_bkinfo_checkin_time(
                slot_value=slot_value,
                dispatcher=dispatcher,
                tracker=tracker,
                domain=domain,
            )

            # TODO: be cautious at this hacking -> using validation of one field to manipulate value's other field
            return {**current_slot, **extension_slot}

        return current_slot

    def validate_bkinfo_bed_type(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,) -> Dict[Text, Any]:

        slot_name = 'bkinfo_bed_type'

        return {slot_name: slot_value}

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
            return {slot_name: None}

        return {slot_name: slot_value}
