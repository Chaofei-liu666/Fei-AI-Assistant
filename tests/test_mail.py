from email.message import EmailMessage

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from fei_assistant.db import Base
from fei_assistant.mail import Imap163Client
from fei_assistant.mail import sync_mailbox
from fei_assistant.models import Application, JobPosting, MailMessage, MailSuggestion
from fei_assistant.schemas import MailAnalysisOutput


class FakeImap:
    def __init__(self): self.readonly = None; self.fetch_query = None
    def login(self, *_): return "OK", []
    def select(self, mailbox, readonly=False): self.readonly = readonly; return "OK", []
    def uid(self, command, *args):
        if command == "search": return "OK", [b"11"]
        self.fetch_query = args[-1]
        message = EmailMessage(); message["Subject"] = "Interview"; message.set_content("hello")
        return "OK", [(b"11 BODY[]", message.as_bytes())]
    def close(self): pass
    def logout(self): pass


def test_imap_sync_uses_examine_and_body_peek(monkeypatch) -> None:
    fake = FakeImap()
    monkeypatch.setattr("fei_assistant.mail.imaplib.IMAP4_SSL", lambda *_: fake)
    rows = Imap163Client("me@163.com", "code").fetch_since(10)
    assert len(rows) == 1
    assert fake.readonly is True
    assert fake.fetch_query == "(BODY.PEEK[])"


class FakeStructuredModel:
    def with_structured_output(self, _): return self
    async def ainvoke(self, _):
        return MailAnalysisOutput(
            relevant=True, mail_type="interview_invite", application_id=self.application_id,
            suggested_status="interview", confidence=0.9, rationale="invite", summary="Interview invite",
        )


class RepeatingClient:
    def fetch_since(self, _):
        message = EmailMessage(); message["From"] = "hr@example.com"; message["Subject"] = "Interview"; message.set_content("hello")
        return [(12, message)]


@pytest.mark.asyncio
async def test_repeated_uid_does_not_create_duplicate_mail_or_suggestion() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        job = JobPosting(company="Example", title="Engineer", description="Build")
        db.add(job); db.flush()
        application = Application(job_id=job.id, status="applied")
        db.add(application); db.commit()
        model = FakeStructuredModel(); model.application_id = application.id
        await sync_mailbox(db, model, RepeatingClient(), "me@163.com"); db.commit()
        await sync_mailbox(db, model, RepeatingClient(), "me@163.com"); db.commit()
        assert len(db.scalars(select(MailMessage)).all()) == 1
        assert len(db.scalars(select(MailSuggestion)).all()) == 1
