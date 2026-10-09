"""天气服务：和风天气实时检测雷雨（V13 get_weather_alert 移植，key 转入 .env）。"""
import httpx

from app.core.config import settings
from app.core.logging import logger

_DANGER_KEYWORDS = ["雷", "thunder", "暴雨", "强对流", "雷暴", "闪电"]


def is_thunderstorm_now() -> bool:
    """当前城市是否处于雷雨/暴雨等危险天气。异常静默返回 False（V13 同款）。"""
    if not settings.weather_api_key or not settings.weather_host:
        logger.info("未配置天气 API，跳过雷雨检测")
        return False
    try:
        resp = httpx.get(
            f"https://{settings.weather_host}/v7/weather/now",
            params={"location": settings.weather_city_id, "key": settings.weather_api_key},
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == "200":
                weather_text = data["now"]["text"]
                return any(kw in weather_text for kw in _DANGER_KEYWORDS)
    except Exception as e:
        logger.warning("天气API异常（已静默处理）: %s", e)
    return False
