from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from fei_assistant.api.career import confirm_review, observe_application
from fei_assistant.career import analysis_fingerprints, confirmed_2027_campus, evidence_sort_key
from fei_assistant.db import Base
from fei_assistant.models import Application, ApplicationEvent, BrowserReview, CandidateProfile, JobPosting
from fei_assistant.schemas import BrowserReviewConfirm, BrowserReviewObservation


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.mark.parametrize(
    ("title", "text", "accepted", "reason"),
    [
        ("后端开发工程师", "2027 届校园招聘正式岗位", True, None),
        ("后端开发实习生", "2027 届校园招聘", False, "internship"),
        ("资深后端开发", "2027 社会招聘", False, "social_recruitment"),
        ("算法研究员", "2027 届校招，仅限博士", False, "doctorate_only"),
        ("算法研究员", "2027 届校招，硕士或博士均可", True, None),
        ("后端开发工程师", "普通招聘页面", False, "cohort_unconfirmed"),
    ],
)
def test_2027_campus_filter(title: str, text: str, accepted: bool, reason: str | None) -> None:
    assert confirmed_2027_campus(title, text) == (accepted, reason)


def test_analysis_fingerprint_changes_with_job_or_profile() -> None:
    job = JobPosting(company="Example", title="工程师", description="Python", cohort=2027)
    profile = CandidateProfile(
        document_id="doc-1", document_version=1, fingerprint="a" * 64,
        target_directions=["后端"], title_keywords=["工程师"], skills=["Python"],
        project_evidence=["服务项目"], supporting_skills=[], excluded_title_keywords=[], learning_targets=[],
    )
    original = analysis_fingerprints(job, profile)
    job.description = "Python 与 PostgreSQL"
    assert analysis_fingerprints(job, profile)[0] != original[0]
    job.description = "Python"
    profile.skills = ["Python", "PostgreSQL"]
    assert analysis_fingerprints(job, profile)[1] != original[1]


def test_evidence_sort_is_not_percentage_based() -> None:
    now = datetime.now(timezone.utc)
    rows = [
        {"evidence_level": "partial", "direct_core_count": 9, "missing_core_count": 0, "first_seen_at": now},
        {"evidence_level": "direct", "direct_core_count": 1, "missing_core_count": 2, "first_seen_at": now},
    ]
    assert sorted(rows, key=evidence_sort_key)[0]["evidence_level"] == "direct"


def test_browser_observation_requires_confirmation_and_cannot_lower_stage(db: Session) -> None:
    job = JobPosting(company="Example", title="工程师", description="2027 届校招")
    db.add(job); db.flush()
    application = Application(job_id=job.id, status="interview", company_name="Example", job_title="工程师")
    db.add(application); db.commit()

    observed = observe_application(application.id, BrowserReviewObservation(
        operation_id="operation-1234", application_id=application.id,
        page_url="https://careers.example.com/status", observed_status="screening",
        confidence=.95, page_title="申请进度", visible_text="筛选中",
        screenshot_sha256="a" * 64,
    ), db)
    db.refresh(application)
    assert application.status == "interview"
    assert observed["requires_user_action"] is True
    assert db.scalars(select(ApplicationEvent)).all() == []

    with pytest.raises(HTTPException) as error:
        confirm_review(observed["id"], BrowserReviewConfirm(status="screening"), db)
    assert error.value.status_code == 409
    review = db.get(BrowserReview, observed["id"])
    assert review is not None and review.confirmed is False
