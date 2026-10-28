from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class ProviderConfig(Base, TimestampMixin):
    __tablename__ = "provider_configs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    base_url: Mapped[str | None] = mapped_column(String(500))
    model: Mapped[str | None] = mapped_column(String(200))
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    secret_ref: Mapped[str | None] = mapped_column(String(200))
    secret_last_four: Mapped[str | None] = mapped_column(String(4))
    configured: Mapped[bool] = mapped_column(Boolean, default=False)


class Document(Base, TimestampMixin):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("sha256", "kind", name="uq_document_sha_kind"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    filename: Mapped[str] = mapped_column(String(300))
    content_type: Mapped[str] = mapped_column(String(100))
    size: Mapped[int]
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    object_key: Mapped[str] = mapped_column(String(500), unique=True)
    extracted_text: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(default=1)


class CandidateProfile(Base, TimestampMixin):
    __tablename__ = "candidate_profiles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), unique=True, index=True)
    document_version: Mapped[int]
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    degree: Mapped[str | None] = mapped_column(String(100))
    job_type: Mapped[str | None] = mapped_column(String(100))
    target_directions: Mapped[list[str]] = mapped_column(JSON, default=list)
    title_keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    excluded_title_keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    project_evidence: Mapped[list[str]] = mapped_column(JSON, default=list)
    supporting_skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    learning_targets: Mapped[list[str]] = mapped_column(JSON, default=list)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)


class Artifact(Base, TimestampMixin):
    __tablename__ = "artifacts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(60), index=True)
    title: Mapped[str] = mapped_column(String(300))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    object_key: Mapped[str | None] = mapped_column(String(500))
    task_id: Mapped[str | None] = mapped_column(String(36), index=True)


class JobPosting(Base, TimestampMixin):
    __tablename__ = "job_postings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company: Mapped[str] = mapped_column(String(200), index=True)
    title: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(String(1000))
    notes: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(String(120), index=True)
    cohort: Mapped[int] = mapped_column(Integer, default=2027, index=True)
    cohort_status: Mapped[str] = mapped_column(String(30), default="confirmed", index=True)
    recruitment_track: Mapped[str] = mapped_column(String(30), default="campus", index=True)
    batch: Mapped[str] = mapped_column(String(30), default="formal", index=True)
    source_kind: Mapped[str] = mapped_column(String(50), default="manual", index=True)
    source_ref: Mapped[str | None] = mapped_column(String(500), index=True)
    jd_status: Mapped[str] = mapped_column(String(30), default="complete", index=True)
    availability_status: Mapped[str] = mapped_column(String(30), default="active", index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    analyses: Mapped[list[JobAnalysis]] = relationship(back_populates="job", cascade="all, delete-orphan")


class JobAnalysis(Base, TimestampMixin):
    __tablename__ = "job_analyses"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(ForeignKey("job_postings.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    document_version: Mapped[int]
    provider_kind: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(200))
    prompt_version: Mapped[str] = mapped_column(String(40))
    match_level: Mapped[str] = mapped_column(String(20))
    evidence_level: Mapped[str] = mapped_column(String(20), default="insufficient", index=True)
    analysis_version: Mapped[str] = mapped_column(String(40), default="career-evidence-v1")
    content_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    profile_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    direct_core_count: Mapped[int] = mapped_column(Integer, default=0)
    missing_core_count: Mapped[int] = mapped_column(Integer, default=0)
    result: Mapped[dict[str, Any]] = mapped_column(JSON)
    job: Mapped[JobPosting] = relationship(back_populates="analyses")


class Application(Base, TimestampMixin):
    __tablename__ = "applications"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(ForeignKey("job_postings.id"), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    company_name: Mapped[str | None] = mapped_column(String(200), index=True)
    job_title: Mapped[str | None] = mapped_column(String(200), index=True)
    record_url: Mapped[str | None] = mapped_column(String(2000))
    source: Mapped[str] = mapped_column(String(40), default="manual")
    events: Mapped[list[ApplicationEvent]] = relationship(back_populates="application", cascade="all, delete-orphan")


class ApplicationEvent(Base):
    __tablename__ = "application_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(30))
    to_status: Mapped[str] = mapped_column(String(30))
    source: Mapped[str] = mapped_column(String(40), default="user")
    note: Mapped[str | None] = mapped_column(Text)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    application: Mapped[Application] = relationship(back_populates="events")


class MailMessage(Base, TimestampMixin):
    __tablename__ = "mail_messages"
    __table_args__ = (UniqueConstraint("mailbox", "uid", name="uq_mailbox_uid"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    mailbox: Mapped[str] = mapped_column(String(320))
    uid: Mapped[int]
    sender: Mapped[str] = mapped_column(String(500))
    subject: Mapped[str] = mapped_column(String(1000))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    body_summary: Mapped[str] = mapped_column(Text)
    message_id: Mapped[str | None] = mapped_column(String(500))
    mail_type: Mapped[str] = mapped_column(String(40), index=True)


class MailSuggestion(Base, TimestampMixin):
    __tablename__ = "mail_suggestions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    mail_id: Mapped[str] = mapped_column(ForeignKey("mail_messages.id", ondelete="CASCADE"), unique=True)
    application_id: Mapped[str | None] = mapped_column(ForeignKey("applications.id"), index=True)
    suggested_status: Mapped[str | None] = mapped_column(String(30))
    confidence: Mapped[float] = mapped_column(Float)
    rationale: Mapped[str] = mapped_column(Text)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EmailSyncState(Base, TimestampMixin):
    __tablename__ = "email_sync_state"
    mailbox: Mapped[str] = mapped_column(String(320), primary_key=True)
    last_uid: Mapped[int] = mapped_column(default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Interview(Base, TimestampMixin):
    __tablename__ = "interviews"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("job_postings.id"), index=True)
    application_id: Mapped[str | None] = mapped_column(ForeignKey("applications.id"), index=True)
    job_title: Mapped[str | None] = mapped_column(String(200))
    company: Mapped[str] = mapped_column(String(200))
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    round: Mapped[str | None] = mapped_column(String(100))
    outcome: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)
    audio_document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id"))
    transcript: Mapped[str | None] = mapped_column(Text)
    transcript_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)


class TranscriptionJob(Base, TimestampMixin):
    __tablename__ = "transcription_jobs"
    __table_args__ = (UniqueConstraint("provider_task_id", name="uq_transcription_provider_task"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    interview_id: Mapped[str] = mapped_column(ForeignKey("interviews.id", ondelete="CASCADE"), index=True)
    provider_task_id: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30), index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    error: Mapped[str | None] = mapped_column(Text)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ReviewReport(Base, TimestampMixin):
    __tablename__ = "review_reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    interview_id: Mapped[str] = mapped_column(ForeignKey("interviews.id", ondelete="CASCADE"), index=True)
    provider_kind: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(200))
    prompt_version: Mapped[str] = mapped_column(String(40))
    result: Mapped[dict[str, Any]] = mapped_column(JSON)


class BackgroundTask(Base, TimestampMixin):
    __tablename__ = "background_tasks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(60), index=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    progress: Mapped[int] = mapped_column(default=0)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    attempts: Mapped[int] = mapped_column(default=0)
    error: Mapped[str | None] = mapped_column(Text)


class CompanySource(Base, TimestampMixin):
    __tablename__ = "company_sources"
    __table_args__ = (UniqueConstraint("company", "entry_url", name="uq_company_source_entry"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company: Mapped[str] = mapped_column(String(200), index=True)
    entry_url: Mapped[str] = mapped_column(String(2000))
    source_kind: Mapped[str] = mapped_column(String(50), default="official")
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    last_error: Mapped[str | None] = mapped_column(Text)
    last_attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    job_count: Mapped[int] = mapped_column(Integer, default=0)
    incomplete_jd_count: Mapped[int] = mapped_column(Integer, default=0)


class ScheduleItem(Base, TimestampMixin):
    __tablename__ = "schedule_items"
    __table_args__ = (UniqueConstraint("source", "source_ref", name="uq_schedule_source_ref"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    application_id: Mapped[str | None] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    item_type: Mapped[str] = mapped_column(String(40), index=True)
    event_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    source: Mapped[str] = mapped_column(String(40), default="manual")
    source_ref: Mapped[str] = mapped_column(String(200))
    note: Mapped[str | None] = mapped_column(Text)


class Automation(Base, TimestampMixin):
    __tablename__ = "automations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    task_kind: Mapped[str] = mapped_column(String(60), index=True)
    schedule_time: Mapped[str] = mapped_column(String(5))
    timezone: Mapped[str] = mapped_column(String(80), default="Asia/Shanghai")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[str | None] = mapped_column(String(30))
    last_error: Mapped[str | None] = mapped_column(Text)


class BrowserReview(Base, TimestampMixin):
    __tablename__ = "browser_reviews"
    __table_args__ = (UniqueConstraint("operation_id", name="uq_browser_review_operation"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    operation_id: Mapped[str] = mapped_column(String(64), index=True)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    page_url: Mapped[str] = mapped_column(String(2000))
    observed_status: Mapped[str | None] = mapped_column(String(50))
    confidence: Mapped[float] = mapped_column(Float, default=0)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    requires_user_action: Mapped[bool] = mapped_column(Boolean, default=True)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)


class AgentPrompt(Base, TimestampMixin):
    """User-authored system prompt override for one agent (or the orchestrator)."""

    __tablename__ = "agent_prompts"
    agent_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    prompt: Mapped[str] = mapped_column(Text, default="")
