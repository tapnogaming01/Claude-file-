from datetime import datetime
import pytz

def get_dashboard_text(story_name: str, total_blocks: int, current_buffer: int, max_buffer: int = 5):
    tz = pytz.timezone('Asia/Kolkata')
    now = datetime.now(tz).strftime("%H:%M:%S")

    text = (
        f"**{story_name}**\n"
        f"📡 **BATCH LINKS LIVE AUTO-GENERATOR**\n"
        f"────────────────────────────\n\n"
        f"✅ **Auto-Generated Blocks:** {total_blocks}\n"
        f"⏳ **Buffer:** {current_buffer}/{max_buffer} files\n"
        f"🕒 **Last Updated:** {now}\n"
        f"────────────────────────────\n\n"
        f"ℹ️ **यह कैसे काम करता है?**\n\n"
        f"यह Live Auto-Generator पूरी तरह से background में automate होकर काम करता है। "
        f"यह Live Job के माध्यम से source channel से आने वाली files को target channel में track करता है "
        f"और automatic तरीके से Batch Link तैयार करके यहाँ button के रूप में post कर देता है।\n\n"
        f"जैसे ही **{max_buffer} files** का threshold पूरा होता है — बोट तुरंत एक नया Batch Link block auto-post कर देता है।"
    )
    return text
