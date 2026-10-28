"""TTS 服务：双后端架构（V14 重构）。

后端：
- EdgeTtsBackend：edge-tts 云端合成，始终可用，作为降级兜底。
- GptSovitsBackend：本地 GPT-SoVITS（api_v2 HTTP 服务）合成，摩耶音色。
  ⚠️ 推理调用层（api_v2 客户端 + 权重热切换 + ref 选取）由 Codex++ 实现，
  见 docs/23《后端语音接线架构与 Codex++ 接口契约》。本文件只定义接口契约、
  好感度→声线映射、路由与降级逻辑。
- SvcBackend：RVC 变声路线（SVC）。音色相似度裁决尚未出炉（训练已暂停），默认关闭。

设计裁决（来自 docs/19 评审 + docs/20 评测报告）：
- 中文模式 = 底模 GPT + 摩耶 SoVITS e3 + 中文 ref（底模 CER 0.0328 全场最低）
- 日文模式 = 微调 GPT + 摩耶 SoVITS e3 + 摩耶原声 ref（日文天然无洋腔）
- 好感度三档（低/中/高）映射声线（高冷/活泼/甜妹），由 ref 池 + 推理参数实现，
  不训练三个独立模型。
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

import edge_tts

from app.core.config import settings
from app.core.logging import logger


# =====================================================================
# 语言 / 声线档位
# =====================================================================
class VoiceLang(str, Enum):
    ZH = "zh"
    JA = "ja"


class VoiceTier(str, Enum):
    LOW = "low"    # 共通线高冷声线 → 低好感度
    MID = "mid"    # g线活泼 → 中好感度
    HIGH = "high"  # 后日谈甜妹 → 高好感度


def intimacy_to_tier(level: int) -> VoiceTier:
    """好感度(intimacy_level 1-4) → 声线档位。

    桥接语音文档的「共通线 / g线 / 后日谈」三档与 app 实际使用的四档亲密度。
    映射：1→LOW；2、3→MID；4→HIGH。如与产品预期不符，改这里即可。
    """
    if level >= 4:
        return VoiceTier.HIGH
    if level >= 2:
        return VoiceTier.MID
    return VoiceTier.LOW


# =====================================================================
# 参考音频（ref 池）
# =====================================================================
@dataclass(frozen=True)
class RefSample:
    audio: str  # 参考音频路径（建议绝对路径；来自 GPT-SoVITS/_training/wav/ 或 _audition/ref_ch/）
    text: str   # 参考音频的文本（中文 ref 填中文朗读稿；日文 ref 填对应日文）


# 每档 3~5 条摩耶「该时期」原声，保证声线情绪与好感度匹配。
# TODO(Codex++): 从 GPT-SoVITS/_training/wav/（z6005 后日谈 / z3007 g线 等）与
#   _audition/ref_ch/ 实际挑选并填入：
#   - LOW（高冷）→ 共通线冷感原声
#   - MID（活泼）→ g线原声
#   - HIGH（甜妹）→ 后日谈原声
#   每条同时提供 audio 路径与 text。中文 ref 的 text 是中文朗读稿；
#   日文 ref 的 text 是日文原文（见 JA_REF_POOL）。
REF_POOLS: dict[VoiceTier, list[RefSample]] = {
    VoiceTier.LOW: [],   # TODO(Codex++)
    VoiceTier.MID: [],   # TODO(Codex++)
    VoiceTier.HIGH: [],  # TODO(Codex++)
}

# 日文模式固定用摩耶原声（z6005 后日谈 / z3007 g线），天然无洋腔。
# TODO(Codex++): 确认这两条 wav 在库中的实际路径与对应日文 text。
JA_REF_POOL: list[RefSample] = []  # TODO(Codex++)


def pick_ref(tier: VoiceTier, lang: VoiceLang) -> RefSample | None:
    """按档位 + 语言选一条参考音频；无可用 ref 时返回 None（上层降级 edge）。"""
    pool = JA_REF_POOL if lang == VoiceLang.JA else REF_POOLS.get(tier, [])
    if not pool:
        return None
    # TODO(Codex++): 可改为按 hash(text) 或随机，保证同一句稳定选同一条。
    return pool[0]


# =====================================================================
# 推理调用层契约（Codex++ 实现 GptSovitsBackend / SvcBackend 时必须满足）
# =====================================================================
class TTSBackend(Protocol):
    def synthesize(
        self,
        *,
        text: str,
        lang: VoiceLang,
        ref_audio: str,
        ref_text: str,
        gpt_weight: str,
        sovits_weight: str,
        speed: float = 1.0,
        top_p: float = 0.7,
        temperature: float = 0.7,
    ) -> bytes:
        """合成文本为音频字节。

        契约要求：
        - 返回 **mp3 字节**（media_type=audio/mpeg 与现有路由一致）；
          若底层产出 wav，必须自行转码（ffmpeg / pydub，settings.ffmpeg_path 可用）。
        - 不做好感度 / 语言路由决策（参数由 tts.text_to_speech 决定）。
        - 任何内部错误（服务未起、权重缺失、合成失败）抛异常，
          上层会降级到 EdgeTtsBackend。不要在这里吞异常返回空字节。
        - gpt_weight / sovits_weight 为空字符串时，视为「使用 api_v2 默认权重」，
          跳过对应的 /set_*_weights 调用（中文底模即此情形）。
        """
        ...


# =====================================================================
# EdgeTtsBackend（保留：始终可用的降级兜底）
# =====================================================================
def _edge_synthesize(text: str, voice: str) -> bytes:
    """edge-tts 异步合成（V13 原实现移植）。"""
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


# =====================================================================
# GptSovitsBackend（本地 GPT-SoVITS，推理调用层由 Codex++ 实现）
# =====================================================================
class GptSovitsBackend:
    """本地 GPT-SoVITS 推理后端。

    ⚠️ 推理调用层（api_v2 HTTP 客户端）由 Codex++ 实现，详见 docs/23。
    本骨架给出契约与降级触发点；synthesize 当前抛 NotImplementedError，
    Codex++ 接入 api_v2 后移除该异常即可启用。在此之前，tts.text_to_speech
    会因异常自动降级到 edge-tts，应用不会中断。
    """

    def __init__(self, base_url: str = settings.gpt_sovits_api_url):
        self.base_url = base_url.rstrip("/")

    def synthesize(
        self,
        *,
        text: str,
        lang: VoiceLang,
        ref_audio: str,
        ref_text: str,
        gpt_weight: str,
        sovits_weight: str,
        speed: float = 1.0,
        top_p: float = 0.7,
        temperature: float = 0.7,
    ) -> bytes:
        # TODO(Codex++): 实现流程（参考 docs/23 §推理调用层契约 + docs/20 §api_v2 用法）
        #   0. 确保 api_v2 服务存活（GET / 或 health；否则抛异常触发降级）
        #   1. 若 gpt_weight 非空：POST /set_gpt_weights?weights_path=<gpt_weight>
        #   2. 若 sovits_weight 非空：POST /set_sovits_weights?weights_path=<sovits_weight>
        #   3. POST /tts  JSON = {
        #        "text": text,
        #        "text_lang": "zh" if lang==VoiceLang.ZH else "ja",
        #        "ref_audio_path": ref_audio,
        #        "ref_text": ref_text,
        #        "ref_lang": "zh" if lang==VoiceLang.ZH else "ja",
        #        "top_p": top_p, "temperature": temperature, "speed": speed,
        #        ...（其余字段以实际 api_v2.py 为准）
        #      }
        #   4. 解析响应取回音频（wav）→ 转 mp3 → 返回字节
        #   注意：api_v2 的精确字段名 / 端口 / 启动命令在 gitignored 的
        #   GPT-SoVITS/ 包内，Codex++ 必须对照实际 api_v2.py 核对。
        raise NotImplementedError(
            "GptSovitsBackend 推理调用层待 Codex++ 实现，详见 docs/23"
        )


# =====================================================================
# SvcBackend（RVC 变声路线，默认关闭，待 SVC 裁决）
# =====================================================================
class SvcBackend:
    """RVC 变声后端（SVC 路线）。SVC 音色 sim 裁决未出，默认关闭。

    TODO(Codex++): SVC 训练完成且 sim 超过 TTS 路线的 0.712 后，实现本后端
    并置 settings.svc_enabled=True。接口与 GptSovitsBackend 同契约。
    """

    def synthesize(
        self,
        *,
        text: str,
        lang: VoiceLang,
        ref_audio: str,
        ref_text: str,
        gpt_weight: str,
        sovits_weight: str,
        speed: float = 1.0,
        top_p: float = 0.7,
        temperature: float = 0.7,
    ) -> bytes:
        raise NotImplementedError("SvcBackend 待 SVC 裁决后由 Codex++ 实现")


# =====================================================================
# 路由层
# =====================================================================
def _weights_for(lang: VoiceLang) -> tuple[str, str]:
    """返回 (gpt_weight, sovits_weight)。

    中文：底模 GPT（gpt_zh_weight 通常空 → 用 api_v2 默认）+ 摩耶 SoVITS e3。
    日文：微调 GPT（gpt_ja_weight）+ 摩耶 SoVITS e3。
    权重路径为空字符串时，synthesize 会跳过对应的热切换调用。
    """
    if lang == VoiceLang.JA:
        return settings.gpt_ja_weight, settings.sovits_weight
    return settings.gpt_zh_weight, settings.sovits_weight


def text_to_speech(
    text: str,
    voice: str | None = None,
    intimacy_level: int = 1,
    lang: str = "zh",
) -> bytes:
    """文本 → 音频字节（mp3）。

    路由决策：
    1. 语言枚举（zh/ja，非法值回退 zh）。
    2. 好感度 → 声线档位（intimacy_to_tier）。
    3. 选 ref（中文按档位池，日文按摩耶原声池）。
    4. 本地后端优先（gpt_sovits 或 svc），失败/无 ref 一律降级 edge-tts。
    """
    lang_enum = VoiceLang(lang) if lang in ("zh", "ja") else VoiceLang.ZH
    tier = intimacy_to_tier(int(intimacy_level))

    ref = pick_ref(tier, lang_enum)
    edge = EdgeTtsBackend(voice or settings.tts_voice)

    # SVC 路线（默认关闭，待裁决）
    if settings.svc_enabled:
        backend: TTSBackend = SvcBackend()
        if ref is not None:
            gpt_w, sovits_w = _weights_for(lang_enum)
            try:
                return backend.synthesize(
                    text=text, lang=lang_enum,
                    ref_audio=ref.audio, ref_text=ref.text,
                    gpt_weight=gpt_w, sovits_weight=sovits_w,
                )
            except Exception as e:
                logger.warning("SVC 合成失败，降级 edge-tts: %s", e)
        else:
            logger.warning("SVC 模式无可用 ref，降级 edge-tts")
        return edge.synthesize(text)

    # GPT-SoVITS 本地路线
    if settings.tts_backend == "gpt_sovits":
        backend = GptSovitsBackend()
        if ref is not None:
            gpt_w, sovits_w = _weights_for(lang_enum)
            try:
                return backend.synthesize(
                    text=text, lang=lang_enum,
                    ref_audio=ref.audio, ref_text=ref.text,
                    gpt_weight=gpt_w, sovits_weight=sovits_w,
                )
            except Exception as e:
                logger.warning("GPT-SoVITS 合成失败，降级 edge-tts: %s", e)
        else:
            logger.warning("无可用 ref 样本，降级 edge-tts")

    return edge.synthesize(text)
