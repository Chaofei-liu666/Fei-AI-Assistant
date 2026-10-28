from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from fei_assistant import household_models  # noqa: F401
from fei_assistant import mail_models  # noqa: F401
from fei_assistant.api.app import app
from fei_assistant.db import Base, get_db

engine = create_engine(
    "sqlite+pysqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Base.metadata.create_all(engine)
TestingSession = sessionmaker(bind=engine, expire_on_commit=False)


def _override():
    with TestingSession() as session:
        yield session


app.dependency_overrides[get_db] = _override
client = TestClient(app)


def test_create_list_and_move_item() -> None:
    created = client.post("/api/household/items", json={
        "name": "洗衣液", "location": "卧室/衣柜/第二层", "quantity": 1, "unit": "瓶",
    })
    assert created.status_code == 201
    item = created.json()
    assert item["location_path"] == ["卧室", "衣柜", "第二层"]

    listed = client.get("/api/household/items", params={"q": "洗衣"})
    assert [row["id"] for row in listed.json()] == [item["id"]]

    moved = client.patch(f"/api/household/items/{item['id']}/move", json={"location": "阳台/柜子"})
    assert moved.status_code == 200
    assert moved.json()["location_text"] == "阳台 / 柜子"

    history = client.get(f"/api/household/items/{item['id']}/history")
    assert [row["action"] for row in history.json()] == ["put", "move"]


def test_locations_and_low_stock() -> None:
    client.post("/api/household/items", json={"name": "抽纸", "location": "客厅/电视柜", "quantity": 1})
    locations = client.get("/api/household/locations").json()
    assert any(row["path"] == "客厅" for row in locations)
    low = client.get("/api/household/low-stock").json()
    assert any(row["name"] == "抽纸" for row in low)


def test_agents_endpoint_lists_household() -> None:
    payload = client.get("/api/agents").json()
    assert {"job_search", "household"} <= {row["id"] for row in payload}


def test_batch_endpoint_writes_reviewed_list() -> None:
    response = client.post("/api/household/batch", json={"items": [
        {"name": "垃圾袋", "location": "厨房/水槽下", "quantity": 2, "unit": "卷"},
        {"name": "备用电池", "location": "储物间/纸箱", "quantity": 4},
    ]})
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 2
    assert all(row["status"] == "applied" for row in payload["applied"])

    listed = client.get("/api/household/items", params={"location": "储物间"}).json()
    assert [row["name"] for row in listed] == ["备用电池"]
