from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def create_batch_button(bot_username: str, story_slug: str, start_ep: int, end_ep: int) -> InlineKeyboardButton:
    """
    कैप्शन रेंज के आधार पर एक सिंगल क्लीन बटन बनाता है (उदा: '1-10' या '11-20')।
    """
    clean_username = bot_username.replace("@", "") if bot_username else ""
    
    # स्क्रीनशॉट के मुताबिक क्लीन लेबल (बिना किसी इमोजी के)
    label = f"{start_ep}-{end_ep}" if start_ep != end_ep else f"{start_ep}"
    
    # Direct Telegram Deep Link Payload
    url = f"https://t.me/{clean_username}?start=batch-{story_slug}-{start_ep}-{end_ep}"
    
    return InlineKeyboardButton(label, url=url)


def build_batch_keyboard_2col(existing_keyboard: InlineKeyboardMarkup, new_button: InlineKeyboardButton, per_row: int = 2) -> InlineKeyboardMarkup:
    """
    पुराने बटन्स को रिटेन करते हुए नए बटन को अटैच करता है 
    और 2-Column Grid (2x2 + 1) लेआउट में ऑटोमैटिक री-अरेंज करता है।
    """
    flat_buttons = []

    # 1. पुराना Inline Keyboard अगर मौजूद है तो उसके सारे बटन्स एक लिस्ट में निकालें
    if existing_keyboard and existing_keyboard.inline_keyboard:
        for row in existing_keyboard.inline_keyboard:
            for btn in row:
                flat_buttons.append(btn)

    # 2. नया बटन लिस्ट में अटैच करें
    flat_buttons.append(new_button)

    # 3. 2-2 की जोड़ी बनाकर 2-Column Grid तैयार करें
    grid_rows = []
    for i in range(0, len(flat_buttons), per_row):
        grid_rows.append(flat_buttons[i : i + per_row])

    return InlineKeyboardMarkup(grid_rows)
