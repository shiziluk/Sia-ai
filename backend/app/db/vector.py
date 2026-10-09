"""向量记忆库：chromadb 嵌入式（沿用 V13 的 ONNXMiniLM_L6_V2 嵌入）。

选型说明：V13 旧记忆库本就是 chroma 格式，嵌入式 chroma 可零损耗导入，
且与 SQLite 同为本机零服务方案，符合"SQLite+向量库"的用户决策。
"""
from app.core.config import settings
from app.core.logging import logger


class VectorMemory:
    """长期记忆的向量存取（collection: user_memories）。"""

    def __init__(self) -> None:
        import chromadb
        from chromadb.utils import embedding_functions

        client = chromadb.PersistentClient(path=str(settings.data_path / "memory_db"))
        self._embedding_func = embedding_functions.ONNXMiniLM_L6_V2()
        self.collection = client.get_or_create_collection(
            "user_memories", embedding_function=self._embedding_func
        )

    def count(self) -> int:
        return self.collection.count()

    def save(self, text: str) -> str:
        """存入一条记忆，返回其 id。"""
        mem_id = f"mem_{self.collection.count() + 1}"
        self.collection.add(documents=[text], ids=[mem_id])
        logger.info("记忆入库: %s", text)
        return mem_id

    def search(self, query: str, n_results: int = 2) -> str:
        """按相似度检索记忆，返回换行拼接的文本（空库返回空串）。"""
        if self.collection.count() == 0:
            return ""
        results = self.collection.query(query_texts=[query], n_results=n_results)
        return "\n".join(results["documents"][0])

    def all_documents(self) -> list[str]:
        """全部记忆（调试/前端记忆库面板用）。"""
        if self.collection.count() == 0:
            return []
        return list(self.collection.get()["documents"])
