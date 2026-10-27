"""Initial Fei business schema.

Revision ID: 0001
Revises:
"""
from alembic import op

from fei_assistant.db import Base
from fei_assistant import models  # noqa: F401


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind(), checkfirst=True)
