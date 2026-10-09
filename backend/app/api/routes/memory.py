"""记忆路由：查看 / 手动写入。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_memory_dep
from app.api.schemas import MemoryCreate
from app.db.database import get_db

router = APIRouter(prefix="/api/memories", tags=["memories"])


@router.get("")
def list_memories(memory=Depends(get_memory_dep)):
    """全部长期记忆（调试/前端记忆库面板）。"""
    return {"count": len(memory.all_memories()), "items": memory.all_memories()}


@router.post("")
def add_memory(body: MemoryCreate, memory=Depends(get_memory_dep)):
    """手动写入一条记忆（V13 仅自动沉淀，此处补充手动入口）。"""
    mem_id = memory.vector.save(body.text.strip())
    return {"ok": True, "id": mem_id}
