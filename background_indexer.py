import asyncio
import logging
from pyrogram import Client
import database as db
from dashboard_format import get_dashboard_text
from log_utils import log

logger = logging.getLogger("episode_bot")

async def start_background_indexing(client: Client):
    """
    यह बैकग्राउंड टास्क हमेशा चलता रहेगा और हर 60 सेकंड में 
    टारगेट चैनल के डैशबोर्ड कार्ड (Pinned Message) को अपडेट करता रहेगा।
    """
    logger.info("Starting Background Auto-Indexing Engine...")
    
    while True:
        try:
            # 1. डेटाबेस से सभी एक्टिव स्टोरीज़/मैपिंग्स उठाएं
            all_mappings = await db.get_all_mappings() if hasattr(db, "get_all_mappings") else []
            
            for mapping in all_mappings:
                source_id = mapping.get("source_channel_id")
                target_id = mapping.get("target_channel_id")
                
                if not target_id:
                    continue

                # स्टोरी की डिटेल्स डेटाबेस से फ़ेच करें
                stories = await db.get_stories_by_source(source_id) if hasattr(db, "get_stories_by_source") else []
                
                for story in stories:
                    story_name = story.get("story_name")
                    story_slug = story.get("story_slug")
                    pending_count = story.get("pending_file_count", 0)
                    total_blocks = story.get("total_blocks", 0)
                    dashboard_msg_id = story.get("dashboard_msg_id")

                    if not story_slug or not dashboard_msg_id:
                        continue

                    # 2. नया लाइव डैशबोर्ड टेक्स्ट जनरेट करें
                    updated_text = get_dashboard_text(
                        story_name=story_name,
                        total_blocks=total_blocks,
                        current_buffer=pending_count,
                        max_buffer=5
                    )

                    # 3. चैनल का Peer Resolve करें और मैसेज Edit करें
                    try:
                        target_chat = await client.get_chat(target_id)
                        await client.edit_message_text(
                            chat_id=target_chat.id,
                            message_id=dashboard_msg_id,
                            text=updated_text
                        )
                    except Exception as err:
                        # अगर मैसेज बदला ही नहीं है (Same Content) तो Ignore करें
                        if "MESSAGE_NOT_MODIFIED" not in str(err):
                            logger.warning(f"Could not update dashboard for {story_slug}: {err}")

        except Exception as e:
            logger.error(f"Error in background indexing loop: {e}")

        # हर 60 सेकंड (1 मिनट) के बाद फिर से चेक करेगा
        await asyncio.sleep(60)
          
