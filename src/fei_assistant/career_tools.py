from __future__ import annotations

import json

from langchain_core.tools import tool
from sqlalchemy import select

from .career import EVIDENCE_LABELS
from .db import SessionLocal
from .models import Application, BackgroundTask, CompanySource, JobAnalysis, JobPosting, MailMessage, MailSuggestion, ScheduleItem


def _compact(value) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


@tool
def search_2027_campus_jobs(query: str = "", limit: int = 10) -> str:
    """Search confirmed 2027 full-time campus jobs and return evidence tiers, never numeric scores."""
    with SessionLocal() as db:
        statement = select(JobPosting).where(
            JobPosting.cohort == 2027,
            JobPosting.cohort_status == "confirmed",
            JobPosting.recruitment_track == "campus",
            JobPosting.availability_status == "active",
        )
        if query.strip():
            statement = statement.where((JobPosting.title.ilike(f"%{query.strip()}%")) | (JobPosting.company.ilike(f"%{query.strip()}%")))
        jobs = db.scalars(statement.order_by(JobPosting.first_seen_at.desc()).limit(min(max(limit, 1), 30))).all()
        result = []
        for job in jobs:
            analysis = db.scalar(select(JobAnalysis).where(JobAnalysis.job_id == job.id).order_by(JobAnalysis.created_at.desc()).limit(1))
            result.append({
                "job_id": job.id, "company": job.company, "title": job.title, "city": job.city,
                "jd_status": job.jd_status, "source_url": job.source_url,
                "evidence_level": analysis.evidence_level if analysis else None,
                "evidence_label": EVIDENCE_LABELS.get(analysis.evidence_level) if analysis else "未分析",
                "summary": (analysis.result or {}).get("summary") if analysis else None,
            })
        return _compact(result)


@tool
def get_job_evidence(job_id: str) -> str:
    """Read a job JD and its latest requirement-to-resume evidence report."""
    with SessionLocal() as db:
        job = db.get(JobPosting, job_id)
        if not job:
            return _compact({"error": "job_not_found"})
        analysis = db.scalar(select(JobAnalysis).where(JobAnalysis.job_id == job.id).order_by(JobAnalysis.created_at.desc()).limit(1))
        return _compact({
            "job": {"id": job.id, "company": job.company, "title": job.title, "city": job.city,
                    "description": job.description, "source_url": job.source_url, "jd_status": job.jd_status},
            "analysis": ({"evidence_level": analysis.evidence_level, "label": EVIDENCE_LABELS.get(analysis.evidence_level),
                          "result": analysis.result, "model": analysis.model, "prompt_version": analysis.prompt_version,
                          "created_at": analysis.created_at} if analysis else None),
        })


@tool
def list_applications(status: str = "") -> str:
    """List application records and current stages. This tool never changes a stage."""
    with SessionLocal() as db:
        statement = select(Application).order_by(Application.updated_at.desc())
        if status:
            statement = statement.where(Application.status == status)
        rows = db.scalars(statement.limit(100)).all()
        return _compact([{"application_id": row.id, "company": row.company_name, "title": row.job_title,
                          "status": row.status, "record_url": row.record_url, "updated_at": row.updated_at} for row in rows])


@tool
def list_pending_recruitment_mail(limit: int = 20) -> str:
    """List unconfirmed recruitment-mail suggestions without exposing full message bodies."""
    with SessionLocal() as db:
        rows = db.execute(select(MailSuggestion, MailMessage).join(MailMessage, MailSuggestion.mail_id == MailMessage.id)
                          .where(MailSuggestion.confirmed.is_(False)).order_by(MailMessage.sent_at.desc()).limit(min(max(limit, 1), 50))).all()
        return _compact([{"suggestion_id": suggestion.id, "sender": message.sender, "subject": message.subject,
                          "summary": message.body_summary, "mail_type": message.mail_type,
                          "application_id": suggestion.application_id, "suggested_status": suggestion.suggested_status,
                          "confidence": suggestion.confidence, "rationale": suggestion.rationale} for suggestion, message in rows])


@tool
def list_schedule_items(status: str = "pending") -> str:
    """List recruitment schedule items and todos."""
    with SessionLocal() as db:
        statement = select(ScheduleItem).order_by(ScheduleItem.event_date.asc().nullslast(), ScheduleItem.deadline_at.asc().nullslast())
        if status:
            statement = statement.where(ScheduleItem.status == status)
        rows = db.scalars(statement.limit(100)).all()
        return _compact([{"id": row.id, "title": row.title, "type": row.item_type,
                          "event_date": row.event_date, "deadline_at": row.deadline_at,
                          "status": row.status, "source": row.source} for row in rows])


@tool
def get_career_task_status(task_id: str = "") -> str:
    """Read one durable career task or the latest task; it never starts work."""
    with SessionLocal() as db:
        row = db.get(BackgroundTask, task_id) if task_id else db.scalar(select(BackgroundTask).order_by(BackgroundTask.created_at.desc()).limit(1))
        if not row:
            return _compact({"status": "none"})
        return _compact({"task_id": row.id, "kind": row.kind, "status": row.status, "progress": row.progress,
                         "result": row.result, "error": row.error, "updated_at": row.updated_at})


@tool
def list_company_sources() -> str:
    """List configured company recruitment sources and crawl health."""
    with SessionLocal() as db:
        rows = db.scalars(select(CompanySource).order_by(CompanySource.company)).all()
        return _compact([{"id": row.id, "company": row.company, "entry_url": row.entry_url,
                          "status": row.status, "job_count": row.job_count,
                          "incomplete_jd_count": row.incomplete_jd_count,
                          "last_error": row.last_error} for row in rows])


JOB_TOOLS = [search_2027_campus_jobs, get_job_evidence, list_company_sources]
APPLICATION_TOOLS = [list_applications]
MAIL_TOOLS = [list_pending_recruitment_mail]
SCHEDULE_TOOLS = [list_schedule_items]
OPERATIONS_TOOLS = [get_career_task_status, list_company_sources]
