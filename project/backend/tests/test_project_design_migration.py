"""项目设计领域迁移回归测试。

覆盖计划 7.3 节与 Task 1 验收项：
- 每次迁移单独升级、降级、再次升级。
- 升级前后核心表记录数一致。
- 历史项目保持草稿（review_status 默认枚举 name 'DRAFT'），不伪造新字段。
- 新增非空约束前提供安全默认（review_status server_default='DRAFT'，
  与 SAEnum(ReviewStatus) 按 name 存储一致；若误用 value 'draft' 会导致
  历史行 ORM 加载时 LookupError）。

注意：现有 Alembic 迁移链存在历史遗留问题（paper_templates 等表缺少
create_table 迁移），全链从 base 升级无法完成；测试套件通过
`Base.metadata.create_all` 建表绕过该问题。本测试聚焦新增迁移
`f1a2b3c4d5e6` 本身的可逆性与数据一致性，使用 `stamp` 将库标记到父版本后
单独执行新增迁移的升级/降级/再升级，符合计划"每次迁移单独升级、降级、再次升级"。
"""
from __future__ import annotations

import uuid

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.enums import ReviewStatus
from app.models.project import Project


PARENT = "e3a1b2c4d5e6"
NEW = "f1a2b3c4d5e6"

# 父版本 projects 表的旧 schema（与初始迁移一致，无新增列）。
_OLD_PROJECTS_SQL = """
CREATE TABLE projects (
    id VARCHAR(36) NOT NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    cover_image_url VARCHAR(500),
    status VARCHAR(20) NOT NULL,
    creator_id VARCHAR(36) NOT NULL,
    school_id VARCHAR(36),
    grade VARCHAR(20),
    start_date DATE,
    end_date DATE,
    is_template BOOLEAN NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (id)
)
"""


def _make_config(db_path: str, monkeypatch) -> Config:
    """构造指向临时 SQLite 的 Alembic 配置。

    env.py 在运行时会用 `settings.DATABASE_URL` 覆盖配置中的 URL，
    因此必须 monkeypatch settings 指向临时库，否则迁移会写到真实开发库。
    """
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{db_path}")
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


def _create_old_projects(db_path: str) -> None:
    """以父版本 schema 创建 projects 表（绕过断裂的全链升级）。"""
    eng = create_engine(f"sqlite:///{db_path}")
    with eng.begin() as conn:
        conn.execute(text(_OLD_PROJECTS_SQL))
    eng.dispose()


def _seed_projects(db_path: str, statuses: list[str]) -> list[str]:
    """插入历史项目行。

    `statuses` 须传枚举 *name*（如 'DRAFT'、'ACTIVE'），与 Project.status 列
    SAEnum(ProjectStatus) 按 name 存储一致；传 value（'draft'）会导致后续
    ORM 加载抛 LookupError。
    """
    eng = create_engine(f"sqlite:///{db_path}")
    ids = []
    with eng.begin() as conn:
        for i, st in enumerate(statuses):
            pid = str(uuid.uuid4())
            ids.append(pid)
            conn.execute(text(
                "INSERT INTO projects (id, title, status, creator_id, is_template) "
                "VALUES (:id, :t, :s, :c, 0)"
            ), {"id": pid, "t": f"项目{i}", "s": st, "c": f"teacher-{i}"})
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


def _has_columns(db_path: str, table: str, cols: set[str]) -> bool:
    eng = create_engine(f"sqlite:///{db_path}")
    inspector = inspect(eng)
    existing = {c["name"] for c in inspector.get_columns(table)}
    eng.dispose()
    return cols <= existing


def _has_tables(db_path: str, tables: set[str]) -> bool:
    eng = create_engine(f"sqlite:///{db_path}")
    inspector = inspect(eng)
    existing = set(inspector.get_table_names())
    eng.dispose()
    return tables <= existing


class TestProjectDesignMigration:
    """验证 add_project_design_domain 迁移可升级、降级、再次升级且记录一致。"""

    def test_upgrade_downgrade_reupgrade_record_counts_consistent(self, tmp_path, monkeypatch):
        db_path = str(tmp_path / "migr.db")
        cfg = _make_config(db_path, monkeypatch)

        # 1) 以父版本 schema 建表，stamp 到父版本，插入历史数据
        _create_old_projects(db_path)
        command.stamp(cfg, PARENT)
        _seed_projects(db_path, ["DRAFT", "ACTIVE", "COMPLETED"])
        assert _count(db_path, "projects") == 3

        # 2) 升级到新版本
        command.upgrade(cfg, NEW)

        assert _count(db_path, "projects") == 3  # 核心表记录数不变
        # 新表存在且为空（未伪造数据）
        assert _count(db_path, "project_problems") == 0
        assert _count(db_path, "subject_contributions") == 0
        assert _count(db_path, "learning_goals") == 0
        assert _count(db_path, "evaluation_indicators") == 0
        assert _count(db_path, "evidence_plans") == 0
        # 新列存在
        assert _has_columns(db_path, "projects", {"project_type", "core_subject_id", "review_status", "data_origin"})
        # 新表存在
        assert _has_tables(db_path, {
            "project_problems", "subject_contributions", "learning_goals",
            "evaluation_indicators", "evidence_plans",
        })

        # 历史项目 review_status 默认枚举 name 'DRAFT'（SAEnum 按 name 存储），
        # 不伪造其他新字段（project_type/core_subject_id/data_origin 均为 NULL）。
        eng = create_engine(f"sqlite:///{db_path}")
        with eng.connect() as conn:
            rows = conn.execute(text(
                "SELECT review_status, project_type, core_subject_id, data_origin FROM projects"
            )).fetchall()
            for r in rows:
                assert r[0] == "DRAFT"
                assert r[1] is None
                assert r[2] is None
                assert r[3] is None
        eng.dispose()

        # 3) 降级回父版本
        command.downgrade(cfg, PARENT)

        assert _count(db_path, "projects") == 3  # 记录数仍不变
        # 新表已移除
        assert _count(db_path, "project_problems") == -1
        assert _count(db_path, "subject_contributions") == -1
        assert _count(db_path, "learning_goals") == -1
        assert _count(db_path, "evaluation_indicators") == -1
        assert _count(db_path, "evidence_plans") == -1
        # 新列已移除
        assert not _has_columns(db_path, "projects", {"review_status"})

        # 4) 再次升级
        command.upgrade(cfg, NEW)
        assert _count(db_path, "projects") == 3
        assert _count(db_path, "project_problems") == 0
        assert _has_columns(db_path, "projects", {"review_status", "data_origin"})
        # 与首次升级结果一致
        eng = create_engine(f"sqlite:///{db_path}")
        with eng.connect() as conn:
            rows = conn.execute(text(
                "SELECT review_status FROM projects"
            )).fetchall()
            for r in rows:
                assert r[0] == "DRAFT"
        eng.dispose()

    def test_empty_database_upgrade_succeeds(self, tmp_path, monkeypatch):
        """空库（无历史数据）升级新增迁移成功。"""
        db_path = str(tmp_path / "empty.db")
        cfg = _make_config(db_path, monkeypatch)
        _create_old_projects(db_path)
        command.stamp(cfg, PARENT)

        command.upgrade(cfg, NEW)

        assert _has_tables(db_path, {
            "project_problems", "subject_contributions", "learning_goals",
            "evaluation_indicators", "evidence_plans",
        })
        assert _count(db_path, "projects") == 0

    def test_historical_project_status_preserved(self, tmp_path, monkeypatch):
        """历史项目的 status 字段不被迁移篡改。"""
        db_path = str(tmp_path / "hist.db")
        cfg = _make_config(db_path, monkeypatch)
        _create_old_projects(db_path)
        command.stamp(cfg, PARENT)
        statuses = ["DRAFT", "ACTIVE", "COMPLETED", "ARCHIVED"]
        ids = _seed_projects(db_path, statuses)

        command.upgrade(cfg, NEW)

        eng = create_engine(f"sqlite:///{db_path}")
        with eng.connect() as conn:
            for i, pid in enumerate(ids):
                st = conn.execute(
                    text("SELECT status FROM projects WHERE id=:id"), {"id": pid}
                ).scalar()
                assert st == statuses[i]
        eng.dispose()

    def test_new_design_data_survives_only_after_upgrade(self, tmp_path, monkeypatch):
        """升级后写入的设计数据在降级时随表移除，再次升级后表为空。"""
        db_path = str(tmp_path / "data.db")
        cfg = _make_config(db_path, monkeypatch)
        _create_old_projects(db_path)
        command.stamp(cfg, PARENT)
        pid = _seed_projects(db_path, ["DRAFT"])[0]

        # 升级后写入一条真实问题
        command.upgrade(cfg, NEW)
        eng = create_engine(f"sqlite:///{db_path}")
        with eng.begin() as conn:
            conn.execute(text(
                "INSERT INTO project_problems (id, project_id, context, is_current, version) "
                "VALUES (:id, :pid, :ctx, 1, 1)"
            ), {"id": str(uuid.uuid4()), "pid": pid, "ctx": "测试情境"})
        eng.dispose()
        assert _count(db_path, "project_problems") == 1

        # 降级：设计表连同数据移除
        command.downgrade(cfg, PARENT)
        assert _count(db_path, "project_problems") == -1
        # 核心项目记录仍保留
        assert _count(db_path, "projects") == 1

        # 再次升级：表恢复为空
        command.upgrade(cfg, NEW)
        assert _count(db_path, "project_problems") == 0
        assert _count(db_path, "projects") == 1

    def test_historical_rows_loadable_via_orm(self, tmp_path, monkeypatch):
        """历史行（由 server_default 填充 review_status）必须能被 ORM 加载。

        回归守卫：若迁移误将 server_default 设为枚举 value 'draft'，而
        SAEnum(ReviewStatus) 按 name 存储，则历史行加载会抛 LookupError。
        本测试用迁移真实填充 review_status 后，经 ORM 读取并断言枚举值，
        确保迁移默认值与 ORM 枚举存储约定一致。

        注意：只查询 review_status 列，避免 Project 模型后续新增字段
        （如 teacher_reflection，由 g8b9c0d1e2f3 引入）在此迁移版本
        f1a2b3c4d5e6 中不存在的列触发 OperationalError。
        """
        from sqlalchemy import select

        db_path = str(tmp_path / "orm.db")
        cfg = _make_config(db_path, monkeypatch)
        _create_old_projects(db_path)
        command.stamp(cfg, PARENT)
        ids = _seed_projects(db_path, ["DRAFT", "ACTIVE", "COMPLETED"])
        assert len(ids) == 3

        # 升级：review_status 由 server_default 填充
        command.upgrade(cfg, NEW)

        # 经 ORM 加载历史行 review_status——此处不应抛 LookupError
        eng = create_engine(f"sqlite:///{db_path}")
        Session = sessionmaker(bind=eng)
        db = Session()
        try:
            rows = db.execute(select(Project.id, Project.review_status)).all()
            assert len(rows) == 3
            for row in rows:
                assert row.review_status == ReviewStatus.DRAFT
        finally:
            db.close()
            eng.dispose()
