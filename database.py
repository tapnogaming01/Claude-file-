from pymongo import ReturnDocument
import motor.motor_asyncio

import config
from utils import slugify

client = motor.motor_asyncio.AsyncIOMotorClient(config.MONGO_URI)
db = client[config.MONGO_DB_NAME]

mappings_col = db["mappings"]     # _id = source_channel_id (int) -> {story_name, story_slug, target_channel_id}
stories_col = db["stories"]       # _id = story_slug -> {name, target_channel_id, episodes, pending_episodes, pending_file_count, dashboard_msg_id, total_blocks}
settings_col = db["settings"]     # _id = "log_channel" / "verification"
users_col = db["users"]          # _id = user_id -> {verified_at}


# ---------------- Mappings (source channel -> story -> target channel) ----------------

async def add_mapping(source_channel_id: int, story_name: str, target_channel_id: int) -> str:
    story_slug = slugify(story_name)

    await mappings_col.update_one(
        {"_id": source_channel_id},
        {"$set": {
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
            "target_channel_id": target_channel_id,
            "episodes": {},
            "pending_episodes": [],
            "pending_file_count": 0,
            "total_blocks": 0,
            "dashboard_msg_id": None
        })

    return story_slug


async def remove_mapping(source_channel_id: int):
    await mappings_col.delete_one({"_id": source_channel_id})


async def update_target_channel(source_channel_id: int, new_target_channel_id: int):
    mapping = await mappings_col.find_one({"_id": source_channel_id})
    if not mapping:
        return None

    await mappings_col.update_one(
        {"_id": source_channel_id},
        {"$set": {"target_channel_id": new_target_channel_id}},
    )
    await stories_col.update_one(
        {"_id": mapping["story_slug"]},
        {"$set": {"target_channel_id": new_target_channel_id}},
    )
    return mapping["story_slug"]


async def get_mapping(source_channel_id: int):
    return await mappings_col.find_one({"_id": source_channel_id})


async def get_all_mappings():
    return [doc async for doc in mappings_col.find({})]


async def backfill_story_slug(source_channel_id: int, story_slug: str):
    await mappings_col.update_one(
        {"_id": source_channel_id},
        {"$set": {"story_slug": story_slug}},
    )

    mapping = await mappings_col.find_one({"_id": source_channel_id})
    if not mapping:
        return

    existing = await stories_col.find_one({"_id": story_slug})
    if not existing:
        await stories_col.insert_one({
            "_id": story_slug,
            "name": mapping["story_name"],
            "target_channel_id": mapping["target_channel_id"],
            "episodes": {},
            "pending_episodes": [],
            "pending_file_count": 0,
            "total_blocks": 0,
            "dashboard_msg_id": None
        })


async def list_mappings():
    return [doc async for doc in mappings_col.find({})]


# ---------------- Stories / Episodes ----------------

async def get_story(story_slug: str):
    return await stories_col.find_one({"_id": story_slug})


async def get_stories_by_source(source_channel_id: int):
    mapping = await mappings_col.find_one({"_id": source_channel_id})
    if not mapping:
        return []
    story = await stories_col.find_one({"_id": mapping.get("story_slug")})
    return [story] if story else []


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


async def set_dashboard_msg_id(story_slug: str, message_id: int):
    await stories_col.update_one(
        {"_id": story_slug},
        {"$set": {"dashboard_msg_id": message_id}},
        upsert=True,
    )


async def get_dashboard_msg_id(story_slug: str):
    doc = await stories_col.find_one({"_id": story_slug})
    return doc.get("dashboard_msg_id") if doc else None


# ---------------- Dynamic Verification Settings ----------------

async def get_verification_settings():
    doc = await settings_col.find_one({"_id": "verification"})
    if not doc:
        return {
            "status": True,
            "api_url": getattr(config, "SHORTENER_API_URL", "gplinks.in"),
            "api_key": getattr(config, "SHORTENER_API_KEY", ""),
            "token_timeout": 86400
        }
    return doc


async def update_verification_settings(key: str, value):
    await settings_col.update_one(
        {"_id": "verification"},
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
