import database as db


async def log(client, text: str):
    """Sends a notification to the configured log channel, if one is set."""
    log_channel_id = await db.get_log_channel()
    if not log_channel_id:
        return
    try:
        await client.send_message(log_channel_id, text)
    except Exception:
        pass  # never let a logging failure break the main flow
