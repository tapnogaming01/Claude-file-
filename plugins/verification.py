import time
import aiohttp
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
    
    # Check if 24 hours (or configured time) have passed
    return (time.time() - verified_time) < timeout

async def get_shortlink(url: str) -> str:
    settings = await db.get_verification_settings()
    api_url = settings.get("api_url")
    api_key = settings.get("api_key")

    if not api_url or not api_key:
        return url

    # API Request to Link Shortener
    full_api_url = f"https://{api_url}/api?api={api_key}&url={url}"
    async with aiohttp.ClientSession() as session:
        async with session.get(full_api_url) as response:
            data = await response.json()
            if data.get("status") == "success" or "shortlink" in data:
                return data.get("shortlink", url)
            return url
          
