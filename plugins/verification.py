import time
import secrets
import aiohttp
import config
import database as db

async def is_user_verified(user_id: int) -> bool:
    """यूज़र का वेरिफिकेशन स्टेटस और टाइमआउट चेक करता है"""
    settings = await db.get_verification_settings()
    
    # अगर वेरिफिकेशन OFF है तो सीधे एक्सेस दें
    if not settings.get("status", True):
        return True

    user = await db.get_user(user_id)
    if not user:
        return False

    verified_time = user.get("verified_at", 0)
    timeout = settings.get("token_timeout", 86400)
    
    # चेक करें कि तय समय (Timeout) बीता है या नहीं
    return (time.time() - verified_time) < timeout


async def get_shortlink(url: str) -> str:
    """
    Dynamic API Endpoint Wrapper for Shorteners (AdLinkFly, AroLinks, etc.)
    Strict anti-bypass and fallbacks included.
    """
    settings = await db.get_verification_settings()
    
    # अगर वेरिफिकेशन डिसेबल्ड है तो ओरिजिनल लिंक वापस भेजें
    if not settings.get("status", True):
        return url

    raw_api_url = settings.get("api_url") or getattr(config, "SHORTENER_API_URL", "")
    api_key = settings.get("api_key") or getattr(config, "SHORTENER_API_KEY", "")

    if not raw_api_url or not api_key:
        print("⚠️ [Verification] Shortener API URL or Key missing!")
        return url

    # डोमेन को क्लीन करें और सही API एंडपॉइंट बनाएँ
    cleaned_url = raw_api_url.replace("https://", "").replace("http://", "").strip("/")
    if cleaned_url.endswith("/api"):
        full_api_url = f"https://{cleaned_url}"
    else:
        full_api_url = f"https://{cleaned_url}/api"
    
    params = {
        "api": api_key,
        "url": url
    }

    try:
        # SSL और Timeout इश्यू से बचने के लिए कस्टम कनेक्टर्स
        timeout_config = aiohttp.ClientTimeout(total=15)
        connector = aiohttp.TCPConnector(ssl=False)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout_config) as session:
            async with session.get(full_api_url, params=params) as response:
                if response.status == 200:
                    data = await response.json(content_type=None)
                    
                    # 🟢 AdLinkFly और अन्य शार्टनर्स के संभावित JSON रिस्पॉन्स कीवर्ड्स
                    if data.get("status") == "success":
                        return data.get("shortlink") or data.get("shortenedUrl") or data.get("link") or data.get("url")
                    
                    if "shortlink" in data:
                        return data.get("shortlink")
                    elif "shortenedUrl" in data:
                        return data.get("shortenedUrl")
                    elif "link" in data:
                        return data.get("link")
                    elif "url" in data:
                        return data.get("url")
                    else:
                        print(f"⚠️ [Verification] API JSON Keys Mismatch: {data}")
                else:
                    print(f"⚠️ [Verification] HTTP Error Status Code: {response.status}")

    except Exception as e:
        print(f"❌ [Verification] Exception while generating shortlink: {e}")

    # अगर API फेल हो जाए तो फॉलबैक के रूप में वही URL वापस भेजें
    return url
