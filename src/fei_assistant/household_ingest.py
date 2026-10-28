from __future__ import annotations

from sqlalchemy.orm import Session

from .household import (add_alias, add_item, ambiguous_location, consume_item, find_items,
                        item_view, merge_quantity, move_item, resolve_item, same_place,
                        set_quantity, split_location)
from .household_schemas import HouseholdAction

AUTO_THRESHOLD = 0.6


def _key(value: str | None) -> str:
    return (value or "").strip().lower().replace(" ", "")


def _place(value: str | None) -> str:
    return " / ".join(split_location(value))


def _pending(action: HouseholdAction, reason: str, question: str, candidates: list | None = None) -> dict:
    return {
        "status": "pending",
        "reason": reason,
        "question": question,
        "candidates": candidates or [],
        "draft": {
            "action": action.action,
            "name": action.name,
            "quantity": action.quantity,
            "quantity_mode": action.quantity_mode,
            "unit": action.unit,
            "location": action.location,
        },
    }


def _applied(item, action: HouseholdAction, summary: str) -> dict:
    return {"status": "applied", "action": action.action, "summary": summary, "item": item_view(item)}


def _duplicates(db: Session, name: str) -> list:
    needle = _key(name)
    return [row for row in find_items(db, limit=200) if _key(row.name) == needle]


def apply_action(db: Session, action: HouseholdAction, text: str) -> dict:
    """Apply one parsed action, or explain why it needs the user's eye."""
    if action.action == "query":
        rows = find_items(db, query=action.name or "", location=action.location or "")
        return {
            "status": "answered",
            "question": None,
            "answer": [item_view(row) for row in rows],
            "summary": f"找到 {len(rows)} 件" if rows else "没找到记录",
        }

    if not action.name:
        return _pending(action, "missing_name", "要记的是什么物品？")

    if action.action == "put":
        if not action.location:
            return _pending(action, "missing_location", f"{action.name} 放在哪里？")
        rooms = ambiguous_location(db, action.location)
        if rooms:
            return _pending(action, "ambiguous_location",
                            f"{action.location} 在哪个房间？", rooms)
        if action.confidence < AUTO_THRESHOLD:
            return _pending(action, "low_confidence", "确认一下：记成对吗？")

        item, how = resolve_item(db, action.name)
        if item is not None and item.location_text == _place(action.location):
            merged = merge_quantity(db, item, action.quantity, source_text=text)
            add_alias(db, merged, action.name)
            note = "（按别名合并）" if how == "alias" else "（合并）"
            return _applied(merged, action,
                            f"{action.name} +{action.quantity:g}{action.unit or ''} → {merged.location_text}{note}")
        if item is not None and how == "fuzzy":
            return _pending(action, "similar_item",
                            f"已有一件「{item.name}」在 {item.location_text}，是同一件吗？",
                            [{"id": item.id, "label": f"{item.name} · {item.location_text}"}])
        created = add_item(db, name=action.name, location=action.location, quantity=action.quantity,
                           unit=action.unit, source_text=text)
        return _applied(created, action,
                        f"{action.name} ×{action.quantity:g}{action.unit or ''} → {created.location_text}")

    duplicates = _duplicates(db, action.name)
    if len(duplicates) > 1:
        return _pending(action, "ambiguous_item", f"「{action.name}」有 {len(duplicates)} 件，是哪一件？",
                        [{"id": row.id, "label": f"{row.name} · {row.location_text}"} for row in duplicates[:5]])
    item, _how = resolve_item(db, action.name)
    if item is None:
        return _pending(action, "not_found", f"没有找到「{action.name}」，要先记一条吗？")

    if action.confidence < AUTO_THRESHOLD:
        return _pending(action, "low_confidence", "确认一下：记成对吗？")

    if action.action == "move":
        if not action.location:
            return _pending(action, "missing_location", f"{action.name} 搬到哪？")
        rooms = ambiguous_location(db, action.location)
        if rooms:
            return _pending(action, "ambiguous_location",
                            f"{action.location} 在哪个房间？", rooms)
        before = item.location_text
        moved = move_item(db, item, action.location, source_text=text)
        return _applied(moved, action, f"{item.name}：{before} → {moved.location_text}")

    if action.action == "consume":
        updated = consume_item(db, item, action.quantity, source_text=text)
        state = "用完" if updated.status == "used_up" else f"剩 {updated.quantity:g}{updated.unit or ''}"
        return _applied(updated, action, f"{item.name} 用掉 {action.quantity:g}{action.unit or ''}，{state}")

    if action.action == "adjust":
        if action.quantity_mode != "target":
            updated = merge_quantity(db, item, action.quantity, source_text=text)
        else:
            updated = set_quantity(db, item, action.quantity, source_text=text)
        return _applied(updated, action,
                        f"{item.name} 改为 {updated.quantity:g}{updated.unit or ''}（{updated.location_text}）")

    return _pending(action, "unsupported_action", "这句我还不会处理，换成「放到」「搬到」「用掉」「还剩」试试？")


def apply_batch(db: Session, actions: list[HouseholdAction], text: str) -> list[dict]:
    return [apply_action(db, action, text) for action in actions]
