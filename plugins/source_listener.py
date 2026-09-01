import re
from pyrogram import Client, filters
from pyrogram.types import Message

import config
import database as db
from keyboard import build_batch_keyboard
from log_utils import log
from utils import slugify

# Improved Episode Range Extractor
def parse_episodes(text: str) -> list[str]:
    """
    Extracts all episodes including ranges like '9 to 11', '9-11', '9 - 11', 'EP 9 TO 11'.
    Returns a list of individual episode strings e.g. ["9", "10", "11"]
    """
    if not text:
        return []

    # Detect range patterns (e.g., "9 to 11", "09-11", "ep 09 to 11")
    range_match = re.search(r'(\d+)\s*(?:to|-|\bto\b)\s*(\d+)', text, re.IGNORECASE)
    if range_match:
        start_ep = int(range_match.group(1))
        end_ep = int(range_match.group(2))
        if start_ep <= end_ep:
            return [str(ep) for ep in range(start_ep, end_ep + 1)]

    # Fallback to single numbers or list of numbers
    return re.findall(r'\b\d+\b', text)


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
    episode_numbers = parse_episodes(caption)  # Now correctly parses ranges like '9 to 11'

    file_id = None
    if message.document:
        file_id = message.document.file_id
    elif message.video:
        file_id = message.video.file_id
    elif message.audio:
        file_id = message.audio.file_id

    if not file_id:
        return

    # Save every episode this file covers
    for ep_no in episode_numbers:
        await db.save_episode(story_slug, ep_no, file_id, message.id, source_id)
        await db.add_pending_episode(story_slug, int(ep_no))

    updated_story = await db.increment_pending_file_count(story_slug)
    pending_file_count = updated_story.get("pending_file_count", 0)

    await log(
        client,
        f"\U0001F4E5 **New file received**\nStory: *{story_name}*\n"
        f"Episode(s): {', '.join(episode_numbers)}\n"
        f"Buffer: {pending_file_count}/{config.FILES_PER_BLOCK} files",
    )

    if pending_file_count < config.FILES_PER_BLOCK:
        return

    pending_episodes = sorted(set(updated_story.get("pending_episodes", [])))
    if not pending_episodes:
        await db.reset_pending(story_slug)
        return

    chunks = chunk_list(pending_episodes, config.BATCH_SIZE)
    keyboard = build_batch_keyboard(config.BOT_USERNAME, story_slug, chunks)

    text = (
        f"**{story_name}**\n"
        f"EPS {pending_episodes[0]}-{pending_episodes[-1]}\n\n"
        f"Tap a batch to get it in your DM \U0001F447"
    )

    # Solution 1: Handled Peer ID Invalid error gracefully using try-except
    try:
        await client.send_message(target_channel_id, text, reply_markup=keyboard)
    except ValueError:
        # Resolves channel peer automatically if missing in session cache
        chat = await client.get_chat(target_channel_id)
        await client.send_message(chat.id, text, reply_markup=keyboard)

    await db.reset_pending(story_slug)

    await log(
        client,
        f"\U0001F4E6 **New batch block posted**\nStory: *{story_name}*\n"
        f"Range: {pending_episodes[0]}-{pending_episodes[-1]}",
    )
