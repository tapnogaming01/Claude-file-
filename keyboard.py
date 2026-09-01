from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def chunk_episodes(episodes: list, batch_size: int = 10):
    """
    Episodes की लिस्ट (e.g. [1, 2, 3, ... 20]) को BATCH_SIZE (e.g. 10) के टुकड़ों में बांटता है।
    Output: [[1, 2, ... 10], [11, 12, ... 20]]
    """
    if not episodes:
        return []
    sorted_episodes = sorted(list(set(episodes)))
    return [sorted_episodes[i : i + batch_size] for i in range(0, len(sorted_episodes), batch_size)]


def build_batch_keyboard(story_slug: str, chunks: list, bot_username: str = None, per_row: int = 2):
    """
    chunks: list of lists of episode numbers, e.g. [[211..220], [221..230]]
    Generates batch deep-link buttons.
    """
    buttons = []
    row = []

    for chunk in chunks:
        if not chunk:
            continue
        start, end = chunk[0], chunk[-1]
        label = f"📦 {start}-{end}" if start != end else f"📦 {start}"
        
        # Deep link URL format
        if bot_username:
            url = f"https://t.me/{bot_username}?start=batch-{story_slug}-{start}-{end}"
        else:
            url = f"https://t.me/share/url?url=https://t.me/your_bot?start=batch-{story_slug}-{start}-{end}"

        row.append(InlineKeyboardButton(label, url=url))

        if len(row) == per_row:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    return InlineKeyboardMarkup(buttons)
