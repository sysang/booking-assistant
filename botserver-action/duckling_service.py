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

DIM_TIME = 'time'
DIM_DURATION = 'duration'
DIM_AMOUNTOFMONEY = 'amount-of-money'

UNIT_DAY = 'day'
UNIT_WEEK = 'week'

class ParseResult:
    error_names = {
        'None': None,
        'failed': 'failed',
        'invalid_checkin_time': 'invalid_checkin_time',
        'invalid_bkinfo_duration': 'invalid_bkinfo_duration',
    }

    def __init__(self, value, unit='', parsed=None, error=None):
        self.error = str(error)
        self.value = value
        self.unit = unit
        self.parsed = parsed
        assert self.error in self.error_names.keys(), "error %s is not listed." % (self.error)

    def if_error(self, error):
        assert error in self.error_names.keys(), "Error is not listed." % (error)
        return self.error == error

    @property
    def is_valid(self):
        return not self.error

    def __str__(self):
        return '<ParseResult> error: %s, value: %s, unit: %s' % (self.error, self.value, self.unit)


def duckling_parse(expression, dims, locale='en_US'):
    """
    r = post('http://duckling:8000/parse', data={"locale": "en_GB", "dims": "duration", "text": "3 days"})
    r.json()
    # [{'body': '3 days', 'start': 0, 'value': {'value': 3, 'day': 3, 'type': 'value', 'unit': 'day', 'normalized': {'value': 259200, 'unit': 'second'}}, 'end': 6, 'dim': 'duration', 'latent': False}]
    """
    data = {
            'locale': locale,
            'text': expression,
            'dims': [dims] if isinstance(dims, str) else dims
        }
    r = post(PARSING_URL, data=data)
    r.raise_for_status()

    logger.info('[INFO] duckling_parse, expression: %s, dimention: %s, result: %s', expression, dims, r.text)

    parsed = r.json()

    return r.json()[0] if len(parsed) else None


def parse_checkin_time(expression):
    dim = DIM_TIME
    parsed = duckling_parse(expression=expression, dims=dim)

    if not parsed:
        error = ParseResult.error_names['failed']
        return ParseResult(error=error, value=None)

    parsed_dim = parsed['dim']

    if parsed_dim != dim:
        error = ParseResult.error_names['failed']
        return ParseResult(error=error, value=None)

    parsed_val = parsed['value']['value']
    today_arw = arrow.now().replace(hour=0, minute=0, second=1)
    checkin_time_arw = arrow.get(parsed_val).shift(minutes=1)
    if today_arw.timestamp() > checkin_time_arw.timestamp():
        error = ParseResult.error_names['invalid_checkin_time']
        return ParseResult(error=error, value=None)

    return ParseResult(value=parsed_val, parsed=parsed, error=None)


def parse_bkinfo_duration(expression):
    dim = DIM_DURATION
    units = [UNIT_DAY, UNIT_WEEK]

    parsed = duckling_parse(expression=expression, dims=dim)

    if not parsed:
        error = ParseResult.error_names['failed']
        return ParseResult(error=error, value=None)

    parsed_dim = parsed['dim']

    if parsed_dim != dim:
        error = ParseResult.error_names['failed']
        return ParseResult(error=error, value=None)

    parsed_unit = parsed['value']['unit']
    if parsed_unit not in units:
        error = ParseResult.error_names['invalid_bkinfo_duration']
        return ParseResult(error=error, value=None)

    parsed_val = parsed['value']['value']

    return ParseResult(value=parsed_val, unit=parsed_unit, parsed=parsed, error=None)


def parse_bkinfo_price(expression):
    dim = DIM_AMOUNTOFMONEY

    parsed = duckling_parse(expression=expression, dims=dim)

    if not parsed:
        error = ParseResult.error_names['failed']
        return ParseResult(error=error, value=None)

    parsed_dim = parsed['dim']

    if parsed_dim != dim:
        error = ParseResult.error_names['failed']
        return ParseResult(error=error, value=None)

    parsed_val = parsed['value']['value']
    if not parsed_val:
        error = ParseResult.error_names['failed']
        return ParseResult(error=error, value=None)

    parsed_unit = parsed['value']['unit']

    return ParseResult(value=parsed_val, unit=parsed_unit, parsed=parsed, error=None)


def __test__parse_checkin_time():

    expression = 'some thing not a time expression'
    print('\n[TEST] expression: ', expression)
    print(parse_checkin_time(expression))

    expression = '3 hours'
    print('\n[TEST] expression: ', expression)
    print(parse_checkin_time(expression))

    expression = 'january 1st 1990'
    print('\n[TEST] expression: ', expression)
    print(parse_checkin_time(expression))

    expression = 'february 2023'
    print('\n[TEST] expression: ', expression)
    print(parse_checkin_time(expression))

    expression = 'tomorrow'
    print('\n[TEST] expression: ', expression)
    print(parse_checkin_time(expression))


def __test__parse_bkinfo_duration():

    expression = 'some thing not a time duration'
    print('\n[TEST] expression: ', expression)
    print(parse_bkinfo_duration(expression))

    expression = 'september 5th'
    print('\n[TEST] expression: ', expression)
    print(parse_bkinfo_duration(expression))

    expression = '23 hours'
    print('\n[TEST] expression: ', expression)
    print(parse_bkinfo_duration(expression))

    expression = 'from 1st to 4th january'
    print('\n[TEST] expression: ', expression)
    print(parse_bkinfo_duration(expression))

    expression = '3 days'
    print('\n[TEST] expression: ', expression)
    print(parse_bkinfo_duration(expression))

    expression = '1 week'
    print('\n[TEST] expression: ', expression)
    print(parse_bkinfo_duration(expression))


def __test__parse_bkinfo_price():

    expression = 'some thing not an amount of money'
    print('\n[TEST] expression: ', expression)
    print(parse_bkinfo_price(expression))

    expression = 'a00 USD'
    print('\n[TEST] expression: ', expression)
    print(parse_bkinfo_price(expression))

    expression = '100 USC'
    print('\n[TEST] expression: ', expression)
    print(parse_bkinfo_price(expression))

    expression = '100 eur'
    print('\n[TEST] expression: ', expression)
    print(parse_bkinfo_price(expression))

def __test__():
    import sys
    import pprint
    pp = pprint.PrettyPrinter(indent=4)

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s', '%m-%d-%Y %H:%M:%S')

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO)
    stdout_handler.setFormatter(formatter)

    logger.addHandler(stdout_handler)

    print('\n', ''.join(['-']*150))

    # __test__parse_checkin_time()
    # __test__parse_bkinfo_duration()
    __test__parse_bkinfo_price()

    print(''.join(['-']*150), '\n')