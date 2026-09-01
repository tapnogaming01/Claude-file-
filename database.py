from pymongo import ReturnDocument
import motor.motor_asyncio
import time

import config
from utils import slugify

client = motor.motor_asyncio.AsyncIOMotorClient(config.MONGO_URI)
db = client[config.MONGO_DB_NAME]

mappings_col = db["mappings"]        # Multi-target mappings
stories_col = db["stories"]          # _id = story_slug
settings_col = db["settings"]        # _id = "log_channel" / "verification" / "forcesub" / "protection"
users_col = db["users"]             # _id = user_id -> {verified_at}
verify_tokens_col = db["tokens"]    # Temporary store for shortener verification tokens


# ---------------- Mappings (source channel -> story -> target channels) ----------------

async def add_mapping(source_channel_id: int, story_name: str, target_channel_id: int) -> str:
    story_slug = slugify(story_name)

    await mappings_col.update_one(
        {"source_channel_id": source_channel_id, "story_slug": story_slug},
        {"$set": {
            "source_channel_id": source_channel_id,
            "story_name": story_name,
            "story_slug": story_slug,
            "target_channel_id": target_channel_id,
        }},
        upsert=True,
    )

    existing = await stories_col.find_one({"_id": story_slug})
    if not existing:
        await stories_col.insert_one({
            "_id": story_slug,
            "name": story_name,
            "episodes": {},
            "pending_episodes": [],
            "pending_file_count": 0,
            "total_blocks": 0,
            "dashboards": {}  # Format: {target_channel_id_str: message_id}
        })

    return story_slug


async def remove_mapping(source_channel_id: int, target_channel_id: int = None):
    query = {"source_channel_id": source_channel_id}
    if target_channel_id:
        query["target_channel_id"] = target_channel_id
    await mappings_col.delete_many(query)


async def get_mappings(source_channel_id: int):
    """Source ID के सारे mappings fetch करता है"""
    return [doc async for doc in mappings_col.find({"source_channel_id": source_channel_id})]


# Listener safety alias for get_mappings
get_mappings_by_source = get_mappings


async def list_mappings():
    return [doc async for doc in mappings_col.find({})]


# ---------------- Stories / Episodes ----------------

async def get_story(story_slug: str):
    return await stories_col.find_one({"_id": story_slug})


async def save_episode(story_slug: str, episode_no: str, file_id: str, message_id: int, source_chat_id: int):
    await stories_col.update_one(
        {"_id": story_slug},
        {"$set": {
            f"episodes.{episode_no}": {
                "file_id": file_id,
                "message_id": message_id,
                "source_chat_id": source_chat_id,
            }
        }},
        upsert=True,
    )


# ---------------- Pending Buffer & Live Dashboard Controls ----------------

async def add_pending_episode(story_slug: str, episode_no: int):
    await stories_col.update_one(
        {"_id": story_slug},
        {"$addToSet": {"pending_episodes": episode_no}},
        upsert=True,
    )


async def get_pending_episodes(story_slug: str):
    story = await stories_col.find_one({"_id": story_slug})
    return story.get("pending_episodes", []) if story else []


async def increment_pending_file_count(story_slug: str):
    return await stories_col.find_one_and_update(
        {"_id": story_slug},
        {"$inc": {"pending_file_count": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )


async def increment_block_count(story_slug: str):
    await stories_col.update_one(
        {"_id": story_slug},
        {"$inc": {"total_blocks": 1}},
        upsert=True,
    )


async def reset_pending(story_slug: str):
    await stories_col.update_one(
        {"_id": story_slug},
        {"$set": {"pending_episodes": [], "pending_file_count": 0}},
    )


async def set_dashboard_msg_id(story_slug: str, target_channel_id: int, message_id: int):
    await stories_col.update_one(
        {"_id": story_slug},
        {"$set": {f"dashboards.{target_channel_id}": message_id}},
        upsert=True,
    )


async def get_dashboard_msg_id(story_slug: str, target_channel_id: int):
    doc = await stories_col.find_one({"_id": story_slug})
    if doc and "dashboards" in doc:
        return doc["dashboards"].get(str(target_channel_id))
    return None


# ---------------- Dynamic Verification Settings ----------------

async def get_verification_settings():
    doc = await settings_col.find_one({"_id": "verification"})
    default_timeout = getattr(config, "VERIFY_EXPIRE_TIME", 86400)
    
    if not doc:
        return {
            "status": True,
            "api_url": getattr(config, "SHORTENER_API_URL", "gplinks.in"),
            "api_key": getattr(config, "SHORTENER_API_KEY", ""),
            "token_timeout": default_timeout
        }
    
    if "token_timeout" not in doc:
        doc["token_timeout"] = default_timeout
        
    return doc


async def update_verification_settings(key: str, value):
    await settings_col.update_one(
        {"_id": "verification"},
        {"$set": {key: value}},
        upsert=True,
    )


# ---------------- Dynamic Protection Settings ----------------

async def get_protect_settings() -> bool:
    doc = await settings_col.find_one({"_id": "protection"})
    if not doc:
        return getattr(config, "PROTECT_CONTENT", False)
    return doc.get("status", False)


# ---------------- Verification Tokens Helper (Strict Ownership & One-Time Use) ----------------

async def save_verify_token(user_id: int, token: str, payload: str):
    """Shortener Verification के लिए user_id के साथ temporary token और फाइल payload सेव करता है"""
    await verify_tokens_col.update_one(
        {"token": token},
        {"$set": {
            "user_id": user_id,
            "token": token,
            "payload": payload,
            "created_at": time.time()
        }},
        upsert=True,
    )


async def get_verify_token_payload(user_id: int, token: str):
    """
    Strict Ownership Check & Bypass Detection:
    1. Check if token exists in DB.
    2. Check if token belongs to requesting user_id.
    3. Check if token was verified in less than 2 minutes (120 seconds).
    4. Delete token after successful validation to prevent reuse.
    Returns: (payload, status_code)
    """
    doc = await verify_tokens_col.find_one({"token": token})
    
    if not doc:
        return None, "invalid"  # Link does not exist or already used
    
    if doc.get("user_id") != user_id:
        return None, "wrong_user"  # Link generated by another user

    # 🛑 Bypass Check: 2 min (120 seconds) से पहले आ गया
    created_at = doc.get("created_at", 0)
    if time.time() - created_at < 120:
        return None, "bypassed"  # Too fast! User tried to bypass shortener
    
    # Validation successful: delete token so it cannot be used again
    await verify_tokens_col.delete_one({"_id": doc["_id"]})
    return doc.get("payload", ""), "success"


# ---------------- Dynamic Force Sub Settings ----------------

async def get_forcesub_settings():
    doc = await settings_col.find_one({"_id": "forcesub"})
    if not doc:
        return {
            "status": getattr(config, "DEFAULT_FORCE_SUB_STATUS", True),
            "channel": getattr(config, "DEFAULT_FORCE_SUB_CHANNEL", "")
        }
    return doc


async def update_forcesub_settings(key: str, value):
    await settings_col.update_one(
        {"_id": "forcesub"},
        {"$set": {key: value}},
        upsert=True,
    )


# ---------------- User Verification & Logs Settings ----------------

async def get_user(user_id: int):
    return await users_col.find_one({"_id": user_id})


async def update_user_verification(user_id: int, timestamp: float):
    await users_col.update_one(
        {"_id": user_id},
        {"$set": {"verified_at": timestamp}},
        upsert=True,
    )


async def set_log_channel(channel_id: int):
    await settings_col.update_one(
        {"_id": "log_channel"},
        {"$set": {"value": channel_id}},
        upsert=True,
    )


async def get_log_channel():
    doc = await settings_col.find_one({"_id": "log_channel"})
    return doc["value"] if doc else None
