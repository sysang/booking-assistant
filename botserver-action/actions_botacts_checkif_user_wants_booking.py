import logging
from typing import Any, Dict, List, Text, Optional, Tuple


from rasa_sdk import Action, Tracker
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


class botacts_checkif_user_wants_booking(Action):

    def name(self) -> Text:
        return "botacts_checkif_user_wants_booking"


    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        dispatcher.utter_message(response='utter_checkif_user_wants_booking')

        return [
            SlotSet('userintent_affirm', None),
        ]

class bot_perceive_user_wants_booking(Action):

    def name(self) -> Text:
        return "bot_perceive_user_wants_booking"


    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        return [
            SlotSet('userintent_affirm', True),
        ]
