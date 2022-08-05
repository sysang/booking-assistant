import logging
import argparse
import json
import requests
import time

from datetime import datetime
from pathlib import Path
from ruamel.yaml import YAML

ENDPOINT = 'http://rasachatbot.sysang/webhooks/rest/webhook'

parser = argparse.ArgumentParser()
parser.add_argument('--model', required=True, type=str)
parser.add_argument('--testfile', required=True, type=str)
parser.add_argument('--endpoint', required=False, type=str, default='')
args = parser.parse_args()

model = args.model
testfile = args.testfile
endpoint = args.endpoint if args.endpoint else ENDPOINT
model_path = Path(f"models/{model}")

assert model, "Parameter `model` is not valid."
assert testfile, "Parameter `testfile` is not valid."
assert model_path.exists(), f'Path to model file, {model_path}, does not exists'

now = datetime.now()
reportfile = f"tests/reports/current/{testfile}[{model}].log"

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(message)s')
hdlr = logging.FileHandler(reportfile)
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)

def load_data(testfile):
    yaml = YAML(typ="safe", pure=True)
    with open(f"tests/{testfile}.yml", 'r') as reader:
        stories = yaml.load(reader)

    return stories

testing_data = {
    'area': 'bangkok',
    'time': 'september 5th',
    'duration': '3 days',
    'time_duration': 'from september 5th to september 8th',
    'bed_type': 'single',
    'amount-of-money': '500 usd',
    'time_invalid': '01/06/2022',
    'duration_invalid': '23 hours',
    'amount-of-money_invalid': '500 usa',

}

if __name__ == '__main__':
    stories = load_data(testfile)
    model_name = model.replace('.tar.gz', '')
    counter = 0

    for story in stories['stories']:
        counter += 1
        tracking_time = now.strftime(format='%m%d-%H%M')
        tester = f'ST{counter}-{testfile}[{model_name}][{tracking_time}]'
        name = story['name']
        steps = story['steps']
        is_passed = True

        logger.info("\n_____  STORY  ______________________________________________________________________")
        logger.info("")
        logger.info(f"Name: {name}")
        logger.info(f"Identity: {tester}")
        logger.info("- - -  --- - --- - - - - - - - - - ------- -- - - -- - - -- ---- -- -- - -- ----- ---\n")

        for step in story['steps']:
            message = step .format(**testing_data)
            payload = {'sender': tester, 'message': message}
            r = requests.post(endpoint, data=json.dumps(payload))
            r.raise_for_status()
            body = r.json()

            utter = "\n(USER)  %s" % (message)
            logs = [ "(BOT)   -> %s" % (item.get('text', item.get('image', item.get('buttons')))) for item in body ]
            message = '\n'.join(logs) if len(logs) > 0 else '(BOT)   <<< error >>> '
            is_passed = is_passed and len(logs) > 0

            logger.info(utter)
            logger.info(message)
            time.sleep(0.1)

        result = 'passed' if is_passed else ' E r r o r '
        logger.info(f"\n__________________________________________________________________  {result}  _________\n")

    with open(reportfile, 'r') as reader:
        print(reader.read())


