import os

# ---- Telegram / Pyrogram credentials ----
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# Bot's own @username (without the @), needed to build deep links
BOT_USERNAME = os.environ.get("BOT_USERNAME", "")

# ---- MongoDB ----
MONGO_URI = os.environ.get("MONGO_URI", "")
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "episode_bot")

# ---- Admins ----
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()]

# ---- Batching ----
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "10"))
FILES_PER_BLOCK = int(os.environ.get("FILES_PER_BLOCK", "5"))

# ---- Dynamic Force Sub Defaults ----
DEFAULT_FORCE_SUB_CHANNEL = os.environ.get("FORCE_SUB_CHANNEL", "")  # e.g. "@MyChannel" or "-100xxx"
DEFAULT_FORCE_SUB_STATUS = os.environ.get("FORCE_SUB_STATUS", "True").lower() == "true"

# ---- Shortener Defaults ----
SHORTENER_API_URL = os.environ.get("SHORTENER_API_URL", "gplinks.in")
SHORTENER_API_KEY = os.environ.get("SHORTENER_API_KEY", "")

# ---- Render ----
PORT = int(os.environ.get("PORT", "8080"))
SESSION_NAME = os.environ.get("SESSION_NAME", "episode_bot")

# 0 = OFF (फाइलें कभी डिलीट नहीं होंगी)
# Seconds: 600 = 10 Minutes, 3600 = 1 Hour
AUTO_DELETE_TIME = 600  # यहाँ सेकेंड्स में टाइम दर्ज करें
