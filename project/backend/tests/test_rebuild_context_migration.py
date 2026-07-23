"""重构上下文域迁移测试（Task 2）。

覆盖计划 Task 2 验收项与 7.3 节：
- 新增四张表（project_stage_progress / tool_context_links /
  project_learning_insights / migration_ledger）结构与约束。
- ai_jobs 扩展 context_mode / project_phase 并将 project_id 调整为可空。
- 迁移可在当前 head(g8b9c0d1e2f3) 后升级、降级、再次升级。
- 历史 projects/tasks/evaluations/submissions/ai_jobs 记录数不变。
- migration_ledger 幂等唯一约束生效。

注意：现有 Alembic 迁移链存在历史遗留问题（paper_templates 等表缺少
create_table 迁移），全链从 base 升级无法完成。本测试沿用
test_project_design_migration.py 的做法：用父版本 schema 手工建表后 stamp
到父版本，再单独执行新增迁移的升级/降级/再升级，符合计划“每次迁移单独
升级、降级、再次升级”。
"""
from __future__ import annotations

import uuid

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.core.config import settings


PARENT = "g8b9c0d1e2f3"
NEW = "h1a2b3c4d5e6"

# 父版本 legacy 表 schema（仅迁移涉及与计数校验所需的最小列集）。
_LEGACY_PROJECTS_SQL = """
CREATE TABLE projects (
    id VARCHAR(36) NOT NULL,
    title VARCHAR(200) NOT NULL,
    status VARCHAR(20) NOT NULL,
    creator_id VARCHAR(36) NOT NULL,
    is_template BOOLEAN NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (id)
)
"""
_LEGACY_TASKS_SQL = "CREATE TABLE tasks (id VARCHAR(36) NOT NULL, PRIMARY KEY (id))"
_LEGACY_EVALUATIONS_SQL = "CREATE TABLE evaluations (id VARCHAR(36) NOT NULL, PRIMARY KEY (id))"
_LEGACY_SUBMISSIONS_SQL = "CREATE TABLE submissions (id VARCHAR(36) NOT NULL, PRIMARY KEY (id))"

# ai_jobs 旧 schema：project_id NOT NULL，无 context_mode/project_phase。
# 包含 projects 外键与索引，验证 batch_alter_table 保留既有约束。
_LEGACY_AI_JOBS_SQL = """
CREATE TABLE ai_jobs (
    id VARCHAR(36) NOT NULL,
    project_id VARCHAR(36) NOT NULL,
    scene VARCHAR(20) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'CREATED',
    output_type VARCHAR(32) NOT NULL,
    initiated_by VARCHAR(36) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
)
"""


def _make_config(db_path: str, monkeypatch) -> Config:
    """构造指向临时 SQLite 的 Alembic 配置。

    env.py 在运行时会用 ``settings.DATABASE_URL`` 覆盖配置中的 URL，
    因此必须 monkeypatch settings 指向临时库，否则迁移会写到真实开发库。
    """
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{db_path}")
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


def _create_legacy_schema(db_path: str) -> None:
    """以父版本 schema 建立迁移涉及与计数校验所需的表（绕过断裂的全链升级）。"""
    eng = create_engine(f"sqlite:///{db_path}")
    with eng.begin() as conn:
        for ddl in (
            _LEGACY_PROJECTS_SQL,
            _LEGACY_TASKS_SQL,
            _LEGACY_EVALUATIONS_SQL,
            _LEGACY_SUBMISSIONS_SQL,
            _LEGACY_AI_JOBS_SQL,
        ):
            conn.execute(text(ddl))
        conn.execute(
            text("CREATE INDEX ix_ai_jobs_project_id ON ai_jobs (project_id)")
        )
    eng.dispose()


def _seed_legacy_rows(db_path: str) -> dict[str, list[str]]:
    """插入历史记录，用于校验迁移前后数量不变。"""
    eng = create_engine(f"sqlite:///{db_path}")
    ids: dict[str, list[str]] = {}
    with eng.begin() as conn:
        proj_ids = []
        for i in range(2):
            pid = str(uuid.uuid4())
            proj_ids.append(pid)
            conn.execute(
                text(
                    "INSERT INTO projects (id, title, status, creator_id, is_template) "
                    "VALUES (:id, :t, 'DRAFT', :c, 0)"
                ),
                {"id": pid, "t": f"项目{i}", "c": f"teacher-{i}"},
            )
        ids["projects"] = proj_ids

        ajid = str(uuid.uuid4())
        conn.execute(
            text(
                "INSERT INTO ai_jobs (id, project_id, scene, status, output_type, initiated_by) "
                "VALUES (:id, :pid, 'LESSON_PLAN', 'CREATED', 'lesson_plan', :u)"
            ),
            {"id": ajid, "pid": proj_ids[0], "u": "teacher-0"},
        )
        ids["ai_jobs"] = [ajid]

        for tbl in ("tasks", "evaluations", "submissions"):
            tbl_ids = []
            for _ in range(3):
                rid = str(uuid.uuid4())
                conn.execute(text(f"INSERT INTO {tbl} (id) VALUES (:id)"), {"id": rid})
                tbl_ids.append(rid)
            ids[tbl] = tbl_ids
    eng.dispose()
    return ids


def _count(db_path: str, table: str) -> int:
    eng = create_engine(f"sqlite:///{db_path}")
    try:
        with eng.connect() as conn:
            return conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
    except Exception:
        return -1  # 表不存在
    finally:
        eng.dispose()


def _has_tables(db_path: str, tables: set[str]) -> bool:
    eng = create_engine(f"sqlite:///{db_path}")
    existing = set(inspect(eng).get_table_names())
    eng.dispose()
    return tables <= existing


def _columns(db_path: str, table: str) -> set[str]:
    eng = create_engine(f"sqlite:///{db_path}")
    cols = {c["name"] for c in inspect(eng).get_columns(table)}
    eng.dispose()
    return cols


def _column_nullable(db_path: str, table: str, column: str) -> bool:
    eng = create_engine(f"sqlite:///{db_path}")
    col = next(c for c in inspect(eng).get_columns(table) if c["name"] == column)
    eng.dispose()
    return bool(col.get("nullable", True))


class TestRebuildContextMigration:
    """验证 h1a2b3c4d5e6 迁移可升级/降级/再升级，保留历史数据并建立新结构。"""

    def test_upgrade_creates_new_tables_and_preserves_legacy_rows(self, tmp_path, monkeypatch):
        db_path = str(tmp_path / "up.db")
        cfg = _make_config(db_path, monkeypatch)
        _create_legacy_schema(db_path)
        command.stamp(cfg, PARENT)
        _seed_legacy_rows(db_path)

        before = {
            t: _count(db_path, t)
            for t in ("projects", "tasks", "evaluations", "submissions", "ai_jobs")
        }

        command.upgrade(cfg, NEW)

        # 历史记录数不变
        after = {t: _count(db_path, t) for t in before}
        assert after == before
        # 四张新表存在
        assert _has_tables(
            db_path,
            {
                "project_stage_progress",
                "tool_context_links",
                "project_learning_insights",
                "migration_ledger",
            },
        )
        # ai_jobs 新列存在
        assert {"context_mode", "project_phase"} <= _columns(db_path, "ai_jobs")
        # ai_jobs.project_id 已可空
        assert _column_nullable(db_path, "ai_jobs", "project_id") is True

    def test_ai_jobs_project_id_accepts_null_after_upgrade(self, tmp_path, monkeypatch):
        db_path = str(tmp_path / "null.db")
        cfg = _make_config(db_path, monkeypatch)
        _create_legacy_schema(db_path)
        command.stamp(cfg, PARENT)

        command.upgrade(cfg, NEW)

        eng = create_engine(f"sqlite:///{db_path}")
        with eng.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO ai_jobs (id, project_id, scene, status, output_type, "
                    "initiated_by, context_mode) "
                    "VALUES (:id, NULL, 'LESSON_PLAN', 'CREATED', 'lesson_plan', :u, 'INDEPENDENT')"
                ),
                {"id": str(uuid.uuid4()), "u": "teacher-x"},
            )
        eng.dispose()
        assert _count(db_path, "ai_jobs") == 1

    def test_migration_ledger_idempotent_unique_constraint(self, tmp_path, monkeypatch):
        """同源 (source_table, source_id) 重复写入应被唯一约束拒绝。"""
        db_path = str(tmp_path / "ledger.db")
        cfg = _make_config(db_path, monkeypatch)
        _create_legacy_schema(db_path)
        command.stamp(cfg, PARENT)
        command.upgrade(cfg, NEW)

        eng = create_engine(f"sqlite:///{db_path}")
        with eng.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO migration_ledger (id, batch_id, source_table, source_id, "
                    "target_table, status, executed_at) "
                    "VALUES (:id, 'b1', 'evaluations', 'src-1', 'evaluation_records', "
                    "'SUCCESS', CURRENT_TIMESTAMP)"
                ),
                {"id": str(uuid.uuid4())},
            )
        with pytest.raises(Exception):
            with eng.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO migration_ledger (id, batch_id, source_table, source_id, "
                        "target_table, status, executed_at) "
                        "VALUES (:id, 'b1', 'evaluations', 'src-1', 'evaluation_records', "
                        "'SUCCESS', CURRENT_TIMESTAMP)"
                    ),
                    {"id": str(uuid.uuid4())},
                )
        eng.dispose()

    def test_downgrade_reupgrade_consistent(self, tmp_path, monkeypatch):
        db_path = str(tmp_path / "cycle.db")
        cfg = _make_config(db_path, monkeypatch)
        _create_legacy_schema(db_path)
        command.stamp(cfg, PARENT)
        _seed_legacy_rows(db_path)

        # 升级
        command.upgrade(cfg, NEW)
        assert _has_tables(db_path, {"project_stage_progress", "migration_ledger"})

        # 降级回父版本
        command.downgrade(cfg, PARENT)
        assert not _has_tables(
            db_path,
            {
                "project_stage_progress",
                "tool_context_links",
                "project_learning_insights",
                "migration_ledger",
            },
        )
        assert {"context_mode", "project_phase"}.isdisjoint(_columns(db_path, "ai_jobs"))
        assert _column_nullable(db_path, "ai_jobs", "project_id") is False
        # 历史记录仍保留
        assert _count(db_path, "projects") == 2
        assert _count(db_path, "ai_jobs") == 1

        # 再次升级
        command.upgrade(cfg, NEW)
        assert _has_tables(db_path, {"project_stage_progress", "migration_ledger"})
        assert {"context_mode", "project_phase"} <= _columns(db_path, "ai_jobs")
        assert _column_nullable(db_path, "ai_jobs", "project_id") is True
        assert _count(db_path, "projects") == 2
        assert _count(db_path, "ai_jobs") == 1

    def test_empty_database_upgrade_succeeds(self, tmp_path, monkeypatch):
        db_path = str(tmp_path / "empty.db")
        cfg = _make_config(db_path, monkeypatch)
        _create_legacy_schema(db_path)
        command.stamp(cfg, PARENT)

        command.upgrade(cfg, NEW)

        assert _has_tables(
            db_path,
            {
                "project_stage_progress",
                "tool_context_links",
                "project_learning_insights",
                "migration_ledger",
            },
        )
        for t in (
            "project_stage_progress",
            "tool_context_links",
            "project_learning_insights",
            "migration_ledger",
        ):
            assert _count(db_path, t) == 0

    def test_new_domain_data_survives_only_after_upgrade(self, tmp_path, monkeypatch):
        """升级后写入的阶段数据在降级时随表移除，再次升级后表为空。"""
        db_path = str(tmp_path / "data.db")
        cfg = _make_config(db_path, monkeypatch)
        _create_legacy_schema(db_path)
        command.stamp(cfg, PARENT)
        command.upgrade(cfg, NEW)

        eng = create_engine(f"sqlite:///{db_path}")
        with eng.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO project_stage_progress (id, project_id, phase, status) "
                    "VALUES (:id, :pid, 'DIAGNOSIS', 'NOT_STARTED')"
                ),
                {"id": str(uuid.uuid4()), "pid": str(uuid.uuid4())},
            )
        eng.dispose()
        assert _count(db_path, "project_stage_progress") == 1

        # 降级：新表连同数据移除
        command.downgrade(cfg, PARENT)
        assert _count(db_path, "project_stage_progress") == -1

        # 再次升级：表恢复为空
        command.upgrade(cfg, NEW)
        assert _count(db_path, "project_stage_progress") == 0
