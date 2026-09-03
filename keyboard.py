from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def to_small_caps(text: str) -> str:
    """
    Standard text ko Premium Small Caps unicode text mein convert karta hai.
    """
    if not text:
        return ""
        
    char_map = {
        'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ғ', 'g': 'ɢ',
        'h': 'ʜ', 'i': 'ɪ', 'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ', 'm': 'ᴍ', 'n': 'ɴ',
        'o': 'ᴏ', 'p': 'ᴘ', 'q': 'ǫ', 'r': 'ʀ', 's': 's', 't': 'ᴛ', 'u': 'ᴜ',
        'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x', 'y': 'ʏ', 'z': 'ᴢ',
        'A': 'ᴀ', 'B': 'ʙ', 'C': 'ᴄ', 'D': 'ᴅ', 'E': 'ᴇ', 'F': 'ғ', 'G': 'ɢ',
        'H': 'ʜ', 'I': 'ɪ', 'J': 'ᴊ', 'K': 'ᴋ', 'L': 'ʟ', 'M': 'ᴍ', 'N': 'ɴ',
        'O': 'ᴏ', 'P': 'ᴘ', 'Q': 'ǫ', 'R': 'ʀ', 'S': 's', 'T': 'ᴛ', 'U': 'ᴜ',
        'V': 'ᴠ', 'W': 'ᴡ', 'X': 'x', 'Y': 'ʏ', 'Z': 'ᴢ'
    }
    return "".join(char_map.get(c, c) for c in text)


def build_grid_keyboard_from_captions(
    caption_ranges: list, 
    bot_username: str, 
    story_slug: str, 
    tutorial_url: str = "https://t.me/YourTutorialLink", 
    help_url: str = "https://t.me/YourHelpLink"
) -> InlineKeyboardMarkup:
    """
    Caption ranges [(1, 10), (11, 21)...] se 2-Column Grid Buttons banata hai 
    aur bottom mein Small Caps Utility Buttons (Tutorial / Help Us) attach karta hai.
    """
    clean_username = bot_username.replace("@", "") if bot_username else ""
    buttons = []
    
    # 1. Per-file caption range buttons generate karein
    for start_ep, end_ep in caption_ranges:
        label = f"{start_ep}-{end_ep}" if start_ep != end_ep else f"{start_ep}"
        payload = f"batch-{story_slug}-{start_ep}-{end_ep}"
        url = f"https://t.me/{clean_username}?start={payload}"
        buttons.append(InlineKeyboardButton(label, url=url))

    # 2. 2-Column Grid Layout (Side-by-Side)
    rows = []
    for i in range(0, len(buttons), 2):
        rows.append(buttons[i:i+2])

    # 3. Premium Small Caps Utility Buttons
    tutorial_label = to_small_caps("Tutorial")
    help_label = to_small_caps("Help Us")
    
    rows.append([
        InlineKeyboardButton(f"🎬 {tutorial_label}", url=tutorial_url),
        InlineKeyboardButton(f"💬 {help_label}", url=help_url)
    ])

    return InlineKeyboardMarkup(rows)
