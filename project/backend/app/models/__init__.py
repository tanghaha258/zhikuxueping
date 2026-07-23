from app.models.user import User, Role
from app.models.school import School, Class
from app.models.subject import Subject
from app.models.project import Project, ProjectSubject, ProjectClass, ProjectMember, ProjectStatus
from app.models.audit_log import AuditLog
from app.models.saved_lesson_plan import SavedLessonPlan
from app.models.teacher_class import TeacherClass
from app.models.paper import Paper, AnswerKey, PaperSubmission, PaperStatus, SubmissionStatus
from app.models.task import Task, TaskAssignment, TaskType, TaskStatus
from app.models.submission import Submission
from app.models.evaluation import Evaluation, EvaluationType
from app.models.resource import Resource
from app.models.ai_provider import AiProvider
from app.models.paper_template import PaperTemplate, AiGeneratedPaper
from app.models.knowledge_point import KnowledgePoint
from app.models.question import Question, PaperQuestion
from app.models.prompt_template import PromptTemplate
from app.models.learning_profile import (
    LearningSnapshot,
    ClassLearningReport,
    QuestionUsageLog,
    DifficultyCalibrationHistory,
)
# 核心闭环扩展：项目设计领域
from app.models.enums import (
    TeachingStage,
    ResourceTier,
    ReviewStatus,
    DataOrigin,
    TaskPublishStatus,
    SubmissionType,
    ResourceSourceType,
    EvaluationStatus,
    EvaluationSubjectType,
    EvaluationSource,
    ArtifactSourceType,
    SubmissionReviewStatus,
    RubricStatus,
    AiJobScene,
    AiJobStatus,
    SchemaStatus,
    AdoptionStatus,
    QualitySeverity,
    IssueStatus,
    QualityRuleCode,
)
from app.models.project_design import (
    ProjectProblem,
    SubjectContribution,
    LearningGoal,
    EvaluationIndicator,
    EvidencePlan,
    SubjectRole,
    GoalType,
    EvidenceType,
    EvidenceCollector,
)
# 核心闭环扩展：资源/任务元数据与任务依赖
from app.models.task_dependency import TaskDependency
# 核心闭环扩展：评价计划领域（Task 4）
from app.models.evaluation_plan import (
    Rubric,
    RubricCriterion,
    EvidenceArtifact,
    EvaluationRecord,
    EvaluationScore,
)
# 核心闭环扩展：AI 治理领域（Task 5）
from app.models.ai_job import (
    AiJob,
    AiOutputVersion,
    QualityIssue,
)
# 核心闭环扩展：提交订正版本（Task 6）
from app.models.submission_revision import SubmissionRevision
# 核心闭环扩展：学情改进与二次评价领域（Task 7）
from app.models.improvement import (
    ImprovementSuggestion,
    ImprovementTask,
    SecondEvaluation,
)
# 核心闭环扩展：运营证据领域（Task 8）
from app.models.operational_evidence import (
    OperationalMetric,
    EvidenceLedger,
    ExportRecord,
)
# 共享枚举：学情改进与二次评价（Task 7）
from app.models.enums import (
    ImprovementSuggestionStatus,
    ImprovementTaskType,
)

__all__ = [
    "User", "Role", "School", "Class", "Subject",
    "Project", "ProjectSubject", "ProjectClass", "ProjectMember", "ProjectStatus",
    "AuditLog", "SavedLessonPlan", "TeacherClass",
    "Paper", "AnswerKey", "PaperSubmission", "PaperStatus", "SubmissionStatus",
    "Task", "TaskAssignment", "TaskType", "TaskStatus",
    "Submission", "Evaluation", "EvaluationType", "Resource", "AiProvider",
    "PaperTemplate", "AiGeneratedPaper", "KnowledgePoint",
    "Question", "PaperQuestion", "PromptTemplate",
    "LearningSnapshot", "ClassLearningReport",
    "QuestionUsageLog", "DifficultyCalibrationHistory",
    # 核心闭环共享枚举
    "TeachingStage", "ResourceTier", "ReviewStatus", "DataOrigin",
    "TaskPublishStatus", "SubmissionType", "ResourceSourceType",
    "EvaluationStatus", "EvaluationSubjectType", "EvaluationSource",
    "ArtifactSourceType", "SubmissionReviewStatus", "RubricStatus",
    "AiJobScene", "AiJobStatus", "SchemaStatus", "AdoptionStatus",
    "QualitySeverity", "IssueStatus", "QualityRuleCode",
    "ImprovementSuggestionStatus", "ImprovementTaskType",
    # 项目设计领域
    "ProjectProblem", "SubjectContribution", "LearningGoal",
    "EvaluationIndicator", "EvidencePlan",
    "SubjectRole", "GoalType", "EvidenceType", "EvidenceCollector",
    # 资源/任务依赖
    "TaskDependency",
    # 评价计划领域（Task 4）
    "Rubric", "RubricCriterion", "EvidenceArtifact",
    "EvaluationRecord", "EvaluationScore",
    # AI 治理领域（Task 5）
    "AiJob", "AiOutputVersion", "QualityIssue",
    # 提交订正版本（Task 6）
    "SubmissionRevision",
    # 学情改进与二次评价领域（Task 7）
    "ImprovementSuggestion", "ImprovementTask", "SecondEvaluation",
    # 运营证据领域（Task 8）
    "OperationalMetric", "EvidenceLedger", "ExportRecord",
]
