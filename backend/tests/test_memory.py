"""memory 服务单元测试：写入判定 / 事实提取 / 语义检索 / 完整沉淀链（Bug#1 回归）。"""
import pytest

from app.providers.llm import LLMError, LLMProvider
from app.services.memory import MemoryService


class _RaisingProvider(LLMProvider):
    name = "raising"

    def chat(self, messages):
        raise LLMError("boom")


@pytest.fixture()
def mem(mock_llm, fake_vector):
    return MemoryService(fake_vector, mock_llm)


# =====================================================================
# should_save：LLM 判定是否值得沉淀
# =====================================================================
def test_should_save_yes(mock_llm, mem):
    mock_llm.replies = ["yes"]
    assert mem.should_save("我的生日是4月6日") is True


def test_should_save_no(mock_llm, mem):
    mock_llm.replies = ["no"]
    assert mem.should_save("今天天气不错") is False


def test_should_save_case_insensitive(mock_llm, mem):
    mock_llm.replies = ["YES"]
    assert mem.should_save("我叫小叶") is True


# =====================================================================
# extract_key_info：提取 ≤20 字事实，过滤无效响应
# =====================================================================
def test_extract_valid(mock_llm, mem):
    mock_llm.replies = ["小叶喜欢晴天"]
    assert mem.extract_key_info("我最喜欢晴天了") == "小叶喜欢晴天"


def test_extract_strips_punctuation(mock_llm, mem):
    mock_llm.replies = ["小叶讨厌打雷。"]
    assert mem.extract_key_info("我讨厌打雷") == "小叶讨厌打雷"


@pytest.mark.parametrize("bad", ["抱歉，无法提取", "我不知道", "error occurred", "我不确定"])
def test_extract_filters_invalid(mock_llm, mem, bad):
    mock_llm.replies = [bad]
    assert mem.extract_key_info("随便说说") == ""


def test_extract_filters_too_long(mock_llm, mem):
    mock_llm.replies = ["这" * 40]  # > 30 字符上限
    assert mem.extract_key_info("很长的话") == ""


# =====================================================================
# search_with_rephrase：语义改写 → 检索 → 兜底
# =====================================================================
def test_search_hit(mock_llm, mem, fake_vector):
    fake_vector.save("小叶喜欢晴天")
    mock_llm.replies = ["小叶喜欢什么"]  # 改写结果
    assert "小叶喜欢晴天" in mem.search_with_rephrase("他喜欢什么")


def test_search_fallback_query(mock_llm, mem, fake_vector):
    fake_vector.save("小叶喜欢晴天")
    # 第一次改写不命中，兜底改写命中
    mock_llm.replies = ["无关改写", "小叶的喜好"]
    assert "小叶喜欢晴天" in mem.search_with_rephrase("他喜欢什么")


def test_search_no_result(mock_llm, mem):
    mock_llm.replies = ["改写一", "改写二"]
    assert mem.search_with_rephrase("完全无关") == ""


def test_search_invalid_rephrase_uses_original(mock_llm, mem, fake_vector):
    fake_vector.save("小叶讨厌打雷")
    mock_llm.replies = ["抱歉，无法改写"]  # 含无效标记 → 回退原始查询
    assert "小叶讨厌打雷" in mem.search_with_rephrase("小叶讨厌打雷吗")


def test_search_exception_returns_empty():
    # 记忆检索异常不阻塞对话：返回空串
    class _V:
        def search(self, q, n_results=2):
            return ""

        def save(self, text):
            return "id"

        def all_documents(self):
            return []

    svc = MemoryService(_V(), _RaisingProvider())
    assert svc.search_with_rephrase("任何问题") == ""


# =====================================================================
# remember_if_important：完整沉淀链（修复 V13 Bug#1 的核心回归）
# =====================================================================
def test_remember_full_chain(mock_llm, mem, fake_vector):
    mock_llm.replies = ["yes", "小叶讨厌打雷"]
    fact = mem.remember_if_important("我最讨厌打雷了")
    assert fact == "小叶讨厌打雷"
    assert "小叶讨厌打雷" in fake_vector.docs


def test_remember_rejected(mock_llm, mem, fake_vector):
    mock_llm.replies = ["no"]
    assert mem.remember_if_important("今天吃了火锅") is None
    assert fake_vector.docs == []


def test_remember_extract_empty(mock_llm, mem, fake_vector):
    mock_llm.replies = ["yes", "抱歉，无法提取"]
    assert mem.remember_if_important("嗯嗯哦哦") is None
    assert fake_vector.docs == []


def test_remember_exception_safe(mem):
    class _BoomVector:
        def save(self, text):
            raise RuntimeError("chroma down")

    svc = MemoryService(_BoomVector(), _YesProvider())
    assert svc.remember_if_important("我叫小叶") is None  # 异常静默跳过


class _YesProvider(LLMProvider):
    name = "yes-mock"

    def chat(self, messages):
        first = messages[0]["content"] if messages else ""
        if "记忆管家" in first:
            return "yes"
        if "请从用户的话中提取" in first:
            return "小叶的名字"
        return "哼"


def test_all_memories(mock_llm, mem, fake_vector):
    fake_vector.save("记忆一")
    fake_vector.save("记忆二")
    assert mem.all_memories() == ["记忆一", "记忆二"]
