from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def chunk_episodes(episodes: list, batch_size: int = 10):
    """
    Episodes की लिस्ट को BATCH_SIZE (e.g. 10) के टुकड़ों में बांटता है।
    """
    if not episodes:
        return []
    sorted_episodes = sorted(list(set(episodes)))
    return [sorted_episodes[i : i + batch_size] for i in range(0, len(sorted_episodes), batch_size)]


def build_batch_keyboard(bot_username: str, story_slug: str, chunks: list, per_row: int = 2):
    """
    Direct Deep Link Buttons: https://t.me/<bot_username>?start=batch-<story_slug>-<start>-<end>
    """
    buttons = []
    row = []

    # Clean username if @ is passed
    clean_username = bot_username.replace("@", "") if bot_username else ""

    for chunk in chunks:
        if not chunk:
            continue
        start, end = chunk[0], chunk[-1]
        label = f"📦 {start}-{end}" if start != end else f"📦 {start}"
        
        # Direct Telegram Deep Link
        url = f"https://t.me/{clean_username}?start=batch-{story_slug}-{start}-{end}"

        row.append(InlineKeyboardButton(label, url=url))

        if len(row) == per_row:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    return InlineKeyboardMarkup(buttons)
