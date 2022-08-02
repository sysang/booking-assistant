import logging

from rasa_sdk.events import SlotSet

from .duckling_service import (
    parse_checkin_time,
    parse_bkinfo_duration,
    parse_bkinfo_price,
)

from .service import query_available_rooms, query_room_by_id
from .data_struture import BookingInfo

logger = logging.getLogger(__name__)


class FSMBotmemeBookingProgress():
    """
        State transitioning rules for botmemo_booking_progress
        Signals:
            - bkinfo_area
            - bkinfo_checkin_time
            - bkinfo_duration
            - bkinfo_bed_type
            - bkinfo_room_id
    """
    revising_suffix = '_revised'

    STATES = (
        None,                           # 0
        'initialized',                  # 1 initialized
        'information_collecting',       # 2 inprogress
        'done_information_collecting',  # 3 ready
        'room_showing',                 # 4 showing
        'room_selected',                # 5 done
        'information_revised',          # 6 revised
    )

    # stimuli signal
    _STI_SIGNAL = {
        "bkinfo_area",
        "bkinfo_checkin_time",
        "bkinfo_duration",
        "bkinfo_bed_type",
        'bkinfo_price',
        "bkinfo_area" + revising_suffix,
        "bkinfo_checkin_time" + revising_suffix,
        "bkinfo_duration" + revising_suffix,
        "bkinfo_bed_type" + revising_suffix,
        'bkinfo_price' + revising_suffix,
        "bkinfo_room_id",
        "botmind_context",
        "search_result_flag",
    }

    FORM_SCHEMA = (
        'bkinfo_area',
        'bkinfo_checkin_time',
        'bkinfo_duration',
        'bkinfo_bed_type',
        'bkinfo_price',
    )

    _ASSOCIATIVE_MEM = 'botmemo_booking_progress'

    search_result_flag__waiting__ = 'waiting'
    search_result_flag__updating__ = 'updating'
    search_result_flag__available__ = 'available'

    class Validator():

        def default_validating_func(self, field):
            return True

        def validate_bkinfo_checkin_time(self, value):
            result = parse_checkin_time(expression=value)
            return result.is_valid()

        def validate_bkinfo_duration(self, value):
            result = parse_bkinfo_duration(expression=value)
            return result.is_valid()

        def validate_bkinfo_price(self, value):
            result = parse_bkinfo_price(expression=value)
            return result.is_valid()


    def __init__(self, slots, additional={}, validator=None):

        self.state = slots.get(self._ASSOCIATIVE_MEM)

        _slots = slots.copy()
        _slots = { prop:_slots.get(prop, None) for prop in self._STI_SIGNAL }
        self.slots = {**_slots, **additional}

        self.validator = validator if validator else self.Validator()
        self.form = self.bind_value()

    def bind_value(self):
        form = {}
        for field in self.FORM_SCHEMA:
            value = self.slots[field]
            validating_func = self.get_validating_func(field)
            if value and not validating_func(value):
                form[field] = None
            else:
                form[field] = value

        return form

    def get_validating_func(self, field):
        func = getattr(self.validator, f'validate_{field}', None)

        if func:
            return func

        return getattr(self.validator, 'default_validating_func')

    def is_form_completed(self):
        return all(self.form.values())

    def is_form_revised(self):
        revised = []
        for field in self.FORM_SCHEMA:
            field_revised = field + self.revising_suffix
            value = self.slots.get(field_revised)
            revised.append(value)

        return any(revised)

    def checkif_none(self):
        return self.slots.get('botmind_context') != 'workingonbooking' or self.slots.get('search_result_flag') is None

    def checkif_inintialized(self):
        return all([not v for v in self.form.values()])

    def checkif_inprogress(self):
        return not self.is_form_completed() and not self.is_form_revised()

    def checkif_ready(self):
        return self.is_form_completed()

    def checkif_showing(self):
        return self.slots.get('search_result_flag') == self.search_result_flag__available__

    def checkif_done(self):
        return self.slots.get('bkinfo_room_id')

    def checkif_revised(self):
        return self.is_form_revised()

    @property
    def SlotSetEvent(self):
        return SlotSet(self._ASSOCIATIVE_MEM, self.next_state)

    @property
    def next_state(self):
        if self.checkif_none():
            return self.STATES[0]
        if self.checkif_inintialized():
            return self.STATES[1]
        if self.checkif_inprogress():
            return self.STATES[2]
        if self.checkif_revised():
            return self.STATES[6]
        if self.checkif_done():
            return self.STATES[5]
        if self.checkif_showing():
            return self.STATES[4]

        # ready <- fallback state
        return self.STATES[3]

    @property
    def bkinfo_status(self):
        return list(self.form.values())


def eval_test():
    class DummyValidator():
        def default_validating_func(self, field):
            return True

    def execute(slots, expected, index):
        uit = FSMBotmemeBookingProgress(slots, validator=DummyValidator())
        next_state = uit.next_state
        assert next_state == expected, f"({index})(T) Incorrect next_state: {next_state}"
        print(f' ({index})(T)\t next_state must be {expected}')


    INDEX = 1
    slots = {
        "bkinfo_area": True,
        "bkinfo_checkin_time": True,
        "bkinfo_duration": True,
        "bkinfo_bed_type": True,
        'bkinfo_price': True,
        "bkinfo_area_revised": True,
        "bkinfo_checkin_time_revised": True,
        "bkinfo_duration_revised": True,
        "bkinfo_bed_type_revised": True,
        'bkinfo_price_revised': True,
        "bkinfo_room_id": 1,
        "botmind_context": 'chitchat',
        "search_result_flag": None,
    }
    expected = None
    execute(slots=slots, expected=expected, index=INDEX)

    INDEX = 2
    slots = {
        "bkinfo_area": True,
        "bkinfo_checkin_time": True,
        "bkinfo_duration": True,
        "bkinfo_bed_type": True,
        'bkinfo_price': True,
        "bkinfo_area_revised": True,
        "bkinfo_checkin_time_revised": True,
        "bkinfo_duration_revised": True,
        "bkinfo_bed_type_revised": True,
        'bkinfo_price_revised': True,
        "bkinfo_room_id": 1,
        "botmind_context": 'chitchat',
        "search_result_flag": 'waiting',
    }
    expected = None
    execute(slots=slots, expected=expected, index=INDEX)

    INDEX = 3
    slots = {
        "bkinfo_area": None,
        "bkinfo_checkin_time": None,
        "bkinfo_duration": None,
        "bkinfo_bed_type": None,
        'bkinfo_price': None,
        "bkinfo_area_revised": True,
        "bkinfo_checkin_time_revised": True,
        "bkinfo_duration_revised": True,
        "bkinfo_bed_type_revised": True,
        'bkinfo_price_revised': True,
        "bkinfo_room_id": 1,
        "botmind_context": 'workingonbooking',
        "search_result_flag": 'waiting',
    }
    expected = 'initialized'
    execute(slots=slots, expected=expected, index=INDEX)

    INDEX = 4
    slots = {
        "bkinfo_area": 'test',
        "bkinfo_checkin_time": 'test',
        "bkinfo_duration": 'test',
        "bkinfo_bed_type": 'test',
        'bkinfo_price': None,
        "bkinfo_area_revised": None,
        "bkinfo_checkin_time_revised": None,
        "bkinfo_duration_revised": None,
        "bkinfo_bed_type_revised": None,
        'bkinfo_price_revised': None,
        "bkinfo_room_id": 1,
        "botmind_context": 'workingonbooking',
        "search_result_flag": 'available',
    }
    expected = 'information_collecting'
    execute(slots=slots, expected=expected, index=INDEX)

    INDEX = 5
    slots = {
        "bkinfo_area": None,
        "bkinfo_checkin_time": 'test',
        "bkinfo_duration": None,
        "bkinfo_bed_type": None,
        'bkinfo_price': None,
        "bkinfo_area_revised": None,
        "bkinfo_checkin_time_revised": None,
        "bkinfo_duration_revised": None,
        "bkinfo_bed_type_revised": None,
        'bkinfo_price_revised': None,
        "bkinfo_room_id": 1,
        "botmind_context": 'workingonbooking',
        "search_result_flag": 'available',
    }
    expected = 'information_collecting'
    execute(slots=slots, expected=expected, index=INDEX)

    INDEX = 6
    slots = {
        "bkinfo_area": 'test',
        "bkinfo_checkin_time": 'test',
        "bkinfo_duration": 'test',
        "bkinfo_bed_type": 'test',
        'bkinfo_price': 'test',
        "bkinfo_area_revised": True,
        "bkinfo_checkin_time_revised": None,
        "bkinfo_duration_revised": None,
        "bkinfo_bed_type_revised": None,
        'bkinfo_price_revised': None,
        "bkinfo_room_id": 1,
        "botmind_context": 'workingonbooking',
        "search_result_flag": 'available',
    }
    expected = 'information_revised'
    execute(slots=slots, expected=expected, index=INDEX)

    INDEX = 7
    slots = {
        "bkinfo_area": None,
        "bkinfo_checkin_time": 'test',
        "bkinfo_duration": None,
        "bkinfo_bed_type": None,
        'bkinfo_price': None,
        "bkinfo_area_revised": None,
        "bkinfo_checkin_time_revised": None,
        "bkinfo_duration_revised": None,
        "bkinfo_bed_type_revised": None,
        'bkinfo_price_revised': True,
        "bkinfo_room_id": 1,
        "botmind_context": 'workingonbooking',
        "search_result_flag": 'available',
    }
    expected = 'information_revised'
    execute(slots=slots, expected=expected, index=INDEX)

    INDEX = 8
    slots = {
        "bkinfo_area": 'test',
        "bkinfo_checkin_time": 'test',
        "bkinfo_duration": 'test',
        "bkinfo_bed_type": 'test',
        'bkinfo_price': 'test',
        "bkinfo_area_revised": None,
        "bkinfo_checkin_time_revised": None,
        "bkinfo_duration_revised": None,
        "bkinfo_bed_type_revised": None,
        'bkinfo_price_revised': None,
        "bkinfo_room_id": 1,
        "botmind_context": 'workingonbooking',
        "search_result_flag": 'available',
    }
    expected = 'room_selected'
    execute(slots=slots, expected=expected, index=INDEX)

    INDEX = 9
    slots = {
        "bkinfo_area": 'test',
        "bkinfo_checkin_time": 'test',
        "bkinfo_duration": 'test',
        "bkinfo_bed_type": 'test',
        'bkinfo_price': 'test',
        "bkinfo_area_revised": None,
        "bkinfo_checkin_time_revised": None,
        "bkinfo_duration_revised": None,
        "bkinfo_bed_type_revised": None,
        'bkinfo_price_revised': None,
        "bkinfo_room_id": None,
        "botmind_context": 'workingonbooking',
        "search_result_flag": 'available',
    }
    expected = 'room_showing'
    execute(slots=slots, expected=expected, index=INDEX)

    INDEX = 10
    slots = {
        "bkinfo_area": 'test',
        "bkinfo_checkin_time": 'test',
        "bkinfo_duration": 'test',
        "bkinfo_bed_type": 'test',
        'bkinfo_price': 'test',
        "bkinfo_area_revised": None,
        "bkinfo_checkin_time_revised": None,
        "bkinfo_duration_revised": None,
        "bkinfo_bed_type_revised": None,
        'bkinfo_price_revised': None,
        "bkinfo_room_id": None,
        "botmind_context": 'workingonbooking',
        "search_result_flag": 'waiting',
    }
    expected = 'done_information_collecting'
    execute(slots=slots, expected=expected, index=INDEX)

    INDEX = 11
    slots = {
        "bkinfo_area": 'test',
        "bkinfo_checkin_time": 'test',
        "bkinfo_duration": 'test',
        "bkinfo_bed_type": 'test',
        'bkinfo_price': 'test',
        "bkinfo_area_revised": None,
        "bkinfo_checkin_time_revised": None,
        "bkinfo_duration_revised": None,
        "bkinfo_bed_type_revised": None,
        'bkinfo_price_revised': None,
        "bkinfo_room_id": None,
        "botmind_context": 'workingonbooking',
        "search_result_flag": 'updating',
    }
    expected = 'done_information_collecting'
    execute(slots=slots, expected=expected, index=INDEX)

    print('*** Finished ***')
