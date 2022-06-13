import logging
from typing import Any, Dict, List, Text, Optional, Tuple

from rasa_sdk.events import SlotSet

logger = logging.getLogger(__name__)


class BookingInfo(dict):
  _schema = (
        'bkinfo_area',
        'bkinfo_checkin_time',
        'bkinfo_duration',
        'bkinfo_room_type',
      )

  def __init__(self, slots):
    _slots = slots.copy()
    for name in self._schema:
      v = _slots.get(name)
      self[name] = v

  def is_done(self):
    return all(self.values())

  @classmethod
  def checkif_done_collection_information(self, slots):
    for name in self._schema:
      v = slots.get(name, False)
      logger.info("[DEBUG] slot %s: %s", name, v)
      if not v:
        return False

    return True

  @classmethod
  def set_booking_information_flag__noted__(self) -> List[Dict[Text, Any]]:
    events = []
    for name in self._schema:
      events.append(SlotSet(f"{name}_flag", 'noted'))
      events.append(SlotSet(name, None))

    return events
