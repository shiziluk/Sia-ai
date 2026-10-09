"""persona 服务单元测试：信任引擎 / 主动目标系统 / 生日计算 / 欢迎语。

时间相关测试通过冻结 persona 模块内的 datetime.now() 实现，不依赖真实时钟。
"""
from datetime import datetime

import pytest

from app.core.config import settings
from app.db.models import Goal
from app.services import persona


def _freeze_now(monkeypatch, year, month, day, hour=12, minute=0):
    """把 persona 模块的 datetime.now() 冻结到指定时刻（hour 用于深夜判定）。"""

    class _Fixed(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(year, month, day, hour, minute)

    monkeypatch.setattr(persona, "datetime", _Fixed)


# =====================================================================
# 基础人设
# =====================================================================
def test_character_prompt_contains_profile():
    p = persona.generate_character_system_prompt()
    assert "希亚" in p
    assert "用户专属的AI女友" in p
    assert "表面傲娇腹黑" in p
    assert "哼！" in p  # speech_patterns
    assert "要默默守护小叶" in p


def test_emotion_emoji_map():
    assert persona.EMOTION_EMOJI_MAP["开心"] == "😊"
    assert persona.EMOTION_EMOJI_MAP["难过"] == "😢"


# =====================================================================
# 生日计算
# =====================================================================
def test_days_until_birthday_tomorrow(db, monkeypatch):
    _freeze_now(monkeypatch, 2026, 4, 5)
    assert persona.days_until_birthday("04-06") == 1


def test_days_until_birthday_today(db, monkeypatch):
    _freeze_now(monkeypatch, 2026, 4, 6)
    assert persona.days_until_birthday("04-06") == 0


def test_days_until_birthday_passed_this_year(db, monkeypatch):
    # 4 月 7 日 → 明年 4 月 6 日：364 天
    _freeze_now(monkeypatch, 2026, 4, 7)
    assert persona.days_until_birthday("04-06") == 364


def test_days_until_birthday_cross_year(db, monkeypatch):
    # 2026-10-09 → 2027-04-06：179 天（与真实生日倒计时一致）
    _freeze_now(monkeypatch, 2026, 10, 9)
    assert persona.days_until_birthday("04-06") == 179


def test_days_until_birthday_invalid_format():
    assert persona.days_until_birthday("13-99") == -1


def test_days_until_birthday_default_from_settings(db, monkeypatch):
    _freeze_now(monkeypatch, 2026, 10, 9)
    assert persona.days_until_birthday() == 179  # 默认取 settings.user_birthday


def test_is_night(monkeypatch):
    _freeze_now(monkeypatch, 2026, 4, 5, hour=23)
    assert persona._is_night_now() is True
    _freeze_now(monkeypatch, 2026, 4, 5, hour=5)
    assert persona._is_night_now() is True
    _freeze_now(monkeypatch, 2026, 4, 5, hour=12)
    assert persona._is_night_now() is False


# =====================================================================
# 信任引擎
# =====================================================================
def test_personality_state_default(db):
    state = persona.ensure_personality_state(db)
    assert state.trust == 0
    assert state.intimacy_level == 1


def test_update_state_plain_plus1(db):
    persona.update_personality_state(db, "你好", "平静")
    state = persona.ensure_personality_state(db)
    assert state.trust == 1


def test_update_state_confession_and_happy(db):
    # 表白 +5，开心 +2，基础 +1 → 8
    persona.update_personality_state(db, "我好喜欢你", "开心")
    state = persona.ensure_personality_state(db)
    assert state.trust == 8


@pytest.mark.parametrize("start,expected_level", [(0, 1), (19, 2), (49, 3), (79, 4)])
def test_intimacy_thresholds(db, start, expected_level):
    state = persona.ensure_personality_state(db)
    state.trust = start
    db.commit()
    persona.update_personality_state(db, "你好", "平静")  # 普通 +1
    assert state.trust == start + 1
    assert state.intimacy_level == expected_level


def test_trust_cap_at_100(db):
    state = persona.ensure_personality_state(db)
    state.trust = 99
    db.commit()
    persona.update_personality_state(db, "你好", "开心")  # +1 +2 → 封顶 100
    assert state.trust == 100
    assert state.intimacy_level == 4


def test_reset_affinity(db):
    persona.update_personality_state(db, "我喜欢你", "开心")
    persona.reset_affinity(db)
    state = persona.ensure_personality_state(db)
    assert state.trust == 0
    assert state.intimacy_level == 1


# =====================================================================
# 用户画像
# =====================================================================
def test_ensure_user_profile_defaults(db):
    profile = persona.ensure_user_profile(db)
    assert profile.name == settings.user_name
    assert "晴天" in profile.likes_list()
    assert "打雷" in profile.dislikes_list()
    # 幂等：二次调用不新建
    assert persona.ensure_user_profile(db).id == profile.id


# =====================================================================
# 主动目标系统
# =====================================================================
def test_ensure_goals_initial(db):
    persona.ensure_goals(db, days_to_bday=100)
    goals = db.query(Goal).all()
    assert {g.goal_def_id for g in goals} == {"reduce_stress_weekly", "encourage_sleep"}
    assert all(g.status == "inactive" for g in goals)


def test_ensure_goals_birthday_prep_activated(db):
    persona.ensure_goals(db, days_to_bday=2)
    prep = db.query(Goal).filter(Goal.goal_def_id == "birthday_prep").first()
    assert prep is not None
    assert prep.status == "active"


def test_ensure_goals_idempotent(db):
    persona.ensure_goals(db, 100)
    persona.ensure_goals(db, 100)
    assert db.query(Goal).count() == 2


def test_goal_keyword_trigger(db):
    persona.ensure_goals(db, 100)
    persona.expire_and_check_goals(db, ["今天工作好累啊"], 179)
    reduce_g = db.query(Goal).filter(Goal.goal_def_id == "reduce_stress_weekly").first()
    assert reduce_g.status == "active"
    assert reduce_g.last_triggered is not None


def test_goal_no_keyword_no_trigger(db):
    persona.ensure_goals(db, 100)
    persona.expire_and_check_goals(db, ["今天天气不错"], 179)
    assert all(g.status == "inactive" for g in db.query(Goal).all())


def test_goal_cooldown_skip(db, monkeypatch):
    _freeze_now(monkeypatch, 2026, 4, 5, 12)
    persona.ensure_goals(db, 100)
    goal = db.query(Goal).filter(Goal.goal_def_id == "reduce_stress_weekly").first()
    goal.status = "active"
    goal.last_triggered = datetime(2026, 4, 4, 12, 0)  # 1 天前 < 冷却 2 天
    db.commit()
    persona.expire_and_check_goals(db, ["累死了"], 179)
    db.refresh(goal)
    assert goal.last_triggered.date() == datetime(2026, 4, 4).date()  # 未重新触发


def test_goal_retrigger_after_cooldown(db, monkeypatch):
    _freeze_now(monkeypatch, 2026, 4, 5, 12)
    persona.ensure_goals(db, 100)
    goal = db.query(Goal).filter(Goal.goal_def_id == "reduce_stress_weekly").first()
    goal.status = "active"
    goal.last_triggered = datetime(2026, 3, 30, 12, 0)  # 6 天前 > 冷却 2 天
    db.commit()
    persona.expire_and_check_goals(db, ["压力好大"], 179)
    db.refresh(goal)
    assert goal.last_triggered.date() == datetime(2026, 4, 5).date()  # 已重新触发


def test_sleep_goal_blocked_at_noon(db, monkeypatch):
    _freeze_now(monkeypatch, 2026, 4, 5, 12)  # 正午：不满足 23 点后/6 点前
    persona.ensure_goals(db, 100)
    persona.expire_and_check_goals(db, ["好困啊"], 179)
    goal = db.query(Goal).filter(Goal.goal_def_id == "encourage_sleep").first()
    assert goal.status == "inactive"


def test_sleep_goal_triggers_at_night(db, monkeypatch):
    _freeze_now(monkeypatch, 2026, 4, 5, 23)  # 23 点后
    persona.ensure_goals(db, 100)
    persona.expire_and_check_goals(db, ["困得睁不开眼"], 179)
    goal = db.query(Goal).filter(Goal.goal_def_id == "encourage_sleep").first()
    assert goal.status == "active"


def test_birthday_goal_archived_after_birthday(db):
    persona.ensure_goals(db, 2)
    prep = db.query(Goal).filter(Goal.goal_def_id == "birthday_prep").first()
    assert prep.status == "active"
    persona.expire_and_check_goals(db, [], days_to_bday=-1)  # 生日已过
    db.refresh(prep)
    assert prep.status == "completed"


def test_active_goal_descriptions(db):
    persona.ensure_goals(db, 100)
    persona.expire_and_check_goals(db, ["扛不住了"], 179)
    desc = persona.active_goal_descriptions(db)
    assert desc == ["本周帮小叶减压"]


# =====================================================================
# 欢迎语（优先级：生日 > 雷雨深夜 > 雷雨 > 生日前夜 > 亲密度分档）
# =====================================================================
def test_welcome_birthday(monkeypatch):
    w = persona.build_welcome(True, False, 0, 1)
    assert "生日快乐" in w


def test_welcome_thunderstorm_night(monkeypatch):
    _freeze_now(monkeypatch, 2026, 4, 5, hour=23)
    w = persona.build_welcome(False, True, 100, 1)
    assert "月光" in w  # 深夜雷雨版


def test_welcome_thunderstorm_day(monkeypatch):
    _freeze_now(monkeypatch, 2026, 4, 5, hour=12)
    w = persona.build_welcome(False, True, 100, 1)
    assert "陪你聊会儿天" in w  # 白天雷雨版


def test_welcome_birthday_eve(monkeypatch):
    assert "明天就是你的生日" in persona.build_welcome(False, False, 1, 1)
    assert "后天就是你的生日" in persona.build_welcome(False, False, 2, 1)


def test_welcome_by_intimacy_level():
    assert "谁准你直接叫我的名字" in persona.build_welcome(False, False, 100, 1)
    assert "毒舌吐槽" in persona.build_welcome(False, False, 100, 2)
    assert "置顶聊天" in persona.build_welcome(False, False, 100, 3)
    assert "笨蛋小叶" in persona.build_welcome(False, False, 100, 4)


def test_affinity_tip():
    assert "配看我的好感度" in persona.affinity_tip(1)
    assert "❤️" in persona.affinity_tip(4)
    assert persona.affinity_tip(99) == "……"
