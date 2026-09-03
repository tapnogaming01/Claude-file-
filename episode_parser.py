import re


def parse_range(ep_string: str) -> list[int]:
    """
    Ep string se numbers aur ranges (e.g. '61 To 85' ya '1-10') parse karke 
    saare episode numbers integer list mein return karta hai.
    """
    # Check for range patterns like "61 TO 85" or "61 - 85"
    range_match = re.search(r'(\d+)\s*(?:to|\-)\s*(\d+)', ep_string, re.IGNORECASE)
    if range_match:
        start_ep = int(range_match.group(1))
        end_ep = int(range_match.group(2))
        if start_ep <= end_ep:
            return list(range(start_ep, end_ep + 1))
        else:
            return list(range(end_ep, start_ep + 1))

    # Single or comma separated numbers fallback (e.g. "1, 2, 3")
    nums = re.findall(r'\d+', ep_string)
    return [int(n) for n in nums] if nums else []


def extract_story_info(text: str):
    """
    Extracts Story Name and Episode Numbers list from the first line of caption.
    """
    if not text:
        return None, []

    # Process only the first line
    first_line = text.split('\n')[0].strip()

    # Regex pattern for 'Episode', 'Ep', 'E', 'Part', 'Ch'
    pattern = r'(.*?)(?:\b(?:episode|ep|e|part|ch)\b[\s\.\-\:]*)(\d+[\s\w\,\-\&]*)$'
    match = re.search(pattern, first_line, re.IGNORECASE)

    if match:
        raw_name = match.group(1).strip(" -_[]()*:#")
        story_name = raw_name if raw_name else "Unknown Story"

        ep_string = match.group(2)
        episodes = parse_range(ep_string)

        return story_name, episodes

    # Fallback pattern for numbers at the end without 'Ep' (e.g. "Atript Dulhan 29" or "Atript Dulhan 20 To 30")
    fallback_match = re.search(r'(.*?)\s+(\d+(?:\s*(?:to|\-)\s*\d+)?)$', first_line, re.IGNORECASE)
    if fallback_match:
        raw_name = fallback_match.group(1).strip(" -_[]()*:#")
        story_name = raw_name if raw_name else "Unknown Story"
        
        ep_string = fallback_match.group(2)
        episodes = parse_range(ep_string)

        return story_name, episodes

    return None, []


def parse_episodes(text: str):
    """
    Fallback method for backwards compatibility.
    """
    _, episodes = extract_story_info(text)
    return episodes
