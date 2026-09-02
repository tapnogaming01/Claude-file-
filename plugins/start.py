import time
import asyncio
import random
import string
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import MessageNotModified, FloodWait, UserNotParticipant, ChatAdminRequired, PeerIdInvalid

import config
import database as db
from plugins.verification import is_user_verified, get_shortlink
from log_utils import log

# Global dictionary to manage ongoing batch delivery cancellation
CANCELLED_TASKS = set()

# --- Inline Keyboards ---
MAIN_START_BUTTONS = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("ℹ️ ᴀʙᴏᴜᴛ", callback_data="about_btn"),
        InlineKeyboardButton("❓ ʜᴇʟᴘ", callback_data="help_btn")
    ],
    [
        InlineKeyboardButton("👑 ᴅᴇᴠᴇʟᴏᴘᴇʀ", url="https://t.me/Kaluu")
    ]
])

BACK_BUTTON = InlineKeyboardMarkup([
    [InlineKeyboardButton("🔙 ʙᴀᴄᴋ", callback_data="home_btn")]
])

def get_delivery_keyboard(user_id: int):
    """UI with Developer & Cancel buttons"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👑 ᴅᴇᴠᴇʟᴏᴘᴇʀ", url="https://t.me/Kaluu")],
        [InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data=f"cancel_batch_{user_id}")]
    ])


# --- Dynamic Content Protection Helper ---
async def get_protect_status() -> bool:
    """डेटाबेस से प्रोटेक्ट कंटेंट का डायनेमिक स्टेटस लाता है"""
    doc = await db.settings_col.find_one({"_id": "protection"})
    if not doc:
        return getattr(config, "PROTECT_CONTENT", False)
    return doc.get("status", False)


# --- Auto-Delete Task Helper ---
async def schedule_file_deletion(client: Client, chat_id: int, message_ids: list, delay_seconds: int, payload: str):
    if delay_seconds <= 0 or not message_ids:
        return
    
    minutes = delay_seconds // 60
    time_str = f"{minutes} minutes" if minutes >= 1 else f"{delay_seconds} seconds"

    fs_settings = await db.get_forcesub_settings()
    force_channel = fs_settings.get("channel", "")
    
    if force_channel:
        clean_channel = str(force_channel).replace("@", "")
        channel_url = f"https://t.me/{clean_channel}" if not clean_channel.startswith("-100") else f"https://t.me/c/{clean_channel[4:]}"
    else:
        channel_url = "https://t.me/your_update_channel"

    update_channel_btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 ᴜᴘᴅᴀᴛᴇ ᴄʜᴀɴɴᴇʟ", url=channel_url)]
    ])

    warning_text = (
        f"⚠️ **Important:**\n\n"
        f"*All Messages will be deleted after **{time_str}**. "
        f"Please save or forward these messages to your **personal saved messages** to avoid losing them!*"
    )
    
    warning_msg = await client.send_message(
        chat_id=chat_id,
        text=warning_text,
        reply_markup=update_channel_btn
    )

    await asyncio.sleep(delay_seconds)
    
    try:
        await client.delete_messages(chat_id=chat_id, message_ids=message_ids)
        
        bot_username = getattr(config, "BOT_USERNAME", None) or (await client.get_me()).username
        get_again_url = f"https://t.me/{bot_username}?start={payload}" if payload else f"https://t.me/{bot_username}?start=true"

        get_again_btn = InlineKeyboardMarkup([
            [InlineKeyboardButton("📂 ɢᴇᴛ ғɪʟᴇ ᴀɢᴀɪɴ", url=get_again_url)]
        ])

        await warning_msg.edit_text(
            text=(
                f"🗑️ **ʏᴏᴜʀ ғɪʟᴇs ʜᴀᴠᴇ ʙᴇᴇɴ ᴅᴇʟᴇᴛᴇᴅ!**\n\n"
                f"⚠️ Files were automatically removed after **{time_str}** due to copyright policy.\n"
                f"Please tap the button below to get them back again."
            ),
            reply_markup=get_again_btn
        )

    except Exception as e:
        print(f"Error in auto-delete task: {e}")


# --- Dynamic Force Join Helper ---
async def check_force_sub(client: Client, user_id: int):
    fs_settings = await db.get_forcesub_settings()
    
    if not fs_settings.get("status", True):
        return True, None

    force_channel = fs_settings.get("channel")
    if not force_channel:
        return True, None

    try:
        if str(force_channel).startswith("-100") or str(force_channel).startswith("-"):
            chat_target = int(force_channel)
        else:
            chat_target = str(force_channel) if str(force_channel).startswith("@") else f"@{force_channel}"
    except ValueError:
        chat_target = force_channel

    try:
        user = await client.get_chat_member(chat_id=chat_target, user_id=user_id)
        if user.status in ["kicked", "left"]:
            return False, chat_target
        return True, chat_target

    except UserNotParticipant:
        return False, chat_target
        
    except ChatAdminRequired:
        print(f"⚠️ [ForceSub Error] Bot is NOT ADMIN in Force Sub channel: {chat_target}")
        return True, chat_target
        
    except (PeerIdInvalid, Exception) as e:
        print(f"❌ [ForceSub Exception] Error checking membership for {chat_target}: {e}")
        return True, chat_target


# --- Dynamic Protection Toggle Command (Admin Only) ---
@Client.on_message(filters.command("protect") & filters.private)
async def toggle_protect_cmd(client: Client, message: Message):
    if message.from_user.id not in getattr(config, "ADMINS", getattr(config, "ADMIN_IDS", [])):
        return

    args = message.command
    if len(args) < 2:
        curr_status = await get_protect_status()
        status_text = "🟢 **ON**" if curr_status else "🔴 **OFF**"
        return await message.reply_text(
            f"🛡️ **Dynamic Protection Status:** {status_text}\n\n"
            f"**Usage:** `/protect on` or `/protect off`"
        )

    val = args[1].lower()
    if val in ["on", "true", "yes"]:
        await db.settings_col.update_one({"_id": "protection"}, {"$set": {"status": True}}, upsert=True)
        await message.reply_text("✅ **Content Protection enabled! Users cannot forward or save files.**")
    elif val in ["off", "false", "no"]:
        await db.settings_col.update_one({"_id": "protection"}, {"$set": {"status": False}}, upsert=True)
        await message.reply_text("🔴 **Content Protection disabled! Forwarding allowed.**")
    else:
        await message.reply_text("⚠️ Invalid argument. Use `/protect on` or `/protect off`")


# --- Dynamic Resetting Command (Admin Only) ---
@Client.on_message(filters.command("reset") & filters.private)
async def reset_settings_cmd(client: Client, message: Message):
    if message.from_user.id not in getattr(config, "ADMINS", getattr(config, "ADMIN_IDS", [])):
        return

    await db.settings_col.delete_many({"_id": {"$in": ["protection", "verification", "forcesub"]}})
    await message.reply_text("🔄 **All dynamic settings (Protection, Verification, ForceSub) reset to default!**")


# --- Commands & Deep Link Handler ---
@Client.on_message(filters.command("start") & filters.private)
async def start_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    args = message.command

    # 0. Banned User Check
    if await db.is_user_banned(user_id):
        return await message.reply_text(
            "🚫 **ᴀᴄᴄᴇss ᴅᴇɴɪᴇᴅ!**\n\n"
            "ʏᴏᴜ ʜᴀᴠᴇ ʙᴇᴇɴ **ʙᴀɴɴᴇᴅ** ғʀᴏᴍ ᴜsɪɴɢ ᴛʜɪs ʙᴏᴛ ᴅᴜᴇ ᴛᴏ ᴍᴜʟᴛɪᴘʟᴇ ʙʏᴘᴀss ᴀᴛᴛᴇᴍᴘᴛs."
        )

    # 1. Force Sub Check
    is_joined, fs_channel = await check_force_sub(client, user_id)
    if not is_joined:
        clean_channel = str(fs_channel).replace("@", "")
        invite_link = f"https://t.me/{clean_channel}" if not clean_channel.startswith("-100") else f"https://t.me/c/{clean_channel[4:]}"
        
        param = args[1] if len(args) > 1 else ""
        bot_username = getattr(config, "BOT_USERNAME", None) or (await client.get_me()).username
        
        if param in ["", "true"]:
            try_again_url = f"https://t.me/{bot_username}?start=true"
        else:
            try_again_url = f"https://t.me/{bot_username}?start={param}"

        join_btn = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ", url=invite_link)],
            [InlineKeyboardButton("🔄 ᴛʀʏ ᴀɢᴀɪɴ", url=try_again_url)]
        ])
        return await message.reply_text(
            "⚠️ **ᴀᴄᴄᴇss ᴅᴇɴɪᴇᴅ!**\n\n"
            "ᴘʟᴇᴀsᴇ ᴊᴏɪɴ ᴏᴜʀ ᴄʜᴀɴɴᴇʟ ᴛᴏ ᴜsᴇ ᴛʜɪs ʙᴏᴛ ᴀɴᴅ ɢᴇᴛ ʏᴏᴜʀ ғɪʟᴇs.",
            reply_markup=join_btn
        )

    # 2. Normal /start Check
    if len(args) < 2 or args[1] in ["", "true"]:
        welcome_text = (
            f"ʜɪ [{message.from_user.first_name}]! ɪ ᴀᴍ ᴀɴ **ᴀᴜᴛᴏᴍᴀᴛᴇᴅ sᴍᴀʀᴛ ғɪʟᴇ sᴛᴏʀᴇ ʙᴏᴛ** 🤖\n\n"
            "ɪ ᴄᴀɴ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ ᴅᴇʟɪᴠᴇʀ sᴛᴏʀʏ ᴇᴘɪsᴏᴅᴇs ᴀɴᴅ ᴍᴀɴᴀɢᴇ ʙᴀᴛᴄʜ ғɪʟᴇs."
        )
        return await message.reply_text(text=welcome_text, reply_markup=MAIN_START_BUTTONS)

    payload = args[1]

    # 3. Strict Verification Link Handler (Shortener API Response)
    if payload.startswith("verify_"):
        token = payload.split("verify_")[-1]
        
        res_payload, status = await db.get_verify_token_payload(user_id, token)
        
        if status == "auto_banned":
            return await message.reply_text(
                "🚨 **🚨 ʙᴀɴɴᴇᴅ ᴀʟᴇʀᴛ! 🚨**\n\n"
                "ʏᴏᴜ ʜᴀᴠᴇ ʙᴇᴇɴ **ᴘᴇʀᴍᴀɴᴇɴᴛʟʏ ʙᴀɴɴᴇᴅ** ғᴏʀ ᴀᴛᴛᴇᴍᴘᴛɪɴɢ ᴛᴏ ʙʏᴘᴀss ᴛʜᴇ sʜᴏʀᴛᴇɴᴇʀ **5 ᴛɪᴍᴇs**!"
            )

        if status == "wrong_user":
            return await message.reply_text(
                "⚠️ **Access Denied!**\n\n"
                "This link was generated by another user or is invalid for your account."
            )
            
        if status == "bypassed":
            count = res_payload
            return await message.reply_text(
                f"🚨 **Nice try, hacker!** 😏\n\n"
                f"भाई, तू सिस्टम को बाईपास करने की कोशिश कर रहा है? 🛑\n"
                f"जितनी देर तू ये शॉर्टकट और बाईपास स्क्रिप्ट लगाने में लगाता है, उतने समय में तो genuine तरीके से लिंक ओपन करके फाइल मिल भी जाती! 🎬😂\n\n"
                f"⚠️ **Warning:** Bypass Attempt **{count}/5**! (Reach 5 and you will be automatically banned)."
            )
        
        if status == "invalid":
            return await message.reply_text(
                "❌ **Invalid or Expired Link!**\n\n"
                "This link has expired or was already invalidated due to a bypass attempt. Please generate a new link."
            )
        
        # ✅ Genuine Verification: set verified_at & reset bypass count to 0
        await db.set_user_verified(user_id)
        
        bot_username = getattr(config, "BOT_USERNAME", None) or (await client.get_me()).username
        v_settings = await db.get_verification_settings()
        timeout_hours = v_settings.get("token_timeout", 86400) // 3600

        if res_payload:
            get_files_url = f"https://t.me/{bot_username}?start={res_payload}"
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("📂 ɢᴇᴛ ʏᴏᴜʀ ғɪʟᴇs", url=get_files_url)]
            ])
            return await message.reply_text(
                f"✅ **ᴠᴇʀɪғɪᴄᴀᴛɪᴏɴ sᴜᴄᴄᴇssғᴜʟ!**\n\n"
                f"ʏᴏᴜ ɴᴏᴡ ʜᴀᴠᴇ ᴀᴄᴄᴇss ғᴏʀ {timeout_hours} ʜᴏᴜʀs. Click below to get your files!",
                reply_markup=btn
            )
        else:
            return await message.reply_text(
                f"✅ **ᴠᴇʀɪғɪᴄᴀᴛɪᴏɴ sᴜᴄᴄᴇssғᴜʟ!**\n\nʏᴏᴜ ɴᴏᴡ ʜᴀᴠᴇ ᴀᴄᴄᴇss ғᴏʀ {timeout_hours} ʜᴏᴜʀs."
            )

    # 4. Shortener Verification Check (फाइल मांगने पर Secret API Key Wrap करेगा)
    verified = await is_user_verified(user_id)
    if not verified:
        bot_username = getattr(config, "BOT_USERNAME", None) or (await client.get_me()).username
        token = "".join(random.choices(string.ascii_letters + string.digits, k=12))
        verify_payload = f"verify_{token}"
        
        # Store dynamic secret key with payload in DB
        await db.save_verify_token(user_id, token, payload)
        
        raw_verification_link = f"https://t.me/{bot_username}?start={verify_payload}"
        short_link = await get_shortlink(raw_verification_link)

        v_settings = await db.get_verification_settings()
        timeout_hours = v_settings.get("token_timeout", 86400) // 3600

        verify_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔓 ᴠᴇʀɪғʏ ᴛᴏᴋᴇɴ", url=short_link)],
            [InlineKeyboardButton("❓ ʜᴏᴡ ᴛᴏ ᴠᴇʀɪғʏ", url="https://t.me/your_help_channel")]
        ])

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

    CANCELLED_TASKS.discard(user_id)

    status_msg = await message.reply_text(
        "⚠️ **ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ**\n\n"
        f"⏳ Processing **{story_name}** ({start_ep}-{end_ep})...",
        reply_markup=get_delivery_keyboard(user_id)
    )

    sent_file_ids = set()
    delivered_message_ids = []
    sent_count = 0
    is_cancelled = False

    protect_content = await get_protect_status()

    for ep_no in range(start_ep, end_ep + 1):
        if user_id in CANCELLED_TASKS:
            CANCELLED_TASKS.remove(user_id)
            is_cancelled = True
            break

        ep_data = episodes.get(str(ep_no))
        if not ep_data:
            continue
        file_id = ep_data["file_id"]
        if file_id in sent_file_ids:
            continue
        sent_file_ids.add(file_id)

        file_episodes = [int(k) for k, v in episodes.items() if v.get("file_id") == file_id]
        file_episodes.sort()

        if len(file_episodes) > 1:
            ep_caption = f"🎬 **{story_name}** — Episodes {file_episodes[0]}-{file_episodes[-1]}"
        else:
            ep_caption = f"🎬 **{story_name}** — Episode {ep_no}"

        try:
            sent_msg = await client.send_cached_media(
                chat_id=message.chat.id,
                file_id=file_id,
                caption=ep_caption,
                protect_content=protect_content
            )
            delivered_message_ids.append(sent_msg.id)
            sent_count += 1
            await asyncio.sleep(1.5)

        except FloodWait as e:
            await asyncio.sleep(e.value)
            sent_msg = await client.send_cached_media(
                chat_id=message.chat.id,
                file_id=file_id,
                caption=ep_caption,
                protect_content=protect_content
            )
            delivered_message_ids.append(sent_msg.id)
            sent_count += 1
            await asyncio.sleep(1.5)
        except Exception:
            pass

    delete_timer = getattr(config, "AUTO_DELETE_TIME", 0)

    if is_cancelled:
        if sent_count > 0:
            await status_msg.edit_text(f"❌ **File Delivery Cancelled by User!** ({sent_count} files sent)")
            if delete_timer > 0:
                asyncio.create_task(
                    schedule_file_deletion(client, message.chat.id, delivered_message_ids, delete_timer, payload)
                )
        else:
            await status_msg.edit_text("❌ **File Delivery Cancelled!** No files were sent.")
    else:
        if sent_count == 0:
            await status_msg.edit_text("sᴏʀʀʏ, ɴᴏɴᴇ ᴏғ ᴛʜᴏsᴇ ᴇᴘɪsᴏᴅᴇs ᴀʀᴇ ᴀᴠᴀɪʟᴀʙʟᴇ ʀɪɢʜᴛ ɴᴏᴡ.")
        else:
            await status_msg.edit_text(f"✅ **Sent {sent_count} file(s) from {story_name} ({start_ep}-{end_ep})**.")
            
            if delete_timer > 0:
                asyncio.create_task(
                    schedule_file_deletion(client, message.chat.id, delivered_message_ids, delete_timer, payload)
                )

    await log(
        client,
        f"📤 Batch {start_ep}-{end_ep} of *{story_name}* processed for `{message.chat.id}` ({sent_count} file(s) delivered)"
    )


# --- Callback Handler ---
@Client.on_callback_query()
async def callback_handler(client: Client, query: CallbackQuery):
    data = query.data
    user_id = query.from_user.id

    try:
        if data.startswith("cancel_batch_"):
            target_user_id = int(data.split("_")[-1])
            if user_id != target_user_id:
                return await query.answer("⚠️ This is not your delivery process!", show_alert=True)
            
            CANCELLED_TASKS.add(user_id)
            await query.answer("❌ Cancelling file delivery...", show_alert=True)

        elif data == "about_btn":
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
                "3. ᴛʜᴇ ʙᴏᴛ ᴡɪʟʟ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ ᴅᴇʟɪᴠᴇʀ ᴀʟʟ ғɪʟᴇs!"
            )
            await query.message.edit_text(help_text, reply_markup=BACK_BUTTON)

        elif data == "home_btn":
            welcome_text = (
                f"ʜɪ [{query.from_user.first_name}]! ɪ ᴀᴍ ᴀɴ **ᴀᴜᴛᴏᴍᴀᴛᴇᴅ sᴍᴀʀᴛ ғɪʟᴇ sᴛᴏʀᴇ ʙᴏᴛ** 🤖\n\n"
                "ɪ ᴄᴀɴ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ ᴅᴇʟɪᴠᴇʀ sᴛᴏʀʏ ᴇᴘɪsᴏᴅᴇs ᴀɴᴅ ᴍᴀɴᴀɢᴇ ʙᴀᴛᴄʜ ғɪʟᴇs."
            )
            await query.message.edit_text(welcome_text, reply_markup=MAIN_START_BUTTONS)

    except MessageNotModified:
        await query.answer("ᴀʟʀᴇᴀᴅʏ sʜᴏᴡɪɴɢ ᴛʜɪs ᴘᴀɢᴇ!")
