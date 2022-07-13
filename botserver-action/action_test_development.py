import logging
import re
import json
import random
import copy

from typing import Any, Dict, List, Text, Optional, Tuple
from datetime import datetime
from functools import reduce

import arrow

from rasa_sdk import Action, Tracker
from rasa_sdk.forms import ValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import (
    Restarted,
    SlotSet,
    AllSlotsReset,
    UserUtteranceReverted,
    ConversationPaused,
    FollowupAction,
    ActionExecuted,
    UserUttered,
)


logger = logging.getLogger(__name__)

class action_test_development(Action):

    def name(self) -> Text:
        return "action_test_development"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        return [Restarted()]
