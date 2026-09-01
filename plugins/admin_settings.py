from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import config
import database as db

@Client.on_message(filters.command("settings") & filters.user(config.ADMIN_IDS))
async def settings_panel(client: Client, message: Message):
    fs_settings = await db.get_forcesub_settings()
    v_settings = await db.get_verification_settings()

    fs_status = "🟢 ON" if fs_settings.get("status") else "🔴 OFF"
    v_status = "🟢 ON" if v_settings.get("status") else "🔴 OFF"
    fs_channel = fs_settings.get("channel") or "Not Set"

    text = (
        "⚙️ **ʙᴏᴛ ᴄᴏɴғɪɢᴜʀᴀᴛɪᴏɴ ᴘᴀɴᴇʟ**\n\n"
        f"📢 **ғᴏʀᴄᴇ sᴜʙ:** {fs_status}\n"
        f"🔗 **ᴄʜᴀɴɴᴇʟ:** `{fs_channel}`\n\n"
        f"🔓 **ᴠᴇʀɪғɪᴄᴀᴛɪᴏɴ:** {v_status}\n"
        f"🌐 **ᴀᴘɪ ᴜʀʟ:** `{v_settings.get('api_url')}`"
    )

    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"Force Sub: {fs_status}", callback_data="toggle_forcesub"),
            InlineKeyboardButton(f"Verify: {v_status}", callback_data="toggle_verify_status")
        ],
        [
            InlineKeyboardButton("✏️ Set FS Channel", callback_data="set_fs_channel"),
            InlineKeyboardButton("🔑 Set Shortener API", callback_data="set_api_key")
        ],
        [InlineKeyboardButton("❌ Close", callback_data="close_data")]
    ])

    await message.reply_text(text, reply_markup=buttons)


@Client.on_callback_query(filters.regex("^toggle_forcesub$"))
async def toggle_forcesub_callback(client: Client, query: CallbackQuery):
    if query.from_user.id not in config.ADMIN_IDS:
        return await query.answer("Unauthorized!", show_alert=True)

    settings = await db.get_forcesub_settings()
    new_status = not settings.get("status", True)
    await db.update_forcesub_settings("status", new_status)

    await query.answer(f"Force Sub is now {'ENABLED' if new_status else 'DISABLED'}")
    
    # UI रिफ्रेश करने के लिए /settings कॉल करें या markup अपडेट करें
    fs_status = "🟢 ON" if new_status else "🔴 OFF"
    v_settings = await db.get_verification_settings()
    v_status = "🟢 ON" if v_settings.get("status") else "🔴 OFF"
    fs_channel = settings.get("channel") or "Not Set"

    updated_buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"Force Sub: {fs_status}", callback_data="toggle_forcesub"),
            InlineKeyboardButton(f"Verify: {v_status}", callback_data="toggle_verify_status")
        ],
        [
            InlineKeyboardButton("✏️ Set FS Channel", callback_data="set_fs_channel"),
            InlineKeyboardButton("🔑 Set Shortener API", callback_data="set_api_key")
        ],
        [InlineKeyboardButton("❌ Close", callback_data="close_data")]
    ])
    await query.message.edit_reply_markup(reply_markup=updated_buttons)
