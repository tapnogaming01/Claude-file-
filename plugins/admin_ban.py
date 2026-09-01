from pyrogram import Client, filters
from pyrogram.types import Message
import config
import database as db

def is_admin(user_id: int) -> bool:
    admin_list = getattr(config, "ADMINS", getattr(config, "ADMIN_IDS", []))
    return user_id in admin_list


# --- Ban User Command ---
@Client.on_message(filters.command("ban") & filters.private)
async def ban_user_cmd(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return

    if len(message.command) < 2:
        return await message.reply_text("⚠️ **Usage:** `/ban <user_id> [reason]`")

    try:
        target_user_id = int(message.command[1])
    except ValueError:
        return await message.reply_text("❌ Invalid User ID. Please provide a numeric Telegram ID.")

    reason = " ".join(message.command[2:]) if len(message.command) > 2 else "Banned by Admin"

    await db.ban_user(target_user_id, reason)
    await message.reply_text(f"🚫 **User `{target_user_id}` has been banned.**\n📝 **Reason:** {reason}")


# --- Unban User Command ---
@Client.on_message(filters.command("unban") & filters.private)
async def unban_user_cmd(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return

    if len(message.command) < 2:
        return await message.reply_text("⚠️ **Usage:** `/unban <user_id>`")

    try:
        target_user_id = int(message.command[1])
    except ValueError:
        return await message.reply_text("❌ Invalid User ID. Please provide a numeric Telegram ID.")

    await db.unban_user(target_user_id)
    await message.reply_text(f"✅ **User `{target_user_id}` has been unbanned.** (Bypass counter reset to 0)")


# --- User Status Info Command ---
@Client.on_message(filters.command("userinfo") & filters.private)
async def user_info_cmd(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return

    if len(message.command) < 2:
        return await message.reply_text("⚠️ **Usage:** `/userinfo <user_id>`")

    try:
        target_user_id = int(message.command[1])
    except ValueError:
        return await message.reply_text("❌ Invalid User ID.")

    user = await db.get_user(target_user_id)

    if not user:
        return await message.reply_text("❓ User record not found in database.")

    banned_status = "🔴 **Yes**" if user.get("is_banned", False) else "🟢 **No**"
    ban_reason = user.get("ban_reason", "None")
    bypass_count = user.get("bypass_count", 0)

    info_text = (
        f"👤 **User Information:** `{target_user_id}`\n\n"
        f"• **Banned:** {banned_status}\n"
        f"• **Ban Reason:** {ban_reason}\n"
        f"• **Bypass Attempts:** `{bypass_count}/5`"
    )

    await message.reply_text(info_text)
