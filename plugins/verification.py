import time
import aiohttp
import config
import database as db

async def get_shortlink(url: str) -> str:
    settings = await db.get_verification_settings()
    
    api_url = settings.get("api_url") or getattr(config, "SHORTENER_API_URL", None)
    api_key = settings.get("api_key") or getattr(config, "SHORTENER_API_KEY", None)

    if not api_url or not api_key:
        print("❌ [Shortener Error] API URL or Key missing!")
        return url

    if not api_url.startswith("http://") and not api_url.startswith("https://"):
        api_url = f"https://{api_url}"

    request_url = f"{api_url.rstrip('/')}/api?api={api_key}&url={url}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(request_url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    shortened_url = data.get("shortenedUrl") or data.get("url") or data.get("short_url")
                    if shortened_url:
                        return shortened_url
                    print(f"⚠️ [Shortener Warning] Invalid response: {data}")
                else:
                    print(f"❌ [Shortener Error] HTTP Status {response.status}")
    except Exception as e:
        print(f"❌ [Shortener Exception] Error shortening URL: {e}")

    return url


async def is_user_verified(user_id: int) -> bool:
    v_settings = await db.get_verification_settings()
    if not v_settings.get("status", True):
        return True

    user_data = await db.get_user_verification(user_id)
    if not user_data:
        return False
        
    verified_at = user_data.get("verified_at", 0)
    timeout_seconds = v_settings.get("token_timeout", 86400)

    return (time.time() - verified_at) < timeout_seconds
