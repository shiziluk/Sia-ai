"""Text-to-speech with a local GPT-SoVITS backend and Edge fallback."""

from __future__ import annotations

import asyncio
import hashlib
import json
import subprocess
import threading
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Protocol

import edge_tts
import httpx

from app.core.config import BACKEND_DIR, PROJECT_ROOT, settings
from app.core.logging import logger


class VoiceLang(str, Enum):
    ZH = "zh"
    JA = "ja"


class VoiceTier(str, Enum):
    LOW = "low"
    MID = "mid"
    HIGH = "high"


def intimacy_to_tier(level: int) -> VoiceTier:
    if level >= 4:
        return VoiceTier.HIGH
    if level >= 2:
        return VoiceTier.MID
    return VoiceTier.LOW


@dataclass(frozen=True)
class RefSample:
    audio: Path
    text: str
    style: str = ""
    prompt_lang: str | None = None


@dataclass(frozen=True)
class VoiceTune:
    speed: float = 1.0
    top_p: float = 0.7
    temperature: float = 0.7


@dataclass(frozen=True)
class RefManifest:
    refs: dict[tuple[VoiceLang, VoiceTier], tuple[RefSample, ...]]
    tunes: dict[VoiceTier, VoiceTune]


@dataclass(frozen=True)
class SpeechSynthesisResult:
    audio: bytes
    backend: str


_DEFAULT_TUNES = {
    VoiceTier.LOW: VoiceTune(speed=0.97, top_p=0.65, temperature=0.62),
    VoiceTier.MID: VoiceTune(speed=1.0, top_p=0.70, temperature=0.72),
    VoiceTier.HIGH: VoiceTune(speed=1.03, top_p=0.78, temperature=0.82),
}


def _resolve_path(raw: str, base: Path) -> Path:
    path = Path(raw).expanduser()
    return path if path.is_absolute() else (base / path).resolve()


@lru_cache(maxsize=4)
def _load_ref_manifest(path_text: str, mtime_ns: int) -> RefManifest:
    del mtime_ns
    path = Path(path_text)
    refs: dict[tuple[VoiceLang, VoiceTier], tuple[RefSample, ...]] = {}
    tunes = dict(_DEFAULT_TUNES)

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("读取 TTS ref manifest 失败，将降级 edge-tts: %s", exc)
        return RefManifest(refs=refs, tunes=tunes)

    for tier_name, tune in (raw.get("tiers") or {}).items():
        try:
            tier = VoiceTier(tier_name)
            tunes[tier] = VoiceTune(
                speed=float(tune.get("speed", 1.0)),
                top_p=float(tune.get("top_p", 0.7)),
                temperature=float(tune.get("temperature", 0.7)),
            )
        except (TypeError, ValueError):
            logger.warning("忽略无效 TTS tier 配置: %s", tier_name)

    for lang_name, tiers in (raw.get("refs") or {}).items():
        try:
            lang = VoiceLang(lang_name)
        except ValueError:
            logger.warning("忽略无效 TTS ref 语言: %s", lang_name)
            continue
        for tier_name, entries in (tiers or {}).items():
            try:
                tier = VoiceTier(tier_name)
            except ValueError:
                continue
            valid: list[RefSample] = []
            for entry in entries or []:
                if not isinstance(entry, dict):
                    continue
                audio_raw = str(entry.get("audio") or "").strip()
                text = str(entry.get("text") or "").strip()
                if not audio_raw or not text:
                    continue
                audio = _resolve_path(audio_raw, PROJECT_ROOT)
                if not audio.is_file() or audio.stat().st_size == 0:
                    logger.warning("TTS ref 音频不存在或为空: %s", audio)
                    continue
                valid.append(
                    RefSample(
                        audio=audio,
                        text=text,
                        style=str(entry.get("style") or ""),
                        prompt_lang=str(entry.get("prompt_lang") or "").strip() or None,
                    )
                )
            if valid:
                refs[(lang, tier)] = tuple(valid)

    return RefManifest(refs=refs, tunes=tunes)


def load_ref_manifest() -> RefManifest:
    path = _resolve_path(settings.voice_ref_manifest, BACKEND_DIR)
    try:
        mtime_ns = path.stat().st_mtime_ns
    except OSError:
        mtime_ns = 0
    return _load_ref_manifest(str(path), mtime_ns)


def pick_ref(
    tier: VoiceTier,
    lang: VoiceLang,
    text: str = "",
) -> RefSample | None:
    candidates = load_ref_manifest().refs.get((lang, tier), ())
    if not candidates:
        return None
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return candidates[int.from_bytes(digest[:4], "big") % len(candidates)]


class TTSBackend(Protocol):
    def synthesize(
        self,
        *,
        text: str,
        lang: VoiceLang,
        ref: RefSample,
        gpt_weight: Path,
        sovits_weight: Path,
        tune: VoiceTune,
    ) -> bytes: ...


def _edge_synthesize(text: str, voice: str) -> bytes:
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(_edge_stream(text, voice))
    finally:
        loop.close()
        asyncio.set_event_loop(None)


async def _edge_stream(text: str, voice: str) -> bytes:
    communicate = edge_tts.Communicate(text, voice)
    audio_data = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data += chunk["data"]
    if not audio_data:
        logger.warning("TTS(edge) 未返回音频数据")
    return audio_data


class EdgeTtsBackend:
    def __init__(self, voice: str):
        self.voice = voice

    def synthesize(self, text: str, **_kwargs) -> bytes:
        return _edge_synthesize(text, self.voice)


_GPT_SOVITS_LOCK = threading.Lock()


class GptSovitsBackend:
    """Single-process api_v2 client.

    api_v2 keeps GPT/SoVITS weights in process-global state. The lock covers
    weight switching and synthesis together so concurrent zh/ja requests cannot
    observe each other's swapped weights.
    """

    def __init__(
        self,
        base_url: str = settings.gpt_sovits_api_url,
        timeout_seconds: float = settings.gpt_sovits_timeout_seconds,
        ffmpeg_path: str = settings.ffmpeg_path,
        transport: httpx.BaseTransport | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.ffmpeg_path = ffmpeg_path
        self.transport = transport

    def _to_mp3(self, wav_audio: bytes) -> bytes:
        command = [
            self.ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "wav",
            "-i",
            "pipe:0",
            "-codec:a",
            "libmp3lame",
            "-b:a",
            "128k",
            "-f",
            "mp3",
            "pipe:1",
        ]
        try:
            completed = subprocess.run(
                command,
                input=wav_audio,
                capture_output=True,
                timeout=60,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError(f"ffmpeg 执行失败: {exc}") from exc
        if completed.returncode != 0 or not completed.stdout:
            detail = completed.stderr.decode("utf-8", errors="replace")[-500:]
            raise RuntimeError(f"ffmpeg 转 mp3 失败: {detail}")
        return completed.stdout

    def synthesize(
        self,
        *,
        text: str,
        lang: VoiceLang,
        ref: RefSample,
        gpt_weight: Path,
        sovits_weight: Path,
        tune: VoiceTune,
    ) -> bytes:
        with _GPT_SOVITS_LOCK:
            timeout = httpx.Timeout(self.timeout_seconds, connect=5.0)
            with httpx.Client(
                base_url=self.base_url,
                timeout=timeout,
                transport=self.transport,
            ) as client:
                for endpoint, weight in (
                    ("/set_gpt_weights", gpt_weight),
                    ("/set_sovits_weights", sovits_weight),
                ):
                    response = client.get(
                        endpoint,
                        params={"weights_path": str(weight)},
                    )
                    response.raise_for_status()

                response = client.post(
                    "/tts",
                    json={
                        "text": text,
                        "text_lang": lang.value,
                        "ref_audio_path": str(ref.audio),
                        "prompt_text": ref.text,
                        "prompt_lang": ref.prompt_lang or lang.value,
                        "top_p": tune.top_p,
                        "temperature": tune.temperature,
                        "speed_factor": tune.speed,
                        "text_split_method": "cut5",
                        "batch_size": 1,
                        "media_type": "wav",
                        "streaming_mode": False,
                    },
                )
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                if not content_type.startswith("audio/"):
                    raise RuntimeError(
                        f"api_v2 返回了非音频响应: {content_type or 'unknown'}"
                    )
                if not response.content:
                    raise RuntimeError("api_v2 返回空音频")
                return self._to_mp3(response.content)


class SvcBackend:
    def synthesize(self, **_kwargs) -> bytes:
        raise NotImplementedError("SVC backend remains disabled pending evaluation")


def _resolve_weight(raw: str, label: str) -> Path:
    if not raw.strip():
        raise RuntimeError(f"{label} 权重路径为空")
    path = _resolve_path(raw.strip(), PROJECT_ROOT)
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError(f"{label} 权重不存在或为空: {path}")
    return path


def _weights_for(lang: VoiceLang) -> tuple[Path, Path]:
    gpt = settings.gpt_ja_weight if lang == VoiceLang.JA else settings.gpt_zh_weight
    return (
        _resolve_weight(gpt, "GPT"),
        _resolve_weight(settings.sovits_weight, "SoVITS"),
    )


def synthesize_speech(
    text: str,
    voice: str | None = None,
    intimacy_level: int = 1,
    lang: str = "zh",
) -> SpeechSynthesisResult:
    lang_enum = VoiceLang(lang) if lang in ("zh", "ja") else VoiceLang.ZH
    tier = intimacy_to_tier(int(intimacy_level))
    manifest = load_ref_manifest()
    ref = pick_ref(tier, lang_enum, text)
    edge = EdgeTtsBackend(voice or settings.tts_voice)

    if settings.svc_enabled:
        logger.warning("SVC 已开启但尚未实现，降级 edge-tts")

    if settings.tts_backend == "gpt_sovits" and ref is not None:
        try:
            gpt_weight, sovits_weight = _weights_for(lang_enum)
            audio = GptSovitsBackend().synthesize(
                text=text,
                lang=lang_enum,
                ref=ref,
                gpt_weight=gpt_weight,
                sovits_weight=sovits_weight,
                tune=manifest.tunes[tier],
            )
            return SpeechSynthesisResult(audio=audio, backend="gpt_sovits")
        except Exception as exc:
            logger.warning("GPT-SoVITS 合成失败，降级 edge-tts: %s", exc)
    elif settings.tts_backend == "gpt_sovits":
        logger.warning(
            "没有可用的 TTS ref 样本（lang=%s, tier=%s），降级 edge-tts",
            lang_enum.value,
            tier.value,
        )

    audio = edge.synthesize(text)
    if not audio:
        raise RuntimeError("edge-tts 未返回音频数据")
    return SpeechSynthesisResult(audio=audio, backend="edge")


def text_to_speech(
    text: str,
    voice: str | None = None,
    intimacy_level: int = 1,
    lang: str = "zh",
) -> bytes:
    """Compatibility wrapper; new callers should use synthesize_speech()."""
    return synthesize_speech(
        text,
        voice=voice,
        intimacy_level=intimacy_level,
        lang=lang,
    ).audio
