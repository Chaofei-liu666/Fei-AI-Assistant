from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .models import TimestampMixin, new_id, utcnow


class HouseholdItem(Base, TimestampMixin):
    """A physical thing the user owns, with where it lives and how many are left."""

    __tablename__ = "household_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), index=True)
    aliases: Mapped[list[str]] = mapped_column(JSON, default=list)
    category: Mapped[str | None] = mapped_column(String(60))
    quantity: Mapped[float] = mapped_column(Float, default=1.0)
    unit: Mapped[str | None] = mapped_column(String(20))
    location_path: Mapped[list[str]] = mapped_column(JSON, default=list)
    location_text: Mapped[str] = mapped_column(String(200), default="")
    note: Mapped[str | None] = mapped_column(Text)
    photo_document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id"))
    status: Mapped[str] = mapped_column(String(20), default="in_stock", index=True)
    source_text: Mapped[str | None] = mapped_column(Text)
    last_confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ItemEvent(Base):
    """Append-only history for an item. Never updated, never deleted."""

    __tablename__ = "item_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    item_id: Mapped[str] = mapped_column(ForeignKey("household_items.id"), index=True)
    action: Mapped[str] = mapped_column(String(20))
    from_path: Mapped[list[str] | None] = mapped_column(JSON)
    to_path: Mapped[list[str] | None] = mapped_column(JSON)
    qty_delta: Mapped[float | None] = mapped_column(Float)
    source_text: Mapped[str | None] = mapped_column(Text)
    actor: Mapped[str] = mapped_column(String(40), default="user")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
