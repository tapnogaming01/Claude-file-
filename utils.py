import re


def slugify(text: str) -> str:
    """
    Converts a story name into a safe identifier: only letters, numbers,
    and underscores. Used both as the MongoDB story key and inside
    Telegram deep-link payloads (which only allow A-Z a-z 0-9 _ -).
    """
    slug = re.sub(r"[^A-Za-z0-9]+", "_", text.strip())
    return slug.strip("_").lower()
