import os
import logging
from requests import post

from tinydb import Query
import arrow
from arrow import Arrow

from .dbconnector import db
from .duckling_service import (
    parse_checkin_time,
    parse_bkinfo_duration,
    parse_bkinfo_price,
)


logger = logging.getLogger(__name__)

def query_available_rooms(bkinfo_area, bkinfo_checkin_time, bkinfo_duration, bkinfo_bed_type, bkinfo_price=None):
    logger.info('[INFO] querying parameters(bkinfo_area, bkinfo_bed_type, bkinfo_checkin_time, bkinfo_duration): (%s, %s, %s, %s)', bkinfo_area, bkinfo_bed_type, bkinfo_checkin_time, bkinfo_duration)
    DATE_FORMAT = 'YYYY-MM-DD'

    checkin_date = parse_checkin_time(expression=bkinfo_checkin_time)
    duration = parse_bkinfo_duration(expression=bkinfo_duration)

    checkin_date_arrobj = arrow.get(checkin_date.value)
    checkout_date_arrobj = checkin_date_arrobj.shift(days=duration.value)

    booked_dates = []
    for r in arrow.Arrow.range('day', checkin_date_arrobj, checkout_date_arrobj):
        booked_dates.append(r.format(DATE_FORMAT))

    logger.info('[INFO] booked_dates: %s', str(booked_dates))

    RoomQuery = Query()
    rooms = db.search((RoomQuery.area==bkinfo_area) & (RoomQuery.bed_type==bkinfo_bed_type))

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
