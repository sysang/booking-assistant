import json
import logging
import asyncio
import aiohttp

from typing import Text, Dict, Any, Optional, Callable, Awaitable, NoReturn, List, Iterable


logger = logging.getLogger(__name__)

async def send_message_to_chatwoot(url: Text, botagent_account_id: Any, conversation_id: Any, message: Dict[Text, Text], bot_token: Text) -> Awaitable:
    """Send a message through this channel."""

    url = f"{url}/api/v1/accounts/{botagent_account_id}/conversations/{conversation_id}/messages"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "api_access_token": f"{bot_token}"
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

