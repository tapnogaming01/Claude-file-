import os

# ---- Telegram / Pyrogram credentials ----
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# Bot's own @username (without the @), needed to build deep links like
# https://t.me/YourBot?start=batch-slug-1-10
BOT_USERNAME = os.environ.get("BOT_USERNAME", "")

# ---- MongoDB ----
MONGO_URI = os.environ.get("MONGO_URI", "")
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "episode_bot")

# ---- Admins ----
# Comma separated Telegram user IDs allowed to use /addsource etc.
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()]

# ---- Batching ----
# How many episodes are grouped into a single batch button, e.g. "211-220"
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "10"))
# How many new files must arrive before a new batch block is posted
FILES_PER_BLOCK = int(os.environ.get("FILES_PER_BLOCK", "5"))

# ---- Render ----
# Render injects PORT automatically for Web Services.
PORT = int(os.environ.get("PORT", "8080"))

SESSION_NAME = os.environ.get("SESSION_NAME", "episode_bot")
