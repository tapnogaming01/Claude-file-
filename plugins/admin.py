from pyrogram import Client, filters
from pyrogram.types import Message

import config
import database as db
from log_utils import log


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

    _, source_id, story_name, target_id = parts
    try:
        source_id = int(source_id)
        target_id = int(target_id)
    except ValueError:
        return await message.reply_text("Channel IDs must be numeric (e.g. -1001234567890).")

    story_slug = await db.add_mapping(source_id, story_name, target_id)
    await message.reply_text(
        f"Source channel added:\nSource: `{source_id}`\nStory: `{story_name}` (slug: `{story_slug}`)\n"
        f"Target: `{target_id}`"
    )
    await log(
        client,
        f"\u2795 **New source channel added**\nSource: `{source_id}`\nStory: *{story_name}*\n"
        f"Target: `{target_id}`\nBy: {message.from_user.mention}",
    )


@Client.on_message(filters.command("removesource") & filters.private)
async def remove_source_cmd(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return await message.reply_text("You are not authorized to use this command.")

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.reply_text("Usage: `/removesource <source_channel_id>`")

    try:
        source_id = int(parts[1].strip())
    except ValueError:
        return await message.reply_text("Channel ID must be numeric.")

    await db.remove_mapping(source_id)
    await message.reply_text(f"Source channel `{source_id}` removed.")
    await log(client, f"\u2796 **Source channel removed**: `{source_id}` by {message.from_user.mention}")


@Client.on_message(filters.command("listsources") & filters.private)
async def list_sources_cmd(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return await message.reply_text("You are not authorized to use this command.")

    mappings = await db.list_mappings()
    if not mappings:
        return await message.reply_text("No source channels added yet.")

    lines = [
        f"\u2022 `{m['_id']}` \u2192 *{m['story_name']}* (`{m['story_slug']}`) \u2192 `{m['target_channel_id']}`"
        for m in mappings
    ]
    await message.reply_text("\n".join(lines))


# ---------------- Log channel ----------------

@Client.on_message(filters.command("addlogchannel") & filters.private)
async def add_log_channel_cmd(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return await message.reply_text("You are not authorized to use this command.")

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.reply_text(
            "Usage: `/addlogchannel <log_channel_id>`\n\n"
            "Tip: add the bot as admin in that channel first, then run this command "
            "(get the channel ID by forwarding a message from it to @userinfobot, for example)."
        )

    try:
        log_channel_id = int(parts[1].strip())
    except ValueError:
        return await message.reply_text("Channel ID must be numeric.")

    await db.set_log_channel(log_channel_id)
    await message.reply_text(f"Log channel set to `{log_channel_id}`.")

    try:
        await client.send_message(log_channel_id, "\u2705 This channel is now set as the log channel for the bot.")
    except Exception as e:
        await message.reply_text(
            f"Saved, but I couldn't send a test message there \u2014 make sure I'm an admin in that channel.\n({e})"
        )
