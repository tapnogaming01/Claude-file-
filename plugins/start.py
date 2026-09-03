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
from keyboard import to_small_caps
from log_utils import log

CANCELLED_TASKS = set()

# --- Keyboards ---
MAIN_START_BUTTONS = InlineKeyboardMarkup([
    [
        InlineKeyboardButton(f"ℹ️ {to_small_caps('About')}", callback_data="about_btn"),
        InlineKeyboardButton(f"❓ {to_small_caps('Help')}", callback_data="help_btn")
    ],
    [
        InlineKeyboardButton(f"👑 {to_small_caps('Developer')}", url="https://t.me/Kaluu")
    ]
])

BACK_BUTTON = InlineKeyboardMarkup([
    [InlineKeyboardButton(f"🔙 {to_small_caps('Back')}", callback_data="home_btn")]
])


def get_delivery_keyboard(user_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"👑 {to_small_caps('Developer')}", url="https://t.me/Kaluu")],
        [InlineKeyboardButton(f"❌ {to_small_caps('Cancel')}", callback_data=f"cancel_batch_{user_id}")]
    ])


async def get_protect_status() -> bool:
    return await db.get_protect_settings()


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
        [InlineKeyboardButton(f"📢 {to_small_caps('Update Channel')}", url=channel_url)]
    ])

    imp_label = to_small_caps("Important")
    del_note = to_small_caps("All Messages will be deleted after")
    save_note = to_small_caps("Please save or forward these messages to your personal saved messages to avoid losing them!")

    warning_text = (
        f"⚠️ **{imp_label}:**\n\n"
        f"• {del_note} **{time_str}**.\n"
        f"• {save_note}"
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
            [InlineKeyboardButton(f"📂 {to_small_caps('Get File Again')}", url=get_again_url)]
        ])

        del_title = to_small_caps("Your files have been deleted!")
        del_reason = to_small_caps("Files were automatically removed due to copyright policy.")
        del_action = to_small_caps("Please tap the button below to get them back again.")

        await warning_msg.edit_text(
            text=(
                f"🗑️ **{del_title}**\n\n"
                f"⚠️ {del_reason}\n"
                f"👉 {del_action}"
            ),
            reply_markup=get_again_btn
        )

    except Exception as e:
        print(f"Error in auto-delete task: {e}")


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
        print(f"❌ [ForceSub Exception] Error checking membership: {e}")
        return True, chat_target


# --- Commands ---
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


@Client.on_message(filters.command("reset") & filters.private)
async def reset_settings_cmd(client: Client, message: Message):
    if message.from_user.id not in getattr(config, "ADMINS", getattr(config, "ADMIN_IDS", [])):
        return

    await db.settings_col.delete_many({"_id": {"$in": ["protection", "verification", "forcesub"]}})
    await message.reply_text("🔄 **All dynamic settings reset to default!**")


@Client.on_message(filters.command("start") & filters.private)
async def start_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    args = message.command

    # 0. Banned Check
    if await db.is_user_banned(user_id):
        banned_title = to_small_caps("Access Denied!")
        banned_desc = to_small_caps("You have been banned from using this bot due to multiple bypass attempts.")
        return await message.reply_text(f"🚫 **{banned_title}**\n\n{banned_desc}")

    # 1. Force Sub Check
    is_joined, fs_channel = await check_force_sub(client, user_id)
    if not is_joined:
        clean_channel = str(fs_channel).replace("@", "")
        invite_link = f"https://t.me/{clean_channel}" if not clean_channel.startswith("-100") else f"https://t.me/c/{clean_channel[4:]}"
        
        param = args[1] if len(args) > 1 else ""
        bot_username = getattr(config, "BOT_USERNAME", None) or (await client.get_me()).username
        
        try_again_url = f"https://t.me/{bot_username}?start={param}" if param and param != "true" else f"https://t.me/{bot_username}?start=true"

        join_btn = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"📢 {to_small_caps('Join Channel')}", url=invite_link)],
            [InlineKeyboardButton(f"🔄 {to_small_caps('Try Again')}", url=try_again_url)]
        ])

        access_denied = to_small_caps("Access Denied!")
        join_prompt = to_small_caps("Please join our channel to use this bot and get your files.")

        return await message.reply_text(
            f"⚠️ **{access_denied}**\n\n{join_prompt}",
            reply_markup=join_btn
        )

    # 2. Normal /start Check
    if len(args) < 2 or args[1] in ["", "true"]:
        welcome_desc = to_small_caps("I am an automated smart file store bot. I can automatically deliver story episodes and manage batch files.")
        welcome_text = (
            f"✨ **{to_small_caps('Welcome')} [{message.from_user.first_name}]!**\n\n"
            f"{welcome_desc}"
        )
        return await message.reply_text(text=welcome_text, reply_markup=MAIN_START_BUTTONS)

    payload = args[1]

    # 3. Verification Link Callback Handler
    if payload.startswith("verify_"):
        token = payload.split("verify_")[-1]
        res_payload, status = await db.get_verify_token_payload(user_id, token)
        
        if status == "auto_banned":
            banned_msg = to_small_caps("You have been permanently banned for attempting to bypass the shortener 5 times!")
            return await message.reply_text(f"🚨 **{banned_msg}**")

        if status == "wrong_user":
            wrong_user_msg = to_small_caps("This link was generated by another user or is invalid for your account.")
            return await message.reply_text(f"⚠️ **{wrong_user_msg}**")
            
        if status == "bypassed":
            count = res_payload
            warn_msg = to_small_caps(f"Warning: Bypass Attempt {count}/5! (Reach 5 and you will be automatically banned).")
            return await message.reply_text(f"🚨 **{warn_msg}**")
        
        if status == "invalid":
            invalid_msg = to_small_caps("This link has expired or was already invalidated. Please generate a new link.")
            return await message.reply_text(f"❌ **{invalid_msg}**")
        
        await db.set_user_verified(user_id)
        
        bot_username = getattr(config, "BOT_USERNAME", None) or (await client.get_me()).username
        v_settings = await db.get_verification_settings()
        timeout_hours = v_settings.get("token_timeout", 86400) // 3600

        succ_title = to_small_caps("Verification Successful!")
        succ_desc = to_small_caps(f"You now have access for {timeout_hours} hours.")

        if res_payload and res_payload != "true":
            get_files_url = f"https://t.me/{bot_username}?start={res_payload}"
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"📂 {to_small_caps('Get Your Files')}", url=get_files_url)]
            ])
            return await message.reply_text(
                f"✅ **{succ_title}**\n\n{succ_desc}",
                reply_markup=btn
            )
        else:
            return await message.reply_text(f"✅ **{succ_title}**\n\n{succ_desc}")

    # 4. Shortener Verification Gate
    verified = await is_user_verified(user_id)
    if not verified:
        bot_username = getattr(config, "BOT_USERNAME", None) or (await client.get_me()).username
        token = "".join(random.choices(string.ascii_letters + string.digits, k=12))
        verify_payload = f"verify_{token}"
        
        await db.save_verify_token(user_id, token, payload)
        
        raw_verification_link = f"https://t.me/{bot_username}?start={verify_payload}"
        short_link = await get_shortlink(raw_verification_link)

        v_settings = await db.get_verification_settings()
        timeout_hours = v_settings.get("token_timeout", 86400) // 3600

        verify_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🔓 {to_small_caps('Verify Token')}", url=short_link)],
            [InlineKeyboardButton(f"❓ {to_small_caps('How To Verify')}", url="https://t.me/your_help_channel")]
        ])

        gate_title = to_small_caps("Access Denied / Token Expired!")
        gate_desc = to_small_caps(f"Please verify your token to get {timeout_hours} hours access to all files.")

        return await message.reply_text(
            f"🔒 **{gate_title}**\n\n{gate_desc}",
            reply_markup=verify_keyboard
        )

    # 5. Batch Delivery Processing
    if not payload.startswith("batch-"):
        return await message.reply_text(f"⚠️ {to_small_caps('I did not recognize that link.')}")

    try:
        _, rest = payload.split("-", 1)
        story_slug, start_ep, end_ep = rest.rsplit("-", 2)
        start_ep, end_ep = int(start_ep), int(end_ep)
    except ValueError:
        return await message.reply_text(f"⚠️ {to_small_caps('That link looks broken - please tap the button again.')}")

    story = await db.get_story(story_slug)
    if not story:
        return await message.reply_text(f"❌ {to_small_caps('Sorry, I could not find that story anymore.')}")

    episodes = story.get("episodes", {})
    story_name = story.get("name", story_slug)

    CANCELLED_TASKS.discard(user_id)

    wait_title = to_small_caps("Please Wait")
    processing_desc = to_small_caps(f"Processing {story_name} ({start_ep}-{end_ep})...")

    status_msg = await message.reply_text(
        f"⏳ **{wait_title}**\n\n{processing_desc}",
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

        formatted_story_name = to_small_caps(story_name)
        ep_label = to_small_caps("Episodes") if len(file_episodes) > 1 else to_small_caps("Episode")

        if len(file_episodes) > 1:
            ep_caption = f"🎬 **{formatted_story_name}** — {ep_label} {file_episodes[0]}-{file_episodes[-1]}"
        else:
            ep_caption = f"🎬 **{formatted_story_name}** — {ep_label} {ep_no}"

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
            cancel_msg = to_small_caps(f"File Delivery Cancelled by User! ({sent_count} files sent)")
            await status_msg.edit_text(f"❌ **{cancel_msg}**")
            if delete_timer > 0:
                asyncio.create_task(
                    schedule_file_deletion(client, message.chat.id, delivered_message_ids, delete_timer, payload)
                )
        else:
            cancel_msg = to_small_caps("File Delivery Cancelled! No files were sent.")
            await status_msg.edit_text(f"❌ **{cancel_msg}**")
    else:
        if sent_count == 0:
            no_ep_msg = to_small_caps("Sorry, none of those episodes are available right now.")
            await status_msg.edit_text(f"❌ **{no_ep_msg}**")
        else:
            succ_delivery = to_small_caps(f"Sent {sent_count} file(s) from {story_name} ({start_ep}-{end_ep})")
            await status_msg.edit_text(f"✅ **{succ_delivery}**.")
            
            if delete_timer > 0:
                asyncio.create_task(
                    schedule_file_deletion(client, message.chat.id, delivered_message_ids, delete_timer, payload)
                )

    await log(
        client,
        f"📤 Batch {start_ep}-{end_ep} of *{story_name}* processed for `{message.chat.id}` ({sent_count} file(s) delivered)"
    )


@Client.on_callback_query()
async def callback_handler(client: Client, query: CallbackQuery):
    data = query.data
    user_id = query.from_user.id

    try:
        if data.startswith("cancel_batch_"):
            target_user_id = int(data.split("_")[-1])
            if user_id != target_user_id:
                not_yours = to_small_caps("This is not your delivery process!")
                return await query.answer(f"⚠️ {not_yours}", show_alert=True)
            
            CANCELLED_TASKS.add(user_id)
            cancelling_text = to_small_caps("Cancelling file delivery...")
            await query.answer(f"❌ {cancelling_text}", show_alert=True)

        elif data == "about_btn":
            about_title = to_small_caps("About This Bot")
            framework_label = to_small_caps("Framework")
            database_label = to_small_caps("Database")
            dev_label = to_small_caps("Developer")
            ver_label = to_small_caps("Version")

            about_text = (
                f"⚙️ **{about_title}**\n\n"
                f"• **{framework_label}:** Pyrogram (Python 3)\n"
                f"• **{database_label}:** MongoDB Async (Motor)\n"
                f"• **{dev_label}:** [Kaluu](https://t.me/Kaluu)\n"
                f"• **{ver_label}:** 2.0"
            )
            await query.message.edit_text(about_text, reply_markup=BACK_BUTTON, disable_web_page_preview=True)

        elif data == "help_btn":
            help_title = to_small_caps("Help & Instructions")
            step1 = to_small_caps("1. Join our channel where batch links are posted.")
            step2 = to_small_caps("2. Click on any episode/batch button.")
            step3 = to_small_caps("3. The bot will automatically deliver all files!")

            help_text = (
                f"📖 **{help_title}**\n\n"
                f"{step1}\n"
                f"{step2}\n"
                f"{step3}"
            )
            await query.message.edit_text(help_text, reply_markup=BACK_BUTTON)

        elif data == "home_btn":
            welcome_desc = to_small_caps("I am an automated smart file store bot. I can automatically deliver story episodes and manage batch files.")
            welcome_text = (
                f"✨ **{to_small_caps('Welcome')} [{query.from_user.first_name}]!**\n\n"
                f"{welcome_desc}"
            )
            await query.message.edit_text(welcome_text, reply_markup=MAIN_START_BUTTONS)

    except MessageNotModified:
        already_showing = to_small_caps("Already showing this page!")
        await query.answer(f"ℹ️ {already_showing}")
