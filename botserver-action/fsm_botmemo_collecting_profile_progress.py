import logging

from rasa_sdk.events import SlotSet

from .slot_default_values import BOTMIND_CONTEXT_DEFAULT

logger = logging.getLogger(__name__)


class FSMBotmemoCollectingProfileProgress():
    """
        State transitioning rules for collecting profile
    """
    revising_suffix = '_revised'

    STATES = (
        None,                           # 0
        'initialized',                  # 1 initialized
        'information_collecting',       # 2 inprogress
        'done_information_collecting',  # 3 ready
        'showing_result',                 # 4 showing
        'entity_selected',                # 5 done
        'information_revised',          # 6 revised
    )

    FORM_SCHEMA = (
        'profileinfo_phone_number',
        'profileinfo_user_name',
        'profileinfo_user_age',
        'profileinfo_degree_type',
        'profileinfo_job_title',
        'profileinfo_experience_year',
        'profileinfo_experience_industry',
        'profileinfo_experience_oversea',
    )

    # stimuli signal
    _STI_SIGNAL = [
        "botmind_context",
        "search_result_flag",
        "entity_id",
    ]
    _STI_SIGNAL = _STI_SIGNAL + [field for field in FORM_SCHEMA]
    for field in FORM_SCHEMA:
        _STI_SIGNAL.append(field + revising_suffix)

    _ASSOCIATIVE_MEM = 'botmemo_collecting_profile_progress'

    search_result_flag__waiting__ = 'waiting'
    search_result_flag__updating__ = 'updating'
    search_result_flag__available__ = 'available'

    class Validator():

        def validate(self, field_name, value):
            validating_func = self.get_validating_func(field_name)
            return validating_func(value)

        def default_validating_func(self, field):
            return True

        def get_validating_func(self, field_name):
            func = getattr(self, f'validate_{field_name}', None)

            if func:
                return func

            return getattr(self, 'default_validating_func')


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
            if value and not self.validator.validate(field, value):
                form[field] = None
            else:
                form[field] = value

        return form

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
        return self.slots.get('botmind_context') == BOTMIND_CONTEXT_DEFAULT or self.slots.get('search_result_flag') is None

    def checkif_inintialized(self):
        return all([not v for v in self.form.values()])

    def checkif_inprogress(self):
        return not self.is_form_completed() and not self.is_form_revised()

    def checkif_ready(self):
        return self.is_form_completed()

    def checkif_showing(self):
        return self.slots.get('search_result_flag') == self.search_result_flag__available__

    def checkif_done(self):
        return self.slots.get('entity_id')

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
    def info_statuses(self):
        return list(self.form.values())
