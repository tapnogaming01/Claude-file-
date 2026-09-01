import logging
from pyrogram import Client

logger = logging.getLogger(__name__)

async def try_resolve(client: Client, chat_id: int) -> bool:
    """
    Pyrogram needs to have 'seen' a chat (via an update, or a prior
    get_chat) before it can resolve a bare numeric ID into a peer.
    Calling get_chat forces that resolution so a later send_message /
    edit_message_text doesn't fail the first time the bot talks to a
    channel it was just made admin of.

    Returns True if the chat is accessible right now, False otherwise.
    """
    try:
        await client.get_chat(chat_id)
        return True
    except Exception as e:
        logger.warning(f"Failed to resolve Peer ID {chat_id}: {e}")
        return False
      
