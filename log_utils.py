import logging
from pyrogram import Client

import database as db

logger = logging.getLogger("episode_bot")


async def log(client: Client, text: str):
    """
    Sends a notification to the configured log channel, if one is set.
    Uses direct get_chat resolution to ensure Peer Access Hash is cached.
    """
    log_channel_id = await db.get_log_channel()
    if not log_channel_id:
        return

    try:
        # Filter Bot Pattern: Always resolve chat first to populate peer cache
        chat = await client.get_chat(log_channel_id)
        await client.send_message(chat_id=chat.id, text=text)
    except Exception as e:
        logger.error(f"Failed to send log to channel ({log_channel_id}): {e}")
