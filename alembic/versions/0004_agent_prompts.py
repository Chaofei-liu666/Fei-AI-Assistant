"""Agent prompt overrides.

Revision ID: 0004
Revises: 0003
"""
from alembic import op

from fei_assistant import household_models  # noqa: F401
from fei_assistant import mail_models  # noqa: F401
from fei_assistant import models  # noqa: F401
from fei_assistant import run_models  # noqa: F401
from fei_assistant.db import Base


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    op.drop_table("agent_prompts")
