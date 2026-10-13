"""LLM 双通道 Provider：本地 Ollama（主力）+ 在线 dashscope qwen（备用）。

策略（settings.llm_channel）：
  auto   = 本地优先，超时/异常自动切在线
  local  = 仅本地（失败抛错）
  online = 仅在线
测试时用 MockProvider 注入（见 tests/conftest.py）。
"""
from abc import ABC, abstractmethod

import httpx

from app.core.config import settings
from app.core.logging import logger


class LLMError(Exception):
    """LLM 调用失败。"""


class LLMProvider(ABC):
    """统一接口：输入完整 messages（含 system），返回回复文本。"""

    name: str = "base"

    @abstractmethod
    def chat(self, messages: list[dict]) -> str: ...

    def health(self) -> bool:
        """通道可用性探测（供 /api/health 与 auto 切换）。"""
        return True


class OllamaProvider(LLMProvider):
    """本地 Ollama 通道（如 qwen3.5:4b）。"""

    name = "local"

    def chat(self, messages: list[dict]) -> str:
        import ollama

        try:
            client = ollama.Client(
                host=settings.ollama_base_url, timeout=settings.llm_local_timeout
            )
            resp = client.chat(
                model=settings.ollama_model,
                messages=[{"role": m["role"], "content": m["content"]} for m in messages],
                think=False,  # qwen3.5 默认开思考：答案进 thinking 字段导致 content 为空且极慢
                keep_alive="30m",  # 保持常驻显存，避免同一轮多次调用间反复换载超时
                # 2026-10-14 采样收紧：默认 temperature 0.8 偏激进，4B 模型会采样出
                # "不许客栈当你的饭碗"级乱码缝合与自我模仿复读；收紧三项显著抑制。
                options={
                    "temperature": 0.55,
                    "top_p": 0.85,
                    "repeat_penalty": 1.15,
                },
            )
            return resp["message"]["content"]
        except Exception as e:  # 连接失败/模型缺失统一抛 LLMError
            raise LLMError(f"Ollama 调用失败: {e}") from e

    def health(self) -> bool:
        try:
            import ollama

            ollama.Client(host=settings.ollama_base_url, timeout=3).list()
            return True
        except Exception:
            return False


class QwenProvider(LLMProvider):
    """在线 dashscope 通道（V13 同款 HTTP 直调）。"""

    name = "online"

    def chat(self, messages: list[dict]) -> str:
        payload = {"model": settings.qwen_model, "input": {"messages": messages}}
        headers = {
            "Authorization": f"Bearer {settings.dashscope_api_key}",
            "Content-Type": "application/json",
        }
        try:
            resp = httpx.post(settings.qwen_url, json=payload, headers=headers, timeout=60)
        except httpx.HTTPError as e:
            raise LLMError(f"在线通道网络异常: {e}") from e
        if resp.status_code != 200:
            raise LLMError(f"在线通道 HTTP {resp.status_code}: {resp.text[:200]}")
        try:
            return resp.json()["output"]["text"]
        except (KeyError, ValueError) as e:
            raise LLMError(f"在线通道响应解析失败: {e}") from e


class MockProvider(LLMProvider):
    """测试用：按规则返回固定文本，可脚本化输出。"""

    name = "mock"

    def __init__(self) -> None:
        self.replies: list[str] = []
        self.calls: list[list[dict]] = []

    def chat(self, messages: list[dict]) -> str:
        self.calls.append(messages)
        if self.replies:
            return self.replies.pop(0)
        # 依据 system 里的情绪判定提示返回可预测内容，便于断言
        user_text = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        if "记忆管家" in (messages[0]["content"] if messages else ""):
            return "yes" if any(k in user_text for k in ["喜欢", "生日", "名字"]) else "no"
        if "情绪观察者" in (messages[0]["content"] if messages else ""):
            return "开心"
        return "哼，知道了啦。"


def _local_provider() -> OllamaProvider:
    return OllamaProvider()


def _online_provider() -> QwenProvider:
    return QwenProvider()


def get_llm() -> LLMProvider:
    """按配置返回可用的 Provider 实例（auto：本地优先，health 不通或超时切在线）。"""
    channel = settings.llm_channel
    if channel == "online":
        return _online_provider()
    if channel == "local":
        return _local_provider()

    # auto：本地优先
    local = _local_provider()
    if local.health():
        return local
    logger.warning("本地 Ollama 不可用，回退在线通道")
    return _online_provider()
