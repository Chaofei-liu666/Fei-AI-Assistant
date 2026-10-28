from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..household import low_stock
from ..mail_models import MailEvent
from ..models import BackgroundTask, CandidateProfile

router = APIRouter(prefix="/api/inbox", tags=["inbox"])


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


@router.get("")
def inbox(db: Session = Depends(get_db)) -> dict:
    """One list of things that need the user, across every module."""
    items: list[dict] = []

    profile = db.scalar(
        select(CandidateProfile).where(CandidateProfile.confirmed.is_(False))
        .order_by(CandidateProfile.created_at.desc()).limit(1)
    )
    if profile:
        items.append({
            "kind": "profile",
            "severity": "action",
            "title": "候选人画像还没确认",
            "detail": "确认后岗位分析才会生效",
            "target": "job/profile",
            "created_at": _iso(profile.created_at),
        })

    failed = db.scalars(
        select(BackgroundTask).where(BackgroundTask.status == "failed")
        .order_by(BackgroundTask.created_at.desc()).limit(3)
    ).all()
    for task in failed:
        items.append({
            "kind": "task",
            "severity": "action",
            "title": f"任务失败：{task.kind}",
            "detail": (task.error or "未知错误")[:120],
            "target": "job/automations",
            "created_at": _iso(task.updated_at or task.created_at),
        })

    since = datetime.now(timezone.utc) - timedelta(days=7)
    applied = db.scalars(
        select(MailEvent)
        .where(MailEvent.applied.is_(True), MailEvent.reverted.is_(False),
               MailEvent.created_at >= since)
        .order_by(MailEvent.created_at.desc()).limit(5)
    ).all()
    for event in applied:
        items.append({
            "kind": "mail",
            "severity": "info",
            "title": f"邮件更新：{event.subject or '（无主题）'}",
            "detail": f"投递状态已更新到 {event.suggested_status}" if event.suggested_status else "已自动处理",
            "target": "job/applications",
            "created_at": _iso(event.created_at),
        })

    for item in low_stock(db):
        items.append({
            "kind": "household",
            "severity": "info",
            "title": f"{item.name} 快用完了",
            "detail": f"还剩 {item.quantity:g}{item.unit or ''} · {item.location_text}",
            "target": "items",
            "created_at": _iso(item.updated_at),
        })

    items.sort(key=lambda row: (row["severity"] != "action", row["created_at"] or ""), reverse=False)
    actions = [row for row in items if row["severity"] == "action"]
    notes = [row for row in items if row["severity"] != "action"]
    return {"count": len(items), "actions": actions, "notes": notes}
