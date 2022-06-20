import logging

from .service import duckling_parse, query_available_rooms, query_room_by_id
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
    _STATES = (
        None,                           # 0
        'initialized',                  # 1 initialized
        'information_collecting',       # 2 inprogress
        'done_information_collecting',  # 3 ready
        'room_showing',                 # 4 showing
        'room_selected',                # 5 done
    )

    # stimuli signal
    _STI_SIGNAL = {
        "bkinfo_area",
        "bkinfo_checkin_time",
        "bkinfo_duration",
        "bkinfo_bed_type",
        "bkinfo_room_id",
        "botmind_context",
        "search_result_flag",
    }

    _ASSOCIATIVE_MEM = 'botmemo_booking_progress'

    def __init__(self, slots, additional={}):

        self.state = slots.get(self._ASSOCIATIVE_MEM)

        _slots = slots.copy()
        _slots = { prop:_slots.get(prop, None) for prop in self._STI_SIGNAL }
        self.slots = {**_slots, **additional}
        self.form = BookingInfo(slots=self.slots)

    def checkif_none(self):
        return self.slots['botmind_context'] != 'workingonbooking'

    def checkif_inintialized(self):
        return all([not v for v in self.form.values()])

    def checkif_inprogress(self):
        return any(self.form.value())

    def checkif_ready(self):
        return self.form.is_completed()

    def checkif_showing(self):
        return self.slots.get('search_result_flag')

    def checkif_done(self):
        return self.slots.get('bkinfo_room_id')

    @property
    def next_state(self):
        if self.checkif_none():
            return self._STATES[0]
        if self.checkif_inintialized():
            return self._STATES[1]
        if self.checkif_done():
            return self._STATES[5]
        if self.checkif_showing():
            return self._STATES[4]
        if self.checkif_ready():
            return self._STATES[3]

        # inprogress <- fallback state
        return self._STATES[2]
