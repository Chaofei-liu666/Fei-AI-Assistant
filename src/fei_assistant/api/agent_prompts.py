from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..agents import get_agent
from ..db import get_db
from ..models import AgentPrompt
from ..prompts import ORCHESTRATOR_DEFAULT, ORCHESTRATOR_ID

router = APIRouter(prefix="/api/agents", tags=["agents"])


class PromptUpdate(BaseModel):
    prompt: str


def _default_prompt(agent_id: str) -> str:
    if agent_id == ORCHESTRATOR_ID:
        return ORCHESTRATOR_DEFAULT
    spec = get_agent(agent_id)
    if spec is None:
        raise HTTPException(404, "agent not found")
    return spec.prompt


def _view(db: Session, agent_id: str) -> dict:
    default = _default_prompt(agent_id)
    row = db.get(AgentPrompt, agent_id)
    override = row.prompt if row and row.prompt.strip() else None
    return {
        "agent_id": agent_id,
        "default_prompt": default,
        "prompt": override or default,
        "customized": override is not None,
    }


@router.get("/{agent_id}/prompt")
def read_prompt(agent_id: str, db: Session = Depends(get_db)) -> dict:
    return _view(db, agent_id)


@router.put("/{agent_id}/prompt")
def write_prompt(agent_id: str, payload: PromptUpdate, db: Session = Depends(get_db)) -> dict:
    _default_prompt(agent_id)
    text = payload.prompt.strip()
    row = db.get(AgentPrompt, agent_id) or AgentPrompt(agent_id=agent_id)
    row.prompt = text[:20000]
    db.add(row)
    db.commit()
    return _view(db, agent_id)


@router.delete("/{agent_id}/prompt")
def reset_prompt(agent_id: str, db: Session = Depends(get_db)) -> dict:
    _default_prompt(agent_id)
    row = db.get(AgentPrompt, agent_id)
    if row:
        db.delete(row)
        db.commit()
    return _view(db, agent_id)
