from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import CandidateProfile, CompanySource, Document, JobPosting


EVIDENCE_LABELS = {
    "direct": "推荐关注",
    "partial": "值得尝试",
    "adjacent": "谨慎投入",
    "insufficient": "不建议",
}
EVIDENCE_ORDER = {"direct": 0, "partial": 1, "adjacent": 2, "insufficient": 3}

_INTERNSHIP = re.compile(r"实习|intern(?:ship)?", re.I)
_SOCIAL = re.compile(r"社招|社会招聘|experienced hire", re.I)
_PHD_ONLY = re.compile(r"仅限博士|博士(?:学历)?(?:限定|必须|required)|ph\.?d\.?(?:\s+required)", re.I)
_CAMPUS_2027 = re.compile(r"(?:2027|27届|2027届).{0,12}(?:校招|校园招聘|应届)|(?:校招|校园招聘|应届).{0,12}(?:2027|27届|2027届)", re.I)
_JOB_HINT = re.compile(r"岗位|职位|工程师|开发|算法|产品|运营|设计|研究|job|career|position|engineer|developer", re.I)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_text(value: str) -> str:
    return " ".join(value.split())


def confirmed_2027_campus(title: str, text: str, *, explicit_source: bool = False) -> tuple[bool, str | None]:
    material = normalize_text(f"{title}\n{text}")
    if _INTERNSHIP.search(material):
        return False, "internship"
    if _SOCIAL.search(material):
        return False, "social_recruitment"
    if _PHD_ONLY.search(material):
        return False, "doctorate_only"
    if not explicit_source and not _CAMPUS_2027.search(material):
        return False, "cohort_unconfirmed"
    return True, None


def title_matches_profile(title: str, profile: CandidateProfile | None) -> bool:
    if profile is None or not profile.title_keywords:
        return bool(_JOB_HINT.search(title))
    folded = title.casefold()
    excluded = [word.casefold() for word in profile.excluded_title_keywords if word.strip()]
    if any(word in folded for word in excluded):
        return False
    return any(word.casefold() in folded for word in profile.title_keywords if word.strip())


def analysis_fingerprints(job: JobPosting, profile: CandidateProfile) -> tuple[str, str]:
    content = "\n".join([
        job.company, job.title, job.city or "", job.description,
        str(job.cohort or 2027), job.recruitment_track or "campus", job.batch or "formal",
    ])
    profile_content = "\n".join([
        profile.fingerprint,
        *profile.target_directions,
        *profile.title_keywords,
        *profile.skills,
        *profile.project_evidence,
        *profile.supporting_skills,
    ])
    return sha256_text(content), sha256_text(profile_content)


def evidence_sort_key(item: dict) -> tuple:
    level = item.get("evidence_level") or "insufficient"
    return (
        EVIDENCE_ORDER.get(level, 99),
        -int(item.get("direct_core_count") or 0),
        int(item.get("missing_core_count") or 0),
        -(item.get("first_seen_at") or datetime.min.replace(tzinfo=timezone.utc)).timestamp(),
    )


async def crawl_company_source(db: Session, source: CompanySource) -> dict[str, int | str]:
    """Crawl one public 2027 campus entry page without login or browser automation."""
    source.status = "running"
    source.last_attempted_at = utcnow()
    source.last_error = None
    db.add(source)
    db.commit()
    try:
        async with httpx.AsyncClient(
            timeout=30,
            follow_redirects=True,
            headers={"User-Agent": "FeiCareerAssistant/0.2 (+local user initiated crawl)"},
        ) as client:
            response = await client.get(source.entry_url)
            response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        page_text = normalize_text(soup.get_text(" ", strip=True))[:100_000]
        explicit = bool(_CAMPUS_2027.search(page_text) or source.source_kind == "offerbiu")
        profile = db.scalar(select(CandidateProfile).where(CandidateProfile.confirmed.is_(True)).order_by(CandidateProfile.updated_at.desc()))
        created = updated = rejected = 0
        seen: set[tuple[str, str]] = set()
        for anchor in soup.select("a[href]")[:5000]:
            title = normalize_text(anchor.get_text(" ", strip=True))
            href = urljoin(str(response.url), str(anchor.get("href") or ""))
            parsed = urlparse(href)
            if not title or len(title) > 200 or parsed.scheme not in {"http", "https"}:
                continue
            key = (title.casefold(), href)
            if key in seen:
                continue
            seen.add(key)
            context = normalize_text(anchor.parent.get_text(" ", strip=True) if anchor.parent else title)[:800]
            accepted, _ = confirmed_2027_campus(title, f"{context} {href}", explicit_source=explicit)
            if not accepted or not title_matches_profile(title, profile):
                rejected += 1
                continue
            source_ref = sha256_text(f"{source.id}\n{href}\n{title}")
            job = db.scalar(select(JobPosting).where(JobPosting.source_kind == source.source_kind, JobPosting.source_ref == source_ref))
            if job is None:
                job = JobPosting(
                    company=source.company,
                    title=title,
                    description="JD 尚未补全。请打开官方岗位页后补充完整岗位要求。",
                    source_url=href,
                    city=None,
                    cohort=2027,
                    cohort_status="confirmed",
                    recruitment_track="campus",
                    batch="formal",
                    source_kind=source.source_kind,
                    source_ref=source_ref,
                    jd_status="incomplete",
                    availability_status="active",
                )
                db.add(job)
                created += 1
            else:
                job.last_seen_at = utcnow()
                job.availability_status = "active"
                updated += 1
        source.status = "complete" if created + updated else "empty"
        source.job_count = db.query(JobPosting).filter(JobPosting.source_kind == source.source_kind).count()
        source.incomplete_jd_count = db.query(JobPosting).filter(
            JobPosting.source_kind == source.source_kind,
            JobPosting.jd_status == "incomplete",
        ).count()
        db.add(source)
        db.commit()
        return {"source_id": source.id, "created": created, "updated": updated, "rejected": rejected}
    except Exception as exc:
        db.rollback()
        source = db.get(CompanySource, source.id)
        if source:
            source.status = "failed"
            source.last_error = str(exc)[:2000]
            source.last_attempted_at = utcnow()
            db.add(source)
            db.commit()
        raise


def profile_payload(profile: CandidateProfile) -> dict:
    return {
        "id": profile.id,
        "document_id": profile.document_id,
        "document_version": profile.document_version,
        "fingerprint": profile.fingerprint,
        "degree": profile.degree,
        "job_type": profile.job_type,
        "target_directions": profile.target_directions,
        "title_keywords": profile.title_keywords,
        "excluded_title_keywords": profile.excluded_title_keywords,
        "skills": profile.skills,
        "project_evidence": profile.project_evidence,
        "supporting_skills": profile.supporting_skills,
        "learning_targets": profile.learning_targets,
        "confirmed": profile.confirmed,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }


def resume_fingerprint(document: Document) -> str:
    return sha256_text(f"{document.id}:{document.version}:{document.sha256}:{document.extracted_text or ''}")
