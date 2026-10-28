from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..documents import extract_resume_text, validate_upload
from ..domain import ApplicationStatus, TaskStatus
from ..models import (
    Application,
    ApplicationEvent,
    Artifact,
    BackgroundTask,
    Document,
    Interview,
    JobAnalysis,
    JobPosting,
    MailMessage,
    MailSuggestion,
    ProviderConfig,
    ReviewReport,
    TranscriptionJob,
)
from ..providers import build_text_model, list_text_models, test_dashscope_key, test_text_provider
from ..schemas import (
    ApplicationCreate,
    ApplicationStatusUpdate,
    InterviewCreate,
    JobAnalysisRequest,
    JobCreate,
    MailSuggestionConfirm,
    ProviderConfigInput,
    TranscriptConfirm,
    TranscriptionRequest,
)
from ..secrets import SecretStore, secret_metadata
from ..services import analyze_job, change_application_status, confirm_mail_suggestion, review_interview
from ..storage import ObjectStorage
from ..tasks import TaskManager
from .agents import router as agents_router
from .career import router as career_router
from .household import router as household_router
from .inbox import router as inbox_router
from .mail_events import router as mail_events_router
from .runs import router as runs_router


task_manager = TaskManager()


@asynccontextmanager
async def lifespan(application: FastAPI):
    application.state.task_manager = task_manager
    task_manager.start()
    yield
    task_manager.shutdown()


app = FastAPI(title="Fei Assistant API", version="0.1.0", lifespan=lifespan)
app.include_router(career_router)
app.include_router(household_router)
app.include_router(agents_router)
app.include_router(mail_events_router)
app.include_router(inbox_router)
app.include_router(runs_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _json(model: Any, *fields: str) -> dict:
    return {field: getattr(model, field) for field in fields}


def _provider_view(config: ProviderConfig) -> dict:
    public_config = {k: v for k, v in (config.config or {}).items() if not k.endswith("_ref")}
    return {
        "slot": config.kind,
        "provider": config.config.get("provider"),
        "base_url": config.base_url,
        "model": config.model,
        "config": public_config,
        "configured": config.configured,
        "secret_last_four": config.secret_last_four,
    }


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/settings/providers")
def list_providers(db: Session = Depends(get_db)) -> list[dict]:
    return [_provider_view(row) for row in db.scalars(select(ProviderConfig)).all()]


@app.get("/api/settings/models")
def list_models(db: Session = Depends(get_db)) -> list[dict]:
    try:
        return list_text_models(db)
    except Exception as exc:
        raise HTTPException(400, f"cannot list models: {exc}") from exc


@app.put("/api/settings/providers/{slot}")
def save_provider(slot: str, payload: ProviderConfigInput, db: Session = Depends(get_db)) -> dict:
    if slot != payload.slot:
        raise HTTPException(400, "slot mismatch")
    allowed = {
        "text": {"deepseek", "openai_compatible"},
        "speech": {"aliyun_paraformer"},
        "email": {"email_163"},
    }
    if payload.provider not in allowed.get(slot, set()):
        raise HTTPException(400, "provider is not valid for this slot")
    if slot == "text" and payload.provider == "openai_compatible" and not payload.base_url:
        raise HTTPException(400, "custom OpenAI-compatible provider requires base_url")
    config = db.scalar(select(ProviderConfig).where(ProviderConfig.kind == slot)) or ProviderConfig(kind=slot)
    secret_store = SecretStore()
    primary_ref = config.secret_ref or f"provider:{slot}:primary"
    if payload.secret:
        secret_store.set(primary_ref, payload.secret)
        config.secret_ref = primary_ref
        config.secret_last_four, _ = secret_metadata(payload.secret)
    saved_config = dict(config.config or {})
    saved_config.update(payload.config)
    saved_config["provider"] = payload.provider
    for name, secret in payload.secrets.items():
        ref = f"provider:{slot}:{name}"
        secret_store.set(ref, secret)
        saved_config[f"{name}_ref"] = ref
    if slot == "speech" and "oss_secret" in payload.secrets:
        saved_config["oss_secret_ref"] = saved_config.pop("oss_secret_ref", f"provider:{slot}:oss_secret")
    has_primary_secret = bool(config.secret_ref and secret_store.get(config.secret_ref))
    if slot == "text" and (not payload.model or not has_primary_secret):
        raise HTTPException(400, "model and API key are required")
    if slot == "speech":
        required = {"dashscope_workspace_id", "oss_access_key_id", "oss_endpoint", "oss_bucket", "oss_secret_ref"}
        if not has_primary_secret or any(not saved_config.get(key) for key in required):
            raise HTTPException(400, "DashScope key and complete private OSS configuration are required")
    if slot == "email" and (not saved_config.get("username") or not has_primary_secret):
        raise HTTPException(400, "163 mailbox and authorization code are required")
    config.base_url = payload.base_url
    config.model = payload.model
    config.config = saved_config
    config.configured = True
    db.add(config)
    db.commit()
    db.refresh(config)
    return _provider_view(config)


@app.post("/api/settings/providers/{slot}/test")
async def test_saved_provider(slot: str, db: Session = Depends(get_db)) -> dict:
    config = db.scalar(select(ProviderConfig).where(ProviderConfig.kind == slot))
    if not config or not config.configured:
        raise HTTPException(404, "provider is not configured")
    secrets = SecretStore()
    payload = ProviderConfigInput(
        slot=slot,
        provider=config.config.get("provider"),
        base_url=config.base_url,
        model=config.model,
        secret=secrets.get(config.secret_ref),
        config={k: v for k, v in config.config.items() if not k.endswith("_ref")},
    )
    result = await test_provider(payload)
    if slot == "speech":
        import oss2
        oss_secret = secrets.get(config.config.get("oss_secret_ref"))
        if not oss_secret:
            raise HTTPException(400, "OSS secret is unavailable")
        bucket = oss2.Bucket(
            oss2.Auth(config.config["oss_access_key_id"], oss_secret),
            config.config["oss_endpoint"], config.config["oss_bucket"],
        )
        try:
            await asyncio.to_thread(bucket.get_bucket_info)
            result["oss_private_bucket"] = True
        except Exception as exc:
            raise HTTPException(400, f"OSS connection failed: {exc}") from exc
    return result


@app.post("/api/settings/providers/test")
async def test_provider(payload: ProviderConfigInput) -> dict:
    if payload.slot == "text":
        if not payload.secret:
            raise HTTPException(400, "API key is required for capability test")
        try:
            return await test_text_provider(payload, payload.secret)
        except Exception as exc:
            raise HTTPException(400, str(exc)) from exc
    if payload.slot == "speech":
        if not payload.secret:
            raise HTTPException(400, "DashScope API key is required")
        if not await test_dashscope_key(payload.secret):
            raise HTTPException(400, "DashScope connection failed")
        return {"dashscope": True}
    if payload.slot == "email":
        from ..mail import Imap163Client
        try:
            client = Imap163Client(
                payload.config.get("username", ""), payload.secret or "",
                payload.config.get("host", "imap.163.com"), int(payload.config.get("port", 993)),
            )
            await __import__("asyncio").to_thread(client.fetch_since, 2**31 - 1)
            return {"imap": True, "read_only": True}
        except Exception as exc:
            raise HTTPException(400, str(exc)) from exc
    raise HTTPException(400, "unsupported provider")


@app.post("/api/files", status_code=201)
async def upload_file(kind: str, file: UploadFile = File(...), db: Session = Depends(get_db)) -> dict:
    data = await file.read()
    try:
        validate_upload(file.filename or "upload", data, kind, get_settings().max_upload_mb * 1024 * 1024)
        extracted = extract_resume_text(file.filename or "upload", data) if kind == "resume" else None
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc
    object_id = str(uuid.uuid4())
    storage = ObjectStorage()
    stored = await asyncio.to_thread(storage.put, kind, object_id, file.filename or "upload", data, file.content_type or "application/octet-stream")
    existing = db.scalar(select(Document).where(Document.sha256 == stored.sha256, Document.kind == kind))
    if existing:
        await asyncio.to_thread(storage.delete, stored.key)
        return _json(existing, "id", "kind", "filename", "content_type", "size", "sha256", "version", "created_at")
    latest_version = db.scalar(select(func.max(Document.version)).where(Document.kind == kind)) or 0
    document = Document(
        id=object_id, kind=kind, filename=file.filename or "upload", content_type=file.content_type or "application/octet-stream",
        size=stored.size, sha256=stored.sha256, object_key=stored.key, extracted_text=extracted, version=latest_version + 1,
    )
    db.add(document)
    db.commit()
    return _json(document, "id", "kind", "filename", "content_type", "size", "sha256", "version", "created_at")


@app.get("/api/files")
def list_files(kind: str | None = None, db: Session = Depends(get_db)) -> list[dict]:
    query = select(Document).order_by(Document.created_at.desc())
    if kind:
        query = query.where(Document.kind == kind)
    return [_json(x, "id", "kind", "filename", "content_type", "size", "sha256", "version", "created_at") for x in db.scalars(query).all()]


@app.get("/api/files/{document_id}/download")
def download_file(document_id: str, db: Session = Depends(get_db)):
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(404, "file not found")
    return RedirectResponse(ObjectStorage().download_url(document.object_key))


@app.get("/api/files/{document_id}")
def get_file_metadata(document_id: str, db: Session = Depends(get_db)) -> dict:
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(404, "file not found")
    return _json(document, "id", "kind", "filename", "content_type", "size", "sha256", "version", "created_at")


@app.get("/api/artifacts")
def list_artifacts(kind: str | None = None, db: Session = Depends(get_db)) -> list[dict]:
    query = select(Artifact).order_by(Artifact.created_at.desc())
    if kind:
        query = query.where(Artifact.kind == kind)
    return [_json(row, "id", "kind", "title", "payload", "object_key", "task_id", "created_at") for row in db.scalars(query).all()]


@app.get("/api/artifacts/{artifact_id}/download")
def download_artifact(artifact_id: str, db: Session = Depends(get_db)):
    artifact = db.get(Artifact, artifact_id)
    if not artifact or not artifact.object_key:
        raise HTTPException(404, "artifact not found")
    return RedirectResponse(ObjectStorage().download_url(artifact.object_key))


@app.post("/api/jobs", status_code=201)
def create_job(payload: JobCreate, db: Session = Depends(get_db)) -> dict:
    job = JobPosting(**payload.model_dump(mode="json"))
    db.add(job); db.commit(); db.refresh(job)
    return _json(job, "id", "company", "title", "description", "source_url", "notes", "created_at")


@app.get("/api/jobs")
def list_jobs(db: Session = Depends(get_db)) -> list[dict]:
    result = []
    for job in db.scalars(select(JobPosting).order_by(JobPosting.created_at.desc())).all():
        latest = db.scalar(select(JobAnalysis).where(JobAnalysis.job_id == job.id).order_by(JobAnalysis.created_at.desc()).limit(1))
        result.append({**_json(job, "id", "company", "title", "description", "source_url", "notes", "created_at"), "latest_analysis": _json(latest, "id", "match_level", "result", "model", "prompt_version", "document_version", "created_at") if latest else None})
    return result


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db)) -> dict:
    job = db.get(JobPosting, job_id)
    if not job: raise HTTPException(404, "job not found")
    analyses = db.scalars(select(JobAnalysis).where(JobAnalysis.job_id == job_id).order_by(JobAnalysis.created_at.desc())).all()
    return {**_json(job, "id", "company", "title", "description", "source_url", "notes", "created_at"), "analyses": [_json(x, "id", "document_id", "document_version", "provider_kind", "model", "prompt_version", "match_level", "result", "created_at") for x in analyses]}


@app.post("/api/jobs/{job_id}/analyze")
async def analyze_job_api(job_id: str, payload: JobAnalysisRequest, db: Session = Depends(get_db)) -> dict:
    job, document = db.get(JobPosting, job_id), db.get(Document, payload.document_id)
    if not job or not document: raise HTTPException(404, "job or document not found")
    try:
        analysis = await analyze_job(db, build_text_model(db), job, document)
        db.commit(); db.refresh(analysis)
        return _json(analysis, "id", "document_id", "document_version", "provider_kind", "model", "prompt_version", "match_level", "result", "created_at")
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/applications", status_code=201)
def create_application(payload: ApplicationCreate, db: Session = Depends(get_db)) -> dict:
    if not db.get(JobPosting, payload.job_id): raise HTTPException(404, "job not found")
    if db.scalar(select(Application).where(Application.job_id == payload.job_id)): raise HTTPException(409, "application already exists")
    app_model = Application(job_id=payload.job_id, status=payload.status.value)
    db.add(app_model); db.flush()
    db.add(ApplicationEvent(application_id=app_model.id, from_status=None, to_status=payload.status.value, source="user", note=payload.note))
    db.commit(); db.refresh(app_model)
    return _json(app_model, "id", "job_id", "status", "created_at", "updated_at")


@app.get("/api/applications")
def list_applications(status: str | None = None, db: Session = Depends(get_db)) -> list[dict]:
    query = select(Application, JobPosting).join(JobPosting, Application.job_id == JobPosting.id).order_by(Application.updated_at.desc())
    if status: query = query.where(Application.status == status)
    return [{**_json(a, "id", "job_id", "status", "created_at", "updated_at"), "company": j.company, "title": j.title} for a, j in db.execute(query).all()]


@app.patch("/api/applications/{application_id}/status")
def update_application(application_id: str, payload: ApplicationStatusUpdate, db: Session = Depends(get_db)) -> dict:
    application = db.get(Application, application_id)
    if not application: raise HTTPException(404, "application not found")
    event = change_application_status(db, application, payload.status, source="user", note=payload.note)
    db.commit()
    return _json(event, "id", "application_id", "from_status", "to_status", "source", "note", "created_at")


@app.get("/api/applications/{application_id}/events")
def application_events(application_id: str, db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(ApplicationEvent).where(ApplicationEvent.application_id == application_id).order_by(ApplicationEvent.created_at)).all()
    return [_json(x, "id", "application_id", "from_status", "to_status", "source", "note", "created_at") for x in rows]


@app.post("/api/mail/sync", status_code=202)
def request_mail_sync(db: Session = Depends(get_db)) -> dict:
    existing = db.scalar(select(BackgroundTask).where(BackgroundTask.kind == "mail_sync", BackgroundTask.status.in_([TaskStatus.QUEUED.value, TaskStatus.RUNNING.value])))
    if existing:
        return _json(existing, "id", "kind", "status", "created_at")
    task = task_manager.create(db, "mail_sync", {}); db.commit()
    return _json(task, "id", "kind", "status", "created_at")


@app.get("/api/mail/suggestions")
def list_mail_suggestions(pending_only: bool = True, db: Session = Depends(get_db)) -> list[dict]:
    query = select(MailSuggestion, MailMessage).join(MailMessage, MailSuggestion.mail_id == MailMessage.id).order_by(MailMessage.sent_at.desc())
    if pending_only: query = query.where(MailSuggestion.confirmed.is_(False))
    return [{**_json(s, "id", "mail_id", "application_id", "suggested_status", "confidence", "rationale", "confirmed", "created_at"), **_json(m, "sender", "subject", "sent_at", "body_summary", "mail_type")} for s, m in db.execute(query).all()]


@app.post("/api/mail/suggestions/{suggestion_id}/confirm")
def confirm_suggestion(suggestion_id: str, payload: MailSuggestionConfirm, db: Session = Depends(get_db)) -> dict:
    suggestion = db.get(MailSuggestion, suggestion_id)
    if not suggestion: raise HTTPException(404, "suggestion not found")
    try:
        event = confirm_mail_suggestion(db, suggestion, application_id=payload.application_id, status=payload.status.value if payload.status else None)
        db.commit()
        return _json(event, "id", "application_id", "from_status", "to_status", "source", "created_at")
    except (ValueError, LookupError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/interviews", status_code=201)
def create_interview(payload: InterviewCreate, db: Session = Depends(get_db)) -> dict:
    interview = Interview(**payload.model_dump(), transcript_confirmed=False)
    db.add(interview); db.commit(); db.refresh(interview)
    return _json(interview, "id", "job_id", "application_id", "company", "job_title", "scheduled_at", "round", "outcome", "notes", "transcript", "transcript_confirmed", "created_at")


@app.get("/api/interviews")
def list_interviews(db: Session = Depends(get_db)) -> list[dict]:
    result = []
    for interview in db.scalars(select(Interview).order_by(Interview.created_at.desc())).all():
        latest = db.scalar(select(ReviewReport).where(ReviewReport.interview_id == interview.id).order_by(ReviewReport.created_at.desc()).limit(1))
        result.append({**_json(interview, "id", "job_id", "application_id", "company", "job_title", "scheduled_at", "round", "outcome", "notes", "audio_document_id", "transcript", "transcript_confirmed", "created_at"), "latest_review": _json(latest, "id", "result", "model", "prompt_version", "created_at") if latest else None})
    return result


@app.post("/api/interviews/{interview_id}/audio")
async def upload_interview_audio(interview_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)) -> dict:
    interview = db.get(Interview, interview_id)
    if not interview: raise HTTPException(404, "interview not found")
    data = await file.read()
    try: validate_upload(file.filename or "audio", data, "audio", get_settings().max_upload_mb * 1024 * 1024)
    except ValueError as exc: raise HTTPException(400, str(exc)) from exc
    document_id = str(uuid.uuid4())
    storage = ObjectStorage()
    stored = await asyncio.to_thread(storage.put, "interview-audio", document_id, file.filename or "audio", data, file.content_type or "application/octet-stream")
    document = db.scalar(select(Document).where(Document.sha256 == stored.sha256, Document.kind == "interview_audio"))
    if document:
        await asyncio.to_thread(storage.delete, stored.key)
    else:
        document = Document(id=document_id, kind="interview_audio", filename=file.filename or "audio", content_type=file.content_type or "application/octet-stream", size=stored.size, sha256=stored.sha256, object_key=stored.key)
    interview.audio_document_id = document.id
    db.add_all([document, interview]); db.commit()
    return _json(document, "id", "filename", "content_type", "size", "sha256", "created_at")


@app.post("/api/interviews/{interview_id}/transcribe", status_code=202)
def transcribe_interview(interview_id: str, payload: TranscriptionRequest, db: Session = Depends(get_db)) -> dict:
    interview = db.get(Interview, interview_id)
    if not interview or not interview.audio_document_id: raise HTTPException(400, "upload audio first")
    job = db.scalar(select(TranscriptionJob).where(TranscriptionJob.interview_id == interview_id))
    if job and job.status in {"queued", "running"}:
        raise HTTPException(409, "transcription is already queued or running")
    job = job or TranscriptionJob(interview_id=interview_id, status="queued")
    job.status = "queued"; job.parameters = payload.model_dump(); db.add(job); db.flush()
    task = task_manager.create(db, "transcription", {"interview_id": interview_id}); db.commit()
    return _json(task, "id", "kind", "status", "created_at")


@app.put("/api/interviews/{interview_id}/transcript")
def confirm_transcript(interview_id: str, payload: TranscriptConfirm, db: Session = Depends(get_db)) -> dict:
    interview = db.get(Interview, interview_id)
    if not interview: raise HTTPException(404, "interview not found")
    interview.transcript = payload.transcript; interview.transcript_confirmed = True
    db.add(interview); db.commit()
    return _json(interview, "id", "transcript", "transcript_confirmed", "updated_at")


@app.post("/api/interviews/{interview_id}/review")
async def review_interview_api(interview_id: str, db: Session = Depends(get_db)) -> dict:
    interview = db.get(Interview, interview_id)
    if not interview: raise HTTPException(404, "interview not found")
    try:
        report = await review_interview(db, build_text_model(db), interview)
        db.commit(); db.refresh(report)
        return _json(report, "id", "interview_id", "provider_kind", "model", "prompt_version", "result", "created_at")
    except (ValueError, RuntimeError) as exc: raise HTTPException(400, str(exc)) from exc


@app.get("/api/interviews/{interview_id}/reviews")
def list_reviews(interview_id: str, db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(ReviewReport).where(ReviewReport.interview_id == interview_id).order_by(ReviewReport.created_at.desc())).all()
    return [_json(x, "id", "provider_kind", "model", "prompt_version", "result", "created_at") for x in rows]


@app.get("/api/tasks/{task_id}")
def get_task(task_id: str, db: Session = Depends(get_db)) -> dict:
    task = db.get(BackgroundTask, task_id)
    if not task: raise HTTPException(404, "task not found")
    return _json(task, "id", "kind", "status", "progress", "payload", "result", "attempts", "error", "created_at", "updated_at")


@app.get("/api/tasks")
def list_tasks(limit: int = 20, db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(BackgroundTask).order_by(BackgroundTask.created_at.desc()).limit(min(limit, 100))).all()
    return [_json(task, "id", "kind", "status", "progress", "attempts", "error", "created_at", "updated_at") for task in rows]


@app.post("/api/tasks/{task_id}/retry", status_code=202)
def retry_task(task_id: str, db: Session = Depends(get_db)) -> dict:
    task = db.get(BackgroundTask, task_id)
    if not task or task.status != TaskStatus.FAILED.value: raise HTTPException(400, "only failed tasks can be retried")
    task.status = TaskStatus.QUEUED.value; task.error = None; db.add(task); db.commit(); task_manager.schedule(task.id)
    return _json(task, "id", "kind", "status", "attempts", "updated_at")


def run() -> None:
    settings = get_settings()
    uvicorn.run("fei_assistant.api.app:app", host=settings.api_host, port=settings.api_port, reload=False)
