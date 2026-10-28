from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..mail_events import list_events, recent_summary, revert_event
from ..mail_models import MailEvent

router = APIRouter(prefix="/api/mail", tags=["mail"])


def _view(event: MailEvent) -> dict:
    return {
        "id": event.id,
        "subject": event.subject,
        "sender": event.sender,
        "received_at": event.received_at.isoformat() if event.received_at else None,
        "category": event.category,
        "confidence": event.confidence,
        "rationale": event.rationale,
        "summary": event.summary,
        "application_id": event.application_id,
        "suggested_status": event.suggested_status,
        "deadline": event.deadline.isoformat() if event.deadline else None,
        "deadline_kind": event.deadline_kind,
        "applied": event.applied,
        "reverted": event.reverted,
        "detail": event.detail or {},
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }


@router.get("/events")
def events(only_applied: bool = False, limit: int = 50, db: Session = Depends(get_db)) -> list[dict]:
    return [_view(row) for row in list_events(db, only_applied=only_applied, limit=limit)]


@router.get("/recent")
def recent(limit: int = 10, db: Session = Depends(get_db)) -> list[dict]:
    return recent_summary(db, limit=limit)


@router.get("/events/{event_id}")
def event(event_id: str, db: Session = Depends(get_db)) -> dict:
    row = db.get(MailEvent, event_id)
    if not row:
        raise HTTPException(404, "mail event not found")
    return _view(row)


@router.post("/events/{event_id}/revert")
def revert(event_id: str, db: Session = Depends(get_db)) -> dict:
    row = db.get(MailEvent, event_id)
    if not row:
        raise HTTPException(404, "mail event not found")
    if not revert_event(db, row):
        raise HTTPException(400, "event cannot be reverted (not applied, already reverted, or the application moved since)")
    db.refresh(row)
    return _view(row)
