"""user_session persistent table

Revision ID: 003_user_session
Revises: 002_saved_prompt
Create Date: 2026-04-17

W1-B: Adds a durable session table to persist Spotify tokens across
backend restarts. Hydrates the in-memory SessionStore on cache miss.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "003_user_session"
down_revision: Union[str, None] = "002_saved_prompt"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_session",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("session_id", sa.String(64), nullable=False),
        sa.Column("spotify_user_id", sa.String(100), nullable=True),
        sa.Column("access_token", sa.String(500), nullable=False),
        sa.Column("refresh_token", sa.String(500), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_user_session_session_id",
        "user_session",
        ["session_id"],
        unique=True,
    )
    op.create_index(
        "ix_user_session_spotify_user_id",
        "user_session",
        ["spotify_user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_session_spotify_user_id", table_name="user_session")
    op.drop_index("ix_user_session_session_id", table_name="user_session")
    op.drop_table("user_session")
