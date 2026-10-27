from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .domain import ApplicationStatus
from .models import (
    Application,
    ApplicationEvent,
    Artifact,
    Interview,
    JobAnalysis,
    JobPosting,
    MailSuggestion,
    ReviewReport,
)
from .providers import get_provider_config
from .schemas import InterviewReviewOutput, JobAnalysisOutput
from .structured import invoke_structured
from .storage import ObjectStorage


JOB_ANALYSIS_PROMPT_VERSION = "job-analysis-v1"
INTERVIEW_REVIEW_PROMPT_VERSION = "interview-review-v1"


async def persist_report_artifact(db: Session, kind: str, title: str, payload: dict) -> Artifact:
    artifact = Artifact(kind=kind, title=title, payload=payload)
    db.add(artifact)
    db.flush()
    stored = await asyncio.to_thread(
        ObjectStorage().put,
        "reports",
        artifact.id,
        f"{kind}.json",
        json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
        "application/json",
    )
    artifact.object_key = stored.key
    db.add(artifact)
    return artifact


def change_application_status(
    db: Session,
    application: Application,
    status: ApplicationStatus | str,
    *,
    source: str,
    note: str | None = None,
) -> ApplicationEvent:
    target = status.value if isinstance(status, ApplicationStatus) else status
    event = ApplicationEvent(
        application_id=application.id,
        from_status=application.status,
        to_status=target,
        source=source,
        note=note,
    )
    application.status = target
    db.add_all([application, event])
    return event


def confirm_mail_suggestion(
    db: Session,
    suggestion: MailSuggestion,
    *,
    application_id: str | None = None,
    status: str | None = None,
) -> ApplicationEvent:
    if suggestion.confirmed:
        raise ValueError("suggestion has already been confirmed")
    resolved_application_id = application_id or suggestion.application_id
    resolved_status = status or suggestion.suggested_status
    if not resolved_application_id or not resolved_status:
        raise ValueError("application and status must be selected")
    application = db.get(Application, resolved_application_id)
    if not application:
        raise LookupError("application not found")
    event = change_application_status(
        db,
        application,
        resolved_status,
        source="mail_confirmation",
        note=f"Confirmed mail suggestion {suggestion.id}",
    )
    suggestion.application_id = resolved_application_id
    suggestion.suggested_status = resolved_status
    suggestion.confirmed = True
    suggestion.confirmed_at = datetime.now(timezone.utc)
    db.add(suggestion)
    return event


async def analyze_job(
    db: Session,
    model: BaseChatModel,
    job: JobPosting,
    document: Any,
) -> JobAnalysis:
    if not document.extracted_text:
        raise ValueError("resume text is empty")
    prompt = f"""你是岗位分析 Agent。只使用下面两份材料，禁止推断或编造候选人事实。
输出高/中/低匹配等级，不要输出百分制。每条证据尽量给出简历原文短句；没有证据就标记 missing。

公司：{job.company}
职位：{job.title}
JD：
{job.description}

简历：
{document.extracted_text}
"""
    result = await invoke_structured(model, JobAnalysisOutput, prompt)
    config = get_provider_config(db, "text")
    analysis = JobAnalysis(
        job_id=job.id,
        document_id=document.id,
        document_version=document.version,
        provider_kind=config.config.get("provider", "unknown"),
        model=config.model or "unknown",
        prompt_version=JOB_ANALYSIS_PROMPT_VERSION,
        match_level=result.match_level.value,
        result=result.model_dump(mode="json"),
    )
    db.add(analysis)
    db.flush()
    await persist_report_artifact(
        db,
        "job_analysis",
        f"{job.company} · {job.title} 岗位分析",
        {"job_id": job.id, "analysis_id": analysis.id, **result.model_dump(mode="json")},
    )
    return analysis


async def review_interview(
    db: Session, model: BaseChatModel, interview: Interview
) -> ReviewReport:
    if not interview.transcript_confirmed or not interview.transcript:
        raise ValueError("transcript must be edited and confirmed before review")
    result = await invoke_structured(model, InterviewReviewOutput,
        f"""你是面试复盘 Agent。把记录拆成问题与回答，逐项评价。不得补写候选人没有说过的事实。
公司：{interview.company}
轮次：{interview.round or '未填写'}
面试记录：
{interview.transcript}
"""
    )
    config = get_provider_config(db, "text")
    report = ReviewReport(
        interview_id=interview.id,
        provider_kind=config.config.get("provider", "unknown"),
        model=config.model or "unknown",
        prompt_version=INTERVIEW_REVIEW_PROMPT_VERSION,
        result=result.model_dump(mode="json"),
    )
    db.add(report)
    db.flush()
    await persist_report_artifact(
        db,
        "interview_review",
        f"{interview.company} 面试复盘",
        {"interview_id": interview.id, "review_id": report.id, **result.model_dump(mode="json")},
    )
    return report
