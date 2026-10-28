from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl

from .domain import ApplicationStatus, MailType, MatchLevel


class RouteDecision(BaseModel):
    route: Literal["general", "job_search", "household", "clarify"]
    reason: str = Field(description="一句话说明路由依据")


class EvidenceRow(BaseModel):
    requirement: str
    evidence: str | None = None
    assessment: Literal["direct", "adjacent", "missing"]
    requirement_type: Literal["core", "supporting", "basic"] = "supporting"
    source_quote: str | None = None


class JobAnalysisOutput(BaseModel):
    evidence_level: Literal["direct", "partial", "adjacent", "insufficient"]
    summary: str
    evidence_table: list[EvidenceRow]
    missing_core_requirements: list[str]
    advantages: list[str]
    gaps: list[str]
    risks: list[str]
    preparation_actions: list[str]


class CandidateProfileOutput(BaseModel):
    degree: str | None = None
    job_type: str | None = None
    target_directions: list[str] = Field(default_factory=list)
    title_keywords: list[str] = Field(default_factory=list)
    excluded_title_keywords: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    project_evidence: list[str] = Field(default_factory=list)
    supporting_skills: list[str] = Field(default_factory=list)
    learning_targets: list[str] = Field(default_factory=list)


class CandidateProfileUpdate(CandidateProfileOutput):
    confirmed: bool = True


class MailAnalysisOutput(BaseModel):
    relevant: bool
    mail_type: MailType
    application_id: str | None = None
    suggested_status: ApplicationStatus | None = None
    confidence: float = Field(ge=0, le=1)
    rationale: str
    summary: str
    # Explicit deadline when the mail states one; "none" only when the mail says
    # there is no deadline. "unknown" means the mail simply did not mention it.
    deadline: date | None = None
    deadline_kind: Literal["explicit", "none", "unknown"] = "unknown"


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
    city: str | None = None
    cohort: Literal[2027] = 2027
    recruitment_track: Literal["campus"] = "campus"
    batch: Literal["early", "formal"] = "formal"


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
    application_id: str | None = None
    company: str = Field(min_length=1, max_length=200)
    job_title: str | None = Field(default=None, max_length=200)
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


class CompanySourceCreate(BaseModel):
    company: str = Field(min_length=1, max_length=200)
    entry_url: HttpUrl
    source_kind: Literal["official", "offerbiu", "manual"] = "official"


class ScheduleItemCreate(BaseModel):
    application_id: str | None = None
    title: str = Field(min_length=1, max_length=300)
    item_type: Literal["assessment", "written", "interview", "offer", "deadline", "todo"]
    event_date: datetime | None = None
    deadline_at: datetime | None = None
    note: str | None = None


class AutomationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    task_kind: Literal["job_discovery", "mail_sync", "application_review"]
    schedule_time: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    timezone: str = "Asia/Shanghai"
    payload: dict[str, Any] = Field(default_factory=dict)


class BrowserReviewObservation(BaseModel):
    operation_id: str = Field(min_length=8, max_length=64)
    application_id: str
    page_url: HttpUrl
    observed_status: ApplicationStatus | None = None
    confidence: float = Field(ge=0, le=1)
    page_title: str = Field(default="", max_length=500)
    visible_text: str = Field(default="", max_length=12000)
    screenshot_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    login_required: bool = False
    captcha_required: bool = False


class BrowserReviewConfirm(BaseModel):
    status: ApplicationStatus
    note: str | None = None
