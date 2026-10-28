from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from .db import SessionLocal
from .career import crawl_company_source
from .domain import TaskStatus
from .mail import Imap163Client, sync_mailbox
from .models import Automation, BackgroundTask, CompanySource, Document, Interview, ProviderConfig, TranscriptionJob
from .providers import build_text_model, get_provider_config
from .secrets import SecretStore
from .storage import ObjectStorage
from .transcription import ParaformerConfig, ParaformerTranscriber


class TaskManager:
    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone="UTC")

    def start(self) -> None:
        self.scheduler.start()
        self.scheduler.add_job(
            self.enqueue_periodic_mail_sync,
            "interval",
            minutes=15,
            id="mail-sync-15m",
            replace_existing=True,
            max_instances=1,
        )
        with SessionLocal() as db:
            recoverable = db.scalars(
                select(BackgroundTask).where(
                    BackgroundTask.status.in_([TaskStatus.QUEUED.value, TaskStatus.RUNNING.value])
                )
            ).all()
            for task in recoverable:
                task.status = TaskStatus.QUEUED.value
                db.add(task)
                self.schedule(task.id)
            for automation in db.scalars(select(Automation)).all():
                self.register_automation(automation)
            db.commit()

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    def schedule(self, task_id: str) -> None:
        self.scheduler.add_job(
            self.execute,
            "date",
            run_date=datetime.now(timezone.utc) + timedelta(seconds=1),
            args=[task_id],
            id=f"task-{task_id}",
            replace_existing=True,
        )

    def create(self, db, kind: str, payload: dict) -> BackgroundTask:
        task = BackgroundTask(kind=kind, status=TaskStatus.QUEUED.value, payload=payload)
        db.add(task)
        db.flush()
        self.schedule(task.id)
        return task

    def register_automation(self, automation: Automation) -> None:
        job_id = f"automation-{automation.id}"
        try:
            self.scheduler.remove_job(job_id)
        except Exception:
            pass
        if not automation.enabled:
            return
        hour, minute = (int(part) for part in automation.schedule_time.split(":"))
        self.scheduler.add_job(
            self.enqueue_automation,
            "cron",
            hour=hour,
            minute=minute,
            timezone=automation.timezone,
            args=[automation.id],
            id=job_id,
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

    async def enqueue_automation(self, automation_id: str) -> None:
        with SessionLocal() as db:
            automation = db.get(Automation, automation_id)
            if not automation or not automation.enabled:
                return
            payload = {**(automation.payload or {}), "automation_id": automation.id}
            if automation.task_kind == "job_discovery" and not payload.get("source_id"):
                payload["all_sources"] = True
            self.create(db, automation.task_kind, payload)
            automation.last_run_at = datetime.now(timezone.utc)
            automation.last_status = "queued"
            automation.last_error = None
            db.add(automation)
            db.commit()

    async def enqueue_periodic_mail_sync(self) -> None:
        with SessionLocal() as db:
            provider = db.scalar(select(ProviderConfig).where(ProviderConfig.kind == "email"))
            pending = db.scalar(
                select(BackgroundTask).where(
                    BackgroundTask.kind == "mail_sync",
                    BackgroundTask.status.in_([TaskStatus.QUEUED.value, TaskStatus.RUNNING.value]),
                )
            )
            if provider and provider.configured and not pending:
                self.create(db, "mail_sync", {})
                db.commit()

    async def execute(self, task_id: str) -> None:
        with SessionLocal() as db:
            task = db.get(BackgroundTask, task_id)
            if not task or task.status == TaskStatus.SUCCEEDED.value:
                return
            task.status = TaskStatus.RUNNING.value
            task.attempts += 1
            task.error = None
            db.commit()
            try:
                if task.kind == "mail_sync":
                    task.result = await self._mail_sync(db)
                elif task.kind == "transcription":
                    task.result = await self._transcribe(db, task.payload["interview_id"])
                elif task.kind == "job_discovery":
                    task.result = await self._job_discovery(db, task)
                elif task.kind == "application_review":
                    task.result = {"requires_user_action": True, "reason": "open applications in the Fei desktop browser"}
                else:
                    raise ValueError(f"unknown task kind: {task.kind}")
                task.status = TaskStatus.SUCCEEDED.value
                task.progress = 100
            except Exception as exc:
                db.rollback()
                task = db.get(BackgroundTask, task_id)
                if not task:
                    return
                task.status = TaskStatus.FAILED.value
                task.error = str(exc)[:4000]
            db.add(task)
            automation_id = (task.payload or {}).get("automation_id")
            if automation_id:
                automation = db.get(Automation, automation_id)
                if automation:
                    automation.last_status = task.status
                    automation.last_error = task.error
                    db.add(automation)
            db.commit()

    async def _job_discovery(self, db, task: BackgroundTask) -> dict:
        if task.payload.get("all_sources"):
            sources = db.scalars(select(CompanySource).order_by(CompanySource.company)).all()
        else:
            source = db.get(CompanySource, task.payload.get("source_id"))
            sources = [source] if source else []
        if not sources:
            raise LookupError("company source not found")
        results = []
        total = len(sources)
        for index, source in enumerate(sources, 1):
            results.append(await crawl_company_source(db, source))
            task = db.get(BackgroundTask, task.id)
            if task:
                task.progress = int(index / total * 95)
                db.add(task); db.commit()
        return {"sources": results}

    async def _mail_sync(self, db) -> dict:
        config = get_provider_config(db, "email")
        secret = SecretStore().get(config.secret_ref)
        username = config.config.get("username")
        if not username or not secret:
            raise RuntimeError("163 mailbox credentials are unavailable")
        client = Imap163Client(
            username=username,
            authorization_code=secret,
            host=config.config.get("host", "imap.163.com"),
            port=int(config.config.get("port", 993)),
        )
        model = build_text_model(db)
        result = await sync_mailbox(db, model, client, username)
        db.commit()
        return result

    async def _transcribe(self, db, interview_id: str) -> dict:
        interview = db.get(Interview, interview_id)
        if not interview or not interview.audio_document_id:
            raise LookupError("interview audio not found")
        document = db.get(Document, interview.audio_document_id)
        config = get_provider_config(db, "speech")
        secrets = SecretStore()
        dashscope_key = secrets.get(config.secret_ref)
        oss_secret = secrets.get(config.config.get("oss_secret_ref"))
        if not dashscope_key or not oss_secret:
            raise RuntimeError("Paraformer credentials are unavailable")
        transcription = db.scalar(
            select(TranscriptionJob).where(TranscriptionJob.interview_id == interview.id)
        ) or TranscriptionJob(interview_id=interview.id, status="running")
        transcription.status = "running"
        transcription.attempts += 1
        db.add(transcription)
        db.flush()
        params = transcription.parameters or {}
        transcriber = ParaformerTranscriber(
            ParaformerConfig(
                dashscope_api_key=dashscope_key,
                oss_access_key_id=config.config["oss_access_key_id"],
                oss_access_key_secret=oss_secret,
                oss_endpoint=config.config["oss_endpoint"],
                oss_bucket=config.config["oss_bucket"],
                workspace_id=config.config["dashscope_workspace_id"],
                region_domain=config.config.get("dashscope_region_domain", "cn-beijing.maas.aliyuncs.com"),
                model=config.model or "paraformer-v2",
            )
        )
        try:
            audio_data = await asyncio.to_thread(ObjectStorage().get, document.object_key)
            interview.transcript = await transcriber.transcribe(
                audio_data,
                document.filename,
                language_hints=params.get("language_hints", ["zh", "en"]),
                vocabulary=params.get("vocabulary", []),
                diarization=params.get("diarization", True),
            )
            interview.transcript_confirmed = False
            transcription.provider_task_id = transcriber.task_id
            transcription.status = "succeeded"
            transcription.error = None
            db.add_all([interview, transcription])
            db.commit()
            return {"interview_id": interview.id, "transcript_ready": True}
        except Exception as exc:
            transcription.status = "failed"
            transcription.provider_task_id = transcriber.task_id
            transcription.error = str(exc)[:4000]
            db.add(transcription)
            db.commit()
            raise
