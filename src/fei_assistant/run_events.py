from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .run_models import RunStep

KINDS = ("plan", "delegate", "tool", "result", "approval", "error", "note")


def _next_seq(db: Session, run_id: str) -> int:
    current = db.scalar(select(func.max(RunStep.seq)).where(RunStep.run_id == run_id))
    return int(current or 0) + 1


def record(
    db: Session,
    run_id: str | None,
    kind: str,
    *,
    actor: str | None = None,
    title: str = "",
    status: str = "ok",
    summary: str | None = None,
    detail: dict | None = None,
    error: str | None = None,
) -> RunStep | None:
    """Append one step. Returns None when there is no run to attach it to."""
    if not run_id:
        return None
    step = RunStep(
        run_id=run_id,
        seq=_next_seq(db, run_id),
        kind=kind,
        actor=actor,
        title=title[:300],
        status=status,
        summary=summary,
        detail=detail or {},
        error=error,
        ended_at=datetime.now(timezone.utc) if status in ("ok", "failed") else None,
    )
    db.add(step)
    db.flush()
    return step


def record_safe(run_id: str | None, kind: str, **kwargs) -> None:
    """Telemetry entry point for graph nodes: never raises, never joins the caller's transaction."""
    if not run_id:
        return
    from .db import SessionLocal

    try:
        with SessionLocal() as db:
            record(db, run_id, kind, **kwargs)
            db.commit()
    except Exception:
        # Observability must never break the run it observes.
        return


def list_steps(db: Session, run_id: str, limit: int = 200) -> list[RunStep]:
    return list(db.scalars(
        select(RunStep).where(RunStep.run_id == run_id).order_by(RunStep.seq).limit(limit)
    ).all())


def recent_runs(db: Session, limit: int = 20) -> list[dict]:
    rows = db.execute(
        select(RunStep.run_id, func.count(RunStep.id), func.max(RunStep.started_at))
        .group_by(RunStep.run_id)
        .order_by(func.max(RunStep.started_at).desc())
        .limit(min(max(limit, 1), 100))
    ).all()
    return [
        {"run_id": run_id, "steps": count, "last_at": last_at.isoformat() if last_at else None}
        for run_id, count, last_at in rows
    ]


def step_view(step: RunStep) -> dict:
    return {
        "id": step.id,
        "run_id": step.run_id,
        "seq": step.seq,
        "kind": step.kind,
        "actor": step.actor,
        "title": step.title,
        "status": step.status,
        "summary": step.summary,
        "detail": step.detail or {},
        "started_at": step.started_at.isoformat() if step.started_at else None,
        "ended_at": step.ended_at.isoformat() if step.ended_at else None,
        "error": step.error,
    }
