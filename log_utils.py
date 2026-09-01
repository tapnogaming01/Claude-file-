import logging
from pyrogram import Client
from pyrogram.errors import RPCError

import database as db

logger = logging.getLogger("episode_bot")


async def log(client: Client, text: str):
    """Sends a notification to the configured log channel, if one is set.

    Automatically resolves peer hash if not found in session cache.
    """
    log_channel_id = await db.get_log_channel()
    if not log_channel_id:
        return

    try:
        # Try direct send first
        await client.send_message(log_channel_id, text)
    except (ValueError, RPCError):
        try:
            # If Peer ID is invalid/missing in local session, resolve it on-the-fly
            chat = await client.get_chat(log_channel_id)
            await client.send_message(chat.id, text)
        except Exception as e:
            logger.error(f"Failed to resolve and send to log channel ({log_channel_id}): {e}")
    except Exception as e:
        logger.error(f"Unexpected error while logging: {e}")
