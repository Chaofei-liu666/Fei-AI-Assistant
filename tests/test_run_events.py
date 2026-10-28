from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from fei_assistant import run_models  # noqa: F401
from fei_assistant.db import Base
from fei_assistant.run_events import list_steps, recent_runs, record, step_view


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_steps_get_increasing_seq(db: Session) -> None:
    first = record(db, "run-1", "plan", actor="orchestrator", title="拆解任务")
    second = record(db, "run-1", "delegate", actor="orchestrator", title="委托给 岗位情报")
    db.commit()
    assert [first.seq, second.seq] == [1, 2]
    assert [row.seq for row in list_steps(db, "run-1")] == [1, 2]


def test_runs_are_isolated(db: Session) -> None:
    record(db, "run-a", "note", title="a")
    record(db, "run-b", "note", title="b")
    db.commit()
    assert [row.title for row in list_steps(db, "run-a")] == ["a"]
    assert [row.title for row in list_steps(db, "run-b")] == ["b"]


def test_record_without_run_id_is_a_noop(db: Session) -> None:
    assert record(db, None, "note", title="ignored") is None
    assert list_steps(db, "anything") == []


def test_recent_runs_groups_by_run(db: Session) -> None:
    record(db, "run-x", "plan", title="x1")
    record(db, "run-x", "result", title="x2")
    record(db, "run-y", "plan", title="y1")
    db.commit()
    summary = {row["run_id"]: row["steps"] for row in recent_runs(db)}
    assert summary["run-x"] == 2
    assert summary["run-y"] == 1


def test_step_view_exposes_kind_and_status(db: Session) -> None:
    step = record(db, "run-v", "error", title="失败", status="failed", error="boom")
    db.commit()
    payload = step_view(step)
    assert payload["kind"] == "error"
    assert payload["status"] == "failed"
    assert payload["error"] == "boom"
