from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .household_models import HouseholdItem, ItemEvent

SEPARATORS = ("›", ">", "→", "／", "/", "·", "，")
LOW_STOCK_THRESHOLD = 1.0


def split_location(raw: str | None) -> list[str]:
    """Turn "卧室/衣柜/第二层" into a path. A bare "衣柜第二层" stays one segment."""
    text = (raw or "").strip()
    if not text:
        return []
    for sep in SEPARATORS:
        text = text.replace(sep, "|")
    parts = [part.strip() for part in text.split("|")]
    return [part for part in parts if part] or [text]


def _write_event(db: Session, item: HouseholdItem, action: str, *, from_path=None,
                 to_path=None, qty_delta=None, source_text=None, actor: str = "user") -> None:
    db.add(ItemEvent(
        item_id=item.id,
        action=action,
        from_path=from_path,
        to_path=to_path,
        qty_delta=qty_delta,
        source_text=source_text,
        actor=actor,
    ))


def add_item(db: Session, *, name: str, location: str, quantity: float = 1.0,
             unit: str | None = None, category: str | None = None,
             aliases: list[str] | None = None, note: str | None = None,
             source_text: str | None = None, actor: str = "user") -> HouseholdItem:
    clean_name = (name or "").strip()
    if not clean_name:
        raise ValueError("item name is required")
    path = split_location(location)
    if not path:
        raise ValueError("item location is required")
    item = HouseholdItem(
        name=clean_name,
        aliases=aliases or [],
        category=category,
        quantity=float(quantity),
        unit=unit,
        location_path=path,
        location_text=" / ".join(path),
        note=note,
        source_text=source_text,
        status="in_stock",
    )
    db.add(item)
    db.flush()
    _write_event(db, item, "put", to_path=path, qty_delta=float(quantity),
                 source_text=source_text, actor=actor)
    db.commit()
    db.refresh(item)
    return item


def get_item(db: Session, item_id: str) -> HouseholdItem | None:
    return db.get(HouseholdItem, item_id)


def find_items(db: Session, query: str | None = None, location: str | None = None,
               include_gone: bool = False, limit: int = 100) -> list[HouseholdItem]:
    statement = select(HouseholdItem).order_by(HouseholdItem.updated_at.desc())
    if not include_gone:
        statement = statement.where(HouseholdItem.status == "in_stock")
    rows = list(db.scalars(statement.limit(500)).all())
    needle = (query or "").strip().lower()
    place = (location or "").strip().lower()
    if needle:
        rows = [
            row for row in rows
            if needle in row.name.lower() or any(needle in alias.lower() for alias in (row.aliases or []))
        ]
    if place:
        rows = [
            row for row in rows
            if place in (row.location_text or "").lower()
            or any(place in segment.lower() for segment in (row.location_path or []))
        ]
    return rows[: max(1, min(limit, 200))]


def move_item(db: Session, item: HouseholdItem, location: str, *,
              source_text: str | None = None, actor: str = "user") -> HouseholdItem:
    path = split_location(location)
    if not path:
        raise ValueError("target location is required")
    before = list(item.location_path or [])
    item.location_path = path
    item.location_text = " / ".join(path)
    db.add(item)
    _write_event(db, item, "move", from_path=before, to_path=path,
                 source_text=source_text, actor=actor)
    db.commit()
    db.refresh(item)
    return item


def consume_item(db: Session, item: HouseholdItem, quantity: float = 1.0, *,
                 source_text: str | None = None, actor: str = "user") -> HouseholdItem:
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    item.quantity = max(0.0, float(item.quantity) - float(quantity))
    if item.quantity <= 0:
        item.status = "used_up"
    db.add(item)
    _write_event(db, item, "consume", qty_delta=-float(quantity),
                 source_text=source_text, actor=actor)
    db.commit()
    db.refresh(item)
    return item


def remove_item(db: Session, item: HouseholdItem, *, source_text: str | None = None,
                actor: str = "user") -> HouseholdItem:
    item.status = "moved_out"
    db.add(item)
    _write_event(db, item, "remove", from_path=list(item.location_path or []),
                 source_text=source_text, actor=actor)
    db.commit()
    db.refresh(item)
    return item


def merge_quantity(db: Session, item: HouseholdItem, delta: float, *,
                   source_text: str | None = None, actor: str = "user") -> HouseholdItem:
    """Same item, same place: add to the count instead of creating a duplicate."""
    item.quantity = max(0.0, float(item.quantity) + float(delta))
    if item.quantity > 0 and item.status == "used_up":
        item.status = "in_stock"
    db.add(item)
    _write_event(db, item, "adjust", qty_delta=float(delta), source_text=source_text, actor=actor)
    db.commit()
    db.refresh(item)
    return item


def set_quantity(db: Session, item: HouseholdItem, quantity: float, *,
                 source_text: str | None = None, actor: str = "user") -> HouseholdItem:
    """Correct the count to an absolute value ("还剩两瓶"), rather than adding a delta."""
    if quantity < 0:
        raise ValueError("quantity cannot be negative")
    delta = float(quantity) - float(item.quantity)
    item.quantity = float(quantity)
    item.status = "used_up" if quantity <= 0 else "in_stock"
    db.add(item)
    _write_event(db, item, "adjust", qty_delta=delta, source_text=source_text, actor=actor)
    db.commit()
    db.refresh(item)
    return item


def add_alias(db: Session, item: HouseholdItem, alias: str | None, *, actor: str = "user") -> HouseholdItem:
    """Learn another name for the same thing, so next time it merges instead of duplicating."""
    clean = (alias or "").strip()
    if not clean or _norm(clean) == _norm(item.name):
        return item
    if any(_norm(existing) == _norm(clean) for existing in (item.aliases or [])):
        return item
    item.aliases = [*(item.aliases or []), clean]
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def _norm(value: str | None) -> str:
    return (value or "").strip().lower().replace(" ", "").replace("　", "")


def resolve_item(db: Session, name: str | None) -> tuple[HouseholdItem | None, str | None]:
    """Match an incoming name against stored names and aliases.

    Returns (item, how) where how is exact / alias / fuzzy / None. Fuzzy only means
    "one name contains the other", which is deliberately conservative.
    """
    needle = _norm(name)
    if not needle:
        return None, None
    rows = find_items(db, limit=200)
    for row in rows:
        if _norm(row.name) == needle:
            return row, "exact"
    for row in rows:
        if any(_norm(alias) == needle for alias in (row.aliases or [])):
            return row, "alias"
    for row in rows:
        stored = _norm(row.name)
        if len(stored) >= 2 and len(needle) >= 2 and (stored in needle or needle in stored):
            return row, "fuzzy"
    return None, None


def undo_last(db: Session, item: HouseholdItem, *, actor: str = "user") -> HouseholdItem | None:
    """Reverse the most recent change by appending a compensating event."""
    events = history(db, item.id)
    if not events:
        return None
    last = events[-1]
    if last.action == "undo":
        return None
    if last.action == "put":
        item.status = "moved_out"
    elif last.action == "remove":
        item.status = "in_stock"
    elif last.action == "move":
        path = list(last.from_path or [])
        if path:
            item.location_path = path
            item.location_text = " / ".join(path)
    elif last.action in ("consume", "adjust"):
        item.quantity = max(0.0, float(item.quantity) - float(last.qty_delta or 0))
        if item.quantity > 0 and item.status == "used_up":
            item.status = "in_stock"
    db.add(item)
    _write_event(db, item, "undo", source_text=f"撤销 {last.action}", actor=actor)
    db.commit()
    db.refresh(item)
    return item


def same_place(db: Session, name: str, location: str) -> HouseholdItem | None:
    target = " / ".join(split_location(location))
    for row in find_items(db, query=name):
        if row.name == name and row.location_text == target:
            return row
    return None


def ambiguous_location(db: Session, location: str) -> list[str]:
    """A bare "柜子" is ambiguous when several rooms already have one."""
    path = split_location(location)
    if len(path) != 1:
        return []
    needle = path[0]
    rooms = {
        (row.location_path or ["?"])[0]
        for row in find_items(db, limit=200)
        if any(needle in segment for segment in (row.location_path or []))
    }
    return sorted(rooms) if len(rooms) > 1 else []


def list_by_location(db: Session, location: str) -> list[HouseholdItem]:
    return find_items(db, location=location)


def low_stock(db: Session, threshold: float = LOW_STOCK_THRESHOLD) -> list[HouseholdItem]:
    rows = find_items(db, limit=200)
    return [row for row in rows if float(row.quantity) <= float(threshold)]


def history(db: Session, item_id: str) -> list[ItemEvent]:
    return list(db.scalars(
        select(ItemEvent).where(ItemEvent.item_id == item_id).order_by(ItemEvent.created_at)
    ).all())


def item_view(item: HouseholdItem) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "aliases": item.aliases or [],
        "category": item.category,
        "quantity": item.quantity,
        "unit": item.unit,
        "location_path": item.location_path or [],
        "location_text": item.location_text,
        "note": item.note,
        "status": item.status,
        "source_text": item.source_text,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }
