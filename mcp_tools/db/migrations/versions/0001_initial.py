"""Initial schema — members, coverage_snapshots, verifications, cases, callbacks, audit_log.

Written by hand per spec constraint (no autogenerate).

Revision ID: 0001
Revises:
Create Date: 2026-09-27
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # members
    # ------------------------------------------------------------------
    op.create_table(
        "members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("member_id", sa.String(), nullable=False),
        sa.Column("first_name", sa.String(), nullable=False),
        sa.Column("last_name", sa.String(), nullable=False),
        sa.Column("dob", sa.Date(), nullable=True),
        sa.Column("zip", sa.String(10), nullable=True),
        sa.Column("employer_group", sa.String(), nullable=True),
        sa.Column("subscriber_name", sa.String(), nullable=True),
        sa.Column("relationship", sa.String(), nullable=True),
        sa.Column("payer_id", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_members_member_id", "members", ["member_id"], unique=True)

    # ------------------------------------------------------------------
    # coverage_snapshots
    # ------------------------------------------------------------------
    op.create_table(
        "coverage_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", sa.String(), nullable=True),
        sa.Column("member_id", sa.String(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("source", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="unverified"),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('unverified', 'verified', 'discarded')",
            name="ck_coverage_snapshots_status",
        ),
    )
    op.create_index(
        "ix_coverage_snapshots_session_id", "coverage_snapshots", ["session_id"]
    )
    op.create_index(
        "ix_coverage_snapshots_member_id", "coverage_snapshots", ["member_id"]
    )

    # ------------------------------------------------------------------
    # verifications
    # ------------------------------------------------------------------
    op.create_table(
        "verifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", sa.String(), nullable=True),
        sa.Column("member_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="PENDING"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("asked_question_ids", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'PASSED', 'FAILED', 'LOCKED')",
            name="ck_verifications_status",
        ),
    )
    op.create_index("ix_verifications_session_id", "verifications", ["session_id"])
    op.create_index("ix_verifications_member_id", "verifications", ["member_id"])

    # ------------------------------------------------------------------
    # cases  (A-3: missing_fields ARRAY + complete bool)
    # ------------------------------------------------------------------
    op.create_table(
        "cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("case_number", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=True),
        sa.Column("member_id", sa.String(), nullable=True),
        sa.Column(
            "snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("coverage_snapshots.id"),
            nullable=True,
        ),
        sa.Column(
            "verification_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("verifications.id"),
            nullable=True,
        ),
        sa.Column("claim", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("missing_fields", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column(
            "complete", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("status", sa.String(), nullable=False, server_default="NEW"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_cases_case_number", "cases", ["case_number"], unique=True)
    op.create_index("ix_cases_session_id", "cases", ["session_id"])

    # ------------------------------------------------------------------
    # callbacks  (A-1 party-mode decision)
    # ------------------------------------------------------------------
    op.create_table(
        "callbacks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", sa.String(), nullable=True),
        sa.Column("member_id_hash", sa.String(), nullable=True),
        sa.Column("contact_number", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="PENDING"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_callbacks_session_id", "callbacks", ["session_id"])

    # ------------------------------------------------------------------
    # audit_log  (bigserial PK)
    # ------------------------------------------------------------------
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(), nullable=True),
        sa.Column("event", sa.String(), nullable=True),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_audit_log_session_id", "audit_log", ["session_id"])


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("callbacks")
    op.drop_table("cases")
    op.drop_table("verifications")
    op.drop_table("coverage_snapshots")
    op.drop_table("members")
