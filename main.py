import asyncio
import logging
import os
from aiohttp import web
from pyrogram import Client, idle

import config
import database as db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("episode_bot")

app = Client(
    config.SESSION_NAME,
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
    plugins=dict(root="plugins"),
)


# --- Render Health Check Route ---
async def handle_health_check(request):
    return web.Response(text="Bot is alive and running!", status=200)


async def start_web_server():
    server = web.Application()
    server.router.add_get("/", handle_health_check)
    runner = web.AppRunner(server)
    await runner.setup()

    # Port detection for Render
    port = int(os.environ.get("PORT", getattr(config, "PORT", 8080)))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Health-check web server started on port {port}")


# --- Main Async Boot Function ---
async def main():
    # 1. Web Server Start (Render Port Scan Satisfied Immediately)
    await start_web_server()

    # 2. Pyrogram Client Start
    logger.info("Starting Pyrogram Client...")
    await app.start()
    logger.info("Pyrogram Client started successfully.")

    # 3. Pre-resolve Mapped Target Channels into Pyrogram Cache
    try:
        mappings = await db.get_all_mappings() if hasattr(db, "get_all_mappings") else []
        for mapping in mappings:
            target_id = mapping.get("target_channel_id")
            if target_id:
                try:
                    await app.get_chat(target_id)
                    logger.info(f"Pre-resolved target channel: {target_id}")
                except Exception as e:
                    logger.warning(f"Could not pre-resolve target channel {target_id}: {e}")
    except Exception as e:
        logger.warning(f"Could not load mappings on startup: {e}")

    # 4. Send Bot Startup Log Notification (Direct Pattern)
    try:
        log_channel_id = (
            await db.get_log_channel()
            if hasattr(db, "get_log_channel")
            else getattr(config, "LOG_CHANNEL", None)
        )
        
        if log_channel_id:
            startup_msg = (
                "🚀 **ʙᴏᴛ sᴛᴀʀᴛᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ!**\n\n"
                "• **sʏsᴛᴇᴍ:** ᴏɴʟɪɴᴇ\n"
                "• **ᴀᴜᴛᴏ-ɪɴᴅᴜᴄᴛɪᴏɴ:** ᴀᴄᴛɪᴠᴇ"
            )
            
            # Filter Bot Pattern: Always resolve channel object first
            log_chat = await app.get_chat(log_channel_id)
            await app.send_message(chat_id=log_chat.id, text=startup_msg)
            logger.info("Startup notification sent to log channel.")
            
    except Exception as e:
        logger.error(f"Failed to send startup log notification: {e}")

    # 5. Keep Bot Active
    await idle()
    await app.stop()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
