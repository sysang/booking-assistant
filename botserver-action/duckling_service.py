import os
import logging
import pprint
import arrow

from cachetools import cached, TTLCache
from tinydb import Query
from requests import post
from arrow import Arrow

from .dbconnector import db


pp = pprint.PrettyPrinter(indent=4)
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
        None: None,
        'failed': 'failed',
        'invalid_checkin_time': 'invalid_checkin_time',
        'invalid_bkinfo_duration': 'invalid_bkinfo_duration',
    }

    def __init__(self, value, unit='', value_type='', parsed=None, error=None):
        self.error = error
        self.value = value
        self.unit = unit
        self.value_type = value_type
        self.parsed = parsed
        assert self.error in self.error_names.keys(), "error %s is not listed." % (self.error)

    def if_error(self, error):
        assert error in self.error_names.keys(), "Error is not listed." % (error)
        return self.error == error

    def is_valid(self):
        return not self.error

    def __str__(self):
        return '<ParseResult> error: %s, value: %s, unit: %s, type: %s' % (self.error, self.value, self.unit, self.value_type)


@cached(cache=TTLCache(maxsize=256, ttl=60))
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

    return r.json()


def parse_checkin_time(expression):
    dim = DIM_TIME
    result = duckling_parse(expression=expression, dims=dim)
    parsed = None
    parsed_dim = None

    if len(result) == 0:
        error = ParseResult.error_names['failed']
        return ParseResult(error=error, value=None)

    for item in result:
        if item['dim'] == dim:
            parsed = item
            parsed_dim =item['dim']

    if not parsed:
        error = ParseResult.error_names['failed']
        return ParseResult(error=error, value=None, parsed=parsed)

    """
    parsed format is various depending on expression, cases:
    - normal value such as: september 5th
    - embedded value (duration) such as: from march 3rd to march 4th
    check value type to determine which case, 'value' -> normal, 'interval' -> embedded
    """
    parsed_value = parsed['value']
    parsed_type = parsed_value['type']
    if parsed_type == 'interval':
        value = parsed_value['from']['value']
    else:
        value = parsed_value['value']
    today_arw = arrow.now().replace(hour=0, minute=0, second=1)
    checkin_time_arw = arrow.get(value).shift(minutes=1)
    if today_arw.timestamp() > checkin_time_arw.timestamp():
        error = ParseResult.error_names['invalid_checkin_time']
        return ParseResult(error=error, value=value, parsed=parsed)

    return ParseResult(value=value, value_type=parsed_type, parsed=parsed, error=None)


def parse_bkinfo_duration(expression):
    dim_duration = DIM_DURATION
    dim_time = DIM_TIME
    units = [UNIT_DAY, UNIT_WEEK]

    result = duckling_parse(expression=expression, dims=dim_duration)
    parsed = None
    parsed_dim = None

    if len(result) == 0:
        error = ParseResult.error_names['failed']
        return ParseResult(error=error, value=None)

    """
    parsed format is various depending on expression, cases:
    - normal value such as: september 5th
    - 'from exp1 to exp2' (duration) such as: from march 3rd to march 4th
    check value type to determine which case, 'value' -> normal, 'from', 'to' -> 'from exps to exp2'
    """

    for item in result:
        if item['dim'] in [dim_time, dim_duration]:
            parsed = item
            parsed_dim =item['dim']

    if not parsed:
        error = ParseResult.error_names['failed']
        return ParseResult(error=error, value=None, parsed=parsed)

    parsed_value = parsed['value']
    parsed_type = parsed_value['type']

    if parsed_dim == dim_duration:
        value = parsed_value['value']
        parsed_unit = parsed_value['unit']
    elif parsed_dim == dim_time and parsed_value.get('from') and parsed_value.get('to'):
        parsed_unit = UNIT_DAY
        time_from = parsed_value.get('from')
        time_to = parsed_value.get('to')
        time_delta = arrow.get(time_to.get('value')) - arrow.get(time_from.get('value'))
        # NOTE: check-out date must be exclued when calculate staying duration
        value = time_delta.days - 1
    else:
        error = ParseResult.error_names['failed']
        return ParseResult(error=error, value=None, parsed=parsed)

    if parsed_unit not in units:
        error = ParseResult.error_names['invalid_bkinfo_duration']
        return ParseResult(error=error, value=None, parsed=parsed)

    return ParseResult(value=value, value_type=parsed_type, unit=parsed_unit, parsed=parsed, error=None)


def parse_bkinfo_price(expression):
    dim = DIM_AMOUNTOFMONEY

    result = duckling_parse(expression=expression, dims=dim)
    parsed = None
    parsed_dim = None

    if len(result) == 0:
        error = ParseResult.error_names['failed']
        return ParseResult(error=error, value=None)

    for item in result:
        if item['dim'] == dim:
            parsed = item
            parsed_dim =item['dim']

    if not parsed:
        error = ParseResult.error_names['failed']
        return ParseResult(error=error, value=None)

    if parsed_dim != dim:
        error = ParseResult.error_names['failed']
        return ParseResult(error=error, value=None)

    parsed_value = parsed['value']
    value = parsed_value['value']
    if not value:
        error = ParseResult.error_names['failed']
        return ParseResult(error=error, value=None)

    parsed_unit = parsed_value['unit']

    return ParseResult(value=value, unit=parsed_unit, parsed=parsed, error=None)


def __test__parse_checkin_time():
    expression = 'some thing not a time expression'
    print('\n[TEST] invalid expression: ', expression)
    result = parse_checkin_time(expression)
    print(result)
    assert result.error == 'failed'

    expression = '3 hours'
    print('\n[TEST] invalid expression: ', expression)
    result = parse_checkin_time(expression)
    print(result)
    assert result.error == 'failed'

    expression = '7/32'
    print('\n[TEST] invalid expression: ', expression)
    result = parse_checkin_time(expression)
    print(result)
    assert result.error == 'failed'

    expression = 'january 1st 1990'
    print('\n[TEST] invalid expression (past): ', expression)
    result = parse_checkin_time(expression)
    print(result)
    assert result.error == 'invalid_checkin_time'

    expression = 'june 1st 2022'
    print('\n[TEST] invalid expression (past): ', expression)
    result = parse_checkin_time(expression)
    print(result)
    assert result.error == 'invalid_checkin_time'

    expression = 'february 2023'
    print('\n[TEST] expression: ', expression)
    result = parse_checkin_time(expression)
    print(result)
    assert result.error == None

    expression = 'tomorrow'
    print('\n[TEST] expression: ', expression)
    result = parse_checkin_time(expression)
    print(result)
    assert result.error == None

    expression = '7/28'
    print('\n[TEST] expression: ', expression)
    result = parse_checkin_time(expression)
    print(result)
    assert result.error == None

    expression = 'from 1st to 4th january'
    print('\n[TEST] expression: ', expression)
    result = parse_checkin_time(expression)
    print(result)
    assert result.error == None


def __test__parse_bkinfo_duration():
    expression = 'some thing not a time duration'
    print('\n[TEST] expression: ', expression)
    result = parse_bkinfo_duration(expression)
    print(result)
    assert result.error == 'failed'

    expression = 'september 5th'
    print('\n[TEST] expression: ', expression)
    result = parse_bkinfo_duration(expression)
    print(result)
    assert result.error == 'failed'

    expression = '23 hours'
    print('\n[TEST] expression: ', expression)
    result = parse_bkinfo_duration(expression)
    print(result)
    assert result.error == 'invalid_bkinfo_duration'

    expression = 'from 1st to 4th january'
    print('\n[TEST] expression: ', expression)
    result = parse_bkinfo_duration(expression)
    print(result)
    assert result.error == None

    expression = '3 days'
    print('\n[TEST] expression: ', expression)
    result = parse_bkinfo_duration(expression)
    print(result)
    assert result.error == None

    expression = '2 weeks'
    print('\n[TEST] expression: ', expression)
    result = parse_bkinfo_duration(expression)
    print(result)
    assert result.error == None


def __test__parse_bkinfo_price():

    expression = 'some thing not an amount of money'
    print('\n[TEST] expression: ', expression)
    result = parse_bkinfo_price(expression)
    print(result)
    assert result.error == 'failed'

    expression = 'a00 USD'
    print('\n[TEST] expression: ', expression)
    result = parse_bkinfo_price(expression)
    print(result)
    assert result.error == 'failed'

    expression = '100 USC'
    print('\n[TEST] expression: ', expression)
    result = parse_bkinfo_price(expression)
    print(result)
    assert result.error == 'failed'

    expression = '100 eur'
    print('\n[TEST] expression: ', expression)
    result = parse_bkinfo_price(expression)
    print(result)
    assert result.error == None


"""
__pytest__
import os;from actions.duckling_service import eval_test;eval_test(tfunc=os.environ.get('TEST_FUNC', None));
"""

def eval_test(tfunc):
    __test__fn = f'__test__{tfunc}'
    eval(__test__fn)()
