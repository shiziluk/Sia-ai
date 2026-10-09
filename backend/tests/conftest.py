"""pytest 共享夹具：临时数据目录 / Mock LLM / Fake 向量库 / TestClient。

关键点：
- 在导入 app 模块前设置 DATA_DIR 环境变量，让 SQLite 引擎绑定到临时目录
- VectorMemory 用内存假实现替换（避免真实 chroma 嵌入模型下载）
- LLM 一律 MockProvider（脚本化输出，可断言）
"""
import os
import tempfile
from pathlib import Path

# 必须在任何 app 导入之前设置环境变量
_TMP = tempfile.mkdtemp(prefix="xia_test_")
os.environ["DATA_DIR"] = _TMP
os.environ["LLM_CHANNEL"] = "auto"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.database import Base, SessionLocal, engine  # noqa: E402
from app.db.database import init_db  # noqa: E402
from app.api import deps  # noqa: E402
from app.main import app  # noqa: E402
from app.providers.llm import MockProvider  # noqa: E402


class FakeVector:
    """内存版向量记忆（替代 chroma，测试零外部依赖）。"""

    def __init__(self) -> None:
        self.docs: list[str] = []

    def count(self) -> int:
        return len(self.docs)

    def save(self, text: str) -> str:
        self.docs.append(text)
        return f"mem_{len(self.docs)}"

    def search(self, query: str, n_results: int = 2) -> str:
        # 极简"相似度"：包含查询词的文档
        hits = [d for d in self.docs if any(kw in d for kw in query if kw)]
        return "\n".join(hits[:n_results])

    def all_documents(self) -> list[str]:
        return list(self.docs)


@pytest.fixture()
def mock_llm():
    """每个测试一个全新 MockProvider 并注入依赖。"""
    provider = MockProvider()
    deps.override_llm(provider)
    yield provider
    deps.reset_overrides()


@pytest.fixture()
def fake_vector():
    deps._vector = FakeVector()
    yield deps._vector
    deps._vector = None


@pytest.fixture()
def client(monkeypatch, mock_llm, fake_vector):
    """干净数据库 + 关闭天气外呼 + Mock 依赖的 TestClient。"""
    # 关闭天气 API（.env 里有占位 key，避免测试触发真实外呼）
    monkeypatch.setattr(settings, "weather_api_key", "", raising=False)
    # 每个测试重建全部表
    Base.metadata.drop_all(engine)
    init_db()
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db(monkeypatch):
    """干净数据库的裸会话（persona/chat/memory 单元测试直接用）。"""
    monkeypatch.setattr(settings, "weather_api_key", "", raising=False)
    Base.metadata.drop_all(engine)
    init_db()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
