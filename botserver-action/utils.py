import arrow
from arrow import Arrow


DATE_FORMAT = 'YYYY-MM-DD'

def parse_date_range(from_time, duration, format=DATE_FORMAT):
  arrobj_now = arrow.now()
  arrobj_checkin = arrow.get(from_time)
  arrobj_checkout = arrobj_checkin.shift(days=duration)

  return (arrobj_checkin.format(format), arrobj_checkout.format(format))


def __test__parse_date_range():
    from_time, to_time = parse_date_range('2022-01-01', 3)
    assert from_time == '2022-01-01', "from_time is incorrect."
    assert to_time == '2022-01-04', "to_time is incorrect."

    from_time, to_time = parse_date_range('2022-01-01', 32)
    assert from_time == '2022-01-01', "from_time is incorrect."
    assert to_time == '2022-02-02', "to_time is incorrect."

    print('Success.')


def __test__():
    __test__parse_date_range()
