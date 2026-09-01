import motor.motor_asyncio

import config

client = motor.motor_asyncio.AsyncIOMotorClient(config.MONGO_URI)
db = client[config.MONGO_DB_NAME]

mappings_col = db["mappings"]     # _id = source_channel_id (int) -> {story_name, target_channel_id}
stories_col = db["stories"]       # _id = story_name -> {target_channel_id, target_message_id, episodes: {...}}
settings_col = db["settings"]     # _id = "log_channel" -> {value: channel_id}


# ---------------- Mappings (source channel -> story -> target channel) ----------------

async def add_mapping(source_channel_id: int, story_name: str, target_channel_id: int):
    await mappings_col.update_one(
        {"_id": source_channel_id},
        {"$set": {"story_name": story_name, "target_channel_id": target_channel_id}},
        upsert=True,
    )

    existing = await stories_col.find_one({"_id": story_name})
    if not existing:
        await stories_col.insert_one({
            "_id": story_name,
            "target_channel_id": target_channel_id,
            "target_message_id": None,
            "episodes": {},
        })


async def remove_mapping(source_channel_id: int):
    await mappings_col.delete_one({"_id": source_channel_id})


async def get_mapping(source_channel_id: int):
    return await mappings_col.find_one({"_id": source_channel_id})


async def list_mappings():
    return [doc async for doc in mappings_col.find({})]


# ---------------- Stories / episodes ----------------

async def get_story(story_name: str):
    return await stories_col.find_one({"_id": story_name})


async def save_episode(story_name: str, episode_no: str, file_id: str, message_id: int, source_chat_id: int):
    await stories_col.update_one(
        {"_id": story_name},
        {"$set": {
            f"episodes.{episode_no}": {
                "file_id": file_id,
                "message_id": message_id,
                "source_chat_id": source_chat_id,
            }
        }},
        upsert=True,
    )


async def set_target_message_id(story_name: str, message_id: int):
    await stories_col.update_one(
        {"_id": story_name},
        {"$set": {"target_message_id": message_id}},
        upsert=True,
    )


# ---------------- Settings (log channel) ----------------

async def set_log_channel(channel_id: int):
    await settings_col.update_one(
        {"_id": "log_channel"},
        {"$set": {"value": channel_id}},
        upsert=True,
    )


async def get_log_channel():
    doc = await settings_col.find_one({"_id": "log_channel"})
    return doc["value"] if doc else None
