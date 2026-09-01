from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import RPCError

import config
import database as db
from episode_parser import parse_episodes
from keyboard import build_batch_keyboard
from log_utils import log
from utils import slugify


def chunk_list(items, size):
    return [items[i:i + size] for i in range(0, len(items), size)]


@Client.on_message(filters.channel & (filters.document | filters.video | filters.audio))
async def source_channel_handler(client: Client, message: Message):
    source_id = message.chat.id
    mapping = await db.get_mapping(source_id)
    if not mapping:
        return  # this channel isn't registered as a source, ignore

    story_name = mapping["story_name"]
    target_channel_id = mapping["target_channel_id"]

    story_slug = mapping.get("story_slug")
    if not story_slug:
        story_slug = slugify(story_name)
        await db.backfill_story_slug(source_id, story_slug)

    caption = message.caption or ""
    episode_numbers = parse_episodes(caption)

    file_id = None
    if message.document:
        file_id = message.document.file_id
    elif message.video:
        file_id = message.video.file_id
    elif message.audio:
        file_id = message.audio.file_id

    if not file_id:
        return

    for ep_no in episode_numbers:
        await db.save_episode(story_slug, ep_no, file_id, message.id, source_id)
        await db.add_pending_episode(story_slug, int(ep_no))

    updated_story = await db.increment_pending_file_count(story_slug)
    pending_file_count = updated_story.get("pending_file_count", 0)

    await log(
        client,
        f"📥 **ɴᴇᴡ ғɪʟᴇ ʀᴇᴄᴇɪᴠᴇᴅ**\nsᴛᴏʀʏ: *{story_name}*\n"
        f"ᴇᴘɪsᴏᴅᴇ(s): {', '.join(episode_numbers)}\n"
        f"ʙᴜғғᴇʀ: {pending_file_count}/{config.FILES_PER_BLOCK} ғɪʟᴇs",
    )

    if pending_file_count < config.FILES_PER_BLOCK:
        return  # not enough new files yet, wait for more before posting a block

    pending_episodes = sorted(set(updated_story.get("pending_episodes", [])))
    if not pending_episodes:
        await db.reset_pending(story_slug)
        return

    chunks = chunk_list(pending_episodes, config.BATCH_SIZE)
    keyboard = build_batch_keyboard(config.BOT_USERNAME, story_slug, chunks)

    text = (
        f"**{story_name}**\n"
        f"ᴇᴘs {pending_episodes[0]}-{pending_episodes[-1]}\n\n"
        f"ᴛᴀᴘ ᴀ ʙᴀᴛᴄʜ ᴛᴏ ɢᴇᴛ ɪᴛ ɪɴ ʏᴏᴜʀ ᴅᴍ 👇"
    )

    # Automatic Peer ID Fix for Target Channel
    try:
        await client.send_message(target_channel_id, text, reply_markup=keyboard)
    except (ValueError, RPCError):
        try:
            chat = await client.get_chat(target_channel_id)
            await client.send_message(chat.id, text, reply_markup=keyboard)
        except Exception as e:
            await log(client, f"❌ **ғᴀɪʟᴇᴅ ᴛᴏ ᴘᴏsᴛ ʙᴀᴛᴄʜ ᴛᴏ {target_channel_id}:** `{e}`")

    await db.reset_pending(story_slug)

    await log(
        client,
        f"📦 **ɴᴇᴡ ʙᴀᴛᴄʜ ʙʟᴏᴄᴋ ᴘᴏsᴛᴇᴅ**\nsᴛᴏʀʏ: *{story_name}*\n"
        f"ʀᴀɴɢᴇ: {pending_episodes[0]}-{pending_episodes[-1]}",
    )
