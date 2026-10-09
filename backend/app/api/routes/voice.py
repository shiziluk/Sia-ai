"""语音路由：TTS 合成 + STT 识别。"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.api.deps import get_llm_dep
from app.api.schemas import STTRequest, TTSRequest
from app.providers.llm import LLMError
from app.services import stt as stt_service
from app.services import tts as tts_service

router = APIRouter(prefix="/api/voice", tags=["voice"])


@router.post("/tts")
def tts(body: TTSRequest):
    """文本 → mp3 音频流。"""
    try:
        audio = tts_service.text_to_speech(body.text, voice=body.voice)
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
