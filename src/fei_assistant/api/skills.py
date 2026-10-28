from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..agents import get_agent
from ..db import get_db
from ..models import Skill
from ..skills import list_skills

router = APIRouter(prefix="/api/agents", tags=["skills"])


class SkillUpdate(BaseModel):
    description: str | None = None
    prompt: str | None = None
    enabled: bool | None = None


def _view(row: Skill) -> dict:
    return {
        "skill_id": row.skill_id,
        "agent_id": row.agent_id,
        "title": row.title,
        "description": row.description,
        "prompt": row.prompt,
        "tools": row.tool_names or [],
        "enabled": row.enabled,
        "builtin": row.builtin,
    }


@router.get("/{agent_id}/skills")
def get_skills(agent_id: str, db: Session = Depends(get_db)) -> list[dict]:
    if get_agent(agent_id) is None:
        raise HTTPException(404, "agent not found")
    return [_view(row) for row in list_skills(db, agent_id)]


@router.put("/{agent_id}/skills/{skill_id}")
def update_skill(agent_id: str, skill_id: str, payload: SkillUpdate, db: Session = Depends(get_db)) -> dict:
    row = db.get(Skill, {"agent_id": agent_id, "skill_id": skill_id})
    if row is None:
        raise HTTPException(404, "skill not found")
    if payload.description is not None:
        row.description = payload.description.strip()[:500]
    if payload.prompt is not None:
        row.prompt = payload.prompt.strip()[:20000]
    if payload.enabled is not None:
        row.enabled = payload.enabled
    db.add(row)
    db.commit()
    return _view(row)
