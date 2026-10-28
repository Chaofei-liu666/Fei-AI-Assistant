from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .models import new_id, utcnow


class MailEvent(Base):
    """One relevant mail, turned into a state-change fact.

    Append-only. Applying it writes an ApplicationEvent; reverting writes a
    compensating event. The mail itself is never edited.
    """

    __tablename__ = "mail_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    dedupe_key: Mapped[str] = mapped_column(String(300), unique=True, index=True)
    message_id: Mapped[str | None] = mapped_column(String(300))
    mailbox: Mapped[str] = mapped_column(String(200), index=True)
    uid: Mapped[int | None] = mapped_column(Integer)
    subject: Mapped[str | None] = mapped_column(String(500))
    sender: Mapped[str | None] = mapped_column(String(300))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    category: Mapped[str] = mapped_column(String(40), index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    rationale: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)

    application_id: Mapped[str | None] = mapped_column(String(36), index=True)
    suggested_status: Mapped[str | None] = mapped_column(String(30))
    deadline: Mapped[date | None] = mapped_column(Date)
    deadline_kind: Mapped[str] = mapped_column(String(20), default="unknown")

    applied: Mapped[bool] = mapped_column(Boolean, default=False)
    applied_event_id: Mapped[str | None] = mapped_column(String(36))
    reverted: Mapped[bool] = mapped_column(Boolean, default=False)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
