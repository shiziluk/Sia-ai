"""SQLite 连接与会话管理（SQLAlchemy 2.0）。"""
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """ORM 基类。"""


def _db_url() -> str:
    return f"sqlite:///{(settings.data_path / 'xia.db').as_posix()}"


# check_same_thread=False：FastAPI 多线程访问 SQLite 必需
engine = create_engine(
    _db_url(),
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """建表（幂等）。"""
    # noqa: 导入 models 触发表注册
    from app.db import models  # noqa: F401

    Base.metadata.create_all(engine)


def get_db():
    """FastAPI 依赖：每请求一个会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
