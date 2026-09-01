from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def build_batch_keyboard(bot_username: str, story_slug: str, chunks, per_row: int = 2):
    """
    chunks: list of lists of episode numbers, e.g. [[211..220], [221..230], [231..237]]
    Each chunk becomes one deep-link button like "211-220" that opens
    https://t.me/<bot_username>?start=batch-<story_slug>-<start>-<end>
    """
    buttons = []
    row = []
    for chunk in chunks:
        start, end = chunk[0], chunk[-1]
        label = f"{start}-{end}" if start != end else f"{start}"
        url = f"https://t.me/{bot_username}?start=batch-{story_slug}-{start}-{end}"
        row.append(InlineKeyboardButton(label, url=url))
        if len(row) == per_row:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)
