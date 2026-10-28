from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from fei_assistant import household_models  # noqa: F401
from fei_assistant import mail_mcp
from fei_assistant import mail_models  # noqa: F401
from fei_assistant.db import Base
from fei_assistant.mail_events import (apply_event, is_forward, list_events, record_event,
                                       revert_event)
from fei_assistant.models import Application, ApplicationEvent, JobPosting


@pytest.fixture
def engine():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db(engine):
    with Session(engine) as session:
        yield session


def _application(db: Session, status: str = "applied") -> Application:
    job = JobPosting(company="Example", title="Backend", description="Python", cohort=2027)
    db.add(job)
    db.flush()
    application = Application(job_id=job.id, status=status)
    db.add(application)
    db.flush()
    return application


def _record(db: Session, application: Application, status: str | None, **kwargs):
    return record_event(
        db,
        mailbox="inbox",
        uid=kwargs.pop("uid", 1),
        message_id=kwargs.pop("message_id", "<m1@example.com>"),
        subject=kwargs.pop("subject", "Interview invitation"),
        sender="hr@example.com",
        received_at=datetime.now(timezone.utc),
        category=kwargs.pop("category", "interview_invite"),
        confidence=0.9,
        rationale="says interview",
        summary="interview",
        application_id=application.id,
        suggested_status=status,
        **kwargs,
    )


def test_record_is_idempotent(db: Session) -> None:
    application = _application(db)
    first = _record(db, application, "interview")
    second = _record(db, application, "interview")
    assert first is not None and second is not None
    assert first.id == second.id
    assert len(list_events(db)) == 1


def test_apply_moves_forward_and_logs(db: Session) -> None:
    application = _application(db, status="applied")
    event = _record(db, application, "interview")
    applied = apply_event(db, event)
    db.commit()
    assert applied is not None
    assert application.status == "interview"
    assert event.applied is True
    history = db.scalars(select(ApplicationEvent).where(ApplicationEvent.application_id == application.id)).all()
    assert [row.to_status for row in history] == ["interview"]


def test_apply_never_downgrades(db: Session) -> None:
    application = _application(db, status="offer")
    event = _record(db, application, "interview")
    assert apply_event(db, event) is None
    assert application.status == "offer"
    assert event.applied is False


def test_stage_order() -> None:
    assert is_forward("applied", "interview")
    assert not is_forward("interview", "applied")
    assert not is_forward("interview", "interview")
    assert is_forward("interview", "rejected")
    assert not is_forward("rejected", "offer")


def test_revert_restores_previous_stage(db: Session) -> None:
    application = _application(db, status="applied")
    event = _record(db, application, "interview")
    apply_event(db, event)
    db.commit()
    assert revert_event(db, event) is True
    assert application.status == "applied"
    assert event.reverted is True


def test_revert_refuses_when_application_moved_on(db: Session) -> None:
    application = _application(db, status="applied")
    event = _record(db, application, "interview")
    apply_event(db, event)
    application.status = "offer"
    db.commit()
    assert revert_event(db, event) is False
    assert application.status == "offer"


def test_deadline_fields_round_trip(db: Session) -> None:
    application = _application(db)
    event = _record(db, application, None, deadline=date(2026, 11, 3), deadline_kind="explicit")
    assert event.deadline == date(2026, 11, 3)
    assert event.deadline_kind == "explicit"


def test_mcp_server_exposes_read_only_tools(engine) -> None:
    application = _application_db(engine)
    response = mail_mcp.handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    names = {tool["name"] for tool in response["result"]["tools"]}
    assert names == {"mail_search", "mail_recent", "application_list"}

    original = mail_mcp.SessionLocal
    mail_mcp.SessionLocal = sessionmaker(bind=engine)
    try:
        result = mail_mcp.handle_request({
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "application_list", "arguments": {}},
        })
    finally:
        mail_mcp.SessionLocal = original
    payload = result["result"]["content"][0]["text"]
    assert application.id not in ("", None)
    assert "Backend" in payload


def _application_db(engine) -> Application:
    with Session(engine) as session:
        application = _application(session)
        session.commit()
        session.refresh(application)
        return application
