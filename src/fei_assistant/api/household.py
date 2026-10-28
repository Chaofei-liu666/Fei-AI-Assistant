from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from langchain.messages import HumanMessage, SystemMessage
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..household import (add_item, consume_item, find_items, get_item, history,
                         item_view, list_by_location, low_stock, move_item, remove_item,
                         undo_last)
from ..household_ingest import apply_action, apply_batch
from ..household_models import HouseholdItem
from ..household_schemas import (HouseholdAction, HouseholdBatch, HouseholdCapture,
                                 HouseholdConsume, HouseholdDraft, HouseholdItemCreate,
                                 HouseholdItemMove)
from ..providers import build_text_model
from ..structured import invoke_structured

router = APIRouter(prefix="/api/household", tags=["household"])

CAPTURE_PROMPT = """你是物品记录抽取器。把用户的话拆成一到多条动作，不要编造。
规则：
1. action：放入 put，移动 move，用掉 consume，修改数量 adjust，询问 query，无法判断 unknown。
2. name 是物品名（洗衣液），unit 是单位（瓶、包、个），quantity 是数量，默认 1。
3. location 用路径表示，用 / 分隔，例如 卧室/衣柜/第二层；用户只说"衣柜第二层"就保留原话，不要自己补房间。
4. 一句话里有多个物品、或是整段清单时，拆成多条 actions；每行一个物品。
5. 用户说「还剩两瓶」「还有三包」时：action=adjust，quantity_mode=target，quantity=剩余数量。
6. 用户说「用掉一瓶」时：action=consume，quantity_mode=delta。
7. 整句明确（有物品名，且数量或位置清楚）时 confidence 给 0.9 以上；只有物品或位置真的含糊时才低于 0.6。
8. 只输出字段，不要解释。"""


@router.get("/items")
def list_items(q: str = "", location: str = "", include_gone: bool = False,
               db: Session = Depends(get_db)) -> list[dict]:
    rows = find_items(db, query=q or None, location=location or None, include_gone=include_gone)
    return [item_view(row) for row in rows]


@router.post("/items", status_code=201)
def create_item(payload: HouseholdItemCreate, db: Session = Depends(get_db)) -> dict:
    try:
        item = add_item(
            db,
            name=payload.name,
            location=payload.location,
            quantity=payload.quantity,
            unit=payload.unit,
            category=payload.category,
            aliases=payload.aliases,
            note=payload.note,
            source_text=payload.source_text,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return item_view(item)


@router.patch("/items/{item_id}/move")
def move(item_id: str, payload: HouseholdItemMove, db: Session = Depends(get_db)) -> dict:
    item = get_item(db, item_id)
    if not item:
        raise HTTPException(404, "item not found")
    try:
        updated = move_item(db, item, payload.location, source_text=payload.source_text)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return item_view(updated)


@router.post("/items/{item_id}/consume")
def consume(item_id: str, payload: HouseholdConsume, db: Session = Depends(get_db)) -> dict:
    item = get_item(db, item_id)
    if not item:
        raise HTTPException(404, "item not found")
    try:
        updated = consume_item(db, item, payload.quantity, source_text=payload.source_text)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return item_view(updated)


@router.post("/items/{item_id}/remove")
def remove(item_id: str, db: Session = Depends(get_db)) -> dict:
    item = get_item(db, item_id)
    if not item:
        raise HTTPException(404, "item not found")
    return item_view(remove_item(db, item))


@router.get("/items/{item_id}/history")
def item_history(item_id: str, db: Session = Depends(get_db)) -> list[dict]:
    if not get_item(db, item_id):
        raise HTTPException(404, "item not found")
    return [
        {
            "id": event.id,
            "action": event.action,
            "from_path": event.from_path,
            "to_path": event.to_path,
            "qty_delta": event.qty_delta,
            "source_text": event.source_text,
            "created_at": event.created_at.isoformat() if event.created_at else None,
        }
        for event in history(db, item_id)
    ]


@router.get("/locations")
def locations(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(HouseholdItem).where(HouseholdItem.status == "in_stock")).all()
    seen: dict[str, int] = {}
    for row in rows:
        for depth in range(1, len(row.location_path or []) + 1):
            prefix = " / ".join((row.location_path or [])[:depth])
            seen[prefix] = seen.get(prefix, 0) + 1
    return [{"path": path, "items": count} for path, count in sorted(seen.items())]


@router.get("/low-stock")
def low_stock_items(threshold: float = 1.0, db: Session = Depends(get_db)) -> list[dict]:
    return [item_view(row) for row in low_stock(db, threshold)]


@router.post("/capture")
async def capture(payload: HouseholdCapture, db: Session = Depends(get_db)) -> dict:
    """Parse one sentence into draft actions. Nothing is written until the user confirms."""
    text = payload.text.strip()
    if not text:
        raise HTTPException(400, "text is required")
    draft = await _parse(db, text)
    first = draft.actions[0] if draft.actions else None
    return {
        "text": text,
        "draft": first.model_dump() if first else None,
        "actions": [action.model_dump() for action in draft.actions],
        "requires_confirmation": True,
    }


@router.post("/ingest")
async def ingest(payload: HouseholdCapture, db: Session = Depends(get_db)) -> dict:
    """Smart capture: parse, resolve against what is already stored, then apply or ask.

    Multi-line input or three or more items comes back as a preview so the user can
    fix a line before anything is written. Everything else applies immediately when
    it is confident, unambiguous and reversible.
    """
    text = payload.text.strip()
    if not text:
        raise HTTPException(400, "text is required")
    draft = await _parse(db, text)
    if not draft.actions:
        return {"status": "pending", "question": "没听清，再说一次？", "pending": None, "applied": []}

    if "\n" in text or len(draft.actions) >= 3:
        return {
            "status": "preview",
            "actions": [action.model_dump() for action in draft.actions],
            "count": len(draft.actions),
        }

    applied: list[dict] = []
    answers: list[dict] = []
    pending: dict | None = None
    for action in draft.actions[:5]:
        outcome = apply_action(db, action, text)
        if outcome["status"] == "applied":
            applied.append(outcome)
        elif outcome["status"] == "answered":
            answers.append(outcome)
        elif pending is None:
            pending = outcome

    status = "pending" if pending else ("applied" if applied else "answered")
    return {
        "status": status,
        "applied": applied,
        "answer": answers,
        "pending": pending,
        "undo": [row["item"]["id"] for row in applied],
    }


@router.post("/batch")
def batch(payload: HouseholdBatch, db: Session = Depends(get_db)) -> dict:
    """Write a reviewed list of items. Each line is still resolved and merged."""
    if not payload.items:
        raise HTTPException(400, "items are required")
    actions = [
        HouseholdAction(
            action="put",
            name=item.name,
            quantity=item.quantity,
            unit=item.unit,
            location=item.location,
            confidence=0.95,
        )
        for item in payload.items[:50]
    ]
    results = apply_batch(db, actions, payload.text or "")
    applied = [row for row in results if row["status"] == "applied"]
    pending = [row for row in results if row["status"] == "pending"]
    return {"applied": applied, "pending": pending, "count": len(applied)}


@router.post("/items/{item_id}/undo")
def undo(item_id: str, db: Session = Depends(get_db)) -> dict:
    item = get_item(db, item_id)
    if not item:
        raise HTTPException(404, "item not found")
    updated = undo_last(db, item)
    if updated is None:
        raise HTTPException(400, "nothing to undo")
    return item_view(updated)


async def _parse(db: Session, text: str) -> HouseholdDraft:
    try:
        model = build_text_model(db)
    except RuntimeError as exc:
        raise HTTPException(400, f"text provider is not configured: {exc}") from exc
    try:
        return await invoke_structured(
            model,
            HouseholdDraft,
            [SystemMessage(content=CAPTURE_PROMPT), HumanMessage(content=text)],
        )
    except Exception as exc:
        raise HTTPException(502, f"capture failed: {exc}") from exc
