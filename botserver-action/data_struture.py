import logging
from typing import Any, Dict, List, Text, Optional, Tuple

import arrow

from rasa_sdk.events import SlotSet

logger = logging.getLogger(__name__)

DATE_FORMAT = 'MMMM Do YYYY'

class BookingInfo(dict):    # TODO: transform flags to FSM
  _SCHEMA = {
        'bkinfo_area',
        'bkinfo_checkin_time',
        'bkinfo_duration',
        'bkinfo_bed_type',
    }

  def __init__(self, slots):
    _slots = slots.copy()
    for name in self._SCHEMA:
      v = _slots.get(name, None)
      self[name] = v

  def is_completed(self):
    return all(self.values())

  @classmethod
  def assertif_valid_slot_name(self, name):
      assert name in self._SCHEMA, f"slot name {name} is invalid."

  @classmethod
  def checkif_done_collection_information(self, slots):
    for name in self._SCHEMA:
      v = slots.get(name, False)
      logger.info("[DEBUG] slot %s: %s", name, v)
      if not v:
        return False

    return True

  @classmethod
  def set_booking_information_flag(self, value) -> List[Dict[Text, Any]]:
    events = []
    for name in self._SCHEMA:
      events.append(SlotSet(f"{name}_flag", value))

    return events

  @classmethod
  def set_booking_information(self, value) -> List[Dict[Text, Any]]:
    events = []
    for name in self._SCHEMA:
      events.append(SlotSet(name, value))

    return events
  @classmethod
  def set_bkinfo_slot_flag(self, slot_name, slot_value):
    return SlotSet(f"{slot_name}_flag", slot_value)

  @property
  def checkin_time(self):
    return arrow.get(self['bkinfo_checkin_time']).format(DATE_FORMAT)

  @property
  def duration(self):
    duration = self['bkinfo_duration']
    duration = str(duration) + ' days' if duration > 1 else str(duration) + ' day'

    return duration

  @property
  def bed_type(self):
      return self['bkinfo_bed_type']
