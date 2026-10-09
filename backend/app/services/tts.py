"""TTS 服务：edge-tts 异步合成（V13 原实现移植），输出 mp3 字节。"""
import asyncio

import edge_tts

from app.core.config import settings
from app.core.logging import logger


def text_to_speech(text: str, voice: str | None = None) -> bytes:
    """同步封装：文本 → mp3 音频字节。失败抛异常由路由统一处理。"""
    voice = voice or settings.tts_voice
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(_synthesize(text, voice))
    finally:
        loop.close()
        asyncio.set_event_loop(None)


async def _synthesize(text: str, voice: str) -> bytes:
    communicate = edge_tts.Communicate(text, voice)
    audio_data = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data += chunk["data"]
    if not audio_data:
        logger.warning("TTS 未返回音频数据")
    return audio_data
