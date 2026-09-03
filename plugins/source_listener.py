import logging
from pyrogram import Client, filters
from pyrogram.types import Message

import config
import database as db
from episode_parser import extract_story_info
from utils import slugify
from keyboard import build_grid_keyboard_from_captions, to_small_caps
from peer_utils import try_resolve

logger = logging.getLogger(__name__)


@Client.on_message(filters.channel & (filters.document | filters.video | filters.audio))
async def source_channel_handler(client: Client, message: Message):
    source_id = message.chat.id
    
    # 1. Fetch Target Mappings for Source Channel
    mappings = await db.get_mappings_by_source(source_id)
    if not mappings:
        return

    caption = message.caption or (message.document.file_name if message.document else "")
    if not caption:
        return

    # 2. Extract Story Name & Episode Numbers
    extracted_name, episode_numbers = extract_story_info(caption)
    if not episode_numbers:
        return

    extracted_slug = slugify(extracted_name) if extracted_name else ""

    # 3. Exact Story Matching Logic
    matched_mapping = None
    caption_lower = caption.lower()

    for m in mappings:
        m_slug = m.get("story_slug", "")
        m_name = m.get("story_name", "").lower()

        if extracted_slug and (extracted_slug in m_slug or m_slug in extracted_slug):
            matched_mapping = m
            break
        
        if m_name and m_name in caption_lower:
            matched_mapping = m
            break

    if not matched_mapping:
        logger.warning(f"No mapped story found matching caption: '{caption}'")
        return

    target_channel_id = matched_mapping["target_channel_id"]
    story_slug = matched_mapping["story_slug"]
    story_name = matched_mapping["story_name"]

    # 4. Safe Peer Resolution
    if not await try_resolve(client, target_channel_id):
        logger.error(f"Cannot resolve peer for target channel: {target_channel_id}")
        return

    file_id = message.document.file_id if message.document else (message.video.file_id if message.video else message.audio.file_id)
    if not file_id:
        return

    # Extract Range for current file (e.g., Ep 11 to 21 -> start: 11, end: 21)
    ep_start = min(episode_numbers)
    ep_end = max(episode_numbers)

    # 5. Save Episodes & Buffer Ranges
    for ep_no in episode_numbers:
        await db.save_episode(story_slug, str(ep_no), file_id, message.id, source_id)

    # Save per-file caption range in DB pending list
    await db.add_pending_range(story_slug, ep_start, ep_end)

    updated_story = await db.increment_pending_file_count(story_slug)
    pending_file_count = updated_story.get("pending_file_count", 0)

    # 6. BATCH LIMIT REACHED (5 Files Completed) -> Post Premium Card
    if pending_file_count >= config.FILES_PER_BLOCK:
        caption_ranges = await db.get_pending_ranges(story_slug)
        if caption_ranges:
            bot_username = getattr(config, "BOT_USERNAME", "") or (await client.get_me()).username
            
            # Generate 2-Column Grid Keyboard with Small Caps Utility Buttons
            keyboard = build_grid_keyboard_from_captions(caption_ranges, bot_username, story_slug)

            max_ep = max(r[1] for r in caption_ranges)
            min_ep = min(r[0] for r in caption_ranges)

            # Small Caps Text Formatting
            formatted_title = to_small_caps(story_name)
            eps_label = to_small_caps("EPS")

            post_text = (
                f"✨ **{formatted_title}**\n"
                f"⚡ **{eps_label} {min_ep} - {max_ep}**"
            )

            try:
                await client.send_message(
                    chat_id=target_channel_id,
                    text=post_text,
                    reply_markup=keyboard
                )
            except Exception as e:
                logger.error(f"Failed to post card to {target_channel_id}: {e}")

            # Reset Buffer & Pending Ranges
            await db.reset_pending_ranges(story_slug)
            await db.reset_pending(story_slug)
            await db.increment_block_count(story_slug)
