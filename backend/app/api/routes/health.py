"""健康检查路由。"""
from fastapi import APIRouter

from app.api.deps import get_llm_dep
from app.core.config import settings

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("")
def health():
    """服务与 LLM 通道状态。"""
    llm = get_llm_dep()
    return {
        "status": "ok",
        "llm": {
            "channel": settings.llm_channel,
            "active_provider": llm.name,
            "local_model": settings.ollama_model,
        },
    }
