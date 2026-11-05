"""真实 PostgreSQL 上的迁移与约束测试（只在隔离 test 库运行）。"""

from __future__ import annotations

import uuid

import pytest
from alembic import command
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from tests.integration.db_utils import alembic_config, sync_database_url, upgrade_to_head

EXPECTED_TABLES = {
    "users",
    "projects",
    "environments",
    "api_definitions",
    "cases",
    "runs",
    "step_results",
    "run_events",
    "run_outbox",
    "alembic_version",
}


def test_migration_creates_all_tables_constraints_and_indexes() -> None:
    upgrade_to_head()
    engine = create_engine(sync_database_url())
    try:
        inspector = inspect(engine)
        assert set(inspector.get_table_names()) >= EXPECTED_TABLES

        environment_unique = inspector.get_unique_constraints("environments")
        assert any(item["column_names"] == ["project_id", "name"] for item in environment_unique)
        run_unique = inspector.get_unique_constraints("runs")
        assert any(item["column_names"] == ["project_id", "idempotency_key"] for item in run_unique)
        run_indexes = {item["name"] for item in inspector.get_indexes("runs")}
        assert "ix_runs_project_created" in run_indexes
        assert "ix_runs_status_created" in run_indexes

        foreign_keys = {
            (table, tuple(fk["constrained_columns"]))
            for table in EXPECTED_TABLES - {"alembic_version"}
            for fk in inspector.get_foreign_keys(table)
        }
        assert ("projects", ("owner_id",)) in foreign_keys
        assert ("runs", ("project_id",)) in foreign_keys
        assert ("step_results", ("run_id",)) in foreign_keys
        assert ("run_events", ("run_id",)) in foreign_keys
        assert ("run_outbox", ("run_id",)) in foreign_keys

        # 外键列存在索引（复合唯一约束的前缀索引也算）。
        step_index_columns = {
            tuple(index["column_names"]) for index in inspector.get_indexes("step_results")
        }
        assert ("run_id",) in step_index_columns
    finally:
        engine.dispose()


def test_upgrade_is_idempotent_and_downgrade_roundtrip() -> None:
    upgrade_to_head()
    upgrade_to_head()
    config = alembic_config()
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    engine = create_engine(sync_database_url())
    try:
        assert "runs" in inspect(engine).get_table_names()
    finally:
        engine.dispose()


def test_duplicate_idempotency_key_and_step_position_rejected() -> None:
    upgrade_to_head()
    engine = create_engine(sync_database_url())
    project_id = uuid.uuid4()
    case_id = uuid.uuid4()
    environment_id = uuid.uuid4()
    run_id = uuid.uuid4()
    key = uuid.uuid4()
    try:
        with engine.begin() as connection:
            user_id = connection.execute(
                text(
                    "INSERT INTO users (id, username, password_hash) "
                    "VALUES (:id, 'constraint_user', 'hash') RETURNING id"
                ),
                {"id": uuid.uuid4()},
            ).scalar_one()
            connection.execute(
                text(
                    "INSERT INTO projects (id, owner_id, name, description) "
                    "VALUES (:id, :owner, '项目', '')"
                ),
                {"id": project_id, "owner": user_id},
            )
            connection.execute(
                text(
                    "INSERT INTO cases (id, project_id, name, description, steps, version) "
                    "VALUES (:id, :project, '用例', '', '[]'::jsonb, 1)"
                ),
                {"id": case_id, "project": project_id},
            )
            connection.execute(
                text(
                    "INSERT INTO environments (id, project_id, name, base_url, "
                    "config_ciphertext, version) VALUES (:id, :project, '环境', "
                    "'http://demo-api:8001', 'cipher', 1)"
                ),
                {"id": environment_id, "project": project_id},
            )
            connection.execute(
                text(
                    "INSERT INTO runs (id, project_id, case_id, environment_id, case_name, "
                    "case_version, environment_name, environment_version, status, "
                    "snapshot_ciphertext, idempotency_key, request_fingerprint) VALUES "
                    "(:id, :project, :case, :environment, '用例', 1, '环境', 1, 'queued', "
                    "'cipher', :key, 'fingerprint')"
                ),
                {
                    "id": run_id,
                    "project": project_id,
                    "case": case_id,
                    "environment": environment_id,
                    "key": key,
                },
            )

        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO runs (id, project_id, case_id, environment_id, case_name, "
                    "case_version, environment_name, environment_version, status, "
                    "snapshot_ciphertext, idempotency_key, request_fingerprint) VALUES "
                    "(:id, :project, :case, :environment, '用例', 1, '环境', 1, 'queued', "
                    "'cipher', :key, 'fingerprint')"
                ),
                {
                    "id": uuid.uuid4(),
                    "project": project_id,
                    "case": case_id,
                    "environment": environment_id,
                    "key": key,
                },
            )

        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO step_results (id, run_id, position, name, status) "
                    "VALUES (:id, :run, 1, '步骤', 'pending')"
                ),
                {"id": uuid.uuid4(), "run": run_id},
            )
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO step_results (id, run_id, position, name, status) "
                    "VALUES (:id, :run, 1, '重复', 'pending')"
                ),
                {"id": uuid.uuid4(), "run": run_id},
            )
    finally:
        engine.dispose()


def test_run_event_ids_increment_and_created_at_is_aware() -> None:
    upgrade_to_head()
    engine = create_engine(sync_database_url())
    run_id = uuid.uuid4()
    try:
        with engine.begin() as connection:
            user_id = connection.execute(
                text(
                    "INSERT INTO users (id, username, password_hash) "
                    "VALUES (:id, 'event_user', 'hash') RETURNING id"
                ),
                {"id": uuid.uuid4()},
            ).scalar_one()
            project_id = connection.execute(
                text(
                    "INSERT INTO projects (id, owner_id, name, description) "
                    "VALUES (:id, :owner, '项目', '') RETURNING id"
                ),
                {"id": uuid.uuid4(), "owner": user_id},
            ).scalar_one()
            case_id = connection.execute(
                text(
                    "INSERT INTO cases (id, project_id, name, description, steps, version) "
                    "VALUES (:id, :project, '用例', '', '[]'::jsonb, 1) RETURNING id"
                ),
                {"id": uuid.uuid4(), "project": project_id},
            ).scalar_one()
            environment_id = connection.execute(
                text(
                    "INSERT INTO environments (id, project_id, name, base_url, "
                    "config_ciphertext, version) VALUES (:id, :project, '环境', "
                    "'http://demo-api:8001', 'cipher', 1) RETURNING id"
                ),
                {"id": uuid.uuid4(), "project": project_id},
            ).scalar_one()
            connection.execute(
                text(
                    "INSERT INTO runs (id, project_id, case_id, environment_id, case_name, "
                    "case_version, environment_name, environment_version, status, "
                    "snapshot_ciphertext, idempotency_key, request_fingerprint) VALUES "
                    "(:id, :project, :case, :environment, '用例', 1, '环境', 1, 'queued', "
                    "'cipher', :key, 'fingerprint')"
                ),
                {
                    "id": run_id,
                    "project": project_id,
                    "case": case_id,
                    "environment": environment_id,
                    "key": uuid.uuid4(),
                },
            )
            first_id = connection.execute(
                text(
                    "INSERT INTO run_events (run_id, event_type, payload_safe) "
                    "VALUES (:run, 'run.queued', '{}'::jsonb) RETURNING id, created_at"
                ),
                {"run": run_id},
            ).one()
            second_id = connection.execute(
                text(
                    "INSERT INTO run_events (run_id, event_type, payload_safe) "
                    "VALUES (:run, 'run.started', '{}'::jsonb) RETURNING id"
                ),
                {"run": run_id},
            ).scalar_one()
        assert second_id > first_id[0]
        assert first_id[1].tzinfo is not None
    finally:
        engine.dispose()
