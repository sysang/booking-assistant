import asyncio
import inspect
import requests
import logging
import json

from sanic import Sanic, Blueprint, response
from sanic.request import Request
from sanic.response import HTTPResponse
from typing import Text, Dict, Any, Optional, Callable, Awaitable, NoReturn, List, Iterable
from asyncio import Queue, CancelledError

import rasa.utils.endpoints
from rasa.core.channels.channel import (
    InputChannel,
    OutputChannel,
    CollectingOutputChannel,
    UserMessage,
)


logger = logging.getLogger(__name__)

class ChatwootInput(InputChannel):

    def __init__(self) -> None:
        self.bot_token = '9sSWuJYVQr6rLCyufiMgv14a'
        self.botagent_account_id = 1

    def name(self) -> Text:
        """Name of your custom channel."""
        return "chatwoot"

    def blueprint(
        self, on_new_message: Callable[[UserMessage], Awaitable[None]]
    ) -> Blueprint:

        custom_webhook = Blueprint(
            "custom_webhook_{}".format(type(self).__name__),
            inspect.getmodule(self).__name__,
        )

        @custom_webhook.route("/", methods=["GET"])
        async def health(request: Request) -> HTTPResponse:
            return response.json({"status": "ok"})

        @custom_webhook.route("/cwwebsite", methods=["POST"])
        async def cwwebsite(request: Request) -> HTTPResponse:
            input_channel = self.name()
            logger.info('[DEV] request.json: %s', request.json.items())
            message_type = request.json.get("message_type", None)
            conversation = request.json.get('conversation', {})
            conversation_status = conversation.get('status', None)
            # account = request.json.get('account', {})
            # account_id = account.get('id', DEFAULT_ACCOUNT)
            # metadata = self.get_metadata(request)

            # include exception handling
            # check sender_id, content, conversation_id, if any of them unavailable
            # log error, exit

            if(message_type == "incoming" and conversation_status == 'pending'):
                sender = request.json.get("sender", {})
                sender_id = sender.get('id', None)
                content = request.json.get("content", None)
                conversation_id = conversation.get('id', None)

                collector = CollectingOutputChannel()
                out_channel = ChatwootOutput(conversation_id)

                if content and conversation_id:
                    try:
                        await on_new_message(
                            UserMessage(
                                text=content,
                                output_channel=collector,
                                sender_id=sender_id,
                                input_channel=input_channel,
                                # metadata=metadata,
                            )
                        )

                        for message in collector.messages:
                            await out_channel.send_response(message)

                    except CancelledError:
                        logger.error(
                            f"Message handling timed out for " f"user message '{text}'."
                        )
                    except Exception:
                        logger.exception(
                            f"An exception occured while handling "
                            f"user message '{text}'.")

            return response.text("", status=204)


        return custom_webhook


class ChatwootOutput:

    @classmethod
    def name(cls) -> Text:
        """Every output channel needs a name to identify it."""
        return cls.__name__

    async def send_response(self, message: Dict[Text, Any]) -> None:
        """Send a message to the client."""

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

    def __init__(self,conversation_id) -> None:
        self.bot_token = '9sSWuJYVQr6rLCyufiMgv14a'
        self.botagent_account_id = 1
        self.conversation_id = conversation_id

    async def _send_message(self, message: Text) -> None:
        """Send a message through this channel."""
        CHATWOOT_URL = 'http://192.168.58.7:3000'
        account_id=self.botagent_account_id
        conversation_id=self.conversation_id
        chatwoot_bot_token=self.bot_token

        url = f"{CHATWOOT_URL}/api/v1/accounts/{account_id}/conversations/{conversation_id}/messages"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "api_access_token": f"{chatwoot_bot_token}"
        }
        data = {
            'content': json.dumps(message),
            'message_type': 'outgoing',
        }

        # TDOD: check if error
        r = requests.post(url, json=data, headers=headers)

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

        logger.info('[DEV] send_text_with_buttons -> messages: %s', messages)
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


class QueueOutputChannel(CollectingOutputChannel):
    """Output channel that collects send messages in a list
    (doesn't send them anywhere, just collects them)."""

    # FIXME: this is breaking Liskov substitution principle
    # and would require some user-facing refactoring to address
    messages: Queue  # type: ignore[assignment]

    @classmethod
    def name(cls) -> Text:
        """Name of QueueOutputChannel."""
        return "queue"

    # noinspection PyMissingConstructor
    def __init__(self, message_queue: Optional[Queue] = None) -> None:
        super().__init__()
        self.messages = Queue() if not message_queue else message_queue

    def latest_output(self) -> NoReturn:
        raise NotImplementedError("A queue doesn't allow to peek at messages.")

    async def _persist_message(self, message: Dict[Text, Any]) -> None:
        await self.messages.put(message)
