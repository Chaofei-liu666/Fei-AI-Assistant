from __future__ import annotations

import asyncio
import email
import imaplib
from datetime import datetime, timezone
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parsedate_to_datetime

from langchain_core.language_models.chat_models import BaseChatModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .domain import MailType
from .mail_events import apply_event, record_event
from .models import (
    Application,
    EmailSyncState,
    JobPosting,
    MailMessage,
    MailSuggestion,
)
from .schemas import MailAnalysisOutput
from .structured import invoke_structured


def _header(value: str | None) -> str:
    return str(make_header(decode_header(value or "")))


def _plain_body(message: Message) -> str:
    parts = message.walk() if message.is_multipart() else [message]
    for part in parts:
        if part.get_content_type() != "text/plain" or "attachment" in str(part.get("Content-Disposition", "")):
            continue
        payload = part.get_payload(decode=True) or b""
        charset = part.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace")
    return ""


def _sent_at(message: Message) -> datetime | None:
    try:
        value = parsedate_to_datetime(message.get("Date"))
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


class Imap163Client:
    """Read-only UID client. EXAMINE and BODY.PEEK preserve mailbox read state."""

    def __init__(self, username: str, authorization_code: str, host: str = "imap.163.com", port: int = 993):
        self.username = username
        self.authorization_code = authorization_code
        self.host = host
        self.port = port

    def fetch_since(self, last_uid: int) -> list[tuple[int, Message]]:
        client = imaplib.IMAP4_SSL(self.host, self.port)
        try:
            client.login(self.username, self.authorization_code)
            status, _ = client.select("INBOX", readonly=True)
            if status != "OK":
                raise RuntimeError("cannot EXAMINE INBOX")
            status, data = client.uid("search", None, f"UID {last_uid + 1}:*")
            if status != "OK":
                raise RuntimeError("UID search failed")
            result: list[tuple[int, Message]] = []
            for raw_uid in (data[0] or b"").split():
                uid = int(raw_uid)
                status, chunks = client.uid("fetch", raw_uid, "(BODY.PEEK[])")
                if status != "OK":
                    continue
                raw = next((item[1] for item in chunks if isinstance(item, tuple)), None)
                if raw:
                    result.append((uid, email.message_from_bytes(raw)))
            return result
        finally:
            try:
                client.close()
            except Exception:
                pass
            try:
                client.logout()
            except Exception:
                pass


async def sync_mailbox(
    db: Session,
    model: BaseChatModel,
    client: Imap163Client,
    mailbox: str,
) -> dict[str, int]:
    state = db.get(EmailSyncState, mailbox) or EmailSyncState(mailbox=mailbox, last_uid=0)
    applications = db.scalars(select(Application)).all()
    jobs = {job.id: job for job in db.scalars(select(JobPosting)).all()}
    context = [
        {"application_id": app.id, "company": jobs[app.job_id].company, "title": jobs[app.job_id].title}
        for app in applications
        if app.job_id in jobs
    ]
    valid_application_ids = {item["application_id"] for item in context}
    fetched = await asyncio.to_thread(client.fetch_since, state.last_uid)
    kept = 0
    for uid, message in fetched:
        state.last_uid = max(state.last_uid, uid)
        if db.scalar(select(MailMessage).where(MailMessage.mailbox == mailbox, MailMessage.uid == uid)):
            continue
        sender, subject, body = _header(message.get("From")), _header(message.get("Subject")), _plain_body(message)
        analysis = await invoke_structured(model, MailAnalysisOutput,
            f"""判断邮件是否属于求职流程，只能从候选投递中选择 application_id；不确定时必须返回 null。
候选投递：{context}
发件人：{sender}
主题：{subject}
正文：{body[:12000]}
"""
        )
        if not analysis.relevant or analysis.mail_type == MailType.IRRELEVANT:
            continue
        application_id = analysis.application_id if analysis.application_id in valid_application_ids else None
        stored = MailMessage(
            mailbox=mailbox,
            uid=uid,
            sender=sender,
            subject=subject,
            sent_at=_sent_at(message),
            body_summary=analysis.summary,
            message_id=message.get("Message-ID"),
            mail_type=analysis.mail_type.value,
        )
        db.add(stored)
        db.flush()
        db.add(
            MailSuggestion(
                mail_id=stored.id,
                application_id=application_id,
                suggested_status=analysis.suggested_status.value if analysis.suggested_status else None,
                confidence=analysis.confidence,
                rationale=analysis.rationale,
            )
        )
        mail_event = record_event(
            db,
            mailbox=mailbox,
            uid=uid,
            message_id=message.get("Message-ID"),
            subject=subject,
            sender=sender,
            received_at=stored.sent_at,
            category=analysis.mail_type.value,
            confidence=analysis.confidence,
            rationale=analysis.rationale,
            summary=analysis.summary,
            application_id=application_id,
            suggested_status=analysis.suggested_status.value if analysis.suggested_status else None,
            deadline=analysis.deadline,
            deadline_kind=analysis.deadline_kind,
        )
        if mail_event is not None:
            apply_event(db, mail_event)
        kept += 1
    state.last_synced_at = datetime.now(timezone.utc)
    state.last_error = None
    db.add(state)
    return {"fetched": len(fetched), "kept": kept, "last_uid": state.last_uid}
