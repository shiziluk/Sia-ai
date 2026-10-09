"""希亚后端入口：FastAPI 应用工厂。

启动：.venv\\Scripts\\python -m uvicorn app.main:app --port 8900
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import logger
from app.db.database import init_db
from app.api.routes import chat, health, memory, persona, voice


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时建表。"""
    init_db()
    logger.info("希亚后端启动完成（LLM 通道: %s）", settings.llm_channel)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="希亚 - 我的AI女友", version="1.0.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(chat.router)
    app.include_router(memory.router)
    app.include_router(persona.router)
    app.include_router(voice.router)
    app.include_router(health.router)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        """兜底异常处理：记录日志，返回统一 500。"""
        logger.exception("未处理异常 %s %s: %s", request.method, request.url.path, exc)
        return JSONResponse(status_code=500, content={"detail": "服务器内部错误"})

    return app


app = create_app()
