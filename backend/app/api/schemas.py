"""请求/响应模型（Pydantic）。"""
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000, description="用户消息")
    enable_polish: bool = Field(default=True, description="提示词润色（2026-10-14 新管线：初步回复后按人设提示词打磨语气，默认开）")


class ChatReply(BaseModel):
    reply: str
    emotion: str
    saved_memory: str | None
    state: dict


class MemoryCreate(BaseModel):
    text: str = Field(min_length=1, max_length=200)


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    voice: str | None = None
    # 好感度档位（1-4）。不传则由后端从 DB 的 PersonalityState 解析（前端无需改动）。
    intimacy_level: int | None = Field(default=None, ge=1, le=4, description="好感度档位")
    # 语言：zh（中文模式，底模 GPT）| ja（日文模式，微调 GPT）。默认 zh。
    lang: str | None = Field(default=None, pattern="^(zh|ja)$", description="合成语言")


class STTRequest(BaseModel):
    audio: str = Field(min_length=8, description="webm 录音的 base64 编码")


class ProfileUpdate(BaseModel):
    """用户画像编辑（全字段可选，传了才改）。"""

    name: str | None = Field(default=None, max_length=64)
    birthday: str | None = Field(default=None, pattern=r"^\d{2}-\d{2}$")
    likes: str | None = None
    dislikes: str | None = None
    fears: str | None = None
    recent_events: str | None = None
