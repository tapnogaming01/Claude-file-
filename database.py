import time
import motor.motor_asyncio
from pymongo import ReturnDocument
import config
from utils import slugify

# MongoDB Connection Initialization
client = motor.motor_asyncio.AsyncIOMotorClient(config.MONGO_URI)
db = client[config.MONGO_DB_NAME]

mappings_col = db["mappings"]        
stories_col = db["stories"]          
settings_col = db["settings"]        
users_col = db["users"]             
verify_tokens_col = db["tokens"]    


# --- TTL Index Initializer (Deletes tokens after 30 mins automatically) ---
async def init_db_indexes():
    await verify_tokens_col.create_index("created_at", expireAfterSeconds=1800)


# --- Title Helper ---
def clean_title_first_line(caption: str) -> str:
    if not caption:
        return "Untitled Story"
    lines = caption.strip().split("\n")
    return lines[0].strip()


# --- Mappings ---
async def add_mapping(source_channel_id: int, story_name: str, target_channel_id: int) -> str:
    clean_name = clean_title_first_line(story_name)
    story_slug = slugify(clean_name)

    await mappings_col.update_one(
        {"source_channel_id": source_channel_id, "story_slug": story_slug},
        {"$set": {
            "source_channel_id": source_channel_id,
            "story_name": clean_name,
            "story_slug": story_slug,
            "target_channel_id": target_channel_id,
        }},
        upsert=True,
    )

    existing = await stories_col.find_one({"_id": story_slug})
    if not existing:
        await stories_col.insert_one({
            "_id": story_slug,
            "name": clean_name,
            "episodes": {},
            "pending_episodes": [],
            "pending_file_count": 0,
            "total_blocks": 0,
            "dashboards": {}
        })

    return story_slug


async def remove_mapping(source_channel_id: int, target_channel_id: int = None):
    query = {"source_channel_id": source_channel_id}
    if target_channel_id:
        query["target_channel_id"] = target_channel_id
    await mappings_col.delete_many(query)


async def get_mappings(source_channel_id: int):
    return [doc async for doc in mappings_col.find({"source_channel_id": source_channel_id})]

get_mappings_by_source = get_mappings

async def list_mappings():
    return [doc async for doc in mappings_col.find({})]


# --- Stories & Episodes ---
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


# --- Verification Settings ---
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


# --- Protection Settings ---
async def get_protect_settings() -> bool:
    doc = await settings_col.find_one({"_id": "protection"})
    if not doc:
        return getattr(config, "PROTECT_CONTENT", False)
    return doc.get("status", False)


# --- User Ban & Bypass Logic ---
async def is_user_banned(user_id: int) -> bool:
    user = await users_col.find_one({"_id": user_id})
    return user.get("is_banned", False) if user else False


async def ban_user(user_id: int, reason: str = "Bypassing shortener multiple times"):
    await users_col.update_one(
        {"_id": user_id},
        {"$set": {"is_banned": True, "ban_reason": reason}},
        upsert=True,
    )


async def unban_user(user_id: int):
    await users_col.update_one(
        {"_id": user_id},
        {"$set": {"is_banned": False, "bypass_count": 0}},
        upsert=True,
    )


async def increment_bypass_count(user_id: int) -> int:
    res = await users_col.find_one_and_update(
        {"_id": user_id},
        {"$inc": {"bypass_count": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return res.get("bypass_count", 1)


async def get_bypass_count(user_id: int) -> int:
    user = await users_col.find_one({"_id": user_id})
    return user.get("bypass_count", 0) if user else 0


async def reset_bypass_count(user_id: int):
    await users_col.update_one(
        {"_id": user_id},
        {"$set": {"bypass_count": 0}}
    )


# --- Temporary Token Handler ---
async def save_verify_token(user_id: int, token: str, payload: str):
    await verify_tokens_col.update_one(
        {"user_id": user_id},
        {"$set": {
            "user_id": user_id,
            "token": token,
            "payload": payload,
            "created_at": time.time()
        }},
        upsert=True,
    )


async def get_verify_token_payload(user_id: int, token: str):
    doc = await verify_tokens_col.find_one({"token": token})
    
    if not doc:
        return None, "invalid"
    
    if doc.get("user_id") != user_id:
        return None, "wrong_user"

    created_at = doc.get("created_at", 0)
    if time.time() - created_at < 120:
        await verify_tokens_col.delete_one({"_id": doc["_id"]})
        count = await increment_bypass_count(user_id)
        if count >= 5:
            await ban_user(user_id, "Automated Ban: Tried to bypass shortener 5 times.")
            return None, "auto_banned"
        
        return count, "bypassed"
    
    await verify_tokens_col.delete_one({"_id": doc["_id"]})
    return doc.get("payload", ""), "success"


# --- Force Sub Settings ---
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


# --- User Verification ---
async def get_user(user_id: int):
    return await users_col.find_one({"_id": user_id})


async def get_user_verification(user_id: int):
    return await users_col.find_one({"_id": user_id})


async def set_user_verified(user_id: int):
    current_time = time.time()
    await users_col.update_one(
        {"_id": user_id},
        {"$set": {"verified_at": current_time, "bypass_count": 0}},
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
