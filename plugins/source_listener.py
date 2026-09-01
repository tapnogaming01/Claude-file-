import logging
from pyrogram import Client, filters
from pyrogram.types import Message

import config
import database as db
from episode_parser import extract_story_info
from dashboard_format import get_dashboard_text
from utils import slugify
from keyboard import build_batch_keyboard, chunk_episodes
from peer_utils import try_resolve
from log_utils import log

logger = logging.getLogger(__name__)


@Client.on_message(filters.channel & (filters.document | filters.video | filters.audio))
async def source_channel_handler(client: Client, message: Message):
    source_id = message.chat.id
    
    # 1. इस Source Channel की सभी Target Mappings फ़ेच करें
    mappings = await db.get_mappings_by_source(source_id)
    if not mappings:
        return

    caption = message.caption or (message.document.file_name if message.document else "")
    if not caption:
        return

    # 2. Captions से Story Name और Episodes निकालें
    extracted_name, episode_numbers = extract_story_info(caption)
    if not episode_numbers:
        return

    # Extracted name को Slugify करें
    extracted_slug = slugify(extracted_name) if extracted_name else ""

    # 3. EXACT STORY MATCHING LOGIC
    matched_mapping = None
    caption_lower = caption.lower()

    for m in mappings:
        m_slug = m.get("story_slug", "")
        m_name = m.get("story_name", "").lower()

        # (A) Check if Slug matches
        if extracted_slug and (extracted_slug in m_slug or m_slug in extracted_slug):
            matched_mapping = m
            break
        
        # (B) Check if Story Name is directly inside Caption text
        if m_name and m_name in caption_lower:
            matched_mapping = m
            break

    # 🚨 STRICT CHECK: अगर किसी भी Mapped Story से नाम मैच नहीं हुआ तो आगे न बढ़ें!
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

    # 5. SAVE EPISODE & BUFFER INCREMENTS FOR MATCHED STORY ONLY
    for ep_no in episode_numbers:
        await db.save_episode(story_slug, str(ep_no), file_id, message.id, source_id)
        await db.add_pending_episode(story_slug, int(ep_no))

    updated_story = await db.increment_pending_file_count(story_slug)
    pending_file_count = updated_story.get("pending_file_count", 0)
    total_blocks = updated_story.get("total_blocks", 0)

    # 6. LIVE DASHBOARD CARD UPDATE (Only in Match Target Channel)
    dashboard_msg_id = await db.get_dashboard_msg_id(story_slug, target_channel_id)
    dashboard_text = get_dashboard_text(
        story_name=story_name,
        total_blocks=total_blocks,
        current_buffer=pending_file_count,
        max_buffer=config.FILES_PER_BLOCK
    )

    if dashboard_msg_id:
        try:
            await client.edit_message_text(
                chat_id=target_channel_id,
                message_id=dashboard_msg_id,
                text=dashboard_text
            )
        except Exception:
            dashboard_msg_id = None

    if not dashboard_msg_id:
        try:
            new_dash = await client.send_message(
                chat_id=target_channel_id,
                text=dashboard_text
            )
            await db.set_dashboard_msg_id(story_slug, target_channel_id, new_dash.id)
            dashboard_msg_id = new_dash.id
            try:
                await new_dash.pin(disable_notification=True)
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Failed to send dashboard to {target_channel_id}: {e}")

    # 7. BATCH LIMIT REACHED -> POST BUTTONS
    if pending_file_count >= config.FILES_PER_BLOCK:
        pending_episodes = await db.get_pending_episodes(story_slug)
        if pending_episodes:
            pending_episodes.sort()

            batch_size = getattr(config, "BATCH_SIZE", 10)
            chunks = chunk_episodes(pending_episodes, batch_size)
            keyboard = build_batch_keyboard(config.BOT_USERNAME, story_slug, chunks)

            post_text = (
                f"🔥 **{story_name}**\n\n"
                f"📦 **Episodes:** `{pending_episodes[0]}` - `{pending_episodes[-1]}`\n"
                f"👇 नीचे दिए गए बटन पर क्लिक करके देखें:"
            )

            await client.send_message(
                chat_id=target_channel_id,
                text=post_text,
                reply_markup=keyboard
            )

            # Reset Buffer & Block Increment
            await db.reset_pending(story_slug)
            await db.increment_block_count(story_slug)

            # Reset Live Dashboard to 0 Buffer
            updated_dash_text = get_dashboard_text(
                story_name=story_name,
                total_blocks=total_blocks + 1,
                current_buffer=0,
                max_buffer=config.FILES_PER_BLOCK
            )
            if dashboard_msg_id:
                try:
                    await client.edit_message_text(
                        chat_id=target_channel_id,
                        message_id=dashboard_msg_id,
                        text=updated_dash_text
                    )
                except Exception:
                    pass
