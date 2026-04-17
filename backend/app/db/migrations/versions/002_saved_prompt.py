"""add saved_prompt table

Revision ID: 002_saved_prompt
Revises: 001_initial
Create Date: 2026-04-17

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "002_saved_prompt"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "saved_prompt",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("session_id", sa.String(128), nullable=False),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("sonic_dna", sa.JSON, nullable=False),
        sa.Column("variants", sa.JSON, nullable=False),
        sa.Column("lyric_template", sa.String(4000), nullable=False),
        sa.Column("user_note", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_saved_prompt_session_id", "saved_prompt", ["session_id"])
    op.create_index("ix_saved_prompt_created_at", "saved_prompt", ["created_at"])


def downgrade() -> None:
    op.drop_table("saved_prompt")
