import logging
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup

import config
import database as db
from episode_parser import extract_story_info
from dashboard_format import get_dashboard_text
from utils import slugify
from keyboard import create_batch_button, build_batch_keyboard_2col
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

    # 6. LIVE DASHBOARD CARD UPDATE (Progress track karne ke liye)
    dashboard_msg_id = await db.get_dashboard_msg_id(story_slug, target_channel_id)
    
    # 7. BATCH LIMIT REACHED -> ATTACH SINGLE BATCH BUTTON IN 2-COL GRID
    if pending_file_count >= config.FILES_PER_BLOCK:
        pending_episodes = await db.get_pending_episodes(story_slug)
        if pending_episodes:
            pending_episodes.sort()

            # बफ़र की मिनिमम और मैक्सिमम रेंज निकालें (उदा: 1-10, 11-20)
            start_ep = pending_episodes[0]
            end_ep = pending_episodes[-1]

            bot_username = getattr(config, "BOT_USERNAME", "") or (await client.get_me()).username

            # 1 से 5 फाइलों का एक ही बटन बनाएगा
            new_btn = create_batch_button(bot_username, story_slug, start_ep, end_ep)

            # पुराना Dashboard Fetch करें ताकि उसके कीबोर्ड को रिड्यूस/अपेंड किया जा सके
            existing_keyboard = None
            if dashboard_msg_id:
                try:
                    old_dash_msg = await client.get_messages(chat_id=target_channel_id, message_ids=dashboard_msg_id)
                    if old_dash_msg and old_dash_msg.reply_markup:
                        existing_keyboard = old_dash_msg.reply_markup
                except Exception as e:
                    logger.warning(f"Could not fetch old dashboard keyboard: {e}")

            # नए बटन को 2-Column Grid में अटैच करें
            updated_keyboard = build_batch_keyboard_2col(existing_keyboard, new_btn)

            # डैशबोर्ड का टेक्स्ट (स्क्रीनशॉट वाला फॉर्मेट)
            dash_card_text = (
                f"**{story_name}**\n"
                f"EPS 1-{end_ep}\n\n"
                f"Tap a batch to get it in your DM 👆"
            )

            # Pinned Dashboard update / send करें
            if dashboard_msg_id:
                try:
                    await client.edit_message_text(
                        chat_id=target_channel_id,
                        message_id=dashboard_msg_id,
                        text=dash_card_text,
                        reply_markup=updated_keyboard
                    )
                except Exception:
                    dashboard_msg_id = None

            if not dashboard_msg_id:
                try:
                    new_dash = await client.send_message(
                        chat_id=target_channel_id,
                        text=dash_card_text,
                        reply_markup=updated_keyboard
                    )
                    await db.set_dashboard_msg_id(story_slug, target_channel_id, new_dash.id)
                    dashboard_msg_id = new_dash.id
                    try:
                        await new_dash.pin(disable_notification=True)
                    except Exception:
                        pass
                except Exception as e:
                    logger.error(f"Failed to post main dashboard card to {target_channel_id}: {e}")

            # Reset Buffer & Block Increment
            await db.reset_pending(story_slug)
            await db.increment_block_count(story_slug)

    else:
        # अगर 5 फाइलें पूरी नहीं हुई हैं तो लाइव बफ़र स्टेटस अपडेट करें
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
                try:
                    await new_dash.pin(disable_notification=True)
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"Failed to send buffer status to {target_channel_id}: {e}")
