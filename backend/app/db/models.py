"""ORM 模型：修复 V13 状态三处分裂（session_state / JSON 文件 / chromadb）的问题。

结构化数据统一入 SQLite；向量记忆仍在 chroma（见 db/vector.py）。
"""
from datetime import datetime, date

from sqlalchemy import Date, DateTime, Integer, String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Message(Base):
    """聊天消息（含用户情绪标签，对应 V13 chat_history.json + emotion 字段）。"""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role: Mapped[str] = mapped_column(String(16))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    emotion: Mapped[str | None] = mapped_column(String(16), default=None)  # 仅 user 消息
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class PersonalityState(Base):
    """希亚人格状态（单行表 id=1，替代 personality_state.json）。

    V13 的 current_mood/mood_streak/unlocked_lines 为死字段，不再保留。
    """

    __tablename__ = "personality_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # 恒为 1
    trust: Mapped[int] = mapped_column(Integer, default=0)  # 0~100
    intimacy_level: Mapped[int] = mapped_column(Integer, default=1)  # 1陌生人 2朋友 3依赖者 4恋人
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class DailyLog(Base):
    """每日情绪日志（修复 V13 Bug#2：session_state 重启即丢）。"""

    __tablename__ = "daily_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    log_date: Mapped[date] = mapped_column(Date, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    user_text: Mapped[str] = mapped_column(Text)
    emotion: Mapped[str] = mapped_column(String(16))
    is_night: Mapped[bool] = mapped_column(Boolean, default=False)
    saved_memory: Mapped[str | None] = mapped_column(Text, default=None)  # 修复 V13 Bug#1：真正落值


class Goal(Base):
    """主动目标实例（对应 V13 session_state.active_goals，修复不持久问题）。"""

    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    goal_def_id: Mapped[str] = mapped_column(String(64), index=True)  # 对应 PREDEFINED_GOALS.id
    description: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(16), default="inactive")  # inactive|active|completed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    last_triggered: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    cooldown_days: Mapped[int] = mapped_column(Integer, default=1)


class UserProfile(Base):
    """核心用户画像（单行表 id=1，对应 V13 USER_MEMORY，前端可编辑）。"""

    __tablename__ = "user_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # 恒为 1
    name: Mapped[str] = mapped_column(String(64), default="小叶")
    birthday: Mapped[str] = mapped_column(String(10), default="04-06")
    likes: Mapped[str] = mapped_column(Text, default="")  # 逗号分隔
    dislikes: Mapped[str] = mapped_column(Text, default="")
    fears: Mapped[str] = mapped_column(Text, default="")
    recent_events: Mapped[str] = mapped_column(Text, default="")

    def likes_list(self) -> list[str]:
        return [x.strip() for x in self.likes.split(",") if x.strip()]

    def dislikes_list(self) -> list[str]:
        return [x.strip() for x in self.dislikes.split(",") if x.strip()]

    def fears_list(self) -> list[str]:
        return [x.strip() for x in self.fears.split(",") if x.strip()]

    def recent_events_list(self) -> list[str]:
        return [x.strip() for x in self.recent_events.split(",") if x.strip()]
