"""聊天路由：对话 / 历史 / 搜索 / 上下文 / 日记。"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_llm_dep, get_memory_dep
from app.api.schemas import ChatReply, ChatRequest
from app.db.database import get_db
from app.providers.llm import LLMError
from app.services import chat as chat_service

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatReply)
def send_message(
    body: ChatRequest,
    db: Session = Depends(get_db),
    llm=Depends(get_llm_dep),
    memory=Depends(get_memory_dep),
):
    """发送一条用户消息，走完整对话流水线。"""
    try:
        result = chat_service.process_message(
            db, llm, memory, body.text, enable_critique=body.enable_critique
        )
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return result


@router.get("/context")
def get_context(db: Session = Depends(get_db)):
    """前端初始化上下文：欢迎语、生日、雷雨、好感度、通知标志。"""
    return chat_service.get_session_context(db)


@router.get("/history")
def history(limit: int = Query(default=100, ge=1, le=500), db: Session = Depends(get_db)):
    """最近对话消息。"""
    return chat_service.get_history(db, limit=limit)


@router.delete("/history")
def clear_history(db: Session = Depends(get_db)):
    """清空全部聊天记录。"""
    chat_service.clear_history(db)
    return {"ok": True}


@router.get("/search")
def search(
    start: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end: str = Query(..., description="结束日期 YYYY-MM-DD"),
    q: str = Query(default=""),
    db: Session = Depends(get_db),
):
    """按日期区间+关键词搜索对话轮次。"""
    try:
        return chat_service.search_history(db, start, end, q)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="日期格式应为 YYYY-MM-DD") from e


@router.get("/diary/{date_str}")
def diary(date_str: str, db: Session = Depends(get_db)):
    """情绪日记（YYYY-MM-DD）。"""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError as e:
        raise HTTPException(status_code=400, detail="日期格式应为 YYYY-MM-DD") from e
    return chat_service.generate_diary(db, date_str)
