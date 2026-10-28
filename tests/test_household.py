from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from fei_assistant.agents import list_agents
from fei_assistant.db import Base
from fei_assistant.household import (add_item, consume_item, find_items, history,
                                     list_by_location, low_stock, move_item, remove_item,
                                     split_location)
from fei_assistant import household_models  # noqa: F401


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_split_location_keeps_compact_chinese_names() -> None:
    assert split_location("卧室/衣柜/第二层") == ["卧室", "衣柜", "第二层"]
    assert split_location("衣柜第二层") == ["衣柜第二层"]
    assert split_location("") == []


def test_add_and_find_item(db: Session) -> None:
    item = add_item(db, name="洗衣液", location="卧室/衣柜/第二层", quantity=1, unit="瓶")
    assert item.location_path == ["卧室", "衣柜", "第二层"]
    assert item.location_text == "卧室 / 衣柜 / 第二层"

    by_name = find_items(db, query="洗衣")
    assert [row.id for row in by_name] == [item.id]

    by_location = list_by_location(db, "衣柜")
    assert [row.id for row in by_location] == [item.id]


def test_move_logs_history(db: Session) -> None:
    item = add_item(db, name="抽纸", location="客厅/电视柜", quantity=6, unit="包")
    move_item(db, item, "储物间/纸箱")
    events = history(db, item.id)
    assert [event.action for event in events] == ["put", "move"]
    assert events[1].from_path == ["客厅", "电视柜"]
    assert events[1].to_path == ["储物间", "纸箱"]
    assert item.location_text == "储物间 / 纸箱"


def test_consume_and_low_stock(db: Session) -> None:
    item = add_item(db, name="洗衣液", location="衣柜", quantity=2, unit="瓶")
    consume_item(db, item, 1)
    assert item.quantity == 1
    assert item.id in [row.id for row in low_stock(db)]

    consume_item(db, item, 1)
    assert item.quantity == 0
    assert item.status == "used_up"
    assert find_items(db) == []
    assert item.id in [row.id for row in find_items(db, include_gone=True)]


def test_remove_keeps_history(db: Session) -> None:
    item = add_item(db, name="灯泡", location="储物间/纸箱", quantity=4)
    remove_item(db, item)
    assert item.status == "moved_out"
    assert [event.action for event in history(db, item.id)] == ["put", "remove"]


def test_registry_exposes_household_agent() -> None:
    ids = {agent["id"] for agent in list_agents()}
    assert {"job_search", "household"} <= ids
    household = next(agent for agent in list_agents() if agent["id"] == "household")
    assert "add_household_item" in household["tools"]
