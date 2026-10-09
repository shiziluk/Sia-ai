"""STT 服务：Vosk 中文语音识别（V13 speech_to_text 移植）。

流程：前端录音 webm(base64) → ffmpeg 转 16kHz 单声道 WAV → Vosk 识别。
模型文件（2GB）不入 Git，下载方式见 docs/05_部署说明.md。
"""
import base64
import json
import os
import subprocess
import tempfile
import wave
from pathlib import Path

from app.core.config import settings
from app.core.logging import logger

_vosk_model = None  # 全局只加载一次（V13 同款）


def speech_to_text(webm_base64: str) -> str:
    """webm 录音 base64 → 识别文本（失败返回空串）。"""
    global _vosk_model
    try:
        from vosk import KaldiRecognizer, Model

        model_path = Path(settings.vosk_model_path)
        if not model_path.is_absolute():
            model_path = Path(__file__).resolve().parent.parent.parent / model_path
        if not model_path.exists():
            logger.error("找不到 Vosk 模型目录: %s", model_path)
            return ""
        if _vosk_model is None:
            logger.info("加载 Vosk 中文模型（首次较慢）...")
            _vosk_model = Model(str(model_path))
            logger.info("Vosk 模型加载成功")

        webm_data = base64.b64decode(webm_base64)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp_in:
            tmp_in.write(webm_data)
            tmp_in_path = tmp_in.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_out:
            tmp_out_path = tmp_out.name

        try:
            result = subprocess.run(
                [
                    settings.ffmpeg_path, "-y", "-hide_banner",
                    "-i", tmp_in_path,
                    "-ar", "16000", "-ac", "1", "-f", "wav", tmp_out_path,
                ],
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                logger.error("FFmpeg 转码失败: %s", result.stderr[:300])
                return ""
            with wave.open(tmp_out_path, "rb") as wf:
                frames = wf.readframes(wf.getnframes())
        finally:
            os.unlink(tmp_in_path)
            os.unlink(tmp_out_path)

        rec = KaldiRecognizer(_vosk_model, 16000)
        rec.AcceptWaveform(frames)
        text = json.loads(rec.FinalResult()).get("text", "").strip()
        logger.info("语音识别结果: %s", text)
        return text
    except Exception as e:
        logger.error("本地语音识别失败: %s", e)
        return ""
