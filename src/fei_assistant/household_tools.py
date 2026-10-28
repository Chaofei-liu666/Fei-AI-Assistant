from __future__ import annotations

import json

from langchain_core.tools import tool

from .db import SessionLocal
from .household import (add_item, consume_item, find_items, item_view, list_by_location,
                        low_stock, merge_quantity, move_item, remove_item, same_place)


def _compact(value) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


@tool
def add_household_item(name: str, location: str, quantity: float = 1.0,
                       unit: str = "", source_text: str = "") -> str:
    """Record that an item was put at a location, e.g. 洗衣液 at 卧室/衣柜/第二层."""
    with SessionLocal() as db:
        try:
            existing = same_place(db, name, location)
            if existing is not None:
                item = merge_quantity(db, existing, quantity, source_text=source_text or None)
                return _compact({"merged": True, **item_view(item)})
            item = add_item(db, name=name, location=location, quantity=quantity,
                            unit=unit or None, source_text=source_text or None)
        except ValueError as exc:
            return _compact({"error": str(exc)})
        return _compact(item_view(item))


@tool
def move_household_item(item_id: str, location: str, source_text: str = "") -> str:
    """Move an existing item to another location."""
    with SessionLocal() as db:
        from .household import get_item
        item = get_item(db, item_id)
        if not item:
            return _compact({"error": "item_not_found"})
        try:
            moved = move_item(db, item, location, source_text=source_text or None)
        except ValueError as exc:
            return _compact({"error": str(exc)})
        return _compact(item_view(moved))


@tool
def consume_household_item(item_id: str, quantity: float = 1.0, source_text: str = "") -> str:
    """Record that some of an item was used up."""
    with SessionLocal() as db:
        from .household import get_item
        item = get_item(db, item_id)
        if not item:
            return _compact({"error": "item_not_found"})
        try:
            updated = consume_item(db, item, quantity, source_text=source_text or None)
        except ValueError as exc:
            return _compact({"error": str(exc)})
        return _compact(item_view(updated))


@tool
def query_household_items(query: str = "", location: str = "") -> str:
    """Find items by name or by location, e.g. 洗衣液 or 衣柜."""
    with SessionLocal() as db:
        rows = find_items(db, query=query or None, location=location or None)
        return _compact([item_view(row) for row in rows])


@tool
def list_household_location(location: str) -> str:
    """List everything stored at a location such as 衣柜第二层."""
    with SessionLocal() as db:
        rows = list_by_location(db, location)
        return _compact({"location": location, "items": [item_view(row) for row in rows]})


@tool
def low_stock_household_items(threshold: float = 1.0) -> str:
    """List items that are at or below the threshold."""
    with SessionLocal() as db:
        rows = low_stock(db, threshold)
        return _compact([item_view(row) for row in rows])


HOUSEHOLD_TOOLS = [
    add_household_item,
    move_household_item,
    consume_household_item,
    query_household_items,
    list_household_location,
    low_stock_household_items,
]
