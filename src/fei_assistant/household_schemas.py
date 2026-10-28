from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class HouseholdItemCreate(BaseModel):
    name: str
    location: str
    quantity: float = 1.0
    unit: str | None = None
    category: str | None = None
    aliases: list[str] = Field(default_factory=list)
    note: str | None = None
    source_text: str | None = None


class HouseholdItemMove(BaseModel):
    location: str
    source_text: str | None = None


class HouseholdConsume(BaseModel):
    quantity: float = 1.0
    source_text: str | None = None


class HouseholdCapture(BaseModel):
    text: str


class HouseholdBatchItem(BaseModel):
    name: str
    location: str
    quantity: float = 1.0
    unit: str | None = None


class HouseholdBatch(BaseModel):
    items: list[HouseholdBatchItem] = Field(default_factory=list)
    text: str | None = None


class HouseholdAction(BaseModel):
    action: Literal["put", "move", "consume", "adjust", "query", "unknown"] = "put"
    name: str | None = None
    quantity: float = 1.0
    quantity_mode: Literal["delta", "target"] = "delta"
    unit: str | None = None
    location: str | None = None
    confidence: float = 0.5
    clarify: str | None = None


class HouseholdDraft(BaseModel):
    """What the model is allowed to produce from one sentence. It never writes by itself."""

    actions: list[HouseholdAction] = Field(default_factory=list)
