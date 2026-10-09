"""请求/响应模型（Pydantic）。"""
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000, description="用户消息")
    enable_critique: bool = Field(default=True, description="是否启用人格自检")


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
