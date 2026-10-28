"""Household inventory, mail event store and run steps.

Revision ID: 0003
Revises: 0002
"""
from alembic import op

from fei_assistant import household_models  # noqa: F401
from fei_assistant import mail_models  # noqa: F401
from fei_assistant import models  # noqa: F401
from fei_assistant import run_models  # noqa: F401
from fei_assistant.db import Base


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    op.drop_table("run_steps")
    op.drop_table("mail_events")
    op.drop_table("item_events")
    op.drop_table("household_items")
