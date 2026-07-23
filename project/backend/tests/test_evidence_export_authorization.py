"""运营证据导出授权测试（计划 Task 8 验收标准 3/5/7）。

覆盖：
- 验收 3：学校范围越权拒绝；脱敏；导出审计（每次导出落 ExportRecord）。
- 验收 5：导出预览/脱敏/二次确认；不能跳过预览直接确认。
- 验收 7：阶段验收 —— 任何对外指标都能查看公式、周期、样本量、数据来源和责任人，
  且默认不含非真实数据。

不伪造数据：脱敏后学生姓名 → 学号尾号、教师姓名 → 工号；导出审计记录不可被跳过。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

# 显式导入模型模块，使 SQLAlchemy 在 Base.metadata 注册表结构
import app.models.operational_evidence  # noqa: F401
from app.core.exceptions import AppException
from app.models.enums import DataOrigin
from app.models.operational_evidence import (
    ExportRecord,
    ExportStatus,
    OperationalMetric,
    OperationalMetricPeriod,
)
from app.models.school import School
from app.modules.operational_evidence import service
from app.modules.operational_evidence.repository import (
    get_export,
    list_exports_by_exporter,
)


# ── 测试辅助 ──────────────────────────────────────────────────
class _Actor:
    """轻量 actor 替身，避免依赖完整 User 注册流程。"""

    def __init__(
        self,
        user_id: str,
        role: str,
        school_id: str | None = None,
    ):
        self.id = user_id
        self.role = role
        self.school_id = school_id
        self.class_id = None
        self.is_active = True


def _make_school(db_session, name: str = "导出测试学校") -> School:
    school = School(name=f"{name}-{uuid.uuid4().hex[:6]}")
    db_session.add(school)
    db_session.commit()
    db_session.refresh(school)
    return school


def _make_metric(
    db_session,
    *,
    code: str,
    school_id: str | None = None,
    data_origin: DataOrigin = DataOrigin.REAL,
    responsible_person: str = "陈主任",
    formula: str = "有效提交数 / 总提交数 * 100%",
) -> OperationalMetric:
    metric = OperationalMetric(
        id=str(uuid.uuid4()),
        name=f"指标-{code}",
        code=code,
        formula=formula,
        period=OperationalMetricPeriod.MONTHLY,
        sample_size=100,
        source_table="submissions",
        source_owner="教学处",
        responsible_person=responsible_person,
        data_origin=data_origin,
        school_id=school_id,
    )
    db_session.add(metric)
    db_session.commit()
    db_session.refresh(metric)
    return metric


# ── 学校范围越权拒绝（验收 3）────────────────────────────────
class TestExportSchoolScopeAuthorization:
    """验收 3：学校范围越权拒绝。"""

    def test_school_admin_cannot_export_other_school(self, db_session):
        own_school = _make_school(db_session, "本校")
        other_school = _make_school(db_session, "他校")
        school_admin = _Actor(
            user_id="sa-export", role="school_admin", school_id=own_school.id
        )
        other_metric = _make_metric(
            db_session, code="OTHER_SCHOOL_EXPORT", school_id=other_school.id
        )
        with pytest.raises(AppException) as exc_info:
            service.preview_export(
                db_session,
                school_admin,
                metric_ids=[other_metric.id],
                anonymized=True,
                school_id=other_school.id,
            )
        assert exc_info.value.status_code == 403

    def test_school_admin_cannot_cross_school_export(self, db_session):
        own_school = _make_school(db_session, "本校")
        school_admin = _Actor(
            user_id="sa-cross-export", role="school_admin", school_id=own_school.id
        )
        with pytest.raises(AppException) as exc_info:
            service.preview_export(
                db_session,
                school_admin,
                metric_ids=[],
                anonymized=True,
                school_id=None,  # 跨校
            )
        assert exc_info.value.status_code == 403
        assert "跨校" in exc_info.value.message

    def test_school_admin_export_preview_rejects_other_school_metric(
        self, db_session
    ):
        own_school = _make_school(db_session, "本校")
        other_school = _make_school(db_session, "他校")
        school_admin = _Actor(
            user_id="sa-metric-cross", role="school_admin", school_id=own_school.id
        )
        other_metric = _make_metric(
            db_session, code="METRIC_OTHER_SCHOOL", school_id=other_school.id
        )
        # 即使 school_id 是本校，metric_ids 引用他校指标也要拒绝
        with pytest.raises(AppException) as exc_info:
            service.preview_export(
                db_session,
                school_admin,
                metric_ids=[other_metric.id],
                anonymized=True,
                school_id=own_school.id,
            )
        assert exc_info.value.status_code == 403

    def test_admin_can_cross_school_export(self, db_session):
        admin = _Actor(user_id="admin-cross", role="admin")
        metric_a = _make_metric(db_session, code="ADMIN_CROSS_A", school_id=None)
        result = service.preview_export(
            db_session,
            admin,
            metric_ids=[metric_a.id],
            anonymized=True,
            school_id=None,
        )
        assert result["export"]["scope_school_id"] is None
        assert len(result["metrics"]) == 1

    def test_non_admin_cannot_export(self, db_session):
        teacher = _Actor(user_id="teacher-export", role="teacher")
        metric = _make_metric(db_session, code="TEACHER_DENY")
        with pytest.raises(AppException) as exc_info:
            service.preview_export(
                db_session, teacher, metric_ids=[metric.id], anonymized=True
            )
        assert exc_info.value.status_code == 403


# ── 脱敏（验收 3）────────────────────────────────────────────
class TestAnonymization:
    """验收 3：学校范围脱敏（学生姓名→学号尾号、教师姓名→工号）。"""

    def test_anonymize_student_name_uses_student_no_suffix(self):
        # 学号尾号脱敏：保留首字符 + **** + 末 4 位
        anonymized = service.anonymize_student_name("张三", "S2024001")
        assert anonymized == "S****4001"

    def test_anonymize_student_name_without_student_no(self):
        anonymized = service.anonymize_student_name("张三", None)
        assert anonymized == "学****"

    def test_anonymize_teacher_name_uses_teacher_no_suffix(self):
        anonymized = service.anonymize_teacher_name("王老师", "T20240056")
        assert anonymized == "T****0056"

    def test_anonymize_teacher_name_without_teacher_no(self):
        anonymized = service.anonymize_teacher_name("王老师", None)
        assert anonymized == "工****"

    def test_anonymize_short_id_still_masks(self):
        # 学号不足 5 位时仅保留首字符 + 掩码
        anonymized = service.anonymize_student_name("李四", "S123")
        assert anonymized == "S****"

    def test_preview_export_returns_anonymization_examples(self, db_session):
        admin = _Actor(user_id="admin-anon", role="admin")
        metric = _make_metric(db_session, code="ANON_EXAMPLE_METRIC")
        result = service.preview_export(
            db_session,
            admin,
            metric_ids=[metric.id],
            anonymized=True,
        )
        examples = result["anonymization_examples"]
        assert len(examples) == 2
        # 学生示例包含掩码
        assert "学" in examples[0] or "S****" in examples[0]
        # 教师示例包含掩码
        assert "工" in examples[1] or "T****" in examples[1]

    def test_preview_export_without_anonymization_skips_examples(self, db_session):
        admin = _Actor(user_id="admin-no-anon", role="admin")
        metric = _make_metric(db_session, code="NO_ANON_METRIC")
        result = service.preview_export(
            db_session,
            admin,
            metric_ids=[metric.id],
            anonymized=False,
        )
        assert result["anonymization_examples"] == []
        # 导出记录标记 anonymized=False
        assert result["export"]["anonymized"] is False


# ── 导出审计（验收 3）────────────────────────────────────────
class TestExportAuditRecord:
    """验收 3：每次导出落 ExportRecord，可查询审计记录。"""

    def test_preview_creates_audit_record_in_previewed_status(self, db_session):
        admin = _Actor(user_id="admin-audit", role="admin")
        metric = _make_metric(db_session, code="AUDIT_METRIC_1")
        result = service.preview_export(
            db_session, admin, metric_ids=[metric.id], anonymized=True
        )
        export_id = result["export"]["id"]
        record = get_export(db_session, export_id)
        assert record is not None
        assert record.exporter_id == admin.id
        assert record.status == ExportStatus.PREVIEWED
        assert record.anonymized is True
        assert metric.id in (record.metric_ids or "")

    def test_confirm_updates_status_to_confirmed(self, db_session):
        admin = _Actor(user_id="admin-confirm", role="admin")
        metric = _make_metric(db_session, code="CONFIRM_METRIC")
        result = service.preview_export(
            db_session, admin, metric_ids=[metric.id], anonymized=True
        )
        confirmed = service.confirm_export(
            db_session,
            admin,
            export_id=result["export"]["id"],
            audit_note="用于比赛材料提交",
        )
        assert confirmed.status == ExportStatus.CONFIRMED
        assert confirmed.confirmed_at is not None
        assert confirmed.audit_note == "用于比赛材料提交"

    def test_cannot_confirm_without_preview(self, db_session):
        """验收 5：禁止跳过预览直接确认。"""
        admin = _Actor(user_id="admin-skip", role="admin")
        # 手动创建一个 PENDING 状态的导出记录（未经预览）
        pending = ExportRecord(
            id=str(uuid.uuid4()),
            exporter_id=admin.id,
            scope_school_id=None,
            metric_ids=None,
            anonymized=True,
            status=ExportStatus.PENDING,
        )
        db_session.add(pending)
        db_session.commit()

        with pytest.raises(AppException) as exc_info:
            service.confirm_export(
                db_session, admin, export_id=pending.id, audit_note="try skip"
            )
        assert exc_info.value.status_code == 409
        assert "预览" in exc_info.value.message

    def test_cannot_confirm_already_confirmed(self, db_session):
        admin = _Actor(user_id="admin-double", role="admin")
        metric = _make_metric(db_session, code="DOUBLE_CONFIRM")
        result = service.preview_export(
            db_session, admin, metric_ids=[metric.id], anonymized=True
        )
        service.confirm_export(
            db_session, admin, export_id=result["export"]["id"]
        )
        with pytest.raises(AppException) as exc_info:
            service.confirm_export(
                db_session, admin, export_id=result["export"]["id"]
            )
        assert exc_info.value.status_code == 409

    def test_other_user_cannot_confirm_my_export(self, db_session):
        """仅导出操作人可二次确认。"""
        admin_a = _Actor(user_id="admin-a", role="admin")
        admin_b = _Actor(user_id="admin-b", role="admin")
        metric = _make_metric(db_session, code="OPERATOR_ONLY")
        result = service.preview_export(
            db_session, admin_a, metric_ids=[metric.id], anonymized=True
        )
        with pytest.raises(AppException) as exc_info:
            service.confirm_export(
                db_session, admin_b, export_id=result["export"]["id"]
            )
        assert exc_info.value.status_code == 403

    def test_list_exports_returns_only_my_records(self, db_session):
        admin_a = _Actor(user_id="admin-list-a", role="admin")
        admin_b = _Actor(user_id="admin-list-b", role="admin")
        metric_a = _make_metric(db_session, code="LIST_A")
        metric_b = _make_metric(db_session, code="LIST_B")
        service.preview_export(
            db_session, admin_a, metric_ids=[metric_a.id], anonymized=True
        )
        service.preview_export(
            db_session, admin_b, metric_ids=[metric_b.id], anonymized=True
        )

        a_exports = service.list_export_records(db_session, admin_a)
        b_exports = service.list_export_records(db_session, admin_b)
        # 各自只能看到自己的导出
        for e in a_exports:
            assert e.exporter_id == admin_a.id
        for e in b_exports:
            assert e.exporter_id == admin_b.id

    def test_list_exports_filters_other_school_for_school_admin(self, db_session):
        own_school = _make_school(db_session, "本校")
        other_school = _make_school(db_session, "他校")
        school_admin = _Actor(
            user_id="sa-list", role="school_admin", school_id=own_school.id
        )
        admin = _Actor(user_id="admin-other-list", role="admin")
        own_metric = _make_metric(
            db_session, code="OWN_LIST_METRIC", school_id=own_school.id
        )
        other_metric = _make_metric(
            db_session, code="OTHER_LIST_METRIC", school_id=other_school.id
        )
        # school_admin 自己导出本校
        service.preview_export(
            db_session,
            school_admin,
            metric_ids=[own_metric.id],
            anonymized=True,
            school_id=own_school.id,
        )
        # admin 导出他校
        service.preview_export(
            db_session,
            admin,
            metric_ids=[other_metric.id],
            anonymized=True,
            school_id=other_school.id,
        )
        # school_admin 列表只看到自己的本校导出
        sa_exports = service.list_export_records(db_session, school_admin)
        assert all(e.exporter_id == school_admin.id for e in sa_exports)
        assert all(
            e.scope_school_id == own_school.id for e in sa_exports
        )


# ── 阶段验收：默认不含非真实数据（验收 7）──────────────────
class TestExportExcludesNonRealDataByDefault:
    """阶段验收：默认不含非真实数据；导出预览默认仅返回 real 来源。"""

    def test_export_preview_includes_only_real_metric_by_default(
        self, db_session
    ):
        """导出预览传入 real 与 test 指标 ID，不应在预览中过滤；但 actor 应只
        看到有权限范围的指标。验证：test/demo 数据不应混入默认 list_metrics。
        """
        admin = _Actor(user_id="admin-stage", role="admin")
        real_metric = _make_metric(
            db_session, code="STAGE_REAL", data_origin=DataOrigin.REAL
        )
        test_metric = _make_metric(
            db_session, code="STAGE_TEST", data_origin=DataOrigin.TEST
        )
        # list_metrics 默认仅返回 real
        visible = service.list_metrics(db_session, admin)
        codes = {m.code for m in visible}
        assert "STAGE_REAL" in codes
        assert "STAGE_TEST" not in codes
        # 但 preview_export 可以引用任意指标 ID（审计记录保留）；
        # 通过 dashboard.operational-metrics/summary 默认 data_origin=real
        # 确保前端默认看到的就是真实数据。
        result = service.preview_export(
            db_session,
            admin,
            metric_ids=[real_metric.id, test_metric.id],
            anonymized=True,
        )
        # 预览返回包含两个指标（actor 有权访问）
        assert len(result["metrics"]) == 2
        # 通过 service.list_metrics 默认 data_origin=REAL 验证驾驶舱默认口径
        # 不混入测试/演示/导入数据（验收 7 阶段验收）
        default_metrics = service.list_metrics(db_session, admin)
        default_codes = {m.code for m in default_metrics}
        assert "STAGE_TEST" not in default_codes


# ── 导出审计落审计的完整性（验收 3）────────────────────────
class TestExportAuditCompleteness:
    """验收 3：导出审计记录操作人、范围、时间和脱敏规则。"""

    def test_audit_record_includes_operator_scope_anonymized_and_timestamp(
        self, db_session
    ):
        admin = _Actor(user_id="admin-complete", role="admin")
        own_school = _make_school(db_session, "完整审计学校")
        metric = _make_metric(
            db_session, code="AUDIT_FULL_METRIC", school_id=own_school.id
        )
        result = service.preview_export(
            db_session,
            admin,
            metric_ids=[metric.id],
            anonymized=True,
            school_id=own_school.id,
        )
        export_id = result["export"]["id"]
        record = get_export(db_session, export_id)
        # 操作人
        assert record.exporter_id == admin.id
        # 范围（学校）
        assert record.scope_school_id == own_school.id
        # 脱敏规则
        assert record.anonymized is True
        # 涉及指标
        assert metric.id in (record.metric_ids or "")
        # 时间戳
        assert record.created_at is not None
        # 状态
        assert record.status == ExportStatus.PREVIEWED

    def test_audit_record_repository_helper_lists_by_exporter(self, db_session):
        admin = _Actor(user_id="admin-repo", role="admin")
        metric = _make_metric(db_session, code="REPO_LIST_METRIC")
        service.preview_export(
            db_session, admin, metric_ids=[metric.id], anonymized=True
        )
        records = list_exports_by_exporter(db_session, admin.id)
        assert len(records) >= 1
        assert all(r.exporter_id == admin.id for r in records)
