import logging
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

import config
import database as db
from episode_parser import extract_story_info
from dashboard_format import get_dashboard_text
from utils.keyboard import build_batch_keyboard, chunk_episodes
from log_utils import log

logger = logging.getLogger(__name__)

@Client.on_message(filters.channel & (filters.document | filters.video | filters.audio))
async def source_channel_handler(client: Client, message: Message):
    source_id = message.chat.id
    mapping = await db.get_mapping(source_id)
    if not mapping:
        return

    target_channel_id = mapping["target_channel_id"]
    # डेटाबेस में मैप्ड story_slug और story_name ही यूज़ करें
    story_slug = mapping.get("story_slug")
    story_name = mapping.get("story_name", "Story")

    caption = message.caption or message.document.file_name or ""

    # 1. SMART STORY DETECTION
    extracted_name, episode_numbers = extract_story_info(caption)
    if not episode_numbers:
        return

    file_id = None
    if message.document: 
        file_id = message.document.file_id
    elif message.video: 
        file_id = message.video.file_id
    elif message.audio: 
        file_id = message.audio.file_id

    if not file_id: 
        return

    # 2. SAVE FILE & INCREMENT BUFFER
    for ep_no in episode_numbers:
        await db.save_episode(story_slug, str(ep_no), file_id, message.id, source_id)
        await db.add_pending_episode(story_slug, int(ep_no))

    updated_story = await db.increment_pending_file_count(story_slug)
    pending_file_count = updated_story.get("pending_file_count", 0)
    total_blocks = updated_story.get("total_blocks", 0)

    try:
        # Resolve Target Channel Peer
        target_chat = await client.get_chat(target_channel_id)
    except Exception as e:
        logger.error(f"Failed to get target chat: {e}")
        return

    # 3. PERMANENT LIVE TRACKING DASHBOARD CARD
    dashboard_msg_id = await db.get_dashboard_msg_id(story_slug)
    dashboard_text = get_dashboard_text(
        story_name=story_name,
        total_blocks=total_blocks,
        current_buffer=pending_file_count,
        max_buffer=config.FILES_PER_BLOCK
    )

    if dashboard_msg_id:
        try:
            # पुराने परमानेंट मैसेज को ही रिफ्रेश (edit) करें
            await client.edit_message_text(
                chat_id=target_chat.id,
                message_id=dashboard_msg_id,
                text=dashboard_text
            )
        except Exception as e:
            logger.warning(f"Failed to edit dashboard, creating new one: {e}")
            dashboard_msg_id = None

    # अगर पहली बार फ़ाइल आ रही हो या पुराना मैसेज डिलीट हो गया हो
    if not dashboard_msg_id:
        try:
            new_dash = await client.send_message(
                chat_id=target_chat.id,
                text=dashboard_text
            )
            await db.set_dashboard_msg_id(story_slug, new_dash.id)
            dashboard_msg_id = new_dash.id
            try:
                await new_dash.pin(disable_notification=True)
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Failed to send dashboard message: {e}")

    # 4. IF BUFFER REACHES LIMIT (e.g., 5 FILES) -> POST BATCH BUTTON BLOCK
    if pending_file_count >= config.FILES_PER_BLOCK:
        pending_episodes = await db.get_pending_episodes(story_slug)
        if pending_episodes:
            pending_episodes.sort()
            
            # Episodes को BATCH_SIZE (जैसे 10-10) के टुकड़ों में बांटकर बटन बनाएं
            chunks = chunk_episodes(pending_episodes, config.BATCH_SIZE)
            keyboard = build_batch_keyboard(story_slug, chunks)
            
            post_text = (
                f"🔥 **{story_name}**\n\n"
                f"📦 **Episodes:** `{pending_episodes[0]}` - `{pending_episodes[-1]}`\n"
                f"👇 नीचे दिए गए बटन पर क्लिक करके फाइलें प्राप्त करें:"
            )

            # Target Channel में Batch Buttons पोस्ट करें
            await client.send_message(
                chat_id=target_chat.id,
                text=post_text,
                reply_markup=keyboard
            )

            # Reset Buffer and Increment Block Count
            await db.reset_pending(story_slug)
            await db.increment_block_count(story_slug)

            # Reset Live Dashboard Buffer to 0/5
            updated_dash_text = get_dashboard_text(
                story_name=story_name,
                total_blocks=total_blocks + 1,
                current_buffer=0,
                max_buffer=config.FILES_PER_BLOCK
            )
            if dashboard_msg_id:
                try:
                    await client.edit_message_text(
                        chat_id=target_chat.id,
                        message_id=dashboard_msg_id,
                        text=updated_dash_text
                    )
                except Exception:
                    pass

            await log(
                client,
                f"✅ **Batch Posted Successfully!**\nStory: {story_name}\nEpisodes: {pending_episodes[0]}-{pending_episodes[-1]}"
            )
