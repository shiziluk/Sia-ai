"""FastAPI 依赖注入：LLM Provider 与记忆服务的单例管理（测试可覆盖）。"""
import time

from app.core.logging import logger
from app.db.vector import VectorMemory
from app.providers.llm import LLMProvider, get_llm as _build_llm
from app.services.memory import MemoryService

_llm: LLMProvider | None = None
_llm_checked_at: float = 0.0
_vector: VectorMemory | None = None
_memory: MemoryService | None = None

_PROVIDER_TTL = 60.0  # auto 模式下 Provider 选择结果缓存 60s，避免每请求探测


def get_llm_dep() -> LLMProvider:
    """请求级依赖：返回当前可用 Provider（auto 模式带 TTL 缓存）。"""
    global _llm, _llm_checked_at
    now = time.time()
    if _llm is None or now - _llm_checked_at > _PROVIDER_TTL:
        _llm = _build_llm()
        _llm_checked_at = now
    return _llm


def get_vector() -> VectorMemory:
    """chroma 向量库单例（懒加载，首次较慢）。"""
    global _vector
    if _vector is None:
        _vector = VectorMemory()
    return _vector


def get_memory_dep() -> MemoryService:
    """记忆服务单例（向量库 + 当前 Provider）。"""
    global _memory
    if _memory is None:
        _memory = MemoryService(get_vector(), get_llm_dep())
    else:
        # Provider 可能已切换，保持记忆服务持最新引用
        _memory.llm = get_llm_dep()
    return _memory


def override_llm(provider: LLMProvider) -> None:
    """测试注入口：强制指定 Provider。"""
    global _llm, _llm_checked_at, _memory
    _llm = provider
    _llm_checked_at = time.time()
    _memory = None  # 重建记忆服务以携带新 Provider


def reset_overrides() -> None:
    """测试清理：恢复自动选择。"""
    global _llm, _llm_checked_at, _vector, _memory
    _llm = None
    _llm_checked_at = 0.0
    _vector = None
    _memory = None
    logger.info("依赖覆盖已重置")
