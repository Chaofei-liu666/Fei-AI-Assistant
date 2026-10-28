from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .career import analysis_fingerprints, resume_fingerprint, sha256_text
from .domain import ApplicationStatus
from .models import (
    Application,
    ApplicationEvent,
    Artifact,
    CandidateProfile,
    Interview,
    JobAnalysis,
    JobPosting,
    MailSuggestion,
    ReviewReport,
)
from .providers import get_provider_config
from .schemas import CandidateProfileOutput, InterviewReviewOutput, JobAnalysisOutput
from .structured import invoke_structured
from .storage import ObjectStorage


JOB_ANALYSIS_PROMPT_VERSION = "career-evidence-v2"
PROFILE_PROMPT_VERSION = "candidate-profile-v1"
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
    evidence: dict | None = None,
) -> ApplicationEvent:
    target = status.value if isinstance(status, ApplicationStatus) else status
    event = ApplicationEvent(
        application_id=application.id,
        from_status=application.status,
        to_status=target,
        source=source,
        note=note,
        evidence=evidence or {},
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
    profile = db.scalar(select(CandidateProfile).where(CandidateProfile.document_id == document.id))
    if profile is None or not profile.confirmed:
        raise ValueError("candidate profile must be generated and confirmed before analysis")
    content_fingerprint, profile_fingerprint = analysis_fingerprints(job, profile)
    config = get_provider_config(db, "text")
    provider_kind = config.config.get("provider", "unknown")
    model_name = config.model or "unknown"
    existing = db.scalar(select(JobAnalysis).where(
        JobAnalysis.job_id == job.id,
        JobAnalysis.content_fingerprint == content_fingerprint,
        JobAnalysis.profile_fingerprint == profile_fingerprint,
        JobAnalysis.prompt_version == JOB_ANALYSIS_PROMPT_VERSION,
        JobAnalysis.analysis_version == "career-evidence-v2",
        JobAnalysis.provider_kind == provider_kind,
        JobAnalysis.model == model_name,
    ).order_by(JobAnalysis.created_at.desc()).limit(1))
    if existing is not None:
        return existing
    prompt = f"""你是严格的校招岗位证据审计员。岗位已经通过 2027 届正式校招的确定性筛选。
只使用下面两份材料，禁止推断或编造候选人事实，不得输出 0-100 分或成功概率。
evidence_level 只能是 direct、partial、adjacent、insufficient：
- direct：岗位核心要求存在直接、具体的简历事实；
- partial：部分核心要求有直接证据，同时存在明确缺口；
- adjacent：只有相邻、可迁移证据；
- insufficient：没有足够候选人证据。
每条要求输出 direct、adjacent 或 missing，并标记 core、supporting 或 basic。
直接或相邻证据必须引用候选人材料中的具体事实，没有证据就使用 missing。

公司：{job.company}
职位：{job.title}
JD：
{job.description}

简历：
{document.extracted_text}
"""
    result = await invoke_structured(model, JobAnalysisOutput, prompt)
    direct_core_count = sum(
        row.assessment == "direct" and row.requirement_type == "core"
        for row in result.evidence_table
    )
    missing_core_count = len(result.missing_core_requirements)
    match_level = {"direct": "high", "partial": "medium", "adjacent": "low", "insufficient": "low"}[result.evidence_level]
    analysis = JobAnalysis(
        job_id=job.id,
        document_id=document.id,
        document_version=document.version,
        provider_kind=provider_kind,
        model=model_name,
        prompt_version=JOB_ANALYSIS_PROMPT_VERSION,
        match_level=match_level,
        evidence_level=result.evidence_level,
        analysis_version="career-evidence-v2",
        content_fingerprint=content_fingerprint,
        profile_fingerprint=profile_fingerprint,
        direct_core_count=direct_core_count,
        missing_core_count=missing_core_count,
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


async def build_candidate_profile(
    db: Session, model: BaseChatModel, document: Any
) -> CandidateProfile:
    if not document.extracted_text:
        raise ValueError("resume text is empty")
    config = get_provider_config(db, "text")
    fingerprint = sha256_text(":".join([
        resume_fingerprint(document),
        config.config.get("provider", "unknown"),
        config.model or "unknown",
        PROFILE_PROMPT_VERSION,
    ]))
    existing = db.scalar(select(CandidateProfile).where(CandidateProfile.document_id == document.id))
    if existing is not None and existing.fingerprint == fingerprint:
        return existing
    result = await invoke_structured(model, CandidateProfileOutput, f"""你是候选人简历事实提取器。
只提取简历明确写出的学历、求职方向、技能和项目事实，不推断熟练度，不把学习目标写成已掌握技能。
title_keywords 必须是适合在岗位标题中检索的短词；excluded_title_keywords 只放用户明确不考虑的方向。
简历：
{document.extracted_text}
""")
    profile = existing or CandidateProfile(document_id=document.id, document_version=document.version, fingerprint=fingerprint)
    profile.document_version = document.version
    profile.fingerprint = fingerprint
    profile.degree = result.degree
    profile.job_type = result.job_type
    profile.target_directions = result.target_directions
    profile.title_keywords = result.title_keywords
    profile.excluded_title_keywords = result.excluded_title_keywords
    profile.skills = result.skills
    profile.project_evidence = result.project_evidence
    profile.supporting_skills = result.supporting_skills
    profile.learning_targets = result.learning_targets
    profile.confirmed = False
    db.add(profile)
    db.flush()
    return profile


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
