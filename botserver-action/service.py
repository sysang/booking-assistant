import os
import logging
from requests import posts

from tinydb import where
import arrow

from dbconnector import db


DUCKLING_BASE_URL = os.environ['RASA_DUCKLING_HTTP_URL']
PARSING_URL = DUCKLING_BASE_URL + '/parse'

def duckling_parse(expression, dim):
"""
  r = post('http://duckling:8000/parse', data={"locale": "en_GB", "text": "3 days"})
  r.json()
  # [{'body': '3 days', 'start': 0, 'value': {'value': 3, 'day': 3, 'type': 'value', 'unit': 'day', 'normalized': {'value': 259200, 'unit': 'second'}}, 'end': 6, 'dim': 'duration', 'latent': False}]
"""
  _expression = expression.replace('night', 'day')
  _expression = _expression.replace('nights', 'days')
  data = {
        'locale': 'en_US',
        'text': _expression,
        'dims': [dim]
      }
  r = posts(PARSING_URL, data=data)
  r.raise_for_status()

  return r.json()[0]


def query_available_rooms(area, room_type, checkin_time, duration):
  parsed_checkin_time = duckling_parse(expression=checkin_time, dim='time')
  parsed_duration = duckling_parse(expression=duration, dim='duration')

  now = arrow.now()
  checkin = arrow.get(parsed_checkin_time['value'])
  if now.timestamp() > checkin.timestamp():
    return []

  DATE_FORMAT = 'YYYY-MM-DD'
  checkin_time_cond = checkin.format(DATE_FORMAT)
  checkout_time_cond = checkin_time_cond.shift(days=parsed_duration.value - 1)
  booked_dates = []
  for r in arrow.Arrow.range('day', checkin_time_cond, checkin_time):
    booked_dates.append(r.format(DATE_FORMAT))

  RoomQuery = Query()
  rooms = db.search((RoomQuery.area==area) & (RoomQuery.room_type==room_type))

  available = []
  for room in rooms:
    for date in booked_dates:
      if date not in room['occupied_dates']
        available.append(room)

  return available

