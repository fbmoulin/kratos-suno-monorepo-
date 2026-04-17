"""initial schema - cached_dna and generation_log

Revision ID: 001_initial
Revises:
Create Date: 2026-04-17

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cached_dna",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("cache_key", sa.String(128), nullable=False),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("prompt_version", sa.String(50), nullable=False),
        sa.Column("model_used", sa.String(100), nullable=False),
        sa.Column("dna_json", sa.JSON, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_cached_dna_cache_key", "cached_dna", ["cache_key"], unique=True)
    op.create_index("ix_cached_dna_subject", "cached_dna", ["subject"])

    op.create_table(
        "generation_log",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("prompt_version", sa.String(50), nullable=False),
        sa.Column("success", sa.Boolean, nullable=False),
        sa.Column("error_type", sa.String(100), nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_generation_log_source", "generation_log", ["source"])
    op.create_index("ix_generation_log_created_at", "generation_log", ["created_at"])


def downgrade() -> None:
    op.drop_table("generation_log")
    op.drop_table("cached_dna")
