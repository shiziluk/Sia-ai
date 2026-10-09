"""旧版数据导入工具：把 V13 留档的聊天记录/人格状态/记忆库迁入新存储。

数据来源（_legacy 留档）：
  _legacy/立绘化与pwa支持/chat_history.json      → messages 表
  _legacy/立绘化与pwa支持/personality_state.json  → personality_state 表
  _legacy/立绘化与pwa支持/memory_db/（chroma）    → 新 chroma 记忆库（重嵌入）

用法：cd backend && .venv\\Scripts\\python tools\\import_legacy.py
幂等：messages 有数据时跳过导入；记忆按文档文本去重。
"""
import json
import sys
from pathlib import Path

# 保证可从 backend 目录运行
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.logging import logger  # noqa: E402
from app.db.database import SessionLocal, init_db  # noqa: E402
from app.db.models import Message, PersonalityState  # noqa: E402
from app.db.vector import VectorMemory  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parent.parent
LEGACY_DIR = BACKEND_DIR.parent / "_legacy" / "立绘化与pwa支持"


def import_chat_history(db) -> None:
    """chat_history.json → messages 表（user 消息带情绪标签与时间戳）。"""
    if db.query(Message).count() > 0:
        print("messages 表已有数据，跳过聊天记录导入")
        return
    src = LEGACY_DIR / "chat_history.json"
    if not src.exists():
        print("未找到 chat_history.json，跳过")
        return
    data = json.loads(src.read_text(encoding="utf-8"))
    count = 0
    for msg in data:
        if msg.get("role") not in ("user", "assistant"):
            continue
        created = None
        if msg.get("timestamp"):
            try:
                from datetime import datetime

                created = datetime.fromisoformat(msg["timestamp"])
            except ValueError:
                created = None
        row = Message(
            role=msg["role"],
            content=msg.get("content", ""),
            emotion=msg.get("emotion"),
        )
        if created:
            row.created_at = created
        db.add(row)
        count += 1
    db.commit()
    print(f"聊天记录导入完成: {count} 条")


def import_personality_state(db) -> None:
    """personality_state.json → personality_state 表。

    留档 trust=25/level=2 是真实数据；若表里已存在行（如服务冒烟时自动建的
    默认空行 trust=0/level=1），仅在其未被真实对话更新过时用留档覆盖。
    """
    src = LEGACY_DIR / "personality_state.json"
    if not src.exists():
        print("未找到 personality_state.json，跳过")
        return
    data = json.loads(src.read_text(encoding="utf-8"))
    trust = int(data.get("trust", 0))
    level = int(data.get("intimacy_level", 1))

    existing = db.get(PersonalityState, 1)
    if existing is None:
        db.add(PersonalityState(id=1, trust=trust, intimacy_level=level))
        db.commit()
        print(f"人格状态导入完成: trust={trust}, intimacy={level}")
        return
    if existing.trust == 0 and existing.intimacy_level == 1:
        existing.trust = trust
        existing.intimacy_level = level
        db.commit()
        print(f"人格状态已从留档覆盖: trust={trust}, intimacy={level}")
    else:
        print("personality_state 已有真实数据，跳过")


def import_vector_memory() -> None:
    """旧 chroma memory_db → 新 chroma 记忆库（按文本去重）。

    旧库是 chroma 0.4.x 格式，新版客户端 get_collection 会报 '_type' 错，
    因此直接用 sqlite3 读 embedding_metadata 里的文档文本（跨版本稳定）。
    """
    old_dir = LEGACY_DIR / "memory_db"
    db_file = old_dir / "chroma.sqlite3"
    if not db_file.exists():
        print("未找到旧 memory_db，跳过")
        return
    import sqlite3

    con = sqlite3.connect(str(db_file))
    try:
        rows = con.execute(
            "SELECT string_value FROM embedding_metadata WHERE key = 'chroma:document'"
        ).fetchall()
        if not rows:  # 兜底：部分旧版本文档存于 fulltext 表
            rows = con.execute(
                "SELECT c0 FROM embedding_fulltext_search_content"
            ).fetchall()
    finally:
        con.close()
    old_docs = [r[0] for r in rows if r[0]]
    if not old_docs:
        print("旧记忆库为空")
        return

    new_vector = VectorMemory()
    existing = set(new_vector.all_documents())
    added = 0
    for doc in old_docs:
        if doc not in existing:
            new_vector.save(doc)
            existing.add(doc)  # 批内同步去重：旧库自身可能含重复文本
            added += 1
    print(f"记忆导入完成: 新增 {added} 条 / 旧库 {len(old_docs)} 条")


def main() -> None:
    logger.info("开始旧数据导入")
    init_db()
    db = SessionLocal()
    try:
        import_chat_history(db)
        import_personality_state(db)
    finally:
        db.close()
    import_vector_memory()
    logger.info("旧数据导入结束")


if __name__ == "__main__":
    main()
