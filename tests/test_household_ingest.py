from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from fei_assistant import household_models  # noqa: F401
from fei_assistant.db import Base
from fei_assistant.household import add_alias, add_item, find_items, history, item_view, undo_last
from fei_assistant.household_ingest import apply_action, apply_batch
from fei_assistant.household_schemas import HouseholdAction


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def action(**kwargs) -> HouseholdAction:
    return HouseholdAction(**{"quantity": 1, "confidence": 0.95, **kwargs})


def test_high_confidence_put_applies_immediately(db: Session) -> None:
    outcome = apply_action(db, action(name="洗衣液", location="卧室/衣柜/第二层", unit="瓶"), "洗衣液放衣柜第二层")
    assert outcome["status"] == "applied"
    assert outcome["item"]["location_text"] == "卧室 / 衣柜 / 第二层"
    assert find_items(db)[0].name == "洗衣液"


def test_same_item_same_place_merges_instead_of_duplicating(db: Session) -> None:
    add_item(db, name="抽纸", location="客厅/电视柜", quantity=2, unit="包")
    outcome = apply_action(db, action(name="抽纸", location="客厅/电视柜", quantity=6, unit="包"), "又买了六包抽纸放电视柜")
    assert outcome["status"] == "applied"
    assert "合并" in outcome["summary"]
    rows = find_items(db)
    assert len(rows) == 1
    assert rows[0].quantity == 8


def test_low_confidence_asks_instead_of_writing(db: Session) -> None:
    outcome = apply_action(db, action(name="洗衣液", location="柜子", confidence=0.4), "洗衣液放柜子里")
    assert outcome["status"] == "pending"
    assert outcome["reason"] == "low_confidence"
    assert find_items(db) == []


def test_bare_container_is_ambiguous_across_rooms(db: Session) -> None:
    add_item(db, name="工具箱", location="卧室/柜子")
    add_item(db, name="备用灯泡", location="客厅/柜子")
    outcome = apply_action(db, action(name="洗衣液", location="柜子"), "洗衣液放柜子里")
    assert outcome["status"] == "pending"
    assert outcome["reason"] == "ambiguous_location"
    assert set(outcome["candidates"]) == {"卧室", "客厅"}


def test_missing_location_asks(db: Session) -> None:
    outcome = apply_action(db, action(name="洗衣液", location=None), "洗衣液放起来")
    assert outcome["status"] == "pending"
    assert outcome["reason"] == "missing_location"


def test_consume_resolves_single_match(db: Session) -> None:
    item = add_item(db, name="洗衣液", location="衣柜", quantity=2, unit="瓶")
    outcome = apply_action(db, action(action="consume", name="洗衣液", quantity=1), "用掉一瓶洗衣液")
    assert outcome["status"] == "applied"
    assert "剩 1瓶" in outcome["summary"]
    assert item.quantity == 1


def test_consume_asks_when_several_matches(db: Session) -> None:
    add_item(db, name="洗衣液", location="卧室/柜子", quantity=1)
    add_item(db, name="洗衣液", location="阳台/柜子", quantity=1)
    outcome = apply_action(db, action(action="consume", name="洗衣液"), "用掉一瓶洗衣液")
    assert outcome["status"] == "pending"
    assert outcome["reason"] == "ambiguous_item"
    assert len(outcome["candidates"]) == 2


def test_move_and_query(db: Session) -> None:
    add_item(db, name="洗衣液", location="卧室/衣柜", quantity=1)
    moved = apply_action(db, action(action="move", name="洗衣液", location="阳台/柜子"), "洗衣液搬到阳台柜子")
    assert moved["status"] == "applied"
    assert moved["item"]["location_text"] == "阳台 / 柜子"

    answer = apply_action(db, action(action="query", name="洗衣液"), "洗衣液在哪")
    assert answer["status"] == "answered"
    assert answer["answer"][0]["location_text"] == "阳台 / 柜子"


def test_undo_reverses_put_move_and_consume(db: Session) -> None:
    item = add_item(db, name="洗衣液", location="衣柜", quantity=2, unit="瓶")
    undo_last(db, item)
    assert item.status == "moved_out"
    assert len(find_items(db)) == 0

    item2 = add_item(db, name="抽纸", location="客厅/电视柜", quantity=2)
    undo_last(db, item2)
    item2.status = "in_stock"
    db.add(item2)
    db.commit()


def test_adjust_target_sets_absolute_quantity(db: Session) -> None:
    item = add_item(db, name="洗衣液", location="衣柜", quantity=1, unit="瓶")
    outcome = apply_action(
        db,
        action(action="adjust", name="洗衣液", quantity=2, quantity_mode="target"),
        "洗衣液还剩两瓶",
    )
    assert outcome["status"] == "applied"
    assert item.quantity == 2
    assert "改为 2瓶" in outcome["summary"]


def test_alias_is_learned_and_merged(db: Session) -> None:
    item = add_item(db, name="洗衣液", location="卧室/衣柜", quantity=1, unit="瓶")
    add_alias(db, item, "蓝月亮")
    outcome = apply_action(
        db,
        action(name="蓝月亮", location="卧室/衣柜", quantity=1, unit="瓶"),
        "蓝月亮放衣柜",
    )
    assert outcome["status"] == "applied"
    assert "别名" in outcome["summary"]
    rows = find_items(db)
    assert len(rows) == 1
    assert rows[0].quantity == 2


def test_similar_name_elsewhere_asks_before_creating(db: Session) -> None:
    add_item(db, name="洗衣液", location="衣柜")
    outcome = apply_action(
        db,
        action(name="洗衣液（蓝瓶）", location="阳台"),
        "洗衣液（蓝瓶）放阳台",
    )
    assert outcome["status"] == "pending"
    assert outcome["reason"] == "similar_item"
    assert len(find_items(db)) == 1


def test_apply_batch_writes_every_line(db: Session) -> None:
    results = apply_batch(db, [
        HouseholdAction(action="put", name="抽纸", location="客厅/电视柜", quantity=6, unit="包", confidence=0.95),
        HouseholdAction(action="put", name="洗衣液", location="卧室/衣柜/第二层", quantity=1, unit="瓶", confidence=0.95),
        HouseholdAction(action="put", name="工具箱", location="阳台/柜子", confidence=0.95),
    ], "清单")
    assert [row["status"] for row in results] == ["applied", "applied", "applied"]
    assert len(find_items(db)) == 3
