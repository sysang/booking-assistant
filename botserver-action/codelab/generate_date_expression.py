from datetime import datetime
from datetime import timedelta

one_day = timedelta(days=1)

DATE_FORMAT = [
    '%B %d',
    '%B %dth',
    '%b %d',
    '%b %dth',
    '%d %B',
    '%dth %B',
    '%d %b',
    '%dth %b',
]

for format in DATE_FORMAT:
    first_date = datetime.fromisoformat('2022-01-01')
    for i in range(1, 365):
        print(first_date.strftime(format))
        first_date = first_date + one_day
