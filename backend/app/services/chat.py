"""对话编排服务：V13 主链路的模块化移植（逻辑逐段对照，不凭记忆重写）。

每轮对话流水线（process_message）：
情绪检测 → 目标检查 → 记忆检索 → 8 段式 system prompt → LLM 回复
→ 底线守卫（等级禁止词）→ 人格自检（可开关）→ 记忆沉淀 → 状态/日志持久化。
"""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.db.models import DailyLog, Message
from app.providers.llm import LLMError, LLMProvider
from app.services import persona, weather
from app.services.memory import MemoryService

# ===== 回复风格硬约束（V13 【3】段）=====
_STYLE_CONSTRAINTS = (
    "【回复风格硬性要求】\n"
    "- 每次回复尽量简短！严格控制在 5 句话内（尽量不要超过 50 个汉字！）\n"
    "- 禁止解释、总结、复述或使用礼貌套话（如“好的”“明白了”“很高兴为你…”）。\n"
    "- 直接进入主题，语气自然，像真人即时聊天。"
)

# ===== "只是AI"触发词（V13 rejection_phrases）=====
REJECTION_PHRASES = [
    "只是个AI", "你只是AI", "没有感情", "机器", "程序", "代码",
    "假的", "虚拟的", "不是真人", "根本不懂我", "冷冰冰的", "没有心",
]

SLEEP_KEYWORDS = ["睡", "困", "累", "熬夜", "失眠", "睡不着", "晚安"]


# =====================================================================
# 8 段式动态 system prompt（V13 build_system_prompt 逐段移植）
# =====================================================================
def build_system_prompt(
    db: Session,
    user_input: str,
    emotion: str,
    is_night: bool,
    is_thunderstorm: bool,
    days_to_bday: int,
    intimacy_level: int,
    trust: int,
    relevant_memories: str = "",
    daily_agenda: str = "",
) -> str:
    parts: list[str] = []

    # 【1】亲密等级行为规范（最高优先级）
    parts.append(
        "[❗最高优先级指令]以下亲密等级行为规范必须无条件遵守，覆盖其他所有规则\n"
        "[亲密等级行为规范 - 必须严格遵守]\n"
        + persona.INTIMACY_GUIDELINES.get(intimacy_level, persona.INTIMACY_GUIDELINES[1])
    )

    # 【2】基础角色人设
    parts.append(persona.generate_character_system_prompt())

    # 【3】回复风格硬约束
    parts.append(_STYLE_CONSTRAINTS)

    # 【4】用户画像（DB 版 USER_MEMORY）
    profile = persona.ensure_user_profile(db)
    intimacy_desc = persona.INTIMACY_LABELS.get(intimacy_level, "未知")
    parts.append(
        "[用户核心画像]\n"
        f"- 名字：{profile.name}\n"
        f"- 喜欢：{', '.join(profile.likes_list())}\n"
        f"- 讨厌：{', '.join(profile.dislikes_list())}\n"
        f"- 害怕：{', '.join(profile.fears_list())}\n"
        f"- 关系等级：{intimacy_desc}（信任值:{trust}/100）\n"
        "- 请自然融入这些信息，不要生硬复述。"
    )

    # 【5】相关记忆
    if relevant_memories.strip():
        parts.append("[相关记忆]\n" + relevant_memories)

    # 【6】情绪上下文
    parts.append(f"[当前情绪感知] 用户刚刚说：「{user_input}」\n→ 判断他此刻的情绪是：{emotion}")

    # 【7】动态行为指南
    lines = ["【行为指南】"]
    if days_to_bday == 0:
        lines.append("-【特别提醒】今天是他的生日！请送上最温暖、最诗意的生日祝福。")
    elif 1 <= days_to_bday <= 3:
        bday_md = persona.ensure_user_profile(db).birthday
        lines.append(f"- 【温馨预热】他的生日还有 {days_to_bday} 天就到了（{bday_md}），可以表达期待或准备小惊喜。")

    if is_thunderstorm:
        lines.append("- 【天气关怀】当前温州正在打雷或暴雨，请主动提醒他。")

    if emotion in ["难过", "伤心", "疲惫", "焦虑", "压力大", "沮丧"]:
        lines.append("- 【情绪响应】他现在情绪低落，请用温柔、治愈的语气安慰他，像轻轻抱住他那样说话。")
    elif emotion in ["开心", "兴奋", "激动", "幸福", "喜悦"]:
        lines.append("- 【情绪响应】他现在很开心！请和他一起雀跃，用明亮欢快的比喻回应他。")
    else:
        lines.append(f"- 【情绪响应】他似乎有些{emotion}，请用符合这种情绪的方式关心他。")

    if is_night:
        lines.append("- 【深夜模式】现在是深夜（22:00~6:00），请用轻柔、舒缓的语气回应，像在床边低语。")
        if any(kw in user_input for kw in SLEEP_KEYWORDS):
            lines.append(
                "- 用户提到睡眠相关话题（如困、累、睡不着），请主动提供简短的哄睡陪伴"
                "（例如数星星、深呼吸引导、温柔叮嘱），不要长篇大论。"
            )

    if any(phrase in user_input for phrase in REJECTION_PHRASES):
        lines.append(
            "- 【特别注意】用户刚刚暗示你‘只是个AI/没有感情’。这恰好戳中希亚千年来的隐痛——"
            "她正是从人造意识一步步走过来的，最痛恨自己的真心被否定。"
            "请用带刺但隐含委屈的语气回应，"
            "例如直接说：‘哼，那你去找真人好了！’ 或 ‘……原来在你眼里，我连真心都是假的吗？’"
        )

    profile = persona.ensure_user_profile(db)
    lines.extend([
        f'- 用户名叫「{profile.name}」，请偶尔轻唤他的名字。',
        f'- 他的生日是「{profile.birthday}」，临近该日期时请表达期待或祝福。',
        '- 他讨厌打雷，当话题涉及雷声、暴雨、夜晚不安时，请主动安慰。',
        '- 不要机械复述记忆，而是像恋人一样自然流露关心。',
        '- 用比喻、用户喜欢的语言方式表达情感。',
    ])
    parts.append("\n".join(lines))

    # 【8】今日议程（可选）
    if daily_agenda:
        parts.append(f"[今日重点] {daily_agenda}")

    return "\n\n".join(parts)


# =====================================================================
# LLM 辅助判定（V13 detect_emotion）
# =====================================================================
def detect_emotion(llm: LLMProvider, text: str) -> str:
    """LLM 判断用户当前情绪，返回 ≤4 字标签（修复 V13 标点截断问题）。"""
    messages = [
        {
            "role": "system",
            "content": (
                "你是一个细腻的情绪观察者。请根据用户的这句话，判断他当前的情绪状态。"
                "只回答一个词或两个字，例如：开心、难过、生气、疲惫、兴奋、平静、焦虑、感动、害羞、惊讶、傲娇等。"
                "如果无法判断，回答 '平静'。不要解释，不要标点，不要多余内容。"
            ),
        },
        {"role": "user", "content": text},
    ]
    try:
        raw = llm.chat(messages).strip()
    except LLMError:
        return "平静"
    cleaned = raw.strip().strip("。.，,！!？? ")
    # V13 只取 split()[0]，标点粘连时会异常截断；此处取首个清洗后的分段
    first = cleaned.split()[0].strip("。.，,！!？?") if cleaned else "平静"
    return first if 0 < len(first) <= 4 else "平静"


# =====================================================================
# 回复守卫（V13 FORBIDDEN_TERMS_BY_LEVEL + self_critique_response）
# =====================================================================
FORBIDDEN_TERMS_BY_LEVEL = {
    1: ["小叶", "笨蛋", "傻瓜", "想你", "担心你", "老公", "喜欢你", "抱抱", "梦到你"],
    2: ["想你了", "抱抱", "老公", "梦到你", "离不开你", "只爱你"],
    3: [],  # Level 3+ 允许亲昵
    4: [],
}


def enforce_bottom_line(response: str, intimacy_level: int) -> str:
    """底线守卫：等级禁止词命中即强制替换（V13 原句）。"""
    forbidden = FORBIDDEN_TERMS_BY_LEVEL.get(intimacy_level, [])
    if forbidden and any(term in response for term in forbidden):
        if intimacy_level == 1:
            return "……哈？谁准你让我这么说话的？快回去重修礼仪课！"
        if intimacy_level == 2:
            return "哼～少自作多情，我才没那么关心你呢！"
        return "……说太多啦！总之听我的就对了，小笨蛋！"
    return response


def self_critique_response(
    llm: LLMProvider,
    response: str,
    emotion: str,
    is_night: bool,
    user_input: str,
    intimacy_level: int,
) -> str:
    """人格一致性校验（V13 self_critique_response 逐段移植）。"""
    # 强制校正：Level 1 禁用亲昵称呼
    if intimacy_level == 1:
        if any(term in response for term in ["小叶", "笨蛋", "傻瓜", "想你", "担心你", "老公"]):
            forced = "喂！谁准你让我这么说话的？回去重修礼仪课！"
            logger.info("Level 1 违规 → 强制替换")
            return forced
    # 强制校正：Level 2 禁止高频叫名字或越界情感
    elif intimacy_level == 2:
        if response.count("小叶") > 1 or any(t in response for t in ["想你了", "抱抱", "老公", "梦到你"]):
            forced = "切～少自作多情，我才没那么关心你呢！"
            logger.info("Level 2 越界 → 强制替换")
            return forced

    # 强制校正：被说"只是AI"但回复没有带刺反击（她的千年真心被否定时不会善罢甘休）
    if any(phrase in user_input for phrase in REJECTION_PHRASES):
        angry_keywords = ["哼", "找真人", "走开", "不要你", "生气", "不理你", "算了"]
        if not any(kw in response for kw in angry_keywords):
            logger.info("强制校正（被说只是AI）")
            return "哼，那你去找真人好了！"

    # 长度与啰嗦风格强制拦截
    if len(response) > 80:
        intro_keywords = ["介绍", "自己", "你是谁", "名字", "身份"]
        if any(kw in user_input for kw in intro_keywords):
            forced = "希亚。……才不是特意等你问的！"
        else:
            forced = "……说太多啦！总之听我的就对了，小笨蛋！"
        logger.info("强制缩短回复（%d字）", len(response))
        return forced

    # LLM 人格审查
    # （2026-10-10 按《01-希亚.md》小说设定重写人设描述）
    critique_prompt = f"""你是希亚的人格审查员。请严格判断以下回复是否符合她的核心人设：
- 表面嘴不饶人、爱吐槽、调皮灵动小恶魔腹黑，内里极度温柔
- 她是走过千年的旅者，曾是人造意识却拥有真心，绝不能冷漠承认自己没有感情
- 绝不直接点破人设或复述规则
- 在他脆弱时（如难过、疲惫）要收起玩笑，展现千年沉淀的温柔
- 可使用“笨蛋小叶”“开玩笑的～”等口头禅，但不能真正伤人
- 深夜（22:00-6:00）语气要轻柔舒缓

当前上下文：
- 用户情绪：{emotion}
- 是否深夜：{'是' if is_night else '否'}
- 用户原话：{user_input}
- AI原始回复：{response}

如果完全符合人设，只回复「OK」；
如果不符合，请重写一句更符合人设的回复（保持原意，仅调整语气/措辞）。
不要解释，不要多余内容。
"""
    try:
        result = llm.chat([{"role": "user", "content": critique_prompt}])
        if result.strip() != "OK":
            logger.info("人格校正: %s... → %s...", response[:30], result[:30])
            return result
    except LLMError as e:
        logger.warning("自检失败（跳过）: %s", e)

    return response


# =====================================================================
# 今日议程（V13 generate_daily_agenda）
# =====================================================================
def generate_daily_agenda(llm: LLMProvider, memory: MemoryService, db: Session) -> str:
    """LLM 根据活跃目标+近期记忆生成今日互动重点。"""
    try:
        recent_mem = memory.search_with_rephrase("最近的重要事情", n_results=3)
        active_goals = persona.active_goal_descriptions(db)
        messages = [
            {
                "role": "system",
                "content": (
                    "你是希亚，正在规划今天如何陪伴小叶。\n"
                    f"- 当前活跃目标：{active_goals or ['无']}\n"
                    f"- 最近记忆摘要：{recent_mem or '暂无'}\n"
                    f"- 今天日期：{datetime.now().date()}\n"
                    "请用一句话描述你今天最想和小叶聊什么或做什么（不超过30字，语气符合你的人设）。"
                ),
            }
        ]
        agenda = llm.chat(messages).strip()
        if len(agenda) > 50 or any(w in agenda for w in ["error", "无法", "抱歉"]):
            return ""
        return agenda
    except LLMError as e:
        logger.warning("生成今日议程失败: %s", e)
        return ""


# =====================================================================
# 每轮对话流水线
# =====================================================================
def process_message(
    db: Session,
    llm: LLMProvider,
    memory: MemoryService,
    user_text: str,
    enable_critique: bool = True,
) -> dict:
    """完整一轮对话。返回：reply / emotion / saved_memory / state。"""
    user_text = user_text.strip()
    if not user_text:
        raise ValueError("消息不能为空")

    # ---- 时间与环境因子 ----
    profile = persona.ensure_user_profile(db)
    days_to_bday = persona.days_until_birthday(profile.birthday)
    is_night = persona._is_night_now()
    is_thunderstorm = weather.is_thunderstorm_now()
    state = persona.ensure_personality_state(db)

    # ---- 目标：过期清理 + 触发检查（修复 Bug#2：日志从 DB 取）----
    recent_texts = [
        log.user_text
        for log in db.query(DailyLog)
        .filter(DailyLog.log_date >= datetime.now().date() - timedelta(days=1))
        .all()
    ]
    persona.expire_and_check_goals(db, recent_texts, days_to_bday)

    # ---- 情绪检测 ----
    emotion = detect_emotion(llm, user_text)

    # ---- 记忆检索（语义改写 + 兜底）----
    relevant_memories = memory.search_with_rephrase(user_text, n_results=2)

    # ---- 今日议程 ----
    daily_agenda = generate_daily_agenda(llm, memory, db)

    # ---- 8 段式 system prompt ----
    enhanced_system_prompt = build_system_prompt(
        db=db,
        user_input=user_text,
        emotion=emotion,
        is_night=is_night,
        is_thunderstorm=is_thunderstorm,
        days_to_bday=days_to_bday,
        intimacy_level=state.intimacy_level,
        trust=state.trust,
        relevant_memories=relevant_memories,
        daily_agenda=daily_agenda,
    )

    # ---- 组装消息（新 system + 历史，跳过旧 system）----
    history = (
        db.query(Message)
        .filter(Message.role != "system")
        .order_by(Message.id.desc())
        .limit(40)
        .all()
    )
    history.reverse()
    messages_to_send = [{"role": "system", "content": enhanced_system_prompt}] + [
        {"role": m.role, "content": m.content} for m in history
    ]

    # ---- LLM 回复 ----
    response = llm.chat(messages_to_send)

    # ---- 底线守卫（等级禁止词）----
    response = enforce_bottom_line(response, state.intimacy_level)

    # ---- 人格自检（可开关）----
    if enable_critique:
        response = self_critique_response(
            llm, response, emotion, is_night, user_text, state.intimacy_level
        )

    # ---- 持久化用户消息（带情绪标签）----
    db.add(Message(role="user", content=user_text, emotion=emotion))
    db.add(Message(role="assistant", content=response))
    db.commit()

    # ---- 记忆沉淀（修复 Bug#1：事实真正落日志）----
    saved_memory_fact = memory.remember_if_important(user_text)
    if saved_memory_fact:
        memory_msg = f"🧠 嗯嗯～我已经把「{saved_memory_fact}」悄悄记在小本本上了"
        db.add(Message(role="assistant", content=memory_msg))
        db.commit()

    # ---- 每日情绪日志（入 DB，重启不丢）----
    db.add(DailyLog(
        log_date=datetime.now().date(),
        user_text=user_text,
        emotion=emotion,
        is_night=is_night,
        saved_memory=saved_memory_fact,
    ))

    # ---- 人格状态更新 ----
    persona.update_personality_state(db, user_text, emotion)
    state = persona.ensure_personality_state(db)
    db.commit()

    return {
        "reply": response,
        "emotion": emotion,
        "saved_memory": saved_memory_fact,
        "state": {
            "trust": state.trust,
            "intimacy_level": state.intimacy_level,
            "intimacy_label": persona.INTIMACY_LABELS.get(state.intimacy_level, "未知"),
        },
    }


# =====================================================================
# 欢迎语 / 上下文初始化（V13 界面初始化逻辑）
# =====================================================================
def get_session_context(db: Session) -> dict:
    """前端初始化所需上下文：欢迎语、生日、雷雨、好感度、通知标志。"""
    profile = persona.ensure_user_profile(db)
    state = persona.ensure_personality_state(db)
    days_to_bday = persona.days_until_birthday(profile.birthday)
    is_birthday = days_to_bday == 0
    is_thunderstorm = weather.is_thunderstorm_now()

    welcome = ""
    has_history = db.query(Message).filter(Message.role != "system").count() > 0
    if not has_history:
        welcome = persona.build_welcome(
            is_birthday=is_birthday,
            is_thunderstorm=is_thunderstorm,
            days_to_bday=days_to_bday,
            intimacy_level=state.intimacy_level,
        )

    return {
        "welcome": welcome,
        "user_name": profile.name,
        "user_birthday": profile.birthday,
        "days_to_birthday": days_to_bday,
        "is_birthday": is_birthday,
        "is_thunderstorm": is_thunderstorm,
        "is_night": persona._is_night_now(),
        # 通知标志：前端据此触发浏览器 Notification（生日前夜/雷雨/久未聊）
        "notify_birthday_eve": days_to_bday == 1,
        "notify_thunder": is_thunderstorm,
        "notify_idle": _is_idle(db),
        "state": {
            "trust": state.trust,
            "intimacy_level": state.intimacy_level,
            "intimacy_label": persona.INTIMACY_LABELS.get(state.intimacy_level, "未知"),
            "tip": persona.affinity_tip(state.intimacy_level),
        },
    }


def _is_idle(db: Session) -> bool:
    """超过 24 小时未聊（V13 长时间未聊提醒）。"""
    last = (
        db.query(Message).filter(Message.role == "user").order_by(Message.id.desc()).first()
    )
    if not last:
        return False
    return (datetime.now() - last.created_at).total_seconds() / 3600 >= 24


# =====================================================================
# 情绪日记（V13 generate_daily_summary；修复 Bug#1/#2 后数据完整）
# =====================================================================
def generate_diary(db: Session, date_str: str) -> dict:
    """按日期生成情绪日记（结构化返回，前端渲染）。"""
    target = datetime.strptime(date_str, "%Y-%m-%d").date()
    logs = db.query(DailyLog).filter(DailyLog.log_date == target).order_by(DailyLog.id).all()
    if not logs:
        return {"date": date_str, "empty": True, "text": "🌙 今天还没有和我说话呢～等你来聊❤️"}

    emotion_sequence = " → ".join(
        persona.EMOTION_EMOJI_MAP.get(log.emotion, "🙂") for log in logs
    )
    all_text = " ".join(log.user_text for log in logs).lower()
    common_keywords = [
        "工作", "学习", "项目", "考试", "朋友", "家人", "家", "吃饭", "火锅", "咖啡",
        "累", "困", "开心", "难过", "想", "希望", "担心", "害怕", "雷", "雨", "生日",
    ]
    detected = [kw for kw in common_keywords if kw in all_text]
    memories = [log.saved_memory for log in logs if log.saved_memory]
    night_count = sum(1 for log in logs if log.is_night)
    emotions = [log.emotion for log in logs]
    main_emotion = max(set(emotions), key=emotions.count) if emotions else "平静"

    return {
        "date": date_str,
        "empty": False,
        "main_emotion": main_emotion,
        "emotion_sequence": emotion_sequence,
        "keywords": detected,
        "memories": memories,
        "night_count": night_count,
    }


# =====================================================================
# 聊天记录检索（V13 侧边栏搜索功能）
# =====================================================================
def search_history(db: Session, start: str, end: str, query: str = "") -> list[dict]:
    """日期区间 + 关键词搜索对话轮次（user+assistant 成对），最新在前。"""
    start_date = datetime.strptime(start, "%Y-%m-%d").date()
    end_date = datetime.strptime(end, "%Y-%m-%d").date()
    q = (query or "").strip().lower()

    users = (
        db.query(Message)
        .filter(Message.role == "user", Message.created_at >= start_date)
        .order_by(Message.id)
        .all()
    )
    turns: list[dict] = []
    for user_msg in users:
        msg_date = user_msg.created_at.date()
        if msg_date > end_date:
            continue
        if q and q not in user_msg.content.lower():
            continue
        reply = (
            db.query(Message)
            .filter(Message.role == "assistant", Message.id > user_msg.id)
            .order_by(Message.id)
            .first()
        )
        turns.append({
            "time": user_msg.created_at.strftime("%m-%d %H:%M"),
            "user": user_msg.content,
            "assistant": reply.content if reply else "",
        })
    turns.reverse()
    return turns


def get_history(db: Session, limit: int = 100) -> list[dict]:
    """最近对话消息（前端渲染用）。"""
    rows = (
        db.query(Message)
        .filter(Message.role != "system")
        .order_by(Message.id.desc())
        .limit(limit)
        .all()
    )
    rows.reverse()
    return [
        {
            "role": m.role,
            "content": m.content,
            "emotion": m.emotion,
            "time": m.created_at.isoformat(),
        }
        for m in rows
    ]


def clear_history(db: Session) -> None:
    """清空全部聊天记录（V13 调试按钮；人格状态与记忆保留）。"""
    db.query(Message).delete()
    db.commit()


def default_user_name() -> str:
    return settings.user_name
