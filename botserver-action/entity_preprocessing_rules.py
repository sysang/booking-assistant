import logging

from .hotel_data.constants import BED_SIZES
from .service import duckling_parse


logger = logging.getLogger(__name__)

def process_duration_value(expression):

    if isinstance(expression, int):
        return expression

    if isinstance(expression, str):
        dim = 'duration'
        unit = 'day'
        expression = expression.replace('night', 'day').replace('nights', 'days')

        parsed = duckling_parse(expression=expression, dim=dim)
        parsed_dim = parsed['dim']
        parsed_value_unit = parsed['value']['unit']

        if parsed_dim == dim and parsed_value_unit == unit:
            return parsed['value']['value']

        logger.info(f"[INFO] expression %s is invalid. More details: in respect to dimension %s", expression, dim)
        logger.info(f"[INFO] (duckling) parsed: %s", str(parsed))

    return None


def process_time_value(expression):

    if isinstance(expression, str):
        return expression

    if isinstance(expression, dict):
        return expression.get('from', None)

    return None

def process_room_type(expression):
  # bed_sizes = BED_SIZES.keys()

  # if expression in bed_sizes:
  #   return BED_SIZES[expression]

  # logger.info(f"[INFO] expression %s is invalid. The valid values: %s", expression, str(bed_sizes))

  # return None
  return expression

def mapping_table(entity_name):
  TABLE = {
      'duration': process_duration_value,
      'time': process_time_value,
      'room_type': process_room_type,
    }

  return TABLE.get(entity_name, lambda exp: exp)
