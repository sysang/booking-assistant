import requests
import json
import logging
import asyncio
import aiohttp
import time

from typing import Text, Dict, Any, Optional, Callable, Awaitable, NoReturn, List, Iterable

from .output import send_message_to_chatwoot


logger = logging.getLogger(__name__)

class CwwhatsappOutput:

    @classmethod
    def name(cls) -> Text:
        """Every output channel needs a name to identify it."""
        return cls.__name__

    async def send_response(self, recipient_id: Text, message: Dict[Text, Any]) -> None:
        """Send a message to the client."""
        logger.info('[DEV] send_response: %s', message)

        if message.get("buttons") and message.get("text"):
            await asyncio.sleep(0.35)
            await self.send_text_with_buttons(message.pop("text"), message.pop("buttons"), **message)

        if message.get("image") and message.get("text"):
            await self.send_text_with_image(message.pop("text"), message.pop("image"), **message)

        if message.get("text"):
            await asyncio.sleep(0.35)
            await self.send_text_message(message.pop("text"), **message)

        # if there is an image we handle it separately as an attachment
        if message.get("image"):
            await self.send_image_url(message.pop("image"), **message)

        if message.get("attachment"):
            await self.send_attachment(message.pop("attachment"), **message)

        if message.get("elements"):
            await self.send_elements(message.pop("elements"), **message)

        if message.get("custom"):
            await self.send_custom_json(message.pop("custom"), **message)

    def __init__(self, chatwoot_url, bot_token, botagent_account_id, conversation_id) -> None:
        self.chatwoot_url = chatwoot_url
        self.bot_token = bot_token
        self.botagent_account_id = botagent_account_id
        self.conversation_id = conversation_id

    async def _send_message(self, message: Text) -> None:
        """Send a message through this channel."""

        await send_message_to_chatwoot(
            url=self.chatwoot_url,
            botagent_account_id=self.botagent_account_id,
            conversation_id=self.conversation_id,
            bot_token=self.bot_token,
            message=message,
        )

    async def send_text_message( self, text: Text, **kwargs: Any) -> None:
        """Send a message through this channel."""

        for message_part in text.strip().split("\n\n"):
            await self._send_message({
                "type": "text",
                "text": { "body": message_part}
            })

    async def send_text_with_image( self, text: Text, image: Text, **kwargs: Any) -> None:
        """Send a message through this channel."""
        message_parts = text.strip().split("\n\n")

        for message_part in message_parts[0:-1]:
            await self._send_message({
                "type": "text",
                "text": { "body": message_part}
            })

        last_message_part = message_parts[-1]
        message = {
            'type': 'image',
            'image': {
                'link': image,
                'caption': last_message_part
            }
        }
        await self._send_message(message)

    async def send_image_url( self, image: Text, **kwargs: Any) -> None:
        """Sends an image to the output"""

        message = {
            "type": "image",
            "image": {"link": image}
        }
        await self._send_message(message)

    async def send_button(self, button: Dict) -> None:
        message = {
            'type': 'interactive',
            'interactive': {
                'type': 'button',
                'action': {
                    'button': {
                        'type': 'payload',
                        'payload': button['payload'],
                        'text': button['title'],
                    }
                }
            }
        }
        await self._send_message(message)

    async def send_text_with_buttons(self, text: Text, buttons: List[Dict[Text, Any]], **kwargs: Any,) -> None:
        """Sends buttons to the output."""

        message_parts = text.strip().split("\n\n") or [text]

        for message_part in message_parts[0:-1]:
            await self._send_message({
                "type": "text",
                "text": { "body": message_part}
            })

        action_btns = []
        for button in buttons:
            action_btns.append({
                "type": "reply",
                "reply": {
                    "id": button["payload"],
                    "title": button["title"]
                }
            })

        last_message_part = message_parts[-1]
        message = {
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {
                    "text": last_message_part,
                },
                "action": {
                    "buttons": action_btns
                }
            }
        }

        await self._send_message(message)

    async def send_elements(self, elements: Iterable[Dict[Text, Any]], **kwargs: Any) -> None:
        """Sends elements to the output."""

        for element in elements:
            message = {
                "attachment": {
                    "type": "template",
                    "payload": {"template_type": "generic", "elements": element},
                }
            }

            await self._send_message(message)

    async def send_custom_json(self, json_message: Dict[Text, Any], **kwargs: Any) -> None:
        """Sends custom json to the output"""

        raise NotImplementedError("send_custom_json")

    async def send_attachment(self, attachment: Dict[Text, Any], **kwargs: Any) -> None:
        """Sends an attachment to the user."""

        raise NotImplementedError("send_custom_json")
