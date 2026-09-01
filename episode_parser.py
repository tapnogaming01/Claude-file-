import re

# Matches things like: "Episode 1-5", "EP 01 - 05", "1 to 5"
RANGE_PATTERNS = [
    r"(?:episode|ep|e)\s*[:\-]?\s*(\d{1,3})\s*(?:-|to|–)\s*(\d{1,3})",
    r"\b(\d{1,3})\s*(?:-|to|–)\s*(\d{1,3})\b",
]

# Matches things like: "Episode 3", "EP03", "E3"
SINGLE_PATTERNS = [
    r"(?:episode|ep|e)\s*[:\-]?\s*(\d{1,3})",
]


def parse_episodes(caption: str):
    """
    Reads a file's caption and returns a list of episode-number strings.

    - "Episode 1-5" / "EP 01-05" -> ["1", "2", "3", "4", "5"]   (combined file)
    - "Episode 3"                -> ["3"]                        (single episode)
    - no caption / no match      -> ["1"]                        (fallback assumption)
    """
    if not caption:
        return ["1"]

    text = caption.lower()

    for pattern in RANGE_PATTERNS:
        match = re.search(pattern, text)
        if match:
            start, end = int(match.group(1)), int(match.group(2))
            if start <= end and (end - start) < 100:
                return [str(n) for n in range(start, end + 1)]

    for pattern in SINGLE_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return [match.group(1)]

    return ["1"]
