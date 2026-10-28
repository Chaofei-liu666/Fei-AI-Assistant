from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .mail_models import MailEvent
from .models import Application, ApplicationEvent
from .services import change_application_status

ACTIVE_STAGES = ["saved", "applied", "screening", "assessment", "interview", "offer"]
TERMINAL_STAGES = {"rejected", "withdrawn"}


def is_forward(current: str, target: str) -> bool:
    """A mail may only move an application forward. It never downgrades a stage."""
    if current == target:
        return False
    if target in TERMINAL_STAGES:
        return current not in TERMINAL_STAGES
    if target not in ACTIVE_STAGES:
        return False
    if current not in ACTIVE_STAGES:
        return False
    return ACTIVE_STAGES.index(target) > ACTIVE_STAGES.index(current)


def record_event(
    db: Session,
    *,
    mailbox: str,
    uid: int | None,
    message_id: str | None,
    subject: str | None,
    sender: str | None,
    received_at: datetime | None,
    category: str,
    confidence: float,
    rationale: str | None,
    summary: str | None,
    application_id: str | None,
    suggested_status: str | None,
    deadline=None,
    deadline_kind: str = "unknown",
) -> MailEvent | None:
    """Idempotent by dedupe_key: the same mail can never produce two events."""
    key = message_id or f"{mailbox}:{uid}"
    existing = db.scalar(select(MailEvent).where(MailEvent.dedupe_key == key))
    if existing:
        return existing
    event = MailEvent(
        dedupe_key=key,
        message_id=message_id,
        mailbox=mailbox,
        uid=uid,
        subject=subject,
        sender=sender,
        received_at=received_at,
        category=category,
        confidence=confidence,
        rationale=rationale,
        summary=summary,
        application_id=application_id,
        suggested_status=suggested_status,
        deadline=deadline,
        deadline_kind=deadline_kind,
    )
    db.add(event)
    db.flush()
    return event


def apply_event(db: Session, event: MailEvent) -> ApplicationEvent | None:
    """Apply the suggested transition. Returns None when there is nothing to apply."""
    if event.applied or event.reverted or not event.suggested_status or not event.application_id:
        return None
    application = db.get(Application, event.application_id)
    if not application or not is_forward(application.status, event.suggested_status):
        event.detail = {**(event.detail or {}), "skipped": "not_forward"}
        db.add(event)
        return None
    applied = change_application_status(
        db,
        application,
        event.suggested_status,
        source="mail",
        note=f"邮件自动更新：{event.subject or ''}".strip(),
        evidence={"mail_event_id": event.id, "message_id": event.message_id,
                  "confidence": event.confidence, "rationale": event.rationale},
    )
    db.flush()
    event.applied = True
    event.applied_event_id = applied.id
    db.add(event)
    return applied


def revert_event(db: Session, event: MailEvent) -> bool:
    """Undo an applied mail update, but only when nothing else moved the application since."""
    if not event.applied or event.reverted or not event.applied_event_id:
        return False
    applied = db.get(ApplicationEvent, event.applied_event_id)
    application = db.get(Application, event.application_id) if event.application_id else None
    if not applied or not application:
        return False
    if application.status != applied.to_status:
        event.detail = {**(event.detail or {}), "revert_skipped": "application_moved_since"}
        db.add(event)
        db.commit()
        return False
    change_application_status(
        db,
        application,
        applied.from_status or "saved",
        source="mail_revert",
        note=f"撤销邮件更新：{event.subject or ''}".strip(),
        evidence={"mail_event_id": event.id, "reverted_event_id": applied.id},
    )
    event.reverted = True
    db.add(event)
    db.commit()
    return True


def list_events(db: Session, *, only_applied: bool = False, limit: int = 50) -> list[MailEvent]:
    statement = select(MailEvent).order_by(MailEvent.created_at.desc()).limit(min(max(limit, 1), 200))
    if only_applied:
        statement = statement.where(MailEvent.applied.is_(True))
    return list(db.scalars(statement).all())


def recent_summary(db: Session, limit: int = 10) -> list[dict]:
    rows = list_events(db, limit=limit)
    return [
        {
            "id": row.id,
            "subject": row.subject,
            "category": row.category,
            "application_id": row.application_id,
            "suggested_status": row.suggested_status,
            "applied": row.applied,
            "reverted": row.reverted,
            "confidence": row.confidence,
            "deadline": row.deadline.isoformat() if row.deadline else None,
            "deadline_kind": row.deadline_kind,
            "received_at": row.received_at.isoformat() if row.received_at else None,
        }
        for row in rows
    ]
