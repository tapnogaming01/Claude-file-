import logging
import threading

from flask import Flask
from pyrogram import Client

import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("episode_bot")

app = Client(
    config.SESSION_NAME,
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
    plugins=dict(root="plugins"),
)

# ---------------- Render health-check web server ----------------
# Render's web-service tier expects something listening on $PORT,
# otherwise it thinks the service is dead. This tiny Flask app just
# answers "alive" so Render is happy while Pyrogram runs in the background.
web = Flask(__name__)


@web.route("/")
def home():
    return "Bot is alive", 200


def run_web():
    web.run(host="0.0.0.0", port=config.PORT)


if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    logger.info("Bot starting...")
    app.run()
