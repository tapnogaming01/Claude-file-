from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import database as db

@Client.on_message(filters.command("verify_config") & filters.user(config.ADMINS))
async def verification_panel(client: Client, message: Message):
    settings = await db.get_verification_settings()
    
    status_icon = "🟢 ON" if settings["status"] else "🔴 OFF"
    text = (
        f"⚙️ **ᴠᴇʀɪғɪᴄᴀᴛɪᴏɴ sᴇᴛᴛɪɴɢs**\n\n"
        f"• **sᴛᴀᴛᴜs:** {status_icon}\n"
        f"• **ᴀᴘɪ ᴜʀʟ:** `{settings['api_url']}`\n"
        f"• **ᴀᴘɪ ᴋᴇʏ:** `{settings['api_key'][:5]}***`\n"
        f"• **ᴛɪᴍᴇᴏᴜᴛ:** `{settings['token_timeout'] // 3600} Hours`"
    )

    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f"Status: {status_icon}", 
                callback_data="toggle_verify_status"
            )
        ],
        [
            InlineKeyboardButton("✏️ Set API URL", callback_data="set_api_url"),
            InlineKeyboardButton("🔑 Set API Key", callback_data="set_api_key")
        ],
        [
            InlineKeyboardButton("❌ Close", callback_data="close_data")
        ]
    ])

    await message.reply_text(text, reply_markup=buttons)


@Client.on_callback_query(filters.regex("^toggle_verify_status$"))
async def toggle_verification(client: Client, query: CallbackQuery):
    settings = await db.get_verification_settings()
    new_status = not settings.get("status", True)
    
    await db.update_verification_settings("status", new_status)
    
    status_icon = "🟢 ON" if new_status else "🔴 OFF"
    
    # Dynamic Button Update without reloading page
    updated_buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f"Status: {status_icon}", 
                callback_data="toggle_verify_status"
            )
        ],
        [
            InlineKeyboardButton("✏️ Set API URL", callback_data="set_api_url"),
            InlineKeyboardButton("🔑 Set API Key", callback_data="set_api_key")
        ],
        [
            InlineKeyboardButton("❌ Close", callback_data="close_data")
        ]
    ])
    
    await query.message.edit_reply_markup(reply_markup=updated_buttons)
    await query.answer(f"Verification is now {'ENABLED' if new_status else 'DISABLED'}")
