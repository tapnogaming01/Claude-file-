import time
import aiohttp
import config
import database as db

async def is_user_verified(user_id: int) -> bool:
    settings = await db.get_verification_settings()
    # अगर verification OFF है तो सीधे access दें
    if not settings.get("status", True):
        return True

    user = await db.get_user(user_id)
    if not user:
        return False

    verified_time = user.get("verified_at", 0)
    timeout = settings.get("token_timeout", 86400)
    
    # Check if configured time has passed
    return (time.time() - verified_time) < timeout


async def get_shortlink(url: str) -> str:
    settings = await db.get_verification_settings()
    
    # अगर verification disabled है
    if not settings.get("status", True):
        return url

    raw_api_url = settings.get("api_url") or getattr(config, "SHORTENER_API_URL", "")
    api_key = settings.get("api_key") or getattr(config, "SHORTENER_API_KEY", "")

    if not raw_api_url or not api_key:
        print("⚠️ [Verification] Shortener API URL or Key missing!")
        return url

    # Clean domain and correctly construct full API endpoint
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
        # ssl=False fixes SSL Certificate verification errors in standard shorteners
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(full_api_url, params=params, timeout=15) as response:
                if response.status == 200:
                    data = await response.json(content_type=None)
                    print(f"DEBUG Shortener Response: {data}")  # Console log for verification
                    
                    # Check all possible AdLinkFly JSON keys
                    if data.get("status") == "success":
                        return data.get("shortlink") or data.get("shortenedUrl") or data.get("link") or data.get("url")
                    
                    # Secondary checks if status field is missing
                    if "shortlink" in data:
                        return data.get("shortlink")
                    elif "shortenedUrl" in data:
                        return data.get("shortenedUrl")
                    elif "link" in data:
                        return data.get("link")
                    elif "url" in data:
                        return data.get("url")
                    else:
                        print(f"⚠️ [Verification] API Error Response: {data}")
                else:
                    print(f"⚠️ [Verification] HTTP Error Status: {response.status}")

    except Exception as e:
        print(f"❌ [Verification] Exception while generating shortlink: {e}")

    # Fallback to original URL if API fails
    return url
