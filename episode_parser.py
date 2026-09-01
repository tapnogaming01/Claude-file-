import re


def extract_story_info(text: str):
    """
    कैप्शन की पहली लाइन से Story Name और Episode Number को अलग-अलग पहचानता है।
    """
    if not text:
        return None, []

    # सिर्फ पहली लाइन पढ़ें (ताकि लिंक्स से कंफ्यूजन न हो)
    first_line = text.split('\n')[0].strip()

    # Regex पैटर्न जो 'Episode', 'Ep', 'E', 'Part' आदि को पहचानेगा
    pattern = r'(.*?)(?:\b(?:episode|ep|e|part|ch)\b[\s\.\-\:]*)(\d+(?:\s*[\,\-\&]\s*\d+)*)'
    match = re.search(pattern, first_line, re.IGNORECASE)

    if match:
        # Story Name निकालें और फालतू सिम्बल्स (*, -, _) साफ करें
        raw_name = match.group(1).strip(" -_[]()*:#")
        story_name = raw_name if raw_name else "Unknown Story"

        # Episode Numbers निकालें
        ep_string = match.group(2)
        episodes = re.findall(r'\d+', ep_string)

        return story_name, episodes

    # अगर 'Ep' वर्ड नहीं लिखा है, लेकिन लास्ट में नंबर है (उदा: "Atript-dulhan 29")
    fallback_match = re.search(r'(.*?)\s+(\d+)$', first_line)
    if fallback_match:
        story_name = fallback_match.group(1).strip(" -_[]()*:#")
        return story_name, [fallback_match.group(2)]

    return None, []


# पुरानी कम्पेटीबिलिटी के लिए (Fallback)
def parse_episodes(text: str):
    _, episodes = extract_story_info(text)
    return episodes
