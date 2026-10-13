"""长期记忆服务：写入判定、事实提取、语义改写检索（V13 原逻辑移植）。

LLM 依赖通过 provider 注入，测试时换 MockProvider。
"""
from app.db.vector import VectorMemory
from app.providers.llm import LLMProvider

_INVALID_MARKS = ["无法", "不知道", "error", "抱歉"]


class MemoryService:
    """封装 chroma 向量库 + LLM 判定的记忆沉淀/检索。"""

    def __init__(self, vector: VectorMemory, llm: LLMProvider) -> None:
        self.vector = vector
        self.llm = llm

    # ---- 检索 ----
    def search(self, query: str, n_results: int = 2) -> str:
        """按相似度检索记忆（V13 search_memory）。"""
        return self.vector.search(query, n_results=n_results)

    def search_with_rephrase(self, query: str, n_results: int = 2) -> str:
        """先让 LLM 把问题改写成利于检索的陈述句再查（V13 语义改写），失败回退原查询。"""
        try:
            rephrased = self.semantic_rephrase(query)
            result = self.search(rephrased, n_results=n_results)
            if result.strip():
                return result
            # 兜底：通用查询（V13 原逻辑）
            fallback = self.semantic_rephrase("用户最近提到的重要信息")
            return self.search(fallback, n_results=1)
        except Exception as e:  # 记忆检索异常不阻塞对话
            from app.core.logging import logger

            logger.warning("记忆检索异常（跳过）: %s", e)
            return ""

    def semantic_rephrase(self, query: str) -> str:
        """LLM 把自然语言问题改写成简洁陈述句，提升向量召回（V13 原逻辑）。"""
        messages = [
            {
                "role": "system",
                "content": (
                    "你是一个记忆检索助手。请将用户的自然语言问题，"
                    "改写成一句简洁、客观、包含潜在语义的陈述句，"
                    "用于从长期记忆中召回相关信息。\n"
                    "要求：\n"
                    "- 不要回答问题，只改写\n"
                    "- 不要添加原文没有的信息\n"
                    "- 保留关键意图（如喜好、事件、情绪）\n"
                    "- 输出不超过20字"
                ),
            },
            {"role": "user", "content": f"问题:{query}"},
        ]
        rephrased = self.llm.chat(messages).strip()
        if not rephrased or any(w in rephrased for w in _INVALID_MARKS):
            return query
        return rephrased[:50]

    # ---- 沉淀 ----
    def should_save(self, text: str) -> bool:
        """LLM 判断是否包含个人专属信息（V13 should_save_to_memory）。"""
        messages = [
            {
                "role": "system",
                "content": (
                    "你是一个记忆管家。如果用户的话包含姓名、喜好、生日、习惯、愿望等"
                    "个人专属信息，只回复 'yes'；否则只回复 'no'。"
                ),
            },
            {"role": "user", "content": text},
        ]
        response = self.llm.chat(messages)
        return "yes" in response.lower()

    def extract_key_info(self, text: str) -> str:
        """提取 ≤20 字的简洁事实用于记忆（V13 原逻辑，含无效响应过滤）。"""
        messages = [
            {
                "role": "system",
                "content": (
                    "请从用户的话中提取一条简洁客观的事实（不超过20字），用于长期记忆。"
                    "主语必须是'用户'（例如'用户喜欢晴天'），不要把对方的名字当主语。"
                    "无法提取则返回空字符串。"
                ),
            },
            {"role": "user", "content": text},
        ]
        fact = self.llm.chat(messages).strip()
        if fact and len(fact) <= 30:
            fact = fact.strip("。.，,！!？?“”\"' ")
            if fact and not any(w in fact for w in ["不知道", "抱歉", "error", "无法", "对不起", "我不"]):
                return fact
        return ""

    def remember_if_important(self, user_text: str) -> str | None:
        """完整沉淀链：判定 → 提取 → 入库。返回入库的事实文本（否则 None）。

        修复 V13 Bug#1：返回值会真正写入 DailyLog.saved_memory。
        """
        try:
            if not self.should_save(user_text):
                return None
            fact = self.extract_key_info(user_text)
            if not fact:
                return None
            self.vector.save(fact)
            return fact
        except Exception as e:
            from app.core.logging import logger

            logger.warning("记忆沉淀异常（跳过）: %s", e)
            return None

    # ---- 调试/面板 ----
    def all_memories(self) -> list[str]:
        return self.vector.all_documents()
