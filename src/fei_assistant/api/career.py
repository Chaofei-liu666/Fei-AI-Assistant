from __future__ import annotations

import hashlib

from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..career import EVIDENCE_LABELS, evidence_sort_key, profile_payload
from ..db import get_db
from ..domain import ApplicationStatus, TaskStatus
from ..models import (
    Application,
    ApplicationEvent,
    Automation,
    BackgroundTask,
    BrowserReview,
    CandidateProfile,
    CompanySource,
    Document,
    Interview,
    JobAnalysis,
    JobPosting,
    MailMessage,
    MailSuggestion,
    ScheduleItem,
)
from ..providers import build_text_model
from ..schemas import (
    ApplicationCreate,
    ApplicationStatusUpdate,
    AutomationCreate,
    BrowserReviewConfirm,
    BrowserReviewObservation,
    CandidateProfileUpdate,
    CompanySourceCreate,
    JobAnalysisRequest,
    JobCreate,
    MailSuggestionConfirm,
    ScheduleItemCreate,
)
from ..services import build_candidate_profile, change_application_status, confirm_mail_suggestion, analyze_job


router = APIRouter(prefix="/api/career", tags=["career"])
_STAGE_ORDER = {value: index for index, value in enumerate([
    "saved", "applied", "screening", "assessment", "interview", "offer",
])}


def _json(model: Any, *fields: str) -> dict:
    return {field: getattr(model, field) for field in fields}


def _analysis_view(row: JobAnalysis | None) -> dict | None:
    if row is None:
        return None
    return {
        **_json(row, "id", "document_id", "document_version", "provider_kind", "model",
                "prompt_version", "analysis_version", "evidence_level", "direct_core_count",
                "missing_core_count", "result", "created_at"),
        "label": EVIDENCE_LABELS.get(row.evidence_level, "不建议"),
    }


def _job_view(db: Session, job: JobPosting) -> dict:
    latest = db.scalar(select(JobAnalysis).where(JobAnalysis.job_id == job.id).order_by(JobAnalysis.created_at.desc()).limit(1))
    return {
        **_json(job, "id", "company", "title", "description", "source_url", "notes", "city",
                "cohort", "cohort_status", "recruitment_track", "batch", "source_kind", "jd_status",
                "availability_status", "first_seen_at", "last_seen_at", "created_at"),
        "latest_analysis": _analysis_view(latest),
    }


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)) -> dict:
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    return {
        "counts": {
            "jobs": db.scalar(select(func.count()).select_from(JobPosting).where(
                JobPosting.cohort == 2027, JobPosting.cohort_status == "confirmed",
                JobPosting.recruitment_track == "campus", JobPosting.availability_status == "active")) or 0,
            "applications": db.scalar(select(func.count()).select_from(Application).where(
                Application.status.not_in(["rejected", "withdrawn"]))) or 0,
            "mail_pending": db.scalar(select(func.count()).select_from(MailSuggestion).where(MailSuggestion.confirmed.is_(False))) or 0,
            "schedule_pending": db.scalar(select(func.count()).select_from(ScheduleItem).where(ScheduleItem.status == "pending")) or 0,
            "interviews": db.scalar(select(func.count()).select_from(Interview)) or 0,
        },
        "today": today.isoformat(),
        "task": _latest_task(db),
    }


def _latest_task(db: Session) -> dict | None:
    task = db.scalar(select(BackgroundTask).order_by(BackgroundTask.created_at.desc()).limit(1))
    return _json(task, "id", "kind", "status", "progress", "error", "created_at", "updated_at") if task else None


@router.get("/profile")
def get_profile(db: Session = Depends(get_db)) -> dict | None:
    row = db.scalar(select(CandidateProfile).order_by(CandidateProfile.updated_at.desc()).limit(1))
    return profile_payload(row) if row else None


@router.post("/profile/from-document/{document_id}", status_code=201)
async def generate_profile(document_id: str, db: Session = Depends(get_db)) -> dict:
    document = db.get(Document, document_id)
    if not document or document.kind != "resume":
        raise HTTPException(404, "resume document not found")
    try:
        profile = await build_candidate_profile(db, build_text_model(db), document)
        db.commit(); db.refresh(profile)
        return profile_payload(profile)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.put("/profile/{profile_id}")
def confirm_profile(profile_id: str, payload: CandidateProfileUpdate, db: Session = Depends(get_db)) -> dict:
    profile = db.get(CandidateProfile, profile_id)
    if not profile:
        raise HTTPException(404, "candidate profile not found")
    for key, value in payload.model_dump().items():
        setattr(profile, key, value)
    db.add(profile); db.commit(); db.refresh(profile)
    return profile_payload(profile)


@router.get("/jobs")
def list_jobs(
    query: str | None = None,
    company: str | None = None,
    evidence_level: str | None = None,
    jd_status: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> dict:
    statement = select(JobPosting).where(
        JobPosting.cohort == 2027,
        JobPosting.cohort_status == "confirmed",
        JobPosting.recruitment_track == "campus",
        JobPosting.availability_status == "active",
    )
    if query:
        keyword = f"%{query.strip()}%"
        statement = statement.where(or_(JobPosting.title.ilike(keyword), JobPosting.company.ilike(keyword)))
    if company:
        statement = statement.where(JobPosting.company == company)
    if jd_status:
        statement = statement.where(JobPosting.jd_status == jd_status)
    rows = db.scalars(statement.order_by(JobPosting.first_seen_at.desc()).limit(min(max(limit, 1), 200))).all()
    items = [_job_view(db, row) for row in rows]
    if evidence_level:
        items = [item for item in items if (item["latest_analysis"] or {}).get("evidence_level") == evidence_level]
    for item in items:
        latest = item["latest_analysis"] or {}
        item.update(
            evidence_level=latest.get("evidence_level", "insufficient"),
            direct_core_count=latest.get("direct_core_count", 0),
            missing_core_count=latest.get("missing_core_count", 999),
        )
    items.sort(key=evidence_sort_key)
    return {"items": items, "total": len(items)}


@router.post("/jobs", status_code=201)
def create_job(payload: JobCreate, db: Session = Depends(get_db)) -> dict:
    job = JobPosting(**payload.model_dump(mode="json"), cohort_status="confirmed", source_kind="manual", jd_status="complete")
    db.add(job); db.commit(); db.refresh(job)
    return _job_view(db, job)


@router.get("/jobs/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db)) -> dict:
    job = db.get(JobPosting, job_id)
    if not job or job.cohort != 2027 or job.recruitment_track != "campus":
        raise HTTPException(404, "2027 campus job not found")
    analyses = db.scalars(select(JobAnalysis).where(JobAnalysis.job_id == job_id).order_by(JobAnalysis.created_at.desc())).all()
    return {**_job_view(db, job), "analyses": [_analysis_view(row) for row in analyses]}


@router.post("/jobs/{job_id}/analysis")
async def analyze(job_id: str, payload: JobAnalysisRequest, db: Session = Depends(get_db)) -> dict:
    job, document = db.get(JobPosting, job_id), db.get(Document, payload.document_id)
    if not job or not document:
        raise HTTPException(404, "job or resume not found")
    if job.cohort != 2027 or job.recruitment_track != "campus":
        raise HTTPException(422, "only confirmed 2027 campus jobs can be analyzed")
    try:
        row = await analyze_job(db, build_text_model(db), job, document)
        db.commit(); db.refresh(row)
        return _analysis_view(row) or {}
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/companies")
def list_sources(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(CompanySource).order_by(CompanySource.company)).all()
    return [_json(row, "id", "company", "entry_url", "source_kind", "status", "last_error",
                  "last_attempted_at", "job_count", "incomplete_jd_count", "updated_at") for row in rows]


@router.post("/companies", status_code=201)
def create_source(payload: CompanySourceCreate, db: Session = Depends(get_db)) -> dict:
    row = CompanySource(**payload.model_dump(mode="json"))
    db.add(row)
    try:
        db.commit(); db.refresh(row)
    except Exception as exc:
        db.rollback(); raise HTTPException(409, "company source already exists") from exc
    return _json(row, "id", "company", "entry_url", "source_kind", "status")


@router.post("/companies/{source_id}/crawl", status_code=202)
def crawl_source(source_id: str, request: Request, db: Session = Depends(get_db)) -> dict:
    if not db.get(CompanySource, source_id):
        raise HTTPException(404, "company source not found")
    manager = request.app.state.task_manager
    task = manager.create(db, "job_discovery", {"source_id": source_id})
    db.commit()
    return _json(task, "id", "kind", "status", "created_at")


@router.get("/applications")
def applications(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Application).order_by(Application.updated_at.desc())).all()
    return [_json(row, "id", "job_id", "company_name", "job_title", "status", "record_url", "source", "created_at", "updated_at") for row in rows]


@router.post("/applications", status_code=201)
def create_application(payload: ApplicationCreate, db: Session = Depends(get_db)) -> dict:
    job = db.get(JobPosting, payload.job_id)
    if not job:
        raise HTTPException(404, "job not found")
    existing = db.scalar(select(Application).where(Application.job_id == job.id))
    if existing:
        raise HTTPException(409, "application already exists")
    row = Application(job_id=job.id, company_name=job.company, job_title=job.title, status=payload.status.value, source="manual")
    db.add(row); db.flush()
    db.add(ApplicationEvent(application_id=row.id, from_status=None, to_status=row.status, source="manual", note=payload.note, evidence={}))
    db.commit(); db.refresh(row)
    return _json(row, "id", "job_id", "company_name", "job_title", "status", "record_url", "created_at")


@router.patch("/applications/{application_id}")
def update_application(application_id: str, payload: ApplicationStatusUpdate, db: Session = Depends(get_db)) -> dict:
    row = db.get(Application, application_id)
    if not row:
        raise HTTPException(404, "application not found")
    event = change_application_status(db, row, payload.status, source="manual", note=payload.note)
    db.commit()
    return _json(event, "id", "application_id", "from_status", "to_status", "source", "note", "evidence", "created_at")


@router.get("/applications/{application_id}/events")
def application_events(application_id: str, db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(ApplicationEvent).where(ApplicationEvent.application_id == application_id).order_by(ApplicationEvent.created_at)).all()
    return [_json(row, "id", "application_id", "from_status", "to_status", "source", "note", "evidence", "created_at") for row in rows]


@router.post("/applications/{application_id}/review-observations", status_code=201)
def observe_application(application_id: str, payload: BrowserReviewObservation, db: Session = Depends(get_db)) -> dict:
    if payload.application_id != application_id:
        raise HTTPException(400, "application mismatch")
    if not db.get(Application, application_id):
        raise HTTPException(404, "application not found")
    blocked = payload.login_required or payload.captcha_required or payload.observed_status is None or payload.confidence < .85
    row = BrowserReview(
        operation_id=payload.operation_id,
        application_id=application_id,
        page_url=str(payload.page_url),
        observed_status=payload.observed_status.value if payload.observed_status else None,
        confidence=payload.confidence,
        evidence={"page_title": payload.page_title,
                  "visible_text_sha256": hashlib.sha256(payload.visible_text.encode("utf-8")).hexdigest(),
                  "screenshot_sha256": payload.screenshot_sha256, "login_required": payload.login_required,
                  "captcha_required": payload.captcha_required},
        requires_user_action=True,
        confirmed=False,
    )
    db.add(row)
    try:
        db.commit(); db.refresh(row)
    except Exception as exc:
        db.rollback(); raise HTTPException(409, "review operation already recorded") from exc
    return _json(row, "id", "operation_id", "application_id", "observed_status", "confidence", "evidence", "requires_user_action", "confirmed", "created_at") | {"blocked": blocked}


@router.post("/review-observations/{review_id}/confirm")
def confirm_review(review_id: str, payload: BrowserReviewConfirm, db: Session = Depends(get_db)) -> dict:
    review = db.get(BrowserReview, review_id)
    if not review or review.confirmed:
        raise HTTPException(404, "pending browser review not found")
    application = db.get(Application, review.application_id)
    if not application:
        raise HTTPException(404, "application not found")
    current, target = application.status, payload.status.value
    if target not in {"rejected", "withdrawn"} and _STAGE_ORDER.get(target, -1) < _STAGE_ORDER.get(current, -1):
        raise HTTPException(409, "official review cannot lower a confirmed application stage")
    event = change_application_status(db, application, target, source="official_browser_confirmation",
                                      note=payload.note, evidence={"review_id": review.id, **review.evidence})
    review.confirmed = True
    review.requires_user_action = False
    db.add(review); db.commit()
    return _json(event, "id", "application_id", "from_status", "to_status", "source", "evidence", "created_at")


@router.get("/mail")
def mail(pending_only: bool = True, db: Session = Depends(get_db)) -> list[dict]:
    query = select(MailSuggestion, MailMessage).join(MailMessage, MailSuggestion.mail_id == MailMessage.id).order_by(MailMessage.sent_at.desc())
    if pending_only:
        query = query.where(MailSuggestion.confirmed.is_(False))
    return [{**_json(s, "id", "mail_id", "application_id", "suggested_status", "confidence", "rationale", "confirmed", "created_at"),
             **_json(m, "sender", "subject", "sent_at", "body_summary", "mail_type")} for s, m in db.execute(query).all()]


@router.post("/mail/sync", status_code=202)
def sync_mail(request: Request, db: Session = Depends(get_db)) -> dict:
    existing = db.scalar(select(BackgroundTask).where(BackgroundTask.kind == "mail_sync", BackgroundTask.status.in_(["queued", "running"])))
    task = existing or request.app.state.task_manager.create(db, "mail_sync", {})
    db.commit()
    return _json(task, "id", "kind", "status", "created_at")


@router.post("/mail/{suggestion_id}/confirm")
def confirm_mail(suggestion_id: str, payload: MailSuggestionConfirm, db: Session = Depends(get_db)) -> dict:
    suggestion = db.get(MailSuggestion, suggestion_id)
    if not suggestion:
        raise HTTPException(404, "mail suggestion not found")
    try:
        event = confirm_mail_suggestion(db, suggestion, application_id=payload.application_id,
                                        status=payload.status.value if payload.status else None)
        db.commit()
        return _json(event, "id", "application_id", "from_status", "to_status", "source", "created_at")
    except (ValueError, LookupError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/schedule")
def schedule(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(ScheduleItem).order_by(ScheduleItem.event_date.asc().nullslast(), ScheduleItem.deadline_at.asc().nullslast())).all()
    return [_json(row, "id", "application_id", "title", "item_type", "event_date", "deadline_at", "status", "source", "note", "created_at", "updated_at") for row in rows]


@router.post("/schedule", status_code=201)
def create_schedule(payload: ScheduleItemCreate, db: Session = Depends(get_db)) -> dict:
    if payload.application_id and not db.get(Application, payload.application_id):
        raise HTTPException(404, "application not found")
    import uuid
    row = ScheduleItem(**payload.model_dump(), source="manual", source_ref=f"manual:{uuid.uuid4().hex}")
    db.add(row); db.commit(); db.refresh(row)
    return _json(row, "id", "application_id", "title", "item_type", "event_date", "deadline_at", "status", "source", "note", "created_at")


@router.get("/automations")
def automations(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Automation).order_by(Automation.created_at.desc())).all()
    return [_json(row, "id", "name", "task_kind", "schedule_time", "timezone", "enabled", "payload", "last_run_at", "last_status", "last_error", "created_at") for row in rows]


@router.post("/automations", status_code=201)
def create_automation(payload: AutomationCreate, request: Request, db: Session = Depends(get_db)) -> dict:
    row = Automation(**payload.model_dump(), enabled=True)
    db.add(row); db.commit(); db.refresh(row)
    request.app.state.task_manager.register_automation(row)
    return _json(row, "id", "name", "task_kind", "schedule_time", "timezone", "enabled", "payload", "created_at")


@router.post("/automations/{automation_id}/toggle")
def toggle_automation(automation_id: str, request: Request, db: Session = Depends(get_db)) -> dict:
    row = db.get(Automation, automation_id)
    if not row:
        raise HTTPException(404, "automation not found")
    row.enabled = not row.enabled
    db.add(row); db.commit(); db.refresh(row)
    request.app.state.task_manager.register_automation(row)
    return {"id": row.id, "enabled": row.enabled}


@router.get("/tasks")
def tasks(limit: int = 30, db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(BackgroundTask).order_by(BackgroundTask.created_at.desc()).limit(min(max(limit, 1), 100))).all()
    return [_json(row, "id", "kind", "status", "progress", "payload", "result", "attempts", "error", "created_at", "updated_at") for row in rows]


@router.get("/tasks/{task_id}")
def task(task_id: str, db: Session = Depends(get_db)) -> dict:
    row = db.get(BackgroundTask, task_id)
    if not row:
        raise HTTPException(404, "task not found")
    return _json(row, "id", "kind", "status", "progress", "payload", "result", "attempts", "error", "created_at", "updated_at")
