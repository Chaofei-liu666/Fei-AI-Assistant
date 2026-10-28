from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from fei_assistant import household_models  # noqa: F401
from fei_assistant import mail_models  # noqa: F401
from fei_assistant import run_models  # noqa: F401
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


@pytest.fixture
def client():
    app.dependency_overrides[get_db] = _override
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)


def test_job_skills_are_seeded(client: TestClient) -> None:
    rows = client.get("/api/agents/job_search/skills").json()
    assert len(rows) >= 5
    ids = {row["skill_id"] for row in rows}
    assert "job_intelligence_agent" in ids
    assert all(row["description"] for row in rows)
    assert any(row["tools"] for row in rows)


def test_skill_update_roundtrip(client: TestClient) -> None:
    updated = client.put("/api/agents/job_search/skills/interview_review_agent", json={
        "description": "只在用户提供确认过的转写时使用。",
        "prompt": "你是严格的面试复盘员。",
        "enabled": False,
    }).json()
    assert updated["description"].startswith("只在用户提供")
    assert updated["prompt"] == "你是严格的面试复盘员。"
    assert updated["enabled"] is False

    rows = client.get("/api/agents/job_search/skills").json()
    row = next(item for item in rows if item["skill_id"] == "interview_review_agent")
    assert row["enabled"] is False


def test_unknown_skill_returns_404(client: TestClient) -> None:
    assert client.put("/api/agents/job_search/skills/nope", json={"prompt": "x"}).status_code == 404
