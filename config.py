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
ADMINS = [int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()]
ADMIN_IDS = ADMINS  # Compatibility alias

# ---- Batching ----
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "10"))
FILES_PER_BLOCK = int(os.environ.get("FILES_PER_BLOCK", "5"))

# ---- Dynamic Force Sub Defaults ----
DEFAULT_FORCE_SUB_CHANNEL = os.environ.get("FORCE_SUB_CHANNEL", "")  # e.g. "@MyChannel" or "-100xxx"
DEFAULT_FORCE_SUB_STATUS = os.environ.get("FORCE_SUB_STATUS", "True").lower() == "true"

# ---- Dynamic Content Protection Default ----
PROTECT_CONTENT = os.environ.get("PROTECT_CONTENT", "False").lower() == "true"

# ---- Shortener & Verification Defaults ----
SHORTENER_API_URL = os.environ.get("SHORTENER_API_URL", "gplinks.in")
SHORTENER_API_KEY = os.environ.get("SHORTENER_API_KEY", "")

# Token Expiry Time in Seconds (Default: 86400 Seconds = 24 Hours)
VERIFY_EXPIRE_TIME = int(os.environ.get("VERIFY_EXPIRE_TIME", "86400"))

# ---- Render & Server ----
PORT = int(os.environ.get("PORT", "8080"))
SESSION_NAME = os.environ.get("SESSION_NAME", "episode_bot")

# Auto-Delete Configuration (0 = OFF, 600 = 10 Minutes, 3600 = 1 Hour)
AUTO_DELETE_TIME = int(os.environ.get("AUTO_DELETE_TIME", "600"))
