from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

JOB_SKILL_DESCRIPTIONS = {
    "job_intelligence_agent": "用户问岗位匹配、JD 证据、能力缺口时使用。",
    "application_status_agent": "用户问投递状态、事件时间线、下一步跟进时使用。",
    "schedule_management_agent": "用户问面试时间、笔试截止、日程冲突时使用。",
    "crawler_operations_agent": "用户问抓取进度、任务失败、自动化运行时使用。",
    "interview_review_agent": "用户提供面试记录、想复盘表现时使用。",
}


def seed_job_skills(db: Session) -> None:
    """Insert builtin job skills once; never overwrite what the user edited."""
    from .models import Skill
    from .modules.job_search.graph import SPECIALISTS

    existing = {row.skill_id for row in db.scalars(select(Skill).where(Skill.agent_id == "job_search")).all()}
    changed = False
    for skill_id, spec in SPECIALISTS.items():
        if skill_id in existing:
            continue
        db.add(Skill(
            agent_id="job_search",
            skill_id=skill_id,
            title=spec["title"],
            description=JOB_SKILL_DESCRIPTIONS.get(skill_id, ""),
            prompt=spec["prompt"],
            tool_names=[tool.name for tool in spec["tools"]],
            enabled=True,
            builtin=True,
        ))
        changed = True
    if changed:
        db.commit()


def list_skills(db: Session, agent_id: str) -> list:
    from .models import Skill

    if agent_id == "job_search":
        seed_job_skills(db)
    return list(db.scalars(
        select(Skill).where(Skill.agent_id == agent_id).order_by(Skill.created_at)
    ).all())


def get_skill_prompt(agent_id: str, skill_id: str, default: str) -> str:
    """Runtime read used by graphs; a database hiccup must never stop a run."""
    try:
        from .db import SessionLocal
        from .models import Skill

        with SessionLocal() as db:
            row = db.get(Skill, {"agent_id": agent_id, "skill_id": skill_id})
            if row and row.prompt.strip() and row.enabled:
                return row.prompt
    except Exception:
        return default
    return default


def enabled_skills(agent_id: str) -> list[dict]:
    try:
        from .db import SessionLocal
        from .models import Skill
        from sqlalchemy import select as _select

        with SessionLocal() as db:
            rows = db.scalars(_select(Skill).where(Skill.agent_id == agent_id, Skill.enabled.is_(True))).all()
            return [{"skill_id": row.skill_id, "title": row.title, "description": row.description} for row in rows]
    except Exception:
        return []
