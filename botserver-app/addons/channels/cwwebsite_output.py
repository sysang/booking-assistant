import requests
import json
import logging
import asyncio
import aiohttp

from typing import Text, Dict, Any, Optional, Callable, Awaitable, NoReturn, List, Iterable


logger = logging.getLogger(__name__)

class CwwebsiteOutput:

    @classmethod
    def name(cls) -> Text:
        """Every output channel needs a name to identify it."""
        return cls.__name__

    async def send_response(self, recipient_id: Text, message: Dict[Text, Any]) -> None:
        """Send a message to the client."""
        logger.info('[DEV] send_response: %s', message)

        if message.get("quick_replies"):
            await self.send_quick_replies(
                message.pop("text"),
                message.pop("quick_replies"),
                **message,
            )

        elif message.get("buttons"):
            await self.send_text_with_buttons(message.pop("text"), message.pop("buttons"), **message)

        elif message.get("text"):
            await self.send_text_message(message.pop("text"), **message)

        if message.get("custom"):
            await self.send_custom_json(message.pop("custom"), **message)

        # if there is an image we handle it separately as an attachment
        if message.get("image"):
            await self.send_image_url(message.pop("image"), **message)

        if message.get("attachment"):
            await self.send_attachment(message.pop("attachment"), **message)

        if message.get("elements"):
            await self.send_elements(message.pop("elements"), **message)

    def __init__(self, chatwoot_url, bot_token, botagent_account_id, conversation_id) -> None:
        self.chatwoot_url = chatwoot_url
        self.bot_token = bot_token
        self.botagent_account_id = botagent_account_id
        self.conversation_id = conversation_id

    async def _send_message(self, message: Text) -> None:
        """Send a message through this channel."""

        url = f"{self.chatwoot_url}/api/v1/accounts/{self.botagent_account_id}/conversations/{self.conversation_id}/messages"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "api_access_token": f"{self.bot_token}"
        }
        data = {
            'content': json.dumps(message),
            'message_type': 'outgoing',
        }

        logger.info('[DEBUG] make request to send message to chatwoot server, url: %s, headers: %s, data: %s', url, headers, data)

        # TDOD: check if error
        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=data, headers=headers) as resp:
                logger.info('[DEBUG] make request to send message to chatwoot server, response: %s', resp)

    async def send_text_message( self, text: Text, **kwargs: Any) -> None:
        """Send a message through this channel."""

        for message_part in text.strip().split("\n\n"):
            await self._send_message({"text": message_part})

    async def send_image_url( self, image: Text, **kwargs: Any) -> None:
        """Sends an image to the output"""

        message = {"attachment": {"type": "image", "payload": {"src": image}}}
        await self._send_message(message)

    async def send_text_with_buttons(self, text: Text, buttons: List[Dict[Text, Any]], **kwargs: Any,) -> None:
        """Sends buttons to the output."""

        # split text and create a message for each text fragment
        # the `or` makes sure there is at least one message we can attach the quick
        # replies to
        message_parts = text.strip().split("\n\n") or [text]
        messages: List[Dict[Text, Any]] = [
            {"text": message, "quick_replies": []} for message in message_parts
        ]

        # attach all buttons to the last text fragment
        messages[-1]["quick_replies"] = [
            {
                "content_type": "text",
                "title": button["title"],
                "payload": button["payload"],
            }
            for button in buttons
        ]

        for message in messages:
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
        await self._send_message({"attachment": attachment})
