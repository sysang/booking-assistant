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
tracking_time = now.strftime(format='%m%d-%H%M')
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
    model_name = model.replace('.tar.gz', '')
    counter = 0

    for story in stories['stories']:
        counter += 1
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
            payload = {'sender': tester, 'message': step}

            r = requests.post(endpoind, data=json.dumps(payload))
            body = r.json()
            utter = "\n(USER)  %s" % (step)
            logs = [ "(BOT)   -> %s" % (item.get('text', item.get('image', item.get('buttons')))) for item in body ]
            message = '\n'.join(logs) if len(logs) > 0 else '(BOT)   <<< error >>> '
            is_passed = is_passed and len(logs) > 0

            logger.info(utter)
            logger.info(message)
            time.sleep(0.1)
        result = 'passed' if is_passed else 'ERROR'
        logger.info(f"\n__________________________________________________________________  {result}  _________\n")

    with open(reportfile, 'r') as reader:
        print(reader.read())


