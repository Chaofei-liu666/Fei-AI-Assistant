from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl

from .domain import ApplicationStatus, MailType, MatchLevel


class RouteDecision(BaseModel):
    route: Literal["general", "job_search", "clarify"]
    reason: str = Field(description="一句话说明路由依据")


class EvidenceRow(BaseModel):
    requirement: str
    evidence: str | None = None
    assessment: Literal["matched", "partial", "missing"]
    source_quote: str | None = None


class JobAnalysisOutput(BaseModel):
    match_level: MatchLevel
    summary: str
    evidence_table: list[EvidenceRow]
    gaps: list[str]
    risks: list[str]
    preparation_actions: list[str]


class MailAnalysisOutput(BaseModel):
    relevant: bool
    mail_type: MailType
    application_id: str | None = None
    suggested_status: ApplicationStatus | None = None
    confidence: float = Field(ge=0, le=1)
    rationale: str
    summary: str


class AnswerReview(BaseModel):
    question: str
    answer: str
    strengths: list[str]
    missing_evidence: list[str]
    structure_issues: list[str]
    improvements: list[str]


class InterviewReviewOutput(BaseModel):
    overview: str
    answers: list[AnswerReview]
    practice_questions: list[str]


class ProviderConfigInput(BaseModel):
    slot: Literal["text", "speech", "email"]
    provider: Literal["deepseek", "openai_compatible", "aliyun_paraformer", "email_163"]
    base_url: str | None = None
    model: str | None = None
    secret: str | None = Field(default=None, exclude=True)
    secrets: dict[str, str] = Field(default_factory=dict, exclude=True)
    config: dict[str, Any] = Field(default_factory=dict)


class ProviderConfigView(BaseModel):
    slot: str
    provider: str
    base_url: str | None
    model: str | None
    config: dict[str, Any]
    configured: bool
    secret_last_four: str | None


class JobCreate(BaseModel):
    company: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)
    source_url: HttpUrl | None = None
    notes: str | None = None


class JobAnalysisRequest(BaseModel):
    document_id: str


class ApplicationCreate(BaseModel):
    job_id: str
    status: ApplicationStatus = ApplicationStatus.SAVED
    note: str | None = None


class ApplicationStatusUpdate(BaseModel):
    status: ApplicationStatus
    note: str | None = None


class MailSuggestionConfirm(BaseModel):
    application_id: str | None = None
    status: ApplicationStatus | None = None


class InterviewCreate(BaseModel):
    job_id: str | None = None
    company: str = Field(min_length=1, max_length=200)
    scheduled_at: datetime | None = None
    round: str | None = None
    outcome: str | None = None
    notes: str | None = None
    transcript: str | None = None


class TranscriptConfirm(BaseModel):
    transcript: str = Field(min_length=1)


class TranscriptionRequest(BaseModel):
    language_hints: list[str] = Field(default_factory=lambda: ["zh", "en"])
    vocabulary: list[str] = Field(default_factory=list)
    diarization: bool = True
