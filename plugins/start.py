import time
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import MessageNotModified, UserNotParticipant

import config
import database as db
from utils.verification import is_user_verified, get_shortlink
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


# --- Force Join Helper ---
async def check_force_sub(client: Client, user_id: int):
    force_channel = getattr(config, "FORCE_SUB_CHANNEL", None)
    if not force_channel:
        return True
    try:
        user = await client.get_chat_member(force_channel, user_id)
        if user.status in ["kicked", "left"]:
            return False
        return True
    except Exception:
        return False


# --- Commands & Deep Link Handler ---
@Client.on_message(filters.command("start") & filters.private)
async def start_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    args = message.command  # e.g. ["start", "batch-slug-211-220"]

    # 1. Force Sub Check
    if not await check_force_sub(client, user_id):
        force_channel = getattr(config, "FORCE_SUB_CHANNEL", "")
        invite_link = f"https://t.me/{str(force_channel).replace('@', '')}"
        
        # Deep link param pass back on retry
        param = args[1] if len(args) > 1 else ""
        bot_username = (await client.get_me()).username
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

    # 2. Normal /start command without deep link
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

    # 3. Dynamic Verification Check
    payload = args[1]
    verified = await is_user_verified(user_id)
    if not verified:
        bot_username = (await client.get_me()).username
        original_link = f"https://t.me/{bot_username}?start={payload}"
        short_link = await get_shortlink(original_link)

        verify_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔓 ᴠᴇʀɪғʏ ᴛᴏᴋᴇɴ", url=short_link)],
            [InlineKeyboardButton("❓ ʜᴏᴡ ᴛᴏ ᴠᴇʀɪғʏ", url="https://t.me/your_help_channel")]
        ])

        return await message.reply_text(
            "🔒 **ᴀᴄᴄᴇss ᴅᴇɴɪᴇᴅ / ᴛᴏᴋᴇɴ ᴇxᴘɪʀᴇᴅ!**\n\n"
            "ᴘʟᴇᴀsᴇ ᴠᴇʀɪғʏ ʏᴏᴜʀ ᴛᴏᴋᴇɴ ᴛᴏ ɢᴇᴛ 1 ʜᴏᴜʀs ᴀᴄᴄᴇss ᴛᴏ ᴀʟʟ ғɪʟᴇs.",
            reply_markup=verify_keyboard
        )

    # 4. Handle Verification Callback/Token Success
    if payload.startswith("verify_"):
        await db.update_user_verification(user_id, time.time())
        return await message.reply_text("✅ **ᴠᴇʀɪғɪᴄᴀᴛɪᴏɴ sᴜᴄᴄᴇssғᴜʟ!**\n\nʏᴏᴜ ɴᴏᴡ ʜᴀᴠᴇ ᴀᴄᴄᴇss ғᴏʀ 24 ʜᴏᴜʀs.")

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
                "• **ᴠᴇʀsɪᴏɴ:** 2.0"
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
