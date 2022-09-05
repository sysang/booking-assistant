import requests
import json
import logging
import asyncio
import aiohttp

from rasa.core.channels.channel import OutputChannel
from telebot import TeleBot
from telebot import types
from telebot import util

from telebot.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup, 
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    ForceReply,
    MessageEntity,
    JsonSerializable,
)
from typing import Text, Dict, Any, Optional, Callable, Awaitable, NoReturn, List, Iterable, Union


logger = logging.getLogger(__name__)

REPLY_MARKUP_TYPES = Union[
    InlineKeyboardMarkup, ReplyKeyboardMarkup,
    ReplyKeyboardRemove, ForceReply
]

def _convert_markup(markup):
    if isinstance(markup, JsonSerializable):
        return markup.to_json()
    return markup

class CwteltegramOutput(TeleBot, OutputChannel):

    @classmethod
    def name(cls) -> Text:
        """Every output channel needs a name to identify it."""
        return cls.__name__

    def __init__(self, chatwoot_url, bot_token, botagent_account_id, conversation_id) -> None:
        self.chatwoot_url = chatwoot_url
        self.bot_token = bot_token
        self.botagent_account_id = botagent_account_id
        self.conversation_id = conversation_id

        super().__init__(self.bot_token)

    async def _make_request(self, message: Text) -> None:
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

    async def send_message(
        self, chat_id: Union[int, str], text: str,
        parse_mode: Optional[str]=None,
        entities: Optional[List[MessageEntity]]=None,
        disable_web_page_preview: Optional[bool]=None,
        disable_notification: Optional[bool]=None,
        protect_content: Optional[bool]=None,
        reply_to_message_id: Optional[int]=None,
        allow_sending_without_reply: Optional[bool]=None,
        reply_markup: Optional[REPLY_MARKUP_TYPES]=None,
        timeout: Optional[int]=None):

        parse_mode = self.parse_mode if (parse_mode is None) else parse_mode

        await self._send_message(
            chat_id, text, disable_web_page_preview, reply_to_message_id,
            reply_markup, parse_mode, disable_notification, timeout,
            entities, allow_sending_without_reply, protect_content=protect_content)

    async def _send_message(
        self, chat_id, text,
        disable_web_page_preview=None, reply_to_message_id=None, reply_markup=None,
        parse_mode=None, disable_notification=None, timeout=None,
        entities=None, allow_sending_without_reply=None, protect_content=None):

        method_url = r'sendMessage'
        payload = {'chat_id': str(chat_id), 'text': text, 'method_url': method_url}
        if disable_web_page_preview is not None:
            payload['disable_web_page_preview'] = disable_web_page_preview
        if reply_to_message_id:
            payload['reply_to_message_id'] = reply_to_message_id
        if reply_markup:
            payload['reply_markup'] = _convert_markup(reply_markup)
        if parse_mode:
            payload['parse_mode'] = parse_mode
        if disable_notification is not None:
            payload['disable_notification'] = disable_notification
        if timeout:
            payload['timeout'] = timeout
        if entities:
            payload['entities'] = json.dumps(MessageEntity.to_list_of_dicts(entities))
        if allow_sending_without_reply is not None:
            payload['allow_sending_without_reply'] = allow_sending_without_reply
        if protect_content is not None:
            payload['protect_content'] = protect_content

        await self._make_request(message=payload)

    async def send_photo(
        self, chat_id: Union[int, str], photo: Union[Any, str],
        caption: Optional[str]=None, parse_mode: Optional[str]=None,
        caption_entities: Optional[List[MessageEntity]]=None,
        disable_notification: Optional[bool]=None,
        protect_content: Optional[bool]=None,
        reply_to_message_id: Optional[int]=None,
        allow_sending_without_reply: Optional[bool]=None,
        reply_markup: Optional[REPLY_MARKUP_TYPES]=None,
        timeout: Optional[int]=None,):

        parse_mode = self.parse_mode if (parse_mode is None) else parse_mode

        await self._send_photo(
            chat_id, photo, caption, reply_to_message_id, reply_markup,
            parse_mode, disable_notification, timeout, caption_entities,
            allow_sending_without_reply, protect_content)

    async def _send_photo(
        self, chat_id, photo,
        caption=None, reply_to_message_id=None, reply_markup=None,
        parse_mode=None, disable_notification=None, timeout=None,
        caption_entities=None, allow_sending_without_reply=None, protect_content=None):

        method_url = r'sendPhoto'
        payload = {'chat_id': chat_id, 'method_url': method_url}
        files = None

        if util.is_string(photo):
            payload['photo'] = photo
        elif util.is_pil_image(photo):
            files = {'photo': util.pil_image_to_file(photo)}
        else:
            files = {'photo': photo}
        if caption:
            payload['caption'] = caption
        if reply_to_message_id:
            payload['reply_to_message_id'] = reply_to_message_id
        if reply_markup:
            payload['reply_markup'] = _convert_markup(reply_markup)
        if parse_mode:
            payload['parse_mode'] = parse_mode
        if disable_notification is not None:
            payload['disable_notification'] = disable_notification
        if timeout:
            payload['timeout'] = timeout
        if caption_entities:
            payload['caption_entities'] = json.dumps(MessageEntity.to_list_of_dicts(caption_entities))
        if allow_sending_without_reply is not None:
            payload['allow_sending_without_reply'] = allow_sending_without_reply
        if protect_content is not None:
            payload['protect_content'] = protect_content

        await self._make_request(message=payload)

    async def send_text_message(
        self, recipient_id: Text, text: Text, **kwargs: Any
    ) -> None:
        for message_part in text.strip().split("\n\n"):
            await self.send_message(recipient_id, message_part)

    async def send_image_url(
        self, recipient_id: Text, image: Text, **kwargs: Any
    ) -> None:
        await self.send_photo(recipient_id, image)

    async def send_text_with_buttons(
        self,
        recipient_id: Text,
        text: Text,
        buttons: List[Dict[Text, Any]],
        button_type: Optional[Text] = "inline",
        **kwargs: Any,
    ) -> None:
        """Sends a message with keyboard.
        For more information: https://core.telegram.org/bots#keyboards
        :button_type inline: horizontal inline keyboard
        :button_type vertical: vertical inline keyboard
        :button_type reply: reply keyboard
        """
        if button_type == "inline":
            reply_markup = InlineKeyboardMarkup()
            button_list = [
                InlineKeyboardButton(s["title"], callback_data=s["payload"])
                for s in buttons
            ]
            reply_markup.row(*button_list)

        elif button_type == "vertical":
            reply_markup = InlineKeyboardMarkup()
            [
                reply_markup.row(
                    InlineKeyboardButton(s["title"], callback_data=s["payload"])
                )
                for s in buttons
            ]

        elif button_type == "reply":
            reply_markup = ReplyKeyboardMarkup(
                resize_keyboard=False, one_time_keyboard=True
            )
            # drop button_type from button_list
            button_list = [b for b in buttons if b.get("title")]
            for idx, button in enumerate(buttons):
                if isinstance(button, list):
                    reply_markup.add(KeyboardButton(s["title"]) for s in button)
                else:
                    reply_markup.add(KeyboardButton(button["title"]))
        else:
            logger.error(
                "Trying to send text with buttons for unknown "
                "button type {}".format(button_type)
            )
            return

        await self.send_message(recipient_id, text, reply_markup=reply_markup)
