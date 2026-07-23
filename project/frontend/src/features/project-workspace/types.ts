/**
 * 项目工作区领域类型。
 *
 * 字段命名与后端 `app.schemas.project_design` 对齐；HTTP 拦截器已将
 * snake_case 自动转为 camelCase，因此前端类型统一使用 camelCase。
 *
 * 这些类型仅服务于项目工作区（创建向导、设计页、总览页），不替换
 * `@/types` 中的共享 `Project` 类型——后者仅扩展必要字段以避免影响其他页面。
 */

// ── 项目设计枚举（与后端 app.models.project_design / app.models.enums 一致）──
export type SubjectRole = 'core' | 'support'
export type GoalType =
  | 'knowledge'
  | 'ability'
  | 'transfer'
  | 'collaboration'
  | 'practice'
export type EvidenceType =
  | 'artifact'
  | 'observation'
  | 'test'
  | 'reflection'
  | 'process_log'
export type EvidenceCollector = 'teacher' | 'student' | 'peer' | 'system'
export type TeachingStage = 'pre_class' | 'in_class' | 'post_class'

// 项目生命周期状态（与后端 ProjectStatus 一致）
export type ProjectStatus =
  | 'draft'
  | 'pending_review'
  | 'active'
  | 'completed'
  | 'archived'

// ── 项目设计实体 ────────────────────────────────────────────────
export interface ProjectProblem {
  id: string
  projectId: string
  context: string
  object?: string | null
  audience?: string | null
  constraints?: string | null
  deliverable?: string | null
  usage?: string | null
  isCurrent: boolean
  version: number
  createdAt?: string
  updatedAt?: string
}

export interface SubjectContribution {
  id: string
  projectId: string
  subjectId: string
  role: SubjectRole
  knowledge?: string | null
  thinking?: string | null
  inquiry?: string | null
  removalImpact?: string | null
  createdAt?: string
  updatedAt?: string
}

export interface LearningGoal {
  id: string
  projectId: string
  goalType: GoalType
  name: string
  description?: string | null
  scope?: string | null
  createdAt?: string
  updatedAt?: string
}

export interface EvaluationIndicator {
  id: string
  goalId: string
  projectId: string
  observableBehavior: string
  levelRule?: string | null
  createdAt?: string
  updatedAt?: string
}

export interface EvidencePlan {
  id: string
  indicatorId: string
  projectId: string
  stage: TeachingStage
  evidenceType: EvidenceType
  collector: EvidenceCollector
  required: boolean
  description?: string | null
  createdAt?: string
  updatedAt?: string
}

// ── 聚合快照（GET /projects/{id}/design）─────────────────────────
export interface ProjectDesignSnapshot {
  problem: ProjectProblem | null
  contributions: SubjectContribution[]
  goals: LearningGoal[]
  indicators: EvaluationIndicator[]
  evidencePlans: EvidencePlan[]
}

// ── 完整性检查结果（POST /projects/{id}/validate-activation）─────
export interface CompletionIssue {
  code: string
  field: string
  message: string
}

export interface ProjectValidationResult {
  canActivate: boolean
  blockers: CompletionIssue[]
  warnings: CompletionIssue[]
  /** 完整度 0-1 */
  completion: number
  details: Record<string, unknown>
}

// ── 创建向导表单 ────────────────────────────────────────────────
/**
 * 向导草稿结构。
 *
 * 后端 `ProjectCreate` 仅接受 title/description/grade/start_date/end_date/
 * subject_ids/class_ids；课时、协作人、审核人为向导规划字段，暂存于本地草稿，
 * 在后端未扩展前不发送到服务端（计划 3.4：草稿允许暂缺字段）。
 */
export interface ProjectWizardDraft {
  /** 步骤 1：基本信息 */
  title: string
  description: string
  grade: string
  classIds: string[]
  /** 课时（规划字段，本地草稿保留） */
  lessonHours?: number
  /** 负责人固定为当前教师，仅展示 */
  /** 协作人 ID 列表（规划字段，本地草稿保留） */
  collaboratorIds: string[]
  /** 审核人 ID（规划字段，本地草稿保留） */
  reviewerId?: string
  /** 步骤 1 附加字段 */
  startDate?: string
  endDate?: string
  coverImageUrl?: string

  /** 步骤 2：真实问题 */
  problemContext: string
  problemObject: string
  problemAudience: string
  problemConstraints: string
  problemDeliverable: string
  problemUsage: string

  /** 步骤 3：学科贡献 */
  /** 核心学科 ID */
  coreSubjectId: string
  /** 支撑学科 ID 列表 */
  supportSubjectIds: string[]
  /** 每个学科（含核心）的贡献描述，key 为 subjectId */
  contributionNotes: Record<string, { knowledge: string; thinking: string; inquiry: string }>

  /** 步骤 4：目标与证据（简化为本地草稿，正式保存走设计页接口） */
  goals: Array<{
    goalType: GoalType
    name: string
    description: string
    scope: string
  }>

  /** 当前步骤索引（0-4），用于草稿恢复 */
  step: number
  /** 最后一次自动保存时间（ISO 字符串） */
  savedAt?: string
}

/** 向导步骤定义 */
export interface WizardStep {
  index: number
  key: 'basic' | 'problem' | 'contribution' | 'goals' | 'confirm'
  title: string
  description: string
}

export const WIZARD_STEPS: WizardStep[] = [
  {
    index: 0,
    key: 'basic',
    title: '基本信息',
    description: '名称、年级、班级、课时与协作人',
  },
  {
    index: 1,
    key: 'problem',
    title: '真实问题',
    description: '情境、对象、受众、约束、成果与用途',
  },
  {
    index: 2,
    key: 'contribution',
    title: '学科贡献',
    description: '唯一核心学科与至少一门支撑学科',
  },
  {
    index: 3,
    key: 'goals',
    title: '目标与证据',
    description: '学习目标、可观察指标与证据计划',
  },
  {
    index: 4,
    key: 'confirm',
    title: '确认创建',
    description: '查看缺失项、警告与推荐下一步',
  },
]

// ── 保存状态机 ──────────────────────────────────────────────────
export type SaveStatus = 'idle' | 'saving' | 'saved' | 'error'

// ── 步骤校验结果 ────────────────────────────────────────────────
export interface StepValidationResult {
  valid: boolean
  /** 错误项：field 为字段路径，message 为中文说明 */
  errors: Array<{ field: string; message: string }>
  /** 警告项（不阻断进入下一步） */
  warnings: Array<{ field: string; message: string }>
}

// ── 服务端错误映射结果 ──────────────────────────────────────────
export interface MappedServerError {
  /** 是否为字段级错误（可定位到向导某步骤某字段） */
  fieldLevel: boolean
  step: number | null
  field: string | null
  message: string
  /** HTTP 状态码 */
  status: number
  /** 后端业务错误码 */
  code: number | null
}
