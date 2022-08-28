import asyncio
import inspect
import logging

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

from .cwwebsite_output import CwwebsiteOutput


logger = logging.getLogger(__name__)

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

    def _check_should_proceed_message(self, message):
        message_type = message.get("message_type", None)
        conversation = message.get('conversation', {})
        conversation_status = conversation.get('status', None)
        sender = message.get("sender", {})
        sender_id = sender.get('id', None)

        return message_type == "incoming" and conversation_status == 'pending' and sender_id

    def select_output_channel(self, channel, cfg, **kwargs):
        out_channel = None
        if channel == 'cwwebsite':
            out_channel = CwwebsiteOutput(
                chatwoot_url=self.chatwoot_url,
                bot_token=cfg.get("bot_token"),
                botagent_account_id=cfg.get("botagent_account_id"),
                conversation_id=kwargs.get("conversation_id"),
            )

        return out_channel


    def blueprint(
        self, on_new_message: Callable[[UserMessage], Awaitable[None]]
    ) -> Blueprint:

        custom_webhook = Blueprint(
            "custom_webhook_{}".format(type(self).__name__),
            inspect.getmodule(self).__name__,
        )

        async def handler(request: Request) -> HTTPResponse:
            cfg = getattr(self, request.route.ctx.configuration_name)
            message = request.json
            logger.info('[DEV] message: %s', message)
            metadata = self.get_metadata(request)

            if self._check_should_proceed_message(message):
                sender = message.get("sender", {})
                sender_id = sender.get('id', None)
                content = message.get("content", None)
                conversation = message.get('conversation', {})
                conversation_id = conversation.get('id', None)

                input_channel = cfg.get("sub_channel")
                collector = CollectingOutputChannel()
                output_channel = self.select_output_channel(
                    channel=input_channel,
                    cfg=cfg,
                    conversation_id=conversation_id,
                )

                if content and conversation_id and output_channel:
                    try:
                        await on_new_message(
                            UserMessage(
                                text=content,
                                input_channel=input_channel,
                                output_channel=output_channel,
                                sender_id=sender_id,
                                metadata=metadata,
                            )
                        )

                        # for message in collector.messages:
                        #     await output_channel.send_response(message)

                    except CancelledError:
                        logger.error(
                                f"Message handling timed out for message: %s", message)
                    except Exception:
                        logger.exception(f"An exception occured while handling message: %s", message)

            return response.text("", status=204)

        @custom_webhook.route("/", methods=["GET"])
        async def health(request: Request) -> HTTPResponse:
            # TODO: check configuration for website channel here
            return response.json({"status": "ok"})

        custom_webhook.add_route(
            handler=handler,
            uri="/cwwebsite",
            methods=["POST"],
            ctx_configuration_name='website',
        )

        return custom_webhook


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
