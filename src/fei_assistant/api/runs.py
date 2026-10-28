from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..run_events import list_steps, recent_runs, step_view

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.get("")
def runs(limit: int = 20, db: Session = Depends(get_db)) -> list[dict]:
    return recent_runs(db, limit)


@router.get("/{run_id}/steps")
def steps(run_id: str, db: Session = Depends(get_db)) -> dict:
    rows = list_steps(db, run_id)
    if not rows:
        raise HTTPException(404, "run has no steps")
    return {"run_id": run_id, "steps": [step_view(row) for row in rows]}
