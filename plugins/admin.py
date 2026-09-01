import logging
from pyrogram import Client, filters
from pyrogram.types import Message

import config
import database as db
from log_utils import log
from peer_utils import try_resolve  # Safe peer resolution helper

logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


# ---------------- Source channel mapping ----------------

@Client.on_message(filters.command("addsource") & filters.private)
async def add_source_cmd(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return await message.reply_text("You are not authorized to use this command.")

    parts = message.text.split(maxsplit=3)
    if len(parts) < 4:
        return await message.reply_text(
            "Usage:\n`/addsource <source_channel_id> <story_name> <target_channel_id>`\n\n"
            "Example:\n`/addsource -1001111111111 MyPossessiveThing -1002222222222`"
        )

    _, source_id_str, story_name, target_id_str = parts
    try:
        source_id = int(source_id_str)
        target_id = int(target_id_str)
    except ValueError:
        return await message.reply_text("Channel IDs must be numeric (e.g. -1001234567890).")

    # 1. Resolve Target Channel Peer to prevent PeerIdInvalid errors later
    if not await try_resolve(client, target_id):
        return await message.reply_text(
            "⚠️ **Could not resolve Target Channel!**\n"
            "Make sure the Bot is added as an **Admin** in the target channel first."
        )

    # 2. Save/Update Mapping in DB
    story_slug = await db.add_mapping(source_id, story_name, target_id)
    
    await message.reply_text(
        f"✅ **Source Mapping Added/Updated!**\n\n"
        f"📡 **Source Channel:** `{source_id}`\n"
        f"📖 **Story:** `{story_name}` (slug: `{story_slug}`)\n"
        f"🎯 **Target Channel:** `{target_id}`"
    )
    
    await log(
        client,
        f"➕ **New source channel mapping added**\n"
        f"Source: `{source_id}`\n"
        f"Story: *{story_name}*\n"
        f"Target: `{target_id}`\n"
        f"By: {message.from_user.mention}",
    )


@Client.on_message(filters.command("removesource") & filters.private)
async def remove_source_cmd(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return await message.reply_text("You are not authorized to use this command.")

    parts = message.text.split()
    if len(parts) < 2:
        return await message.reply_text(
            "Usage:\n`/removesource <source_channel_id>` (removes all targets)\n"
            "OR\n`/removesource <source_channel_id> <target_channel_id>` (removes specific target)"
        )

    try:
        source_id = int(parts[1].strip())
        target_id = int(parts[2].strip()) if len(parts) > 2 else None
    except ValueError:
        return await message.reply_text("Channel IDs must be numeric.")

    await db.remove_mapping(source_id, target_id)
    
    if target_id:
        await message.reply_text(f"Removed Target Channel `{target_id}` from Source `{source_id}`.")
    else:
        await message.reply_text(f"All mappings for Source Channel `{source_id}` removed.")

    await log(client, f"➖ **Source mapping removed**: `{source_id}` by {message.from_user.mention}")


@Client.on_message(filters.command("listsources") & filters.private)
async def list_sources_cmd(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return await message.reply_text("You are not authorized to use this command.")

    mappings = await db.list_mappings()
    if not mappings:
        return await message.reply_text("No source channels added yet.")

    lines = []
    for m in mappings:
        source_id = m.get("source_channel_id") or m.get("_id")
        lines.append(
            f"• `{source_id}` ➔ *{m['story_name']}* (`{m['story_slug']}`) ➔ `{m['target_channel_id']}`"
        )

    await message.reply_text("**Mapped Channels List:**\n\n" + "\n".join(lines))


# ---------------- Log channel ----------------

@Client.on_message(filters.command("addlogchannel") & filters.private)
async def add_log_channel_cmd(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return await message.reply_text("You are not authorized to use this command.")

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.reply_text(
            "Usage: `/addlogchannel <log_channel_id>`\n\n"
            "Tip: Add the bot as admin in that channel first."
        )

    try:
        log_channel_id = int(parts[1].strip())
    except ValueError:
        return await message.reply_text("Channel ID must be numeric.")

    # Safe peer resolution for log channel
    if not await try_resolve(client, log_channel_id):
        return await message.reply_text(
            "⚠️ Could not access the Log Channel. Make sure the bot is added as Admin there first."
        )

    await db.set_log_channel(log_channel_id)
    await message.reply_text(f"Log channel set to `{log_channel_id}`.")

    try:
        await client.send_message(log_channel_id, "✅ This channel is now set as the log channel for the bot.")
    except Exception as e:
        await message.reply_text(
            f"Saved, but I couldn't send a test message there.\n({e})"
        )
