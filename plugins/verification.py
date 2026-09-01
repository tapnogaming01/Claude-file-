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

    api_url = settings.get("api_url") or getattr(config, "SHORTENER_API_URL", "")
    api_key = settings.get("api_key") or getattr(config, "SHORTENER_API_KEY", "")

    if not api_url or not api_key:
        print("⚠️ [Verification] Shortener API URL or Key missing!")
        return url

    # Clean domain & handle https:// properly
    api_url = api_url.replace("https://", "").replace("http://", "").strip("/")
    full_api_url = f"https://{api_url}/api"
    
    params = {
        "api": api_key,
        "url": url
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(full_api_url, params=params, timeout=10) as response:
                if response.status == 200:
                    # content_type=None fixes JSON Decode errors on non-standard headers
                    data = await response.json(content_type=None)
                    
                    # Standard API Key Check
                    if data.get("status") == "success" and "shortlink" in data:
                        return data.get("shortlink")
                    elif "shortlink" in data:
                        return data.get("shortlink")
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
