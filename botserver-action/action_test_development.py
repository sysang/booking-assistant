import logging
import json
import random
import copy
from typing import Any, Dict, List, Text, Optional, Tuple
from datetime import datetime

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
from rasa_sdk.types import DomainDict


logger = logging.getLogger(__name__)

class action_test_development(Action):

    def name(self) -> Text:
        return "action_test_development"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        with open('actions/test_data/search_result.json', 'r') as f:
            hotels = json.load(f)

        room_num = sum([len(rooms) for rooms in hotels.values()])
        dispatcher.utter_message(response="utter_about_to_show_hotel_list", room_num=room_num)

        buttons = []
        counter = 0
        for rooms in hotels.values():
            for room in rooms:
                counter += 1
                bed_type = extract_bed_type(room['bed_configurations'])
                photos = [ photo['url_original'] for photo in room['photos']]
                photos = ' - ' + '\n - '.join(photos)

                room_title = "Room #%s: %s, %s, %s %s" % (counter, room["name_without_policy"], bed_type['name'], room['min_price'], room['price_currency'])
                data = {
                    'hotel_name': room['hotel_name_trans'],
                    'address': room['address_trans'],
                    'city': room['city_trans'],
                    'country': room['country_trans'],
                    'review_score': room['review_score'],
                    'is_beach_front': 'beach front,' if room['is_beach_front'] else '',
                    'nearest_beach_name': room['nearest_beach_name'] if room['is_beach_front'] else '',
                    'room_title': room_title,
                    'photos': photos,
                }

                # IMPORTANT: the json format of params is very strict, use \' instead of \" will yield silently no effect
                payload = { 'room_id': room['room_id'] }
                btn_payload = "/user_click_to_select_hotel%s" % (json.dumps(payload))


                buttons.append({ "title": room_title, "payload": btn_payload})

                dispatcher.utter_message(image=room['hotel_photo_url'])

                hotel_descrition = "{hotel_name}, {address}, {city}, {country}. Review score: {review_score}; {is_beach_front} near {nearest_beach_name}" . format(**data)
                room_description = "{room_title}" . format(**data)
                room_photos = "Room's photos:\n{photos}" . format(**data)

                dispatcher.utter_message(text=room_description)
                dispatcher.utter_message(text=hotel_descrition)
                dispatcher.utter_message(text=room_photos, buttons=buttons)

        # dispatcher.utter_message(response="utter_instruct_to_choose_room")

        return []

def extract_bed_type(bed_configurations):
    if len(bed_configurations) == 0:
        return ''

    bed_types = bed_configurations[0]['bed_types']
    if len(bed_types) == 0:
        return ''

    return bed_types[0]




