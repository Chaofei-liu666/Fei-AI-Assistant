"""Native Fei career platform.

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

from fei_assistant.db import Base
from fei_assistant import models  # noqa: F401


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _add(table: str, column: sa.Column) -> None:
    inspector = sa.inspect(op.get_bind())
    existing = {item["name"] for item in inspector.get_columns(table)}
    if column.name not in existing:
        op.add_column(table, column)


def upgrade() -> None:
    # New owned tables are created from Fei metadata. Existing tables are
    # extended below because SQLAlchemy create_all never mutates them.
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)

    for column in (
        sa.Column("city", sa.String(120), nullable=True),
        sa.Column("cohort", sa.Integer(), nullable=False, server_default="2027"),
        sa.Column("cohort_status", sa.String(30), nullable=False, server_default="confirmed"),
        sa.Column("recruitment_track", sa.String(30), nullable=False, server_default="campus"),
        sa.Column("batch", sa.String(30), nullable=False, server_default="formal"),
        sa.Column("source_kind", sa.String(50), nullable=False, server_default="manual"),
        sa.Column("source_ref", sa.String(500), nullable=True),
        sa.Column("jd_status", sa.String(30), nullable=False, server_default="complete"),
        sa.Column("availability_status", sa.String(30), nullable=False, server_default="active"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ):
        _add("job_postings", column)

    for column in (
        sa.Column("evidence_level", sa.String(20), nullable=False, server_default="insufficient"),
        sa.Column("analysis_version", sa.String(40), nullable=False, server_default="career-evidence-v1"),
        sa.Column("content_fingerprint", sa.String(64), nullable=False, server_default=""),
        sa.Column("profile_fingerprint", sa.String(64), nullable=False, server_default=""),
        sa.Column("direct_core_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("missing_core_count", sa.Integer(), nullable=False, server_default="0"),
    ):
        _add("job_analyses", column)

    for column in (
        sa.Column("company_name", sa.String(200), nullable=True),
        sa.Column("job_title", sa.String(200), nullable=True),
        sa.Column("record_url", sa.String(2000), nullable=True),
        sa.Column("source", sa.String(40), nullable=False, server_default="manual"),
    ):
        _add("applications", column)

    _add("application_events", sa.Column("evidence", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    _add("interviews", sa.Column("application_id", sa.String(36), nullable=True))
    _add("interviews", sa.Column("job_title", sa.String(200), nullable=True))


def downgrade() -> None:
    # Data-preserving downgrade: new career records are intentionally retained.
    pass
