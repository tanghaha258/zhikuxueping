/**
 * 统一项目上下文领域类型（Task 3）。
 *
 * 字段命名与后端 `app.schemas.project_workspace` 对齐；HTTP 拦截器已将
 * snake_case 自动转为 camelCase，因此前端类型统一使用 camelCase。
 *
 * 阶段固定且顺序为：diagnosis → design → preparation → implementation →
 * evaluation → improvement → closure（与后端 PHASE_ORDER 单一来源一致）。
 * 字符串字面量值（phase/type/code）不经 key 转换，保持后端原值。
 */

// ── 阶段（固定顺序，单一来源）──────────────────────────────────
export const PHASE_ORDER = [
  'diagnosis',
  'design',
  'preparation',
  'implementation',
  'evaluation',
  'improvement',
  'closure',
] as const

export type PhaseKey = (typeof PHASE_ORDER)[number]

/** 阶段状态：未开始 / 进行中 / 已完成 / 已阻断。 */
export type PhaseStatus = 'not_started' | 'in_progress' | 'completed' | 'blocked'

/** 单个项目阶段进度。 */
export interface ProjectWorkspacePhase {
  phase: PhaseKey
  status: PhaseStatus
  completedAt?: string | null
  reopenedAt?: string | null
  reopenedBy?: string | null
  reopenReason?: string | null
}

/** 当前用户对该项目的权限快照。 */
export interface ProjectWorkspacePermissions {
  canView: boolean
  canManage: boolean
  /** 归档项目重新开放权限（school_admin）。 */
  canReopen: boolean
  isArchived: boolean
}

/** 阻断或警告项，可定位到阶段/字段。 */
export interface ProjectWorkspaceIssue {
  code: string
  field: string
  message: string
  phase?: PhaseKey | null
}

/** 真实数据计数，不伪造。 */
export interface ProjectWorkspaceCounts {
  tasks: number
  publishedTasks: number
  submissions: number
  evaluations: number
  unpublishedEvaluations: number
  students: number
  aiJobs: number
  pendingAiReviews: number
}

/** 动作类型：状态迁移 / 阶段完成 / 阶段重开 / 导航 / 只读。 */
export type ActionType =
  | 'transition'
  | 'phase_complete'
  | 'phase_reopen'
  | 'navigate'
  | 'read'

/** 可执行动作；primary=true 表示全局唯一主操作。 */
export interface ProjectWorkspaceAction {
  id: string
  label: string
  type: ActionType
  primary: boolean
  route?: string | null
  phase?: PhaseKey | null
  reason?: string | null
}

/** GET /project-workspace/{id}/context 统一上下文响应。 */
export interface ProjectWorkspaceContext {
  project: ProjectContextSummary
  phases: ProjectWorkspacePhase[]
  permissions: ProjectWorkspacePermissions
  blockers: ProjectWorkspaceIssue[]
  warnings: ProjectWorkspaceIssue[]
  counts: ProjectWorkspaceCounts
  actions: ProjectWorkspaceAction[]
  /** 全局唯一主操作；无主操作时为 null。 */
  nextAction: ProjectWorkspaceAction | null
}

/** 上下文内嵌的项目摘要（camelCase，经拦截器转换）。 */
export interface ProjectContextSummary {
  id: string
  title: string
  description?: string | null
  status: string
  creatorId: string
  schoolId?: string | null
  grade?: string | null
  startDate?: string | null
  endDate?: string | null
  projectType?: string | null
  coreSubjectId?: string | null
  reviewStatus?: string | null
  classIds: string[]
  subjectIds: string[]
  createdAt?: string | null
}

/** timeline 真实事件。 */
export interface ProjectWorkspaceTimelineEvent {
  type:
    | 'project_created'
    | 'phase_completed'
    | 'phase_reopened'
    | 'project_reopened'
    | 'evaluation_published'
    | 'task_created'
  label: string
  timestamp: string
  phase?: PhaseKey | null
  actor?: string | null
}

/** 阶段重开请求体；reason 留痕便于审计。 */
export interface PhaseReopenRequest {
  reason?: string | null
}

// ── 网络错误观察 ────────────────────────────────────────────────
/** 可观察的网络/业务错误快照，供 UI 渲染错误条。 */
export interface ContextError {
  /** HTTP 状态码；网络错误为 0。 */
  status: number
  /** 后端业务错误码（如有）。 */
  code: number | null
  message: string
  /** 是否为权限错误（403/跨校访问）。 */
  forbidden: boolean
  /** 是否为未找到（404）。 */
  notFound: boolean
}
