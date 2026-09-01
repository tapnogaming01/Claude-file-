import logging
from aiohttp import web
from pyrogram import Client

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


# --- Render Health Check Server (Async & Native) ---
async def handle_health_check(request):
    return web.Response(text="Bot is alive and running!", status=200)


async def start_web_server():
    server = web.Application()
    server.router.add_get("/", handle_health_check)
    runner = web.AppRunner(server)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", config.PORT)
    await site.start()
    logger.info(f"Health-check web server started on port {config.PORT}")


# --- Bot Startup Routine ---
async def on_startup(client: Client):
    # 1. Start Async Health-Check Web Server
    await start_web_server()

    # 2. Resolve Mapped Channels (Prevents Peer ID Invalid Error permanently)
    try:
        mappings = await db.get_all_mappings() if hasattr(db, "get_all_mappings") else []
        for mapping in mappings:
            target_id = mapping.get("target_channel_id")
            if target_id:
                try:
                    await client.get_chat(target_id)
                except Exception:
                    pass
    except Exception as e:
        logger.warning(f"Could not pre-resolve channels on startup: {e}")

    # 3. Send Bot Startup Log Notification
    try:
        log_channel_id = await db.get_log_channel() if hasattr(db, "get_log_channel") else getattr(config, "LOG_CHANNEL", None)
        if log_channel_id:
            await client.send_message(
                chat_id=log_channel_id,
                text="🚀 **Bot Started Successfully!**\n\n"
                     "• All systems operational.\n"
                     "• Auto-induction & File Store active."
            )
            logger.info("Startup notification sent to log channel.")
    except Exception as e:
        logger.error(f"Failed to send startup log notification: {e}")


if __name__ == "__main__":
    logger.info("Starting bot engine...")
    app.start_handler = on_startup  # Auto-executes startup logic when bot boots up
    app.run()
