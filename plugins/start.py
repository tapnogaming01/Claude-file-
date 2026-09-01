import time
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import MessageNotModified

import config
import database as db
from plugins.verification import is_user_verified, get_shortlink

from log_utils import log

# --- Inline Keyboards ---
MAIN_START_BUTTONS = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("ℹ️ ᴀʙᴏᴜᴛ", callback_data="about_btn"),
        InlineKeyboardButton("❓ ʜᴇʟᴘ", callback_data="help_btn")
    ],
    [
        InlineKeyboardButton("👨‍💻 ᴅᴇᴠᴇʟᴏᴘᴇʀ", url="https://t.me/Kaluu")
    ]
])

BACK_BUTTON = InlineKeyboardMarkup([
    [InlineKeyboardButton("🔙 ʙᴀᴄᴋ", callback_data="home_btn")]
])


# --- Dynamic Force Join Helper ---
async def check_force_sub(client: Client, user_id: int):
    fs_settings = await db.get_forcesub_settings()
    
    # अगर Force Sub OFF है तो सीधे एक्सेस दें
    if not fs_settings.get("status", True):
        return True, None

    force_channel = fs_settings.get("channel")
    if not force_channel:
        return True, None

    try:
        user = await client.get_chat_member(force_channel, user_id)
        if user.status in ["kicked", "left"]:
            return False, force_channel
        return True, force_channel
    except Exception:
        # अगर बॉट उस चैनल में एडमिन नहीं है तो बायपास करें
        return True, force_channel


# --- Commands & Deep Link Handler ---
@Client.on_message(filters.command("start") & filters.private)
async def start_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    args = message.command  # e.g. ["start", "batch-slug-211-220"]

    # 1. Dynamic Force Sub Check
    is_joined, fs_channel = await check_force_sub(client, user_id)
    if not is_joined:
        clean_channel = str(fs_channel).replace("@", "")
        invite_link = f"https://t.me/{clean_channel}" if not clean_channel.startswith("-100") else f"https://t.me/c/{clean_channel[4:]}"
        
        param = args[1] if len(args) > 1 else ""
        bot_username = getattr(config, "BOT_USERNAME", None) or (await client.get_me()).username
        try_again_url = f"https://t.me/{bot_username}?start={param}" if param else f"https://t.me/{bot_username}?start=true"

        join_btn = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ", url=invite_link)],
            [InlineKeyboardButton("🔄 ᴛʀʏ ᴀɢᴀɪɴ", url=try_again_url)]
        ])
        return await message.reply_text(
            "⚠️ **ᴀᴄᴄᴇss ᴅᴇɴɪᴇᴅ!**\n\n"
            "ᴘʟᴇᴀsᴇ ᴊᴏɪɴ ᴏᴜʀ ᴄʜᴀɴɴᴇʟ ᴛᴏ ᴜsᴇ ᴛʜɪs ʙᴏᴛ ᴀɴᴅ ɢᴇᴛ ʏᴏᴜʀ ғɪʟᴇs.",
            reply_markup=join_btn
        )

    # 2. Normal /start command without parameters
    if len(args) < 2:
        welcome_text = (
            f"ʜɪ [{message.from_user.first_name}]! ɪ ᴀᴍ ᴀɴ **ᴀᴜᴛᴏᴍᴀᴛᴇᴅ sᴍᴀʀᴛ ғɪʟᴇ sᴛᴏʀᴇ ʙᴏᴛ** 🤖\n\n"
            "ɪ ᴄᴀɴ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ ᴅᴇʟɪᴠᴇʀ sᴛᴏʀʏ ᴇᴘɪsᴏᴅᴇs ᴀɴᴅ ᴍᴀɴᴀɢᴇ ʙᴀᴛᴄʜ ғɪʟᴇs. "
            "ᴛᴀᴘ ᴀ ʙᴀᴛᴄʜ ʙᴜᴛᴛᴏɴ ɪɴ ᴛʜᴇ ᴄʜᴀɴɴᴇʟ, ᴀɴᴅ ɪ'ʟʟ sᴇɴᴅ ʏᴏᴜʀ ғɪʟᴇs ʀɪɢʜᴛ ʜᴇʀᴇ!"
        )
        return await message.reply_text(
            text=welcome_text,
            reply_markup=MAIN_START_BUTTONS
        )

    payload = args[1]

    # 3. Handle Token Verification Completion Callback Link
    if payload.startswith("verify_"):
        await db.update_user_verification(user_id, time.time())
        return await message.reply_text("✅ **ᴠᴇʀɪғɪᴄᴀᴛɪᴏɴ sᴜᴄᴄᴇssғᴜʟ!**\n\nʏᴏᴜ ɴᴏᴡ ʜᴀᴠᴇ ᴀᴄᴄᴇss ғᴏʀ 24 ʜᴏᴜʀs.")

    # 4. Dynamic Shortener / Verification Check
    verified = await is_user_verified(user_id)
    if not verified:
        bot_username = getattr(config, "BOT_USERNAME", None) or (await client.get_me()).username
        original_link = f"https://t.me/{bot_username}?start={payload}"
        short_link = await get_shortlink(original_link)

        v_settings = await db.get_verification_settings()
        timeout_hours = v_settings.get("token_timeout", 86400) // 3600

        verify_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔓 ᴠᴇʀɪғʏ ᴛᴏᴋᴇɴ", url=short_link)],
            [InlineKeyboardButton("❓ ʜᴏᴡ ᴛᴏ ᴠᴇʀɪғʏ", url="https://t.me/your_help_channel")]
        ])

        # IMPORTANT: 'return' stops file delivery until verified!
        return await message.reply_text(
            "🔒 **ᴀᴄᴄᴇss ᴅᴇɴɪᴇᴅ / ᴛᴏᴋᴇɴ ᴇxᴘɪʀᴇᴅ!**\n\n"
            f"ᴘʟᴇᴀsᴇ ᴠᴇʀɪғʏ ʏᴏᴜʀ ᴛᴏᴋᴇɴ ᴛᴏ ɢᴇᴛ {timeout_hours} ʜᴏᴜʀs ᴀᴄᴄᴇss ᴛᴏ ᴀʟʟ ғɪʟᴇs.",
            reply_markup=verify_keyboard
        )

    # 5. Batch File Delivery Logic
    if not payload.startswith("batch-"):
        return await message.reply_text("ʜɪ! ɪ ᴅɪᴅɴ'ᴛ ʀᴇᴄᴏɢɴɪᴢᴇ ᴛʜᴀᴛ ʟɪɴᴋ.")

    try:
        _, rest = payload.split("-", 1)
        story_slug, start_ep, end_ep = rest.rsplit("-", 2)
        start_ep, end_ep = int(start_ep), int(end_ep)
    except ValueError:
        return await message.reply_text("ᴛʜᴀᴛ ʟɪɴᴋ ʟᴏᴏᴋs ʙʀᴏᴋᴇɴ — ᴘʟᴇᴀsᴇ ᴛᴀᴘ ᴛʜᴇ ʙᴜᴛᴛᴏɴ ᴀɢᴀɪɴ.")

    story = await db.get_story(story_slug)
    if not story:
        return await message.reply_text("sᴏʀʀʏ, ɪ ᴄᴏᴜʟᴅɴ'ᴛ ғɪɴᴅ ᴛʜᴀᴛ sᴛᴏʀʏ ᴀɴʏᴍᴏʀᴇ.")

    episodes = story.get("episodes", {})
    story_name = story.get("name", story_slug)

    status = await message.reply_text(f"sᴇɴᴅɪɴɢ {story_name} ᴇᴘɪsᴏᴅᴇs {start_ep}-{end_ep}...")

    sent_file_ids = set()
    sent_count = 0

    for ep_no in range(start_ep, end_ep + 1):
        ep_data = episodes.get(str(ep_no))
        if not ep_data:
            continue
        file_id = ep_data["file_id"]
        if file_id in sent_file_ids:
            continue
        sent_file_ids.add(file_id)

        file_episodes = [
            int(k) for k, v in episodes.items() if v.get("file_id") == file_id
        ]
        file_episodes.sort()

        if len(file_episodes) > 1:
            ep_caption = f"{story_name} — ᴇᴘɪsᴏᴅᴇs {file_episodes[0]}-{file_episodes[-1]}"
        else:
            ep_caption = f"{story_name} — ᴇᴘɪsᴏᴅᴇ {ep_no}"

        try:
            await client.send_cached_media(
                chat_id=message.chat.id,
                file_id=file_id,
                caption=ep_caption,
            )
            sent_count += 1
        except Exception:
            pass

    if sent_count == 0:
        await status.edit_text("sᴏʀʀʏ, ɴᴏɴᴇ ᴏғ ᴛʜᴏsᴇ ᴇᴘɪsᴏᴅᴇs ᴀʀᴇ ᴀᴠᴀɪʟᴀʙʟᴇ ʀɪɢʜᴛ ɴᴏᴡ.")
    else:
        await status.edit_text(f"sᴇɴᴛ {sent_count} ғɪʟᴇ(s) ғʀᴏᴍ {story_name} ({start_ep}-{end_ep}).")

    await log(
        client,
        f"📤 Batch {start_ep}-{end_ep} of *{story_name}* delivered to "
        f"`{message.chat.id}` ({sent_count} file(s))",
    )


# --- Callback Query Handler for Inline Buttons ---
@Client.on_callback_query()
async def callback_handler(client: Client, query: CallbackQuery):
    data = query.data

    try:
        if data == "about_btn":
            about_text = (
                "⚙️ **ᴀʙᴏᴜᴛ ᴛʜɪs ʙᴏᴛ**\n\n"
                "• **ғʀᴀᴍᴇᴡᴏʀᴋ:** ᴘʏʀᴏɢʀᴀᴍ (ᴘʏᴛʜᴏɴ 3)\n"
                "• **ᴅᴀᴛᴀʙᴀsᴇ:** ᴍᴏɴɢᴏᴅʙ ᴀsʏɴᴄ (ᴍᴏᴛᴏʀ)\n"
                "• **ᴅᴇᴠᴇʟᴏᴘᴇʀ:** [ᴋᴀʟᴜᴜ](https://t.me/Kaluu)\n"
                "• **ᴠᴇsɪᴏɴ:** 2.0"
            )
            await query.message.edit_text(about_text, reply_markup=BACK_BUTTON, disable_web_page_preview=True)

        elif data == "help_btn":
            help_text = (
                "📖 **ʜᴇʟᴘ & ɪɴsᴛʀᴜᴄᴛɪᴏɴs**\n\n"
                "1. ᴊᴏɪɴ ᴏᴜʀ ᴄʜᴀɴɴᴇʟ ᴡʜᴇʀᴇ ʙᴀᴛᴄʜ ʟɪɴᴋs ᴀʀᴇ ᴘᴏsᴛᴇᴅ.\n"
                "2. ᴄʟɪᴄᴋ ᴏɴ ᴀɴʏ ᴇᴘɪsᴏᴅᴇ/ʙᴀᴛᴄʜ ʙᴜᴛᴛᴏɴ.\n"
                "3. ᴛʜᴇ ʙᴏᴛ ᴡɪʟʟ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ ᴅᴇʟɪᴠᴇʀ ᴀʟʟ ғɪʟᴇs ᴅɪʀᴇᴄᴛʟʏ ᴛᴏ ʏᴏᴜʀ ᴅᴍ!"
            )
            await query.message.edit_text(help_text, reply_markup=BACK_BUTTON)

        elif data == "home_btn":
            welcome_text = (
                f"ʜɪ [{query.from_user.first_name}]! ɪ ᴀᴍ ᴀɴ **ᴀᴜᴛᴏᴍᴀᴛᴇᴅ sᴍᴀʀᴛ ғɪʟᴇ sᴛᴏʀᴇ ʙᴏᴛ** 🤖\n\n"
                "ɪ ᴄᴀɴ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ ᴅᴇʟɪᴠᴇʀ sᴛᴏʀʏ ᴇᴘɪsᴏᴅᴇs ᴀɴᴅ ᴍᴀɴᴀɢᴇ ʙᴀᴛᴄʜ ғɪʟᴇs. "
                "ᴛᴀᴘ ᴀ ʙᴀᴛᴄʜ ʙᴜᴛᴛᴏɴ ɪɴ ᴛʜᴇ ᴄʜᴀɴɴᴇʟ, ᴀɴᴅ ɪ'ʟʟ sᴇɴᴅ ʏᴏᴜʀ ғɪʟᴇs ʀɪɢʜᴛ ʜᴇʀᴇ!"
            )
            await query.message.edit_text(welcome_text, reply_markup=MAIN_START_BUTTONS)

    except MessageNotModified:
        await query.answer("ᴀʟʀᴇᴀᴅʏ sʜᴏᴡɪɴɢ ᴛʜɪs ᴘᴀɢᴇ!")
