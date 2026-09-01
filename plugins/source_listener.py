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
    
    # 1. FETCH MULTIPLE TARGET MAPPINGS FOR THIS SOURCE
    mappings = await db.get_mappings(source_id)
    if not mappings:
        return

    caption = message.caption or message.document.file_name or ""

    # SMART STORY DETECTION
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

    # LOOP THROUGH ALL MAPPED TARGET CHANNELS
    for mapping in mappings:
        target_channel_id = mapping["target_channel_id"]
        story_slug = mapping.get("story_slug") or slugify(extracted_name or "story")
        story_name = mapping.get("story_name", extracted_name or "Story")

        # 2. SAFE PEER RESOLUTION
        if not await try_resolve(client, target_channel_id):
            logger.error(f"Cannot resolve peer for target channel: {target_channel_id}")
            continue

        # SAVE FILE & INCREMENT BUFFER
        for ep_no in episode_numbers:
            await db.save_episode(story_slug, str(ep_no), file_id, message.id, source_id)
            await db.add_pending_episode(story_slug, int(ep_no))

        updated_story = await db.increment_pending_file_count(story_slug)
        pending_file_count = updated_story.get("pending_file_count", 0)
        total_blocks = updated_story.get("total_blocks", 0)

        # 3. PERMANENT LIVE TRACKING DASHBOARD CARD
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
            except Exception as e:
                logger.warning(f"Failed to edit dashboard on {target_channel_id}: {e}")
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
                logger.error(f"Failed to send dashboard message to {target_channel_id}: {e}")

        # 4. IF BUFFER REACHES LIMIT -> POST BATCH BUTTON BLOCK
        if pending_file_count >= config.FILES_PER_BLOCK:
            pending_episodes = await db.get_pending_episodes(story_slug)
            if pending_episodes:
                pending_episodes.sort()

                batch_size = getattr(config, "BATCH_SIZE", 10)
                chunks = chunk_episodes(pending_episodes, batch_size)
                
                # Direct deep link keyboard generation
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
                            chat_id=target_channel_id,
                            message_id=dashboard_msg_id,
                            text=updated_dash_text
                        )
                    except Exception:
                        pass

                await log(
                    client,
                    f"✅ **Batch Posted Successfully!**\nTarget Channel: `{target_channel_id}`\nStory: {story_name}\nEpisodes: {pending_episodes[0]}-{pending_episodes[-1]}"
                )
