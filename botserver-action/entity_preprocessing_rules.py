import logging

from .hotel_data.constants import BED_SIZES
from .service import duckling_parse


logger = logging.getLogger(__name__)

def process_duration_value(expression):
  dim = 'duration'
  unit = 'day'
  parsed = duckling_parse(expression=expression, dim=dim)
  parsed_dim = parsed['dim']
  parsed_value_unit = parsed['value']['unit']

  if parsed_dim == dim and parsed_value_unit == unit:
    return parsed
  else:
    logger.info(f"[INFO] expression {expression} is invalid. More details: in respect to dimension {dim}")
    logger.info(f"[INFO] (duckling) parsed: ", parsed)

    return None


def process_date_value(expression):
  dim = 'time'
  parsed = duckling_parse(expression=expression, dim=dim)
  parsed_dim = parsed['dim']
  parsed_value_unit = parsed['value']['unit']

  if parsed_dim == dim:
    return parsed
  else:
    logger.info(f"[INFO] expression {expression} is invalid. More details: in respect to dimension {dim}")
    logger.info(f"[INFO] (duckling) parsed: ", parsed)

    return None

def process_room_type(expression):
  bed_sizes = BED_SIZES.values()

  if expression in bed_sizes:
    return expression

  return None

mapping_table = {
      'duration': process_duration_value,
      'date': process_date_value,
      'room_type': process_room_type,
    }
