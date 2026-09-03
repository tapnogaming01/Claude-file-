import logging
from pyrogram import Client, filters
from pyrogram.types import Message

import config
import database as db
from keyboard import build_grid_keyboard_from_captions, to_small_caps
from log_utils import log
from peer_utils import try_resolve

logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


# ---------------- Source channel mapping ----------------

@Client.on_message(filters.command("addsource") & filters.private)
async def add_source_cmd(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return await message.reply_text(f"❌ {to_small_caps('You are not authorized to use this command.')}")

    parts = message.text.split(maxsplit=3)
    if len(parts) < 4:
        usage_text = to_small_caps("Usage")
        example_text = to_small_caps("Example")
        return await message.reply_text(
            f"⚠️ **{usage_text}:**\n`/addsource <source_channel_id> <story_name> <target_channel_id>`\n\n"
            f"📌 **{example_text}:**\n`/addsource -1001111111111 MyPossessiveThing -1002222222222`"
        )

    _, source_id_str, story_name, target_id_str = parts
    try:
        source_id = int(source_id_str)
        target_id = int(target_id_str)
    except ValueError:
        return await message.reply_text(f"❌ {to_small_caps('Channel IDs must be numeric.')}")

    # 1. Resolve Target Channel Peer
    if not await try_resolve(client, target_id):
        warning_msg = to_small_caps("Could not resolve Target Channel. Make sure Bot is Admin there first.")
        return await message.reply_text(f"⚠️ **{warning_msg}**")

    # 2. Save/Update Mapping in DB
    story_slug = await db.add_mapping(source_id, story_name, target_id)
    
    title_text = to_small_caps("Source Mapping Added/Updated")
    source_label = to_small_caps("Source Channel")
    story_label = to_small_caps("Story")
    target_label = to_small_caps("Target Channel")

    await message.reply_text(
        f"✅ **{title_text}!**\n\n"
        f"📡 **{source_label}:** `{source_id}`\n"
        f"📖 **{story_label}:** `{story_name}` (`{story_slug}`)\n"
        f"🎯 **{target_label}:** `{target_id}`"
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
        return await message.reply_text(f"❌ {to_small_caps('You are not authorized to use this command.')}")

    parts = message.text.split()
    if len(parts) < 2:
        usage_text = to_small_caps("Usage")
        return await message.reply_text(
            f"⚠️ **{usage_text}:**\n"
            f"`/removesource <source_channel_id>` (Removes all targets)\n"
            f"`/removesource <source_channel_id> <target_channel_id>` (Removes specific target)"
        )

    try:
        source_id = int(parts[1].strip())
        target_id = int(parts[2].strip()) if len(parts) > 2 else None
    except ValueError:
        return await message.reply_text(f"❌ {to_small_caps('Channel IDs must be numeric.')}")

    await db.remove_mapping(source_id, target_id)
    
    if target_id:
        msg = to_small_caps("Removed Target Channel")
        await message.reply_text(f"✅ {msg} `{target_id}` from Source `{source_id}`.")
    else:
        msg = to_small_caps("All mappings for Source Channel removed")
        await message.reply_text(f"✅ {msg} `{source_id}`.")

    await log(client, f"➖ **Source mapping removed**: `{source_id}` by {message.from_user.mention}")


@Client.on_message(filters.command("listsources") & filters.private)
async def list_sources_cmd(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return await message.reply_text(f"❌ {to_small_caps('You are not authorized to use this command.')}")

    mappings = await db.list_mappings()
    if not mappings:
        return await message.reply_text(f"ℹ️ {to_small_caps('No source channels added yet.')}")

    lines = []
    for m in mappings:
        source_id = m.get("source_channel_id") or m.get("_id")
        lines.append(
            f"• `{source_id}` ➔ *{m['story_name']}* (`{m['story_slug']}`) ➔ `{m['target_channel_id']}`"
        )

    title_text = to_small_caps("Mapped Channels List")
    await message.reply_text(f"📜 **{title_text}:**\n\n" + "\n".join(lines))


# ---------------- Story Complete / Flush Buffer ----------------

@Client.on_message(filters.command("complete") & filters.private)
async def complete_story_cmd(client: Client, message: Message):
    """
    Usage: /complete <story_slug>
    Force-posts leftover pending episodes for completed stories (when buffer < 5).
    """
    if not is_admin(message.from_user.id):
        return await message.reply_text(f"❌ {to_small_caps('You are not authorized to use this command.')}")

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        usage_text = to_small_caps("Usage")
        example_text = to_small_caps("Example")
        return await message.reply_text(
            f"⚠️ **{usage_text}:** `/complete <story_slug>`\n"
            f"📌 **{example_text}:** `/complete destined-bride`"
        )

    story_slug = parts[1].strip()

    # 1. Check if mapping or story exists
    mapping = await db.get_mapping_by_slug(story_slug) if hasattr(db, "get_mapping_by_slug") else None
    
    if not mapping:
        # Fallback search from list
        all_mappings = await db.list_mappings()
        for m in all_mappings:
            if m.get("story_slug") == story_slug:
                mapping = m
                break

    if not mapping:
        return await message.reply_text(f"❌ {to_small_caps('Story slug not found in mappings.')}")

    target_channel_id = mapping.get("target_channel_id")
    story_name = mapping.get("story_name", story_slug)

    if not await try_resolve(client, target_channel_id):
        return await message.reply_text(f"❌ {to_small_caps('Failed to resolve target channel peer.')}")

    # 2. Get Leftover Pending Ranges
    caption_ranges = await db.get_pending_ranges(story_slug)
    if not caption_ranges:
        return await message.reply_text(f"ℹ️ {to_small_caps('Buffer is already empty for this story.')}")

    bot_username = getattr(config, "BOT_USERNAME", "") or (await client.get_me()).username
    keyboard = build_grid_keyboard_from_captions(caption_ranges, bot_username, story_slug)

    max_ep = max(r[1] for r in caption_ranges)
    min_ep = min(r[0] for r in caption_ranges)

    formatted_title = to_small_caps(story_name)
    eps_label = to_small_caps("EPS")
    completed_label = to_small_caps("COMPLETED")

    post_text = (
        f"✨ **{formatted_title}**\n"
        f"🏆 **{eps_label} {min_ep} - {max_ep} [{completed_label}]**"
    )

    try:
        # Send Final Card to Target Channel
        await client.send_message(
            chat_id=target_channel_id,
            text=post_text,
            reply_markup=keyboard
        )
        
        # Reset Buffer
        await db.reset_pending_ranges(story_slug)
        await db.reset_pending(story_slug)

        success_title = to_small_caps("Story Completed & Flushed Successfully")
        story_label = to_small_caps("Story")
        range_label = to_small_caps("Range Posted")

        await message.reply_text(
            f"✅ **{success_title}!**\n\n"
            f"📖 **{story_label}:** `{story_name}`\n"
            f"📦 **{range_label}:** `{min_ep} - {max_ep}`"
        )

        await log(
            client,
            f"🏁 **Story Force Completed**: `{story_name}` (`{story_slug}`)\n"
            f"Posted Range: `{min_ep} - {max_ep}`\n"
            f"By: {message.from_user.mention}"
        )

    except Exception as e:
        logger.error(f"Failed to force post complete batch for {story_slug}: {e}")
        await message.reply_text(f"❌ {to_small_caps('Error sending to channel')}: `{e}`")


# ---------------- Log channel ----------------

@Client.on_message(filters.command("addlogchannel") & filters.private)
async def add_log_channel_cmd(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return await message.reply_text(f"❌ {to_small_caps('You are not authorized to use this command.')}")

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        usage_text = to_small_caps("Usage")
        return await message.reply_text(f"⚠️ **{usage_text}:** `/addlogchannel <log_channel_id>`")

    try:
        log_channel_id = int(parts[1].strip())
    except ValueError:
        return await message.reply_text(f"❌ {to_small_caps('Channel ID must be numeric.')}")

    if not await try_resolve(client, log_channel_id):
        warning_msg = to_small_caps("Could not access Log Channel. Make sure bot is Admin there first.")
        return await message.reply_text(f"⚠️ **{warning_msg}**")

    await db.set_log_channel(log_channel_id)
    msg = to_small_caps("Log channel set to")
    await message.reply_text(f"✅ {msg} `{log_channel_id}`.")

    try:
        confirm_text = to_small_caps("This channel is now set as the log channel for the bot.")
        await client.send_message(log_channel_id, f"✅ **{confirm_text}**")
    except Exception as e:
        logger.warning(f"Failed to send test message to log channel: {e}")
