import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from fei_assistant.db import Base
from fei_assistant.models import Application, ApplicationEvent, Interview, JobPosting, MailMessage, MailSuggestion
from fei_assistant.services import confirm_mail_suggestion, review_interview


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_mail_suggestion_changes_status_only_after_confirmation(db: Session) -> None:
    job = JobPosting(company="Example", title="Engineer", description="Build things")
    db.add(job); db.flush()
    application = Application(job_id=job.id, status="applied")
    db.add(application); db.flush()
    message = MailMessage(mailbox="me@163.com", uid=1, sender="hr@example.com", subject="Interview", body_summary="invite", mail_type="interview_invite")
    db.add(message); db.flush()
    suggestion = MailSuggestion(mail_id=message.id, application_id=application.id, suggested_status="interview", confidence=0.9, rationale="invite")
    db.add(suggestion); db.commit()

    assert application.status == "applied"
    assert db.scalars(select(ApplicationEvent)).all() == []

    confirm_mail_suggestion(db, suggestion)
    db.commit()
    assert application.status == "interview"
    assert len(db.scalars(select(ApplicationEvent)).all()) == 1
    with pytest.raises(ValueError, match="already"):
        confirm_mail_suggestion(db, suggestion)


@pytest.mark.asyncio
async def test_review_requires_confirmed_transcript(db: Session) -> None:
    interview = Interview(company="Example", transcript="draft", transcript_confirmed=False)
    db.add(interview); db.commit()
    with pytest.raises(ValueError, match="confirmed"):
        await review_interview(db, object(), interview)
