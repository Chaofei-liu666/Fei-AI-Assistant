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


def test_orchestrator_prompt_defaults_and_saves(client: TestClient) -> None:
    initial = client.get("/api/agents/orchestrator/prompt").json()
    assert initial["customized"] is False
    assert initial["prompt"] == initial["default_prompt"]

    saved = client.put("/api/agents/orchestrator/prompt", json={"prompt": "你是 Fei 的主控。"}).json()
    assert saved["customized"] is True
    assert saved["prompt"] == "你是 Fei 的主控。"

    reset = client.delete("/api/agents/orchestrator/prompt").json()
    assert reset["customized"] is False


def test_agent_prompt_roundtrip(client: TestClient) -> None:
    default = client.get("/api/agents/household/prompt").json()
    assert default["customized"] is False

    client.put("/api/agents/household/prompt", json={"prompt": "只记录厨房用品。"})
    updated = client.get("/api/agents/household/prompt").json()
    assert updated["prompt"] == "只记录厨房用品。"
    assert updated["default_prompt"] == default["default_prompt"]


def test_unknown_agent_returns_404(client: TestClient) -> None:
    assert client.get("/api/agents/nope/prompt").status_code == 404
