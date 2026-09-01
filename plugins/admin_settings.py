from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import config
import database as db

# Temporarily store user input state
AWAITING_INPUT = {}

async def get_protect_status() -> bool:
    doc = await db.settings_col.find_one({"_id": "protection"})
    if not doc:
        return getattr(config, "PROTECT_CONTENT", False)
    return doc.get("status", False)

async def build_settings_ui():
    fs_settings = await db.get_forcesub_settings()
    v_settings = await db.get_verification_settings()
    protect_status = await get_protect_status()

    fs_status_bool = fs_settings.get("status", True)
    v_status_bool = v_settings.get("status", True)

    fs_status_text = "🟢 ON" if fs_status_bool else "🔴 OFF"
    v_status_text = "🟢 ON" if v_status_bool else "🔴 OFF"
    protect_status_text = "🟢 ON" if protect_status else "🔴 OFF"

    fs_channel = fs_settings.get("channel") or "Not Set"
    api_url = v_settings.get("api_url") or getattr(config, "SHORTENER_API_URL", "Not Set")
    
    timeout_sec = v_settings.get("token_timeout", getattr(config, "VERIFY_EXPIRE_TIME", 86400))
    timeout_hours = timeout_sec // 3600

    text = (
        "⚙️ **ʙᴏᴛ ᴄᴏɴғɪɢᴜʀᴀᴛɪᴏɴ ᴘᴀɴᴇʟ**\n\n"
        f"📢 **ғᴏʀᴄᴇ sᴜʙ:** {fs_status_text}\n"
        f"🔗 **ᴄʜᴀɴɴᴇʟ:** `{fs_channel}`\n\n"
        f"🔓 **ᴠᴇʀɪғɪᴄᴀᴛɪᴏɴ:** {v_status_text}\n"
        f"🌐 **ᴀᴘɪ ᴜʀʟ:** `{api_url}`\n"
        f"⏳ **ᴛᴏᴋᴇɴ ᴇxᴘɪʀᴇ:** `{timeout_hours} Hours` ({timeout_sec}s)\n\n"
        f"🛡️ **ᴘʀᴏᴛᴇᴄᴛ ᴄᴏɴᴛᴇɴᴛ:** {protect_status_text}"
    )

    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"Force Sub: {fs_status_text}", callback_data="toggle_forcesub"),
            InlineKeyboardButton(f"Verify: {v_status_text}", callback_data="toggle_verify_status")
        ],
        [
            InlineKeyboardButton(f"Protect Content: {protect_status_text}", callback_data="toggle_protect")
        ],
        [
            InlineKeyboardButton("✏️ Set FS Channel", callback_data="set_fs_channel"),
            InlineKeyboardButton("🔑 Set Shortener API", callback_data="set_api_key")
        ],
        [
            InlineKeyboardButton("⏱️ Set Token Timeout", callback_data="set_token_time")
        ],
        [InlineKeyboardButton("❌ Close", callback_data="close_data")]
    ])

    return text, buttons


@Client.on_message(filters.command("settings") & filters.user(config.ADMIN_IDS))
async def settings_panel(client: Client, message: Message):
    text, buttons = await build_settings_ui()
    await message.reply_text(text, reply_markup=buttons)


@Client.on_callback_query(filters.regex("^(toggle_forcesub|toggle_verify_status|toggle_protect|set_fs_channel|set_api_key|set_token_time|close_data)$"))
async def settings_callbacks(client: Client, query: CallbackQuery):
    if query.from_user.id not in config.ADMIN_IDS:
        return await query.answer("Unauthorized!", show_alert=True)

    data = query.data

    if data == "toggle_forcesub":
        settings = await db.get_forcesub_settings()
        new_status = not settings.get("status", True)
        await db.update_forcesub_settings("status", new_status)
        await query.answer(f"Force Sub is now {'ENABLED' if new_status else 'DISABLED'}")
        
        text, buttons = await build_settings_ui()
        await query.message.edit_text(text, reply_markup=buttons)

    elif data == "toggle_verify_status":
        settings = await db.get_verification_settings()
        new_status = not settings.get("status", True)
        await db.update_verification_settings("status", new_status)
        await query.answer(f"Verification is now {'ENABLED' if new_status else 'DISABLED'}")

        text, buttons = await build_settings_ui()
        await query.message.edit_text(text, reply_markup=buttons)

    elif data == "toggle_protect":
        curr_status = await get_protect_status()
        new_status = not curr_status
        await db.settings_col.update_one({"_id": "protection"}, {"$set": {"status": new_status}}, upsert=True)
        await query.answer(f"Protect Content is now {'ENABLED' if new_status else 'DISABLED'}")

        text, buttons = await build_settings_ui()
        await query.message.edit_text(text, reply_markup=buttons)

    elif data == "set_fs_channel":
        AWAITING_INPUT[query.from_user.id] = "set_channel"
        await query.answer()
        await query.message.reply_text(
            "📢 **Send me the new Force Sub Channel Username or ID.**\n\n"
            "Example: `@MyChannel` or `-1001234567890`\n"
            "To cancel, send `/cancel`."
        )

    elif data == "set_api_key":
        AWAITING_INPUT[query.from_user.id] = "set_api"
        await query.answer()
        await query.message.reply_text(
            "🔑 **Send your Shortener API URL and Key in this format:**\n\n"
            "`api_url|api_key`\n"
            "Example: `gplinks.in|1234567890abcdef`\n"
            "To cancel, send `/cancel`."
        )

    elif data == "set_token_time":
        AWAITING_INPUT[query.from_user.id] = "set_timeout"
        await query.answer()
        await query.message.reply_text(
            "⏱️ **Send the Token Expiry Time in Hours or Seconds.**\n\n"
            "Example:\n"
            "• `24h` for 24 Hours\n"
            "• `86400` for 86400 Seconds\n"
            "To cancel, send `/cancel`."
        )

    elif data == "close_data":
        await query.message.delete()
        await query.answer("Closed!")


@Client.on_message(filters.private & filters.user(config.ADMIN_IDS) & ~filters.command(["start", "settings", "cancel"]))
async def handle_admin_inputs(client: Client, message: Message):
    user_id = message.from_user.id
    state = AWAITING_INPUT.get(user_id)

    if not state:
        return

    if state == "set_channel":
        channel_val = message.text.strip()
        await db.update_forcesub_settings("channel", channel_val)
        AWAITING_INPUT.pop(user_id, None)

        await message.reply_text(f"✅ **Force Sub Channel updated to:** `{channel_val}`")
        text, buttons = await build_settings_ui()
        await message.reply_text(text, reply_markup=buttons)

    elif state == "set_api":
        val = message.text.strip()
        if "|" in val:
            api_url, api_key = val.split("|", 1)
            await db.update_verification_settings("api_url", api_url.strip())
            await db.update_verification_settings("api_key", api_key.strip())
            await message.reply_text("✅ **Shortener API URL & Key successfully updated!**")
        else:
            await db.update_verification_settings("api_key", val)
            await message.reply_text("✅ **Shortener API Key successfully updated!**")

        AWAITING_INPUT.pop(user_id, None)
        text, buttons = await build_settings_ui()
        await message.reply_text(text, reply_markup=buttons)

    elif state == "set_timeout":
        val = message.text.strip().lower()
        try:
            if val.endswith("h"):
                seconds = int(val.replace("h", "")) * 3600
            else:
                seconds = int(val)
                
            await db.update_verification_settings("token_timeout", seconds)
            await message.reply_text(f"✅ **Verification Token Expire Time set to:** `{seconds // 3600} Hours` (`{seconds}` seconds)")
        except ValueError:
            await message.reply_text("⚠️ **Invalid input!** Please send numbers only (e.g., `24h` or `86400`).")

        AWAITING_INPUT.pop(user_id, None)
        text, buttons = await build_settings_ui()
        await message.reply_text(text, reply_markup=buttons)


@Client.on_message(filters.command("cancel") & filters.private & filters.user(config.ADMIN_IDS))
async def cancel_input(client: Client, message: Message):
    if message.from_user.id in AWAITING_INPUT:
        AWAITING_INPUT.pop(message.from_user.id)
        await message.reply_text("❌ Input cancelled.")
