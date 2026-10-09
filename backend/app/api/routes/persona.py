"""人设路由：用户画像编辑 / 好感度状态 / 目标列表 / 重置。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import ProfileUpdate
from app.db.database import get_db
from app.db.models import Goal
from app.services import persona

router = APIRouter(prefix="/api/persona", tags=["persona"])


def _profile_dict(p) -> dict:
    return {
        "name": p.name,
        "birthday": p.birthday,
        "likes": p.likes_list(),
        "dislikes": p.dislikes_list(),
        "fears": p.fears_list(),
        "recent_events": p.recent_events_list(),
    }


@router.get("")
def get_persona(db: Session = Depends(get_db)):
    """画像 + 人格状态 + 目标列表。"""
    profile = persona.ensure_user_profile(db)
    state = persona.ensure_personality_state(db)
    goals = db.query(Goal).order_by(Goal.id).all()
    return {
        "profile": _profile_dict(profile),
        "state": {
            "trust": state.trust,
            "intimacy_level": state.intimacy_level,
            "intimacy_label": persona.INTIMACY_LABELS.get(state.intimacy_level, "未知"),
            "tip": persona.affinity_tip(state.intimacy_level),
        },
        "goals": [
            {
                "id": g.goal_def_id,
                "description": g.description,
                "status": g.status,
                "cooldown_days": g.cooldown_days,
                "last_triggered": g.last_triggered.isoformat() if g.last_triggered else None,
            }
            for g in goals
        ],
    }


@router.put("")
def update_profile(body: ProfileUpdate, db: Session = Depends(get_db)):
    """编辑用户画像（传了才改）。"""
    profile = persona.ensure_user_profile(db)
    for field in ["name", "birthday", "likes", "dislikes", "fears", "recent_events"]:
        value = getattr(body, field)
        if value is not None:
            setattr(profile, field, value.strip() if isinstance(value, str) else value)
    db.commit()
    return {"ok": True, "profile": _profile_dict(profile)}


@router.post("/reset-affinity")
def reset_affinity(db: Session = Depends(get_db)):
    """重置好感度（V13 调试按钮保留）。"""
    persona.reset_affinity(db)
    return {"ok": True}
