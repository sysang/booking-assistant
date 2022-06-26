import logging
import argparse
import json
import requests
import time

from datetime import datetime
from pathlib import Path
from ruamel.yaml import YAML

parser = argparse.ArgumentParser()
parser.add_argument('--model', required=True, type=str)
parser.add_argument('--testfile', required=True, type=str)
args = parser.parse_args()

model = args.model
testfile = args.testfile

assert model, "Parameter `model` is not valid."
assert testfile, "Parameter `testfile` is not valid."
assert Path(f"models/{model}").exists(), 'Pre-trained model file does not exists'

now = datetime.now()
tracking_time = now.strftime(format='%y%m%d][%H%M')
reportfile = f"tests/reports/{testfile}[{model}][{tracking_time}].log"

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

endpoind = 'http://rasachatbot.sysang/webhooks/rest/webhook'

if __name__ == '__main__':
    stories = load_data(testfile)

    for story in stories['stories']:
        name = story['name']
        steps = story['steps']
        log = []

        logger.info("\n_____ STORY ________________________________________________________________________")
        logger.info(f"\nName: {name}")
        logger.info("--- -- ---- --- - - - - - - - - - - ------ -- - - -- - - -- ---- -- -- - -- ----- ---\n")

        for step in story['steps']:
            payload = {'sender': f'autotester-{model}-{tracking_time}', 'message': step}

            r = requests.post(endpoind, data=json.dumps(payload))
            body = r.json()
            utter = "\n(USER)  %s" % (step)
            message = [ "(BOT)   -> %s" % (item['text']) for item in body ]
            message = '\n'.join(message)

            logger.info(utter)
            logger.info(message)
            time.sleep(0.1)
        logger.info("\n___________________________________________________________________ END _________\n")

    with open(reportfile, 'r') as reader:
        print(reader.read())


