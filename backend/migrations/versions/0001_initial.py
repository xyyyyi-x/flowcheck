"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username", sa.String(length=32), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )

    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name="fk_projects_owner_id_users", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_projects"),
    )
    op.create_index("ix_projects_owner_id", "projects", ["owner_id"])

    op.create_table(
        "environments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("base_url", sa.String(length=2048), nullable=False),
        sa.Column("config_ciphertext", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
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
        sa.CheckConstraint("version >= 1", name="ck_environments_version_positive"),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_environments_project_id_projects",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_environments"),
        sa.UniqueConstraint("project_id", "name", name="uq_environments_project_name"),
    )
    op.create_index("ix_environments_project_id", "environments", ["project_id"])

    op.create_table(
        "api_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("path", sa.String(length=2048), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column(
            "parameters",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("request_body_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_api_definitions_project_id_projects",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_api_definitions"),
        sa.UniqueConstraint(
            "project_id", "method", "path", name="uq_api_definitions_project_method_path"
        ),
    )
    op.create_index("ix_api_definitions_project_id", "api_definitions", ["project_id"])

    op.create_table(
        "cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("steps", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
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
        sa.CheckConstraint("version >= 1", name="ck_cases_version_positive"),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_cases_project_id_projects",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_cases"),
    )
    op.create_index("ix_cases_project_id", "cases", ["project_id"])

    op.create_table(
        "runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("environment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_name", sa.String(length=80), nullable=False),
        sa.Column("case_version", sa.Integer(), nullable=False),
        sa.Column("environment_name", sa.String(length=80), nullable=False),
        sa.Column("environment_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("snapshot_ciphertext", sa.Text(), nullable=False),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("execution_token", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=40), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued','running','passed','failed','error','interrupted')",
            name="ck_runs_status_valid",
        ),
        sa.ForeignKeyConstraint(
            ["case_id"], ["cases.id"], name="fk_runs_case_id_cases", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["environment_id"],
            ["environments.id"],
            name="fk_runs_environment_id_environments",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name="fk_runs_project_id_projects", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_runs"),
        sa.UniqueConstraint("project_id", "idempotency_key", name="uq_runs_project_idempotency"),
    )
    op.create_index("ix_runs_case_id", "runs", ["case_id"])
    op.create_index("ix_runs_environment_id", "runs", ["environment_id"])
    op.create_index("ix_runs_status_created", "runs", ["status", "created_at"])
    op.create_index(
        "ix_runs_project_created",
        "runs",
        ["project_id", sa.text("created_at DESC"), sa.text("id DESC")],
    )

    op.create_table(
        "step_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("elapsed_ms", sa.Integer(), nullable=True),
        sa.Column("request_safe", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("response_safe", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "assertions_safe",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "extracts_safe",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("error_code", sa.String(length=40), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "position >= 1 AND position <= 20", name="ck_step_results_position_range"
        ),
        sa.CheckConstraint(
            "status IN ('pending','running','passed','failed','error','skipped')",
            name="ck_step_results_status_valid",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"], name="fk_step_results_run_id_runs", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_step_results"),
        sa.UniqueConstraint("run_id", "position", name="uq_step_results_run_position"),
    )
    op.create_index("ix_step_results_run_id", "step_results", ["run_id"])

    op.create_table(
        "run_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column(
            "payload_safe",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"], name="fk_run_events_run_id_runs", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_run_events"),
    )
    op.create_index("ix_run_events_run_id_id", "run_events", ["run_id", "id"])

    op.create_table(
        "run_outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_error_code", sa.String(length=40), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("attempt_count >= 0", name="ck_run_outbox_attempt_count_non_negative"),
        sa.CheckConstraint(
            "status IN ('pending','sent','abandoned')", name="ck_run_outbox_status_valid"
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"], name="fk_run_outbox_run_id_runs", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_run_outbox"),
        sa.UniqueConstraint("run_id", name="uq_run_outbox_run_id"),
    )


def downgrade() -> None:
    op.drop_table("run_outbox")
    op.drop_index("ix_run_events_run_id_id", table_name="run_events")
    op.drop_table("run_events")
    op.drop_index("ix_step_results_run_id", table_name="step_results")
    op.drop_table("step_results")
    op.drop_index("ix_runs_project_created", table_name="runs")
    op.drop_index("ix_runs_status_created", table_name="runs")
    op.drop_index("ix_runs_environment_id", table_name="runs")
    op.drop_index("ix_runs_case_id", table_name="runs")
    op.drop_table("runs")
    op.drop_index("ix_cases_project_id", table_name="cases")
    op.drop_table("cases")
    op.drop_index("ix_api_definitions_project_id", table_name="api_definitions")
    op.drop_table("api_definitions")
    op.drop_index("ix_environments_project_id", table_name="environments")
    op.drop_table("environments")
    op.drop_index("ix_projects_owner_id", table_name="projects")
    op.drop_table("projects")
    op.drop_table("users")
