import inspect
import logging
import requests
import json
import asyncio
import aiohttp
import time

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
from rasa.core.channels.rest import QueueOutputChannel

from .cwwebsite_output import CwwebsiteOutput


logger = logging.getLogger(__name__)

def create_handler(message, chatwoot_url, cfg, on_new_message) -> Callable:

    def select_output_channel(channel, chatwoot_url, cfg, **kwargs):
        out_channel = None
        if channel == 'cwwebsite':
            out_channel = CwwebsiteOutput(
                chatwoot_url=chatwoot_url,
                bot_token=cfg.get("bot_token"),
                botagent_account_id=cfg.get("botagent_account_id"),
                conversation_id=kwargs.get("conversation_id"),
            )

        return out_channel

    async def process_message() -> None:
        logger.info('[DEBUG] (process_message) message: %s', message)

        sender = message.get("sender", {})
        sender_id = sender.get('id', None)
        content = message.get("content", None)
        conversation = message.get('conversation', {})
        conversation_id = conversation.get('id', None)

        input_channel = cfg.get("sub_channel")
        collector = CollectingOutputChannel()
        output_channel = select_output_channel(
            channel=input_channel,
            chatwoot_url=chatwoot_url,
            cfg=cfg,
            conversation_id=conversation_id,
        )

        if content and conversation_id and output_channel:
            logger.info('[DEBUG] on_new_message, content: %s', content)
            user_message = UserMessage(
                text=content,
                input_channel=input_channel,
                output_channel=output_channel,
                sender_id=sender_id,
            )
            await on_new_message(user_message)

            logger.info('[DEBUG] on_new_message -> done')

    return process_message


def check_should_proceed_message(message):
    message_type = message.get("message_type", None)
    conversation = message.get('conversation', {})
    conversation_status = conversation.get('status', None)
    sender = message.get("sender", {})
    sender_id = sender.get('id', None)

    return message_type == "incoming" and conversation_status == 'pending' and sender_id


class ChatwootInput(InputChannel):

    def name(self) -> Text:
        """Name of your custom channel."""
        return "chatwoot"

    @classmethod
    def from_credentials(cls, credentials: Optional[Dict[Text, Any]]) -> InputChannel:
        if not credentials:
            cls.raise_missing_credentials_exception()

        return cls(
            credentials.get("chatwoot_url"),
            credentials.get("website"),
        )

    def __init__(self, chatwoot_url, website: Dict[Text, Any]) -> None:
        self.chatwoot_url = chatwoot_url
        self.website = website

    def blueprint(
        self, on_new_message: Callable[[UserMessage], Awaitable[None]]
    ) -> Blueprint:

        custom_webhook = Blueprint(
            "custom_webhook_{}".format(type(self).__name__),
            inspect.getmodule(self).__name__,
        )

        @custom_webhook.route("/", methods=["GET"])
        async def health(request: Request) -> HTTPResponse:
            # TODO: check configuration for website channel here
            return response.json({"status": "ok"})

        async def handler(_message, _chatwoot_url, _cfg, _on_new_message) -> None:
            process_message = create_handler(
                message=_message,
                chatwoot_url=_chatwoot_url,
                cfg=_cfg,
                on_new_message=_on_new_message,
            )

            try:
                await process_message()

            except CancelledError:
                logger.error(f"[ERROR] Message handling timed out for message: %s", _message)
                raise Exception('CancelledError')

            except Exception:
                logger.error(f"[ERROR] An exception occured while handling message: %s", _message)


        async def async_trigger():
            await asyncio.sleep(0.1)
            return True

        async def cwwebsite(request: Request) -> HTTPResponse:
            logger.info('[DEBUG] (webhooks/chatwoot/cwwebsite) message: %s', request.json)

            if check_should_proceed_message(request.json):
                message = request.json
                chatwoot_url = request.route.ctx.chatwoot_url
                cfg = json.loads(request.route.ctx.cfg)

                await asyncio.shield(handler(
                    _message=message,
                    _chatwoot_url=chatwoot_url,
                    _cfg=cfg,
                    _on_new_message=on_new_message,
                ))

                return response.text("", status=204)

            logger.info("[DEBUG] Invalid message, just response immediately")

            return response.text("", status=204)

        custom_webhook.add_route(
            handler=cwwebsite,
            uri="/cwwebsite",
            methods=["POST"],
            ctx_chatwoot_url=self.chatwoot_url,
            ctx_cfg=json.dumps(self.website),
        )

        return custom_webhook


