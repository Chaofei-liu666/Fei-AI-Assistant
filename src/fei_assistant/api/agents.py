from __future__ import annotations

from fastapi import APIRouter

from ..agents import list_agents

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("")
def agents() -> list[dict]:
    return list_agents()
