from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from fei_assistant import household_models  # noqa: F401
from fei_assistant import mail_models  # noqa: F401
from fei_assistant import run_models  # noqa: F401
from fei_assistant.api.app import app
from fei_assistant.db import Base, get_db
from fei_assistant.models import BackgroundTask, CandidateProfile

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


def _seed() -> None:
    with Session(engine) as db:
        db.add(CandidateProfile(document_id="doc-1", document_version=1, fingerprint="f" * 64,
                                target_directions=[], title_keywords=[], skills=[],
                                project_evidence=[], supporting_skills=[], excluded_title_keywords=[],
                                learning_targets=[], confirmed=False))
        db.add(BackgroundTask(kind="job_discovery", status="failed", progress=0,
                              payload={}, attempts=1, error="network timeout"))
        db.commit()


def test_inbox_aggregates_actions() -> None:
    _seed()
    payload = client.get("/api/inbox").json()
    kinds = {row["kind"] for row in payload["actions"]}
    assert {"profile", "task"} <= kinds
    assert payload["count"] >= 2


def test_inbox_includes_low_stock_notes() -> None:
    created = client.post("/api/household/items", json={
        "name": "洗衣液", "location": "浴室/柜子", "quantity": 0.5, "unit": "瓶",
    })
    assert created.status_code == 201
    payload = client.get("/api/inbox").json()
    titles = [row["title"] for row in payload["notes"]]
    assert any("洗衣液" in title for title in titles)
