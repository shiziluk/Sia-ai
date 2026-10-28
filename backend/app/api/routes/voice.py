"""语音路由：TTS 合成 + STT 识别。"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import get_llm_dep
from app.api.schemas import STTRequest, TTSRequest
from app.core.logging import logger
from app.db.database import get_db
from app.providers.llm import LLMError
from app.services import persona
from app.services import stt as stt_service
from app.services import tts as tts_service

router = APIRouter(prefix="/api/voice", tags=["voice"])


@router.post("/tts")
def tts(body: TTSRequest, db: Session = Depends(get_db)):
    """文本 → mp3 音频流。

    后端双模式（见 docs/23）：本地 GPT-SoVITS（摩耶音色）优先，
    失败自动降级 edge-tts。好感度档位决定声线（高冷/活泼/甜妹），
    不传则由 DB 的 PersonalityState 解析。
    """
    intimacy_level = body.intimacy_level
    if intimacy_level is None:
        try:
            intimacy_level = persona.ensure_personality_state(db).intimacy_level
        except Exception as e:  # 库异常不应阻断语音
            logger.warning("解析好感度失败，回退档位 1: %s", e)
            intimacy_level = 1
    try:
        audio = tts_service.text_to_speech(
            body.text, voice=body.voice,
            intimacy_level=intimacy_level, lang=body.lang or "zh",
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"TTS 合成失败: {e}") from e
    return Response(content=audio, media_type="audio/mpeg")


@router.post("/stt")
def stt(body: STTRequest, llm=Depends(get_llm_dep)):
    """webm 录音 base64 → 识别文本（Vosk 本地识别）。"""
    del llm  # 占位依赖：保持与 chat 相同的通道探测时机
    text = stt_service.speech_to_text(body.audio)
    if not text:
        raise HTTPException(status_code=422, detail="未能识别到有效语音")
    return {"text": text}
