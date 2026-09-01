from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

import database as db
from log_utils import log

# --- Inline Keyboards ---
MAIN_START_BUTTONS = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("ℹ️ About", callback_data="about_btn"),
        InlineKeyboardButton("❓ Help", callback_data="help_btn")
    ],
    [
        InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/Kaluu")  # अपना डेवलपर यूजरनेम/लिंक डालें
    ]
])

BACK_BUTTON = InlineKeyboardMarkup([
    [InlineKeyboardButton("🔙 Back", callback_data="home_btn")]
])


# --- Commands & Deep Link Handler ---
@Client.on_message(filters.command("start") & filters.private)
async def start_cmd(client: Client, message: Message):
    args = message.command  # e.g. ["start", "batch-slug-211-220"]

    # 1. Normal /start command without deep link
    if len(args) < 2:
        welcome_text = (
            "Hi! I am an **Automated Smart File Store Bot** 🤖\n\n"
            "I can automatically deliver story episodes and manage batch files. "
            "Tap a batch button in the channel, and I'll send your files right here!"
        )
        return await message.reply_text(
            text=welcome_text,
            reply_markup=MAIN_START_BUTTONS
        )

    # 2. Deep link handling logic
    payload = args[1]

    if not payload.startswith("batch-"):
        return await message.reply_text("Hi! I didn't recognize that link.")

    try:
        _, rest = payload.split("-", 1)
        story_slug, start_ep, end_ep = rest.rsplit("-", 2)
        start_ep, end_ep = int(start_ep), int(end_ep)
    except ValueError:
        return await message.reply_text("That link looks broken — please tap the button again.")

    story = await db.get_story(story_slug)
    if not story:
        return await message.reply_text("Sorry, I couldn't find that story anymore.")

    episodes = story.get("episodes", {})
    story_name = story.get("name", story_slug)

    status = await message.reply_text(f"Sending {story_name} episodes {start_ep}-{end_ep}...")

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
            ep_caption = f"{story_name} — Episodes {file_episodes[0]}-{file_episodes[-1]}"
        else:
            ep_caption = f"{story_name} — Episode {ep_no}"

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
        await status.edit_text("Sorry, none of those episodes are available right now.")
    else:
        await status.edit_text(f"Sent {sent_count} file(s) from {story_name} ({start_ep}-{end_ep}).")

    await log(
        client,
        f"\U0001F4E4 Batch {start_ep}-{end_ep} of *{story_name}* delivered to "
        f"`{message.chat.id}` ({sent_count} file(s))",
    )


# --- Callback Query Handler for Inline Buttons ---
@Client.on_callback_query()
async def callback_handler(client: Client, query: CallbackQuery):
    data = query.data

    if data == "about_btn":
        about_text = (
            "⚙️ **About This Bot**\n\n"
            "• **Framework:** Pyrogram (Python 3)\n"
            "• **Database:** MongoDB Async (Motor)\n"
            "• **Developer:** [Kaluu](https://t.me/Kaluu)\n"
            "• **Version:** 2.0 (Automated File Store)"
        )
        await query.message.edit_text(about_text, reply_markup=BACK_BUTTON, disable_web_page_preview=True)

    elif data == "help_btn":
        help_text = (
            "📖 **Help & Instructions**\n\n"
            "1. Join our channel where batch links are posted.\n"
            "2. Click on any episode/batch button.\n"
            "3. The bot will automatically deliver all files directly to your DM!"
        )
        await query.message.edit_text(help_text, reply_markup=BACK_BUTTON)

    elif data == "home_btn":
        welcome_text = (
            "Hi! I am an **Automated Smart File Store Bot** 🤖\n\n"
            "I can automatically deliver story episodes and manage batch files. "
            "Tap a batch button in the channel, and I'll send your files right here!"
        )
        await query.message.edit_text(welcome_text, reply_markup=MAIN_START_BUTTONS)
