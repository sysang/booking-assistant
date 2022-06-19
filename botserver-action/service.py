import os
import logging
from requests import post

from tinydb import Query
import arrow
from arrow import Arrow

from .dbconnector import db


logger = logging.getLogger(__name__)

DUCKLING_BASE_URL = os.environ['RASA_DUCKLING_HTTP_URL']
PARSING_URL = DUCKLING_BASE_URL + '/parse'

def duckling_parse(expression, dim):
  """
  r = post('http://duckling:8000/parse', data={"locale": "en_GB", "text": "3 days"})
  r.json()
  # [{'body': '3 days', 'start': 0, 'value': {'value': 3, 'day': 3, 'type': 'value', 'unit': 'day', 'normalized': {'value': 259200, 'unit': 'second'}}, 'end': 6, 'dim': 'duration', 'latent': False}]
  """
  data = {
        'locale': 'en_US',
        'text': expression,
        'dims': [dim]
      }
  r = post(PARSING_URL, data=data)
  r.raise_for_status()

  logger.info('[INFO] duckling_parse, expression: %s, dimention: %s, result: %s', expression, dim, r.text)

  return r.json()[0]


def query_available_rooms(bkinfo_area, bkinfo_checkin_time, bkinfo_duration, bkinfo_room_type):
  logger.info('[INFO] querying parameters(bkinfo_area, bkinfo_room_type, bkinfo_checkin_time, bkinfo_duration): (%s, %s, %s, %s)', bkinfo_area, bkinfo_room_type, bkinfo_checkin_time, bkinfo_duration)
  DATE_FORMAT = 'YYYY-MM-DD'

  bkinfo_duration = bkinfo_duration - 1  # Compensate when count checkin date

  arrobj_now = arrow.now()
  arrobj_checkin = arrow.get(bkinfo_checkin_time)
  if arrobj_now.timestamp() > arrobj_checkin.timestamp():
    return []

  arrobj_checkout = arrobj_checkin.shift(days=bkinfo_duration - 1)

  booked_dates = []
  for r in arrow.Arrow.range('day', arrobj_checkin, arrobj_checkout):
    booked_dates.append(r.format(DATE_FORMAT))

  logger.info('[INFO] booked_dates: %s', str(booked_dates))

  RoomQuery = Query()
  rooms = db.search((RoomQuery.area==bkinfo_area) & (RoomQuery.room_type==bkinfo_room_type))

  logger.info('[INFO] Found %s room in %s', len(rooms), bkinfo_area)

  available = []
  for room in rooms:
    if all([date not in room['occupied_dates'] for date in booked_dates]):
      available.append(room)

  return available


def query_room_by_id(id):
  logger.info('[INFO] query_room_by_id: %d', id)

  RoomQuery = Query()
  room = db.search(RoomQuery.id==id)

  if len(room) == 0:
    raise Exception("Query error: room not found.")
  else:
    return room[0]
