"""chat 服务单元测试：8 段式 prompt / 情绪检测 / 守卫链 / 完整流水线 / 日记。"""
from datetime import datetime, timedelta

import pytest

from app.db.models import DailyLog, Message
from app.providers.llm import LLMError, LLMProvider, MockProvider
from app.services import chat, persona
from app.services.memory import MemoryService


class _RaisingProvider(LLMProvider):
    """永远抛 LLMError 的假 Provider（测试异常分支）。"""

    name = "raising"

    def chat(self, messages):
        raise LLMError("boom")


class _Scripted(MockProvider):
    """在 Mock 基础上对「事实提取」提示词返回固定事实（验证记忆沉淀链）。"""

    def chat(self, messages):
        first = messages[0]["content"] if messages else ""
        if "请从用户的话中提取" in first:
            return "小叶的生日是4月6日"
        return super().chat(messages)


# =====================================================================
# 8 段式 system prompt
# =====================================================================
def test_prompt_contains_core_sections(db):
    prompt = chat.build_system_prompt(
        db=db, user_input="你好", emotion="平静", is_night=False,
        is_thunderstorm=False, days_to_bday=100, intimacy_level=1, trust=0,
    )
    for marker in [
        "最高优先级指令",       # 【1】亲密等级
        "刚认识 | 陌生人",      # 等级 1 规范
        "性格特质",             # 【2】人设
        "回复风格硬性要求",     # 【3】风格
        "用户核心画像",         # 【4】画像
        "当前情绪感知",         # 【6】情绪
        "行为指南",             # 【7】指南
    ]:
        assert marker in prompt
    # 可选段未启用时不应出现
    assert "相关记忆" not in prompt
    assert "今日重点" not in prompt


def test_prompt_includes_memories_and_agenda(db):
    prompt = chat.build_system_prompt(
        db=db, user_input="你好", emotion="平静", is_night=False,
        is_thunderstorm=False, days_to_bday=100, intimacy_level=1, trust=0,
        relevant_memories="小叶喜欢晴天", daily_agenda="提醒小叶喝水",
    )
    assert "[相关记忆]\n小叶喜欢晴天" in prompt
    assert "[今日重点] 提醒小叶喝水" in prompt


def test_prompt_profile_line(db):
    prompt = chat.build_system_prompt(
        db=db, user_input="你好", emotion="平静", is_night=False,
        is_thunderstorm=False, days_to_bday=100, intimacy_level=4, trust=0,
    )
    assert "名字：小叶" in prompt
    assert "喜欢：晴天, 深夜写代码" in prompt
    assert "关系等级：恋人" in prompt
    assert "信任值:0/100" in prompt


def test_prompt_birthday_today(db):
    prompt = chat.build_system_prompt(
        db=db, user_input="你好", emotion="平静", is_night=False,
        is_thunderstorm=False, days_to_bday=0, intimacy_level=1, trust=0,
    )
    assert "今天是他的生日" in prompt


def test_prompt_birthday_eve(db):
    prompt = chat.build_system_prompt(
        db=db, user_input="你好", emotion="平静", is_night=False,
        is_thunderstorm=False, days_to_bday=2, intimacy_level=1, trust=0,
    )
    assert "温馨预热" in prompt
    assert "04-06" in prompt  # 画像里的生日


def test_prompt_thunderstorm(db):
    prompt = chat.build_system_prompt(
        db=db, user_input="你好", emotion="平静", is_night=False,
        is_thunderstorm=True, days_to_bday=100, intimacy_level=1, trust=0,
    )
    assert "天气关怀" in prompt


@pytest.mark.parametrize("emotion,marker", [
    ("难过", "温柔、治愈"),
    ("开心", "一起雀跃"),
    ("平静", "他似乎有些平静"),
])
def test_prompt_emotion_response(db, emotion, marker):
    prompt = chat.build_system_prompt(
        db=db, user_input="随便说说", emotion=emotion, is_night=False,
        is_thunderstorm=False, days_to_bday=100, intimacy_level=1, trust=0,
    )
    assert marker in prompt


def test_prompt_night_with_sleep_keyword(db):
    prompt = chat.build_system_prompt(
        db=db, user_input="好困啊", emotion="疲惫", is_night=True,
        is_thunderstorm=False, days_to_bday=100, intimacy_level=1, trust=0,
    )
    assert "深夜模式" in prompt
    assert "哄睡陪伴" in prompt


def test_prompt_night_without_sleep_keyword(db):
    prompt = chat.build_system_prompt(
        db=db, user_input="随便聊聊", emotion="平静", is_night=True,
        is_thunderstorm=False, days_to_bday=100, intimacy_level=1, trust=0,
    )
    assert "深夜模式" in prompt
    assert "哄睡陪伴" not in prompt


def test_prompt_ai_denial_guide(db):
    prompt = chat.build_system_prompt(
        db=db, user_input="你只是个AI", emotion="平静", is_night=False,
        is_thunderstorm=False, days_to_bday=100, intimacy_level=1, trust=0,
    )
    assert "特别注意" in prompt


# =====================================================================
# 情绪检测（修复 V13 标点截断 Bug#5 的回归测试）
# =====================================================================
def test_detect_emotion_default_happy(mock_llm):
    assert chat.detect_emotion(mock_llm, "你好呀") == "开心"


def test_detect_emotion_strips_punctuation(mock_llm):
    mock_llm.replies = ["难过。"]
    assert chat.detect_emotion(mock_llm, "今天好难受") == "难过"


def test_detect_emotion_takes_first_segment(mock_llm):
    mock_llm.replies = ["平静 还行"]
    assert chat.detect_emotion(mock_llm, "随便") == "平静"


def test_detect_emotion_too_long_falls_back(mock_llm):
    mock_llm.replies = ["特别特别开心呀"]
    assert chat.detect_emotion(mock_llm, "哈哈") == "平静"


def test_detect_emotion_only_punctuation(mock_llm):
    mock_llm.replies = ["！！！"]
    assert chat.detect_emotion(mock_llm, "……") == "平静"


def test_detect_emotion_llm_error_falls_back():
    assert chat.detect_emotion(_RaisingProvider(), "你好") == "平静"


# =====================================================================
# 底线守卫
# =====================================================================
@pytest.mark.parametrize("level,resp,expected", [
    (1, "小叶你好呀", "……哈？谁准你让我这么说话的？快回去重修礼仪课！"),
    (1, "喂，干嘛。", "喂，干嘛。"),
    (2, "给你一个抱抱", "哼～少自作多情，我才没那么关心你呢！"),
    (2, "切～随便你。", "切～随便你。"),
    (3, "抱抱你", "抱抱你"),  # L3+ 无禁止词
    (4, "想你", "想你"),
])
def test_enforce_bottom_line(level, resp, expected):
    assert chat.enforce_bottom_line(resp, level) == expected


# =====================================================================
# 人格自检（强制分支不调用 LLM，LLM 分支用脚本化回复）
# =====================================================================
def test_critique_level1_forced_no_llm_call(mock_llm):
    out = chat.self_critique_response(mock_llm, "小叶，想你啦", "开心", False, "你好", 1)
    assert out == "喂！谁准你让我这么说话的？回去重修礼仪课！"
    assert mock_llm.calls == []  # 强制替换发生在 LLM 审查之前


def test_critique_level2_forced(mock_llm):
    out = chat.self_critique_response(mock_llm, "小叶…小叶…想你了", "开心", False, "你好", 2)
    assert out == "切～少自作多情，我才没那么关心你呢！"


def test_critique_ai_denial_forced(mock_llm):
    out = chat.self_critique_response(mock_llm, "好吧。", "平静", False, "你只是个AI", 2)
    assert out == "哼，那你去找真人好了！"


def test_critique_ai_denial_already_angry_passes(mock_llm):
    mock_llm.replies = ["OK"]
    out = chat.self_critique_response(mock_llm, "哼，才不是呢！", "平静", False, "你只是个AI", 3)
    assert out == "哼，才不是呢！"


def test_critique_too_long_forced_short(mock_llm):
    long_reply = "这是一段特别长的回复" * 10  # 110 字 > 80
    out = chat.self_critique_response(mock_llm, long_reply, "平静", False, "今天天气不错", 3)
    assert out == "……说太多啦！总之听我的就对了，小笨蛋！"


def test_critique_too_long_intro_variant(mock_llm):
    long_reply = "很长" * 50
    out = chat.self_critique_response(mock_llm, long_reply, "平静", False, "介绍一下你自己", 3)
    assert out == "希亚。……才不是特意等你问的！"


def test_critique_llm_rewrite(mock_llm):
    mock_llm.replies = ["切～本小姐才没有难过呢"]
    out = chat.self_critique_response(mock_llm, "哦", "难过", False, "我有点难过", 3)
    assert out == "切～本小姐才没有难过呢"


def test_critique_ok_keeps_original(mock_llm):
    mock_llm.replies = ["OK"]
    out = chat.self_critique_response(mock_llm, "哼，知道了啦。", "平静", False, "你好", 3)
    assert out == "哼，知道了啦。"


def test_critique_llm_error_keeps_original():
    out = chat.self_critique_response(
        _RaisingProvider(), "正常回复", "平静", False, "你好", 3
    )
    assert out == "正常回复"


# =====================================================================
# 今日议程
# =====================================================================
def test_agenda_default(db, mock_llm, fake_vector):
    memory = MemoryService(fake_vector, mock_llm)
    assert chat.generate_daily_agenda(mock_llm, memory, db) == "哼，知道了啦。"


def test_agenda_rejects_too_long(db, mock_llm, fake_vector):
    memory = MemoryService(fake_vector, mock_llm)
    # 前两条被语义改写消费，第三条是议程本身
    mock_llm.replies = ["改写一", "改写二", "x" * 60]
    assert chat.generate_daily_agenda(mock_llm, memory, db) == ""


def test_agenda_rejects_invalid_words(db, mock_llm, fake_vector):
    memory = MemoryService(fake_vector, mock_llm)
    mock_llm.replies = ["改写一", "改写二", "抱歉，今天没有想法"]
    assert chat.generate_daily_agenda(mock_llm, memory, db) == ""


def test_agenda_llm_error_returns_empty(db, fake_vector):
    memory = MemoryService(fake_vector, _RaisingProvider())
    assert chat.generate_daily_agenda(_RaisingProvider(), memory, db) == ""


# =====================================================================
# 完整流水线 process_message
# =====================================================================
def test_process_message_pipeline(db, mock_llm, fake_vector):
    memory = MemoryService(fake_vector, mock_llm)
    result = chat.process_message(db, mock_llm, memory, "你好")

    assert result["reply"] == "哼，知道了啦。"
    assert result["emotion"] == "开心"  # Mock 情绪观察者固定返回
    assert result["saved_memory"] is None
    assert result["state"] == {"trust": 3, "intimacy_level": 1, "intimacy_label": "陌生人"}

    # 消息持久化：user + assistant 各一条
    roles = [m.role for m in db.query(Message).all()]
    assert roles == ["user", "assistant"]
    user_msg = db.query(Message).filter(Message.role == "user").first()
    assert user_msg.emotion == "开心"

    # 每日日志落库（修复 Bug#2）
    log = db.query(DailyLog).one()
    assert log.user_text == "你好"
    assert log.emotion == "开心"
    assert log.saved_memory is None

    # 8 段式 prompt 出现在发给 LLM 的消息里
    sys_call = next(
        c for c in mock_llm.calls if c[0]["content"].startswith("[❗最高优先级指令]")
    )
    assert "用户核心画像" in sys_call[0]["content"]
    assert "[今日重点]" in sys_call[0]["content"]  # Mock 议程生成了默认值


def test_process_message_saves_memory_bug1(db, fake_vector):
    """修复 Bug#1：remember_if_important 的事实写入 DailyLog.saved_memory。"""
    llm = _Scripted()
    memory = MemoryService(fake_vector, llm)
    result = chat.process_message(db, llm, memory, "我的生日是4月6日")

    assert result["saved_memory"] == "小叶的生日是4月6日"
    assert "小叶的生日是4月6日" in fake_vector.docs  # 入向量库
    log = db.query(DailyLog).one()
    assert log.saved_memory == "小叶的生日是4月6日"  # 入日志（V13 永远 None）
    # 记忆提示消息存在
    memory_msgs = [m for m in db.query(Message).all() if "小本本" in m.content]
    assert len(memory_msgs) == 1


def test_process_message_confession_trust(db, mock_llm, fake_vector):
    memory = MemoryService(fake_vector, mock_llm)
    result = chat.process_message(db, mock_llm, memory, "我喜欢你")
    # +1 基础 +5 表白 +2 开心
    assert result["state"]["trust"] == 8


def test_process_message_empty_text_raises(db, mock_llm, fake_vector):
    memory = MemoryService(fake_vector, mock_llm)
    with pytest.raises(ValueError):
        chat.process_message(db, mock_llm, memory, "   ")


# =====================================================================
# 会话上下文 / 久未聊提醒
# =====================================================================
def test_session_context_fresh(db):
    ctx = chat.get_session_context(db)
    assert "希亚" in ctx["welcome"]  # 空库 → 陌生人欢迎语
    assert ctx["is_thunderstorm"] is False
    assert ctx["state"]["trust"] == 0
    assert ctx["state"]["intimacy_label"] == "陌生人"
    assert ctx["notify_idle"] is False
    assert ctx["days_to_birthday"] == persona.days_until_birthday()


def test_session_context_no_welcome_with_history(db):
    db.add(Message(role="user", content="在吗"))
    db.commit()
    ctx = chat.get_session_context(db)
    assert ctx["welcome"] == ""


def test_session_context_idle_after_24h(db):
    m = Message(role="user", content="上次的话")
    m.created_at = datetime.now() - timedelta(hours=25)
    db.add(m)
    db.commit()
    assert chat.get_session_context(db)["notify_idle"] is True


# =====================================================================
# 日记 / 历史搜索
# =====================================================================
def test_generate_diary_empty(db):
    d = chat.generate_diary(db, "2026-01-01")
    assert d["empty"] is True
    assert "还没有和我说话" in d["text"]


def test_generate_diary_with_logs(db):
    day = datetime(2026, 4, 6).date()
    db.add(DailyLog(log_date=day, user_text="今天过生日好开心", emotion="开心",
                    is_night=False, saved_memory="小叶的生日是4月6日"))
    db.add(DailyLog(log_date=day, user_text="收到礼物了", emotion="幸福",
                    is_night=True, saved_memory=None))
    db.commit()
    d = chat.generate_diary(db, "2026-04-06")
    assert d["empty"] is False
    assert d["emotion_sequence"] == "😊 → 🥰"
    assert d["main_emotion"] in ("开心", "幸福")
    assert "生日" in d["keywords"]
    assert d["memories"] == ["小叶的生日是4月6日"]
    assert d["night_count"] == 1


def test_search_history_pairs(db):
    db.add(Message(role="user", content="今天好累啊"))
    db.add(Message(role="assistant", content="哼，早点休息啦"))
    db.add(Message(role="user", content="明天再说"))
    db.commit()
    turns = chat.search_history(db, "2020-01-01", "2030-01-01", "累")
    assert len(turns) == 1
    assert turns[0]["user"] == "今天好累啊"
    assert turns[0]["assistant"] == "哼，早点休息啦"
    # 关键词不命中
    assert chat.search_history(db, "2020-01-01", "2030-01-01", "不存在的词") == []


def test_search_history_date_bounds(db):
    db.add(Message(role="user", content="边界测试"))
    db.commit()
    assert chat.search_history(db, "2020-01-01", "2020-01-02", "边界") == []  # end 之前
    assert len(chat.search_history(db, "2020-01-01", "2099-01-01", "边界")) == 1


def test_get_and_clear_history(db):
    db.add(Message(role="system", content="sys"))
    db.add(Message(role="user", content="hi"))
    db.add(Message(role="assistant", content="哼"))
    db.commit()
    hist = chat.get_history(db)
    assert [h["role"] for h in hist] == ["user", "assistant"]  # system 排除、正序
    assert hist[0]["emotion"] is None or isinstance(hist[0]["emotion"], str)
    chat.clear_history(db)
    assert chat.get_history(db) == []
