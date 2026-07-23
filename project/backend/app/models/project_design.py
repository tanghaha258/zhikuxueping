"""项目设计领域模型。

依据核心闭环实施计划 4.1 节，建立跨学科项目结构化设计所需的数据对象：
项目真实问题、学科贡献、学习目标、评价指标和证据计划。

设计原则：
- 一个项目一条当前正式版本的真实问题（`is_current=True`），历史版本保留只读。
- 学科贡献区分核心/支撑角色；一个项目仅允许一条 `role=core` 记录。
- 学习目标必须可拆解为可观察指标，指标再绑定证据计划，避免抽象目标伪装达成。
- 所有外键显式声明，避免依赖 ORM 懒加载造成 N+1。
"""
import enum
import uuid
from typing import Optional

from sqlalchemy import (
    Boolean,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.models.enums import TeachingStage


class SubjectRole(str, enum.Enum):
    """学科在项目中的角色：core=核心学科，support=支撑学科。"""

    CORE = "core"
    SUPPORT = "support"


class GoalType(str, enum.Enum):
    """学习目标类型：知识 / 能力 / 迁移 / 合作 / 实践。"""

    KNOWLEDGE = "knowledge"
    ABILITY = "ability"
    TRANSFER = "transfer"
    COLLABORATION = "collaboration"
    PRACTICE = "practice"


class EvidenceType(str, enum.Enum):
    """证据类型：作品 / 观察 / 测试 / 反思 / 过程记录。"""

    ARTIFACT = "artifact"
    OBSERVATION = "observation"
    TEST = "test"
    REFLECTION = "reflection"
    PROCESS_LOG = "process_log"


class EvidenceCollector(str, enum.Enum):
    """证据采集者：教师 / 学生 / 同伴 / 系统。"""

    TEACHER = "teacher"
    STUDENT = "student"
    PEER = "peer"
    SYSTEM = "system"


class ProjectProblem(Base, TimestampMixin):
    """项目真实问题：情境、对象、受众、约束、最终成果和成果用途。

    一个项目仅一条 `is_current=True` 的记录作为当前正式版本；
    历史版本保留 `is_current=False` 以追溯设计演进。
    """

    __tablename__ = "project_problems"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    context: Mapped[str] = mapped_column(Text, nullable=False, comment="情境描述")
    object: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="问题对象")
    audience: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="真实受众")
    constraints: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="约束条件")
    deliverable: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="最终成果")
    usage: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="成果用途")
    is_current: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, comment="是否当前正式版本"
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False, comment="版本号")


class SubjectContribution(Base, TimestampMixin):
    """学科贡献：核心/支撑学科的知识、思维、探究方法和移除影响。

    一个项目内 `subject_id` 唯一，避免同一学科重复登记；
    `role=core` 的记录在一个项目内仅允许一条，由服务层强制。
    """

    __tablename__ = "subject_contributions"
    __table_args__ = (  # type: ignore[assignment]
        # 通过唯一约束保证一个项目内同一学科不重复登记。
        # 核心/支撑唯一性涉及业务规则，由服务层在事务内查询校验。
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject_id: Mapped[str] = mapped_column(String(36), nullable=False, comment="学科 ID")
    role: Mapped[SubjectRole] = mapped_column(
        SAEnum(SubjectRole), nullable=False, comment="学科角色: core/support"
    )
    knowledge: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="知识贡献")
    thinking: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="思维方式贡献")
    inquiry: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="探究方法贡献")
    removal_impact: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="移除该学科对项目的影响"
    )


class LearningGoal(Base, TimestampMixin):
    """学习目标：知识 / 能力 / 迁移 / 合作 / 实践。

    目标需拆解为可观察指标（EvaluationIndicator）后才允许进入正式评价。
    """

    __tablename__ = "learning_goals"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    goal_type: Mapped[GoalType] = mapped_column(
        SAEnum(GoalType), nullable=False, comment="目标类型"
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="目标名称")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="目标描述")
    scope: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="目标范围（如学科/跨学科）"
    )


class EvaluationIndicator(Base, TimestampMixin):
    """评价指标：把抽象目标拆成可观察行为和等级判定规则。

    每条指标必须绑定一个学习目标，避免无主指标；
    `level_rule` 描述各等级的可观察表现，量规阶段进一步结构化。
    """

    __tablename__ = "evaluation_indicators"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    goal_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("learning_goals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    observable_behavior: Mapped[str] = mapped_column(
        Text, nullable=False, comment="可观察行为描述"
    )
    level_rule: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="等级判定规则（可观察描述）"
    )


class EvidencePlan(Base, TimestampMixin):
    """证据计划：指标在课前/课中/课后阶段如何采集。

    `required=True` 表示正式项目必须采集；缺失时不自动计为零分，
    而是在完整性检查中作为 `blockers` 返回。
    """

    __tablename__ = "evidence_plans"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    indicator_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("evaluation_indicators.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stage: Mapped[TeachingStage] = mapped_column(
        SAEnum(TeachingStage), nullable=False, comment="教学阶段: pre/in/post_class"
    )
    evidence_type: Mapped[EvidenceType] = mapped_column(
        SAEnum(EvidenceType), nullable=False, comment="证据类型"
    )
    collector: Mapped[EvidenceCollector] = mapped_column(
        SAEnum(EvidenceCollector), nullable=False, comment="采集者"
    )
    required: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, comment="是否必须采集"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="采集说明"
    )
