"""运营指标测试（计划 Task 8 验收标准 1/2/4）。

覆盖：
- 验收 1：真实/测试/演示/导入数据过滤；默认仅返回 real。
- 验收 2：指标公式、周期、样本量、来源追溯。
- 验收 4：运营指标和证据台账实现。

不伪造数据、不产生伪成功结果：未采集值的指标 value 为 None，
不写入随机数或模拟分；测试/演示/导入数据明确标记 data_origin。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

# 显式导入模型模块，使 SQLAlchemy 在 Base.metadata 注册表结构
# （新模型未注册到 app/models/__init__.py，需测试侧显式触发模块加载）
import app.models.operational_evidence  # noqa: F401
from app.core.exceptions import AppException
from app.models.enums import DataOrigin
from app.models.operational_evidence import (
    EvidenceLedger,
    OperationalMetric,
    OperationalMetricPeriod,
)
from app.models.school import School
from app.modules.operational_evidence import service
from app.modules.operational_evidence.repository import (
    get_metric_by_code,
    list_evidence_by_metric,
    list_metrics,
)


# ── 测试辅助 ──────────────────────────────────────────────────
class _Actor:
    """轻量 actor 替身，避免依赖完整 User 注册流程。"""

    def __init__(
        self,
        user_id: str = "admin-1",
        role: str = "admin",
        school_id: str | None = None,
    ):
        self.id = user_id
        self.role = role
        self.school_id = school_id
        self.class_id = None
        self.is_active = True


def _make_school(db_session, name: str = "运营证据测试学校") -> School:
    school = School(name=f"{name}-{uuid.uuid4().hex[:6]}")
    db_session.add(school)
    db_session.commit()
    db_session.refresh(school)
    return school


def _make_metric(
    db_session,
    *,
    code: str,
    name: str | None = None,
    data_origin: DataOrigin = DataOrigin.REAL,
    school_id: str | None = None,
    period: OperationalMetricPeriod = OperationalMetricPeriod.MONTHLY,
    sample_size: int | None = 120,
    source_table: str = "users",
    source_owner: str = "学籍系统",
    responsible_person: str = "李主任",
    formula: str = "活跃用户数 / 总用户数 * 100%",
    value: float | None = None,
) -> OperationalMetric:
    metric = OperationalMetric(
        id=str(uuid.uuid4()),
        name=name or f"指标-{code}",
        code=code,
        formula=formula,
        period=period,
        sample_size=sample_size,
        source_table=source_table,
        source_owner=source_owner,
        responsible_person=responsible_person,
        data_origin=data_origin,
        value=value,
        value_collected_at=None,
        school_id=school_id,
    )
    db_session.add(metric)
    db_session.commit()
    db_session.refresh(metric)
    return metric


def _make_evidence(
    db_session,
    *,
    metric_id: str,
    evidence_ref: str = "users:students.csv",
    summary: str = "学籍系统导出",
    collected_at: datetime | None = None,
    verified_by: str | None = "admin-1",
) -> EvidenceLedger:
    evidence = EvidenceLedger(
        id=str(uuid.uuid4()),
        metric_id=metric_id,
        evidence_ref=evidence_ref,
        evidence_summary=summary,
        collected_at=collected_at or datetime.now(timezone.utc),
        verified_by=verified_by,
    )
    db_session.add(evidence)
    db_session.commit()
    db_session.refresh(evidence)
    return evidence


# ── 数据来源过滤（验收 1）────────────────────────────────────
class TestDataOriginFiltering:
    """验收 1：真实/测试/演示/导入数据过滤，默认仅返回 real。"""

    def test_default_list_returns_only_real_metrics(self, db_session):
        admin = _Actor(user_id="admin-real", role="admin")
        _make_metric(db_session, code="REAL_METRIC", data_origin=DataOrigin.REAL)
        _make_metric(db_session, code="TEST_METRIC", data_origin=DataOrigin.TEST)
        _make_metric(db_session, code="DEMO_METRIC", data_origin=DataOrigin.DEMO)
        _make_metric(db_session, code="IMP_METRIC", data_origin=DataOrigin.IMPORTED)

        # 默认 data_origin=REAL
        metrics = service.list_metrics(db_session, admin)
        codes = {m.code for m in metrics}
        assert "REAL_METRIC" in codes
        assert "TEST_METRIC" not in codes
        assert "DEMO_METRIC" not in codes
        assert "IMP_METRIC" not in codes

    def test_explicit_origin_filter_returns_only_matching(self, db_session):
        admin = _Actor(user_id="admin-origin", role="admin")
        # 使用 uuid 后缀避免与历史测试数据冲突（服务层 commit 会持久化）
        suffix = uuid.uuid4().hex[:8]
        codes = {
            "REAL": f"R1-{suffix}",
            "TEST": f"T1-{suffix}",
            "DEMO": f"D1-{suffix}",
            "IMPORTED": f"I1-{suffix}",
        }
        _make_metric(db_session, code=codes["REAL"], data_origin=DataOrigin.REAL)
        _make_metric(db_session, code=codes["TEST"], data_origin=DataOrigin.TEST)
        _make_metric(db_session, code=codes["DEMO"], data_origin=DataOrigin.DEMO)
        _make_metric(
            db_session, code=codes["IMPORTED"], data_origin=DataOrigin.IMPORTED
        )

        # 显式 origin=TEST 时，本测试的 T1 必在结果中；R1/D1/I1 必不在。
        # 不对结果集做精确等式断言，因为跨测试共享数据库可能存在历史 TEST 指标。
        test_metrics = service.list_metrics(
            db_session, admin, data_origin=DataOrigin.TEST
        )
        test_codes = {m.code for m in test_metrics}
        assert codes["TEST"] in test_codes
        assert codes["REAL"] not in test_codes
        assert codes["DEMO"] not in test_codes
        assert codes["IMPORTED"] not in test_codes

        demo_metrics = service.list_metrics(
            db_session, admin, data_origin=DataOrigin.DEMO
        )
        demo_codes = {m.code for m in demo_metrics}
        assert codes["DEMO"] in demo_codes
        assert codes["TEST"] not in demo_codes

        imported_metrics = service.list_metrics(
            db_session, admin, data_origin=DataOrigin.IMPORTED
        )
        imported_codes = {m.code for m in imported_metrics}
        assert codes["IMPORTED"] in imported_codes
        assert codes["TEST"] not in imported_codes

    def test_no_origin_filter_returns_all(self, db_session):
        admin = _Actor(user_id="admin-all", role="admin")
        _make_metric(db_session, code="RA", data_origin=DataOrigin.REAL)
        _make_metric(db_session, code="TA", data_origin=DataOrigin.TEST)
        _make_metric(db_session, code="DA", data_origin=DataOrigin.DEMO)

        all_metrics = service.list_metrics(db_session, admin, data_origin=None)
        codes = {m.code for m in all_metrics}
        assert {"RA", "TA", "DA"}.issubset(codes)

    def test_default_filter_excludes_test_demo_imported_in_repository(self, db_session):
        """repository 层默认仅返回 real（验收 8.5：驾驶舱默认仅统计真实数据）。"""
        _make_metric(db_session, code="REAL_R", data_origin=DataOrigin.REAL)
        _make_metric(db_session, code="TEST_R", data_origin=DataOrigin.TEST)
        _make_metric(db_session, code="DEMO_R", data_origin=DataOrigin.DEMO)
        _make_metric(db_session, code="IMP_R", data_origin=DataOrigin.IMPORTED)

        default_metrics = list_metrics(db_session)
        codes = {m.code for m in default_metrics}
        assert "REAL_R" in codes
        for excluded in ("TEST_R", "DEMO_R", "IMP_R"):
            assert excluded not in codes


# ── 指标公式/周期/样本量/来源追溯（验收 2/4）─────────────────
class TestMetricFormulaAndSourceTraceability:
    """验收 2：指标公式、周期、样本量、来源追溯。"""

    def test_metric_records_formula_period_sample_size_source(self, db_session):
        admin = _Actor(user_id="admin-trace", role="admin")
        metric = service.create_metric(
            db_session,
            admin,
            name="周活跃教师率",
            code="WEEKLY_ACTIVE_TEACHER_RATE",
            formula="周活跃教师数 / 教师总数 * 100%",
            period=OperationalMetricPeriod.WEEKLY,
            sample_size=156,
            source_table="audit_logs JOIN users",
            source_owner="信息中心",
            responsible_person="张主任",
            data_origin=DataOrigin.REAL,
            value=72.5,
        )
        assert metric.formula == "周活跃教师数 / 教师总数 * 100%"
        assert metric.period == OperationalMetricPeriod.WEEKLY
        assert metric.sample_size == 156
        assert metric.source_table == "audit_logs JOIN users"
        assert metric.source_owner == "信息中心"
        assert metric.responsible_person == "张主任"
        assert metric.data_origin == DataOrigin.REAL
        assert metric.value == 72.5

    def test_metric_detail_includes_formula_and_evidence(self, db_session):
        admin = _Actor(user_id="admin-detail", role="admin")
        metric = service.create_metric(
            db_session,
            admin,
            name="项目完成率",
            code="PROJECT_COMPLETION_RATE",
            formula="已完成项目数 / 项目总数 * 100%",
            period=OperationalMetricPeriod.MONTHLY,
            sample_size=80,
            source_table="projects",
            source_owner="教学处",
            responsible_person="王老师",
        )
        # 登记证据台账
        ev1 = service.register_evidence(
            db_session,
            admin,
            metric_id=metric.id,
            evidence_ref="projects:snapshot-2026-06",
            evidence_summary="项目状态快照（脱敏后）",
            collected_at=datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc),
        )
        ev2 = service.register_evidence(
            db_session,
            admin,
            metric_id=metric.id,
            evidence_ref="projects:snapshot-2026-07",
            evidence_summary="7 月项目状态快照",
            collected_at=datetime(2026, 7, 23, 10, 0, tzinfo=timezone.utc),
        )

        detail = service.get_metric_detail(db_session, admin, metric.id)
        # 公式/周期/样本量/来源/责任人均可见
        m = detail["metric"]
        assert m["formula"] == "已完成项目数 / 项目总数 * 100%"
        assert m["period"] == "monthly"
        assert m["sample_size"] == 80
        assert m["source_table"] == "projects"
        assert m["source_owner"] == "教学处"
        assert m["responsible_person"] == "王老师"
        # 关联证据台账
        assert len(detail["evidence"]) == 2
        refs = {e["evidence_ref"] for e in detail["evidence"]}
        assert "projects:snapshot-2026-06" in refs
        assert "projects:snapshot-2026-07" in refs
        # 核验人 = 操作人
        for e in detail["evidence"]:
            assert e["verified_by"] == admin.id

    def test_metric_value_none_when_not_collected(self, db_session):
        """不伪造数据：未采集值的指标 value 必须为 None。"""
        admin = _Actor(user_id="admin-none", role="admin")
        metric = service.create_metric(
            db_session,
            admin,
            name="待采集指标",
            code="NOT_COLLECTED_METRIC",
            formula="待定",
            period=OperationalMetricPeriod.AD_HOC,
            sample_size=None,
            source_table=None,
            source_owner=None,
            responsible_person=None,
            value=None,
        )
        assert metric.value is None
        assert metric.value_collected_at is None
        # 详情接口返回的 value 也为 None，不补零
        detail = service.get_metric_detail(db_session, admin, metric.id)
        assert detail["metric"]["value"] is None

    def test_duplicate_metric_code_rejected(self, db_session):
        admin = _Actor(user_id="admin-dup", role="admin")
        service.create_metric(
            db_session,
            admin,
            name="指标一",
            code="UNIQUE_CODE_001",
            formula="A/B",
            period=OperationalMetricPeriod.MONTHLY,
        )
        with pytest.raises(AppException) as exc_info:
            service.create_metric(
                db_session,
                admin,
                name="指标二",
                code="UNIQUE_CODE_001",
                formula="A/B",
                period=OperationalMetricPeriod.MONTHLY,
            )
        assert exc_info.value.status_code == 400
        assert "已存在" in exc_info.value.message

    def test_evidence_cannot_be_registered_for_missing_metric(self, db_session):
        admin = _Actor(user_id="admin-ev", role="admin")
        with pytest.raises(AppException) as exc_info:
            service.register_evidence(
                db_session,
                admin,
                metric_id="not-exist-metric",
                evidence_ref="ref",
                collected_at=datetime.now(timezone.utc),
            )
        assert exc_info.value.status_code == 404

    def test_metric_period_persisted_as_enum_name(self, db_session):
        """SAEnum 按枚举 name 存储；重新加载后周期一致。"""
        admin = _Actor(user_id="admin-period", role="admin")
        metric = service.create_metric(
            db_session,
            admin,
            name="季度指标",
            code="QUARTERLY_METRIC_X",
            formula="X/Y",
            period=OperationalMetricPeriod.QUARTERLY,
        )
        db_session.expire_all()
        reloaded = get_metric_by_code(db_session, "QUARTERLY_METRIC_X")
        assert reloaded is not None
        assert reloaded.period == OperationalMetricPeriod.QUARTERLY
        assert reloaded.period.value == "quarterly"

    def test_evidence_repository_returns_ordered_by_collected_at(self, db_session):
        admin = _Actor(user_id="admin-order", role="admin")
        metric = service.create_metric(
            db_session,
            admin,
            name="排序指标",
            code="ORDER_METRIC",
            formula="A",
            period=OperationalMetricPeriod.MONTHLY,
        )
        early = service.register_evidence(
            db_session, admin,
            metric_id=metric.id,
            evidence_ref="earliest",
            collected_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        late = service.register_evidence(
            db_session, admin,
            metric_id=metric.id,
            evidence_ref="latest",
            collected_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        ordered = list_evidence_by_metric(db_session, metric.id)
        # 按 collected_at 升序
        assert ordered[0].id == early.id
        assert ordered[-1].id == late.id


# ── 学校范围可见性（验收 4 阶段验收支撑）──────────────────────
class TestSchoolScopeVisibility:
    """学校管理员只能查看本校指标；跨校汇总对学校管理员不可见。"""

    def test_school_admin_only_sees_own_school_metrics(self, db_session):
        own_school = _make_school(db_session, "本校")
        other_school = _make_school(db_session, "他校")
        school_admin = _Actor(
            user_id="school-admin-1", role="school_admin", school_id=own_school.id
        )

        own_metric = service.create_metric(
            db_session,
            school_admin,
            name="本校指标",
            code="OWN_SCHOOL_METRIC",
            formula="A/B",
            period=OperationalMetricPeriod.MONTHLY,
            school_id=own_school.id,
        )
        # 他校指标（由系统管理员创建）
        admin = _Actor(user_id="sys-admin-1", role="admin")
        service.create_metric(
            db_session,
            admin,
            name="他校指标",
            code="OTHER_SCHOOL_METRIC",
            formula="A/B",
            period=OperationalMetricPeriod.MONTHLY,
            school_id=other_school.id,
        )
        # 跨校汇总指标（NULL）
        service.create_metric(
            db_session,
            admin,
            name="跨校汇总指标",
            code="CROSS_SCHOOL_METRIC",
            formula="A/B",
            period=OperationalMetricPeriod.MONTHLY,
            school_id=None,
        )

        # 学校管理员只能看到本校指标
        visible = service.list_metrics(db_session, school_admin)
        codes = {m.code for m in visible}
        assert "OWN_SCHOOL_METRIC" in codes
        assert "OTHER_SCHOOL_METRIC" not in codes
        assert "CROSS_SCHOOL_METRIC" not in codes  # 跨校对学校管理员不可见

    def test_admin_sees_all_metrics(self, db_session):
        school = _make_school(db_session)
        admin = _Actor(user_id="admin-all-2", role="admin")
        service.create_metric(
            db_session,
            admin,
            name="本校",
            code="ADMIN_SEE_001",
            formula="A",
            period=OperationalMetricPeriod.MONTHLY,
            school_id=school.id,
        )
        service.create_metric(
            db_session,
            admin,
            name="跨校",
            code="ADMIN_SEE_002",
            formula="A",
            period=OperationalMetricPeriod.MONTHLY,
            school_id=None,
        )
        visible = service.list_metrics(db_session, admin)
        codes = {m.code for m in visible}
        assert "ADMIN_SEE_001" in codes
        assert "ADMIN_SEE_002" in codes

    def test_school_admin_cannot_access_other_school_metric_detail(self, db_session):
        own_school = _make_school(db_session, "本校")
        other_school = _make_school(db_session, "他校")
        school_admin = _Actor(
            user_id="sa-cross", role="school_admin", school_id=own_school.id
        )
        admin = _Actor(user_id="admin-cross", role="admin")
        other_metric = service.create_metric(
            db_session,
            admin,
            name="他校指标",
            code="OTHER_DETAIL",
            formula="A/B",
            period=OperationalMetricPeriod.MONTHLY,
            school_id=other_school.id,
        )
        with pytest.raises(AppException) as exc_info:
            service.get_metric_detail(db_session, school_admin, other_metric.id)
        assert exc_info.value.status_code == 403

    def test_non_admin_cannot_list_metrics(self, db_session):
        teacher = _Actor(user_id="teacher-1", role="teacher")
        with pytest.raises(AppException) as exc_info:
            service.list_metrics(db_session, teacher)
        assert exc_info.value.status_code == 403

    def test_school_admin_default_creates_metric_for_own_school(self, db_session):
        school = _make_school(db_session)
        school_admin = _Actor(
            user_id="sa-create", role="school_admin", school_id=school.id
        )
        # school_admin 不指定 school_id 时，应自动绑定本校
        metric = service.create_metric(
            db_session,
            school_admin,
            name="自动绑定",
            code="AUTO_BOUND_METRIC",
            formula="A/B",
            period=OperationalMetricPeriod.MONTHLY,
            # school_id 未传
        )
        assert metric.school_id == school.id


# ── 证据台账关联完整性（验收 4）──────────────────────────────
class TestEvidenceLedgerAssociation:
    """验收 4：实现运营指标和证据台账。"""

    def test_evidence_is_associated_with_metric(self, db_session):
        admin = _Actor(user_id="admin-evidence", role="admin")
        metric = service.create_metric(
            db_session,
            admin,
            name="证据关联指标",
            code="EVIDENCE_ASSOC_METRIC",
            formula="A/B",
            period=OperationalMetricPeriod.MONTHLY,
            sample_size=42,
            source_table="submissions",
            source_owner="教学处",
            responsible_person="陈老师",
        )
        ev = service.register_evidence(
            db_session,
            admin,
            metric_id=metric.id,
            evidence_ref="submissions:batch-2026-06",
            evidence_summary="6 月提交批次",
            collected_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        assert ev.metric_id == metric.id
        assert ev.verified_by == admin.id
        # 通过指标详情可追溯到证据
        detail = service.get_metric_detail(db_session, admin, metric.id)
        assert len(detail["evidence"]) == 1
        assert detail["evidence"][0]["id"] == ev.id
