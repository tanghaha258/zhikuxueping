"""平台共享枚举。

这些枚举在多个业务模块（项目设计、资源、任务、评价、AI 治理、运营证据）
之间复用，集中定义以避免重复和不一致。定义依据来自核心闭环实施计划 4.2 节。
"""
import enum


class TeachingStage(str, enum.Enum):
    """教学阶段：课前 / 课中 / 课后。"""

    PRE_CLASS = "pre_class"
    IN_CLASS = "in_class"
    POST_CLASS = "post_class"


class ResourceTier(str, enum.Enum):
    """资源层级：基础 / 提升 / 拓展。"""

    FOUNDATION = "foundation"
    ENHANCEMENT = "enhancement"
    EXTENSION = "extension"


class ReviewStatus(str, enum.Enum):
    """审核状态：草稿 / 待审核 / 通过 / 退回 / 已发布 / 已归档。"""

    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    RETURNED = "returned"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class DataOrigin(str, enum.Enum):
    """数据来源：真实 / 测试 / 演示 / 导入。

    用于运营证据默认仅统计真实数据，避免测试、演示或导入数据污染指标。
    """

    REAL = "real"
    TEST = "test"
    DEMO = "demo"
    IMPORTED = "imported"


class TaskPublishStatus(str, enum.Enum):
    """任务发布生命周期状态。

    状态机（计划 4.3）：draft -> scheduled/published -> in_progress -> closed -> archived。
    与 Task.status（学生侧进度：pending/in_progress/submitted/evaluated）相互独立：
    publish_status 描述任务对学生的可见性与发布阶段，status 描述单条任务的执行进度。
    旧任务无发布草稿阶段，迁移时映射为 PUBLISHED 以保留可见性。
    """

    DRAFT = "draft"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"
    ARCHIVED = "archived"


class SubmissionType(str, enum.Enum):
    """任务提交类型：在线作答 / 附件上传 / 两者皆可 / 无需提交。"""

    ONLINE = "online"
    ATTACHMENT = "attachment"
    BOTH = "both"
    NONE = "none"


class ResourceSourceType(str, enum.Enum):
    """资源来源类型：教师手动 / AI 生成 / 导入。

    用于资源页展示来源、AI 资源审核状态过滤与运营证据统计。
    """

    MANUAL = "manual"
    AI = "ai"
    IMPORTED = "imported"


class EvaluationStatus(str, enum.Enum):
    """评价记录生命周期状态（计划 4.3）。

    状态机：
    draft -> collecting_evidence -> pending_teacher_confirmation -> confirmed
    -> published -> appealed -> rechecked -> finalized

    - draft：草稿，未采集证据
    - collecting_evidence：证据采集中
    - pending_teacher_confirmation：等待教师确认
    - confirmed：教师已确认（尚未发布给学生）
    - published：已发布给学生可见
    - appealed：学生申诉中
    - rechecked：复核中
    - finalized：终态定稿
    """

    DRAFT = "draft"
    COLLECTING_EVIDENCE = "collecting_evidence"
    PENDING_TEACHER_CONFIRMATION = "pending_teacher_confirmation"
    CONFIRMED = "confirmed"
    PUBLISHED = "published"
    APPEALED = "appealed"
    RECHECKED = "rechecked"
    FINALIZED = "finalized"


class EvaluationSubjectType(str, enum.Enum):
    """评价主体类型：任务级 / 指标级 / 项目级。"""

    TASK = "task"
    INDICATOR = "indicator"
    PROJECT = "project"


class EvaluationSource(str, enum.Enum):
    """评价来源：教师 / 自评 / 同伴 / AI 建议。

    AI 来源仅作为建议，默认权重为零，需教师确认后才转为正式结论。
    """

    TEACHER = "teacher"
    SELF = "self"
    PEER = "peer"
    AI = "ai"


class ArtifactSourceType(str, enum.Enum):
    """证据来源类型：学生提交 / 教师观察 / 测试 / 反思 / 过程记录。"""

    SUBMISSION = "submission"
    OBSERVATION = "observation"
    TEST = "test"
    REFLECTION = "reflection"
    PROCESS_LOG = "process_log"


class SubmissionReviewStatus(str, enum.Enum):
    """提交复核状态机（计划 4.3）。

    draft -> submitted -> ai_reviewed -> teacher_reviewed
    -> returned -> resubmitted -> finalized

    与 Submission.status（自由字符串）并存：旧数据保留原字符串，
    新数据由 review_status 驱动状态机；旧 status 字段同步镜像以兼容旧接口。
    """

    DRAFT = "draft"
    SUBMITTED = "submitted"
    AI_REVIEWED = "ai_reviewed"
    TEACHER_REVIEWED = "teacher_reviewed"
    RETURNED = "returned"
    RESUBMITTED = "resubmitted"
    FINALIZED = "finalized"


class RubricStatus(str, enum.Enum):
    """量规状态：草稿 / 已发布 / 已归档。

    量规发布后不可修改维度，需新建版本；归档后不可再用于新评价。
    """

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


# ============================================================
# AI 治理领域（Task 5）
# ============================================================


class AiJobScene(str, enum.Enum):
    """AI 内容任务场景（计划 3.5.6 输出类型）。

    覆盖教学设计、教案、PPT 大纲、任务单、量规、题目与评分。
    """

    LESSON_PLAN = "lesson_plan"
    PAPER = "paper"
    RUBRIC = "rubric"
    TASK_SHEET = "task_sheet"
    QUESTION = "question"
    GRADING = "grading"


class AiJobStatus(str, enum.Enum):
    """AI 任务状态机（计划 4.3）。

    created -> queued -> running -> succeeded/failed
    -> reviewed -> adopted/rejected

    - created：已创建任务，尚未入队
    - queued：已入队等待执行
    - running：调用 Provider 中
    - succeeded：Provider 返回并落库输出版本
    - failed：超时、结构错误、内容拦截或 Provider 不可用
    - reviewed：教师已完成审核（可进入采用/拒绝）
    - adopted：教师采用为最终版本
    - rejected：教师拒绝
    """

    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REVIEWED = "reviewed"
    ADOPTED = "adopted"
    REJECTED = "rejected"


class SchemaStatus(str, enum.Enum):
    """AI 输出结构校验状态。

    - valid：结构与契约一致，可进入教师审核
    - invalid：结构错误，不产生可采纳结果
    - pending：尚未校验
    """

    VALID = "valid"
    INVALID = "invalid"
    PENDING = "pending"


class AdoptionStatus(str, enum.Enum):
    """AI 输出版本采用状态。

    - pending：待教师审核
    - adopted：教师采用为最终版本
    - partially_adopted：部分采用（教师修改后采用）
    - rejected：教师拒绝
    """

    PENDING = "pending"
    ADOPTED = "adopted"
    PARTIALLY_ADOPTED = "partially_adopted"
    REJECTED = "rejected"


class QualitySeverity(str, enum.Enum):
    """质量问题严重级别（计划 3.5.6 阻断/警告/建议三级）。

    - blocker：阻断性问题，未处理不能标记正式版本
    - warning：警告，需教师关注但不阻断
    - suggestion：建议，供教师参考
    """

    BLOCKER = "blocker"
    WARNING = "warning"
    SUGGESTION = "suggestion"


class IssueStatus(str, enum.Enum):
    """质量问题处理状态。"""

    OPEN = "open"
    RESOLVED = "resolved"
    WONTFIX = "wontfix"


class QualityRuleCode(str, enum.Enum):
    """跨学科质量规则代码（计划 Task 5 验收标准 2）。

    - subject_mismatch：学科拼盘（输出学科与项目核心/支撑学科不一致）
    - unused_contribution：学科贡献未使用（支撑学科贡献未在任务/资源中体现）
    - missing_stage：三阶段缺失（课前/课中/课后任务链不完整）
    - missing_resource_tier：资源层级缺失（基础/提升/拓展三级资源不全）
    - missing_evaluation：评价缺失（缺少量规或指标）
    - invalid_schema：输出结构无效（JSON Schema 校验失败）
    - safety_blocked：内容拦截（安全审查未通过）
    - timeout：调用超时
    """

    SUBJECT_MISMATCH = "subject_mismatch"
    UNUSED_CONTRIBUTION = "unused_contribution"
    MISSING_STAGE = "missing_stage"
    MISSING_RESOURCE_TIER = "missing_resource_tier"
    MISSING_EVALUATION = "missing_evaluation"
    INVALID_SCHEMA = "invalid_schema"
    SAFETY_BLOCKED = "safety_blocked"
    TIMEOUT = "timeout"


# ============================================================
# 学情改进与二次评价领域（Task 7）
# ============================================================


class ImprovementSuggestionStatus(str, enum.Enum):
    """改进建议状态机（计划 4.3 / Task 7）。

    draft -> adopted/modified/rejected
    - draft：草稿建议，引用了评价证据，等待教师决定
    - adopted：教师采用，可转换为改进任务或测评
    - modified：教师修改后采用（保留 reason 留痕）
    - rejected：教师拒绝（保留 reason 留痕）

    阶段验收：教师可采用、修改或拒绝建议；改进任务可追溯到原评价和二次评价。
    """

    DRAFT = "draft"
    ADOPTED = "adopted"
    MODIFIED = "modified"
    REJECTED = "rejected"


class ImprovementTaskType(str, enum.Enum):
    """改进任务类型（计划 3.5.8）。

    将建议转换为对应类型的任务或测评：
    - foundation_consolidation：基础巩固
    - enhancement_application：提升应用
    - extension_transfer：拓展迁移
    - second_evaluation：二次评价（测评）
    """

    FOUNDATION_CONSOLIDATION = "foundation_consolidation"
    ENHANCEMENT_APPLICATION = "enhancement_application"
    EXTENSION_TRANSFER = "extension_transfer"
    SECOND_EVALUATION = "second_evaluation"
