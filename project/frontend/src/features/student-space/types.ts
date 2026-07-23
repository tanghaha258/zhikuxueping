/**
 * 学生空间领域类型（Task 6 / 计划 3.7）。
 *
 * 后端响应经 http 拦截器 snake_case → camelCase 转换，故此处均使用 camelCase。
 * 对应后端 `app/modules/submissions/student_router.py` 与
 * `app/schemas/student_submission.py`、`app/modules/submissions/service.py`。
 *
 * 订正状态机：
 *   draft → submitted → ai_reviewed / teacher_reviewed → returned → resubmitted → finalized
 *   finalized 为终态，二次评价走 reassess 流程（创建新版本，状态回到 resubmitted）。
 */

// ── 订正状态机枚举（后端按 name 存储，前端使用小写字面量） ───────────
export type SubmissionReviewStatus =
  | 'draft'
  | 'submitted'
  | 'ai_reviewed'
  | 'teacher_reviewed'
  | 'returned'
  | 'resubmitted'
  | 'finalized'

// ── 提交（学生视角，隐藏教师私有字段） ─────────────────────────
export interface StudentSubmission {
  id: string
  taskId: string
  studentId?: string
  content?: string | null
  fileUrls?: string[] | null
  status?: string
  reviewStatus: SubmissionReviewStatus
  comment?: string | null
  submittedAt?: string | null
  createdAt?: string | null
}

// ── 订正版本（学生视角，隐藏 teacherPrivateNote） ───────────────
export interface SubmissionRevision {
  id: string
  submissionId?: string | null
  attemptNumber: number
  content?: string | null
  fileUrls?: string[] | null
  reviewStatus: SubmissionReviewStatus
  teacherComment?: string | null
  reassessReason?: string | null
  submittedAt?: string | null
  reviewedAt?: string | null
  createdAt?: string | null
}

// ── 学生可见的评价记录（仅 published/finalized） ───────────────
export interface StudentEvaluationRecord {
  id: string
  status: string
  source: string
  totalScore?: number | null
  comment?: string | null
  publishedAt?: string | null
  confirmedBy?: string | null
}

// ── 幂等提交响应 ──────────────────────────────────────────────
export interface IdempotentSubmitResult {
  submissionId: string
  revisionId: string
  attemptNumber: number
  reviewStatus: SubmissionReviewStatus
  /** created=false 表示重复点击，返回已有版本。 */
  created: boolean
}

// ── 学生视角反馈视图（GET /student/submissions/{id}/feedback） ────
export interface StudentFeedbackView {
  submission: {
    id: string
    taskId: string
    reviewStatus: SubmissionReviewStatus
    content?: string | null
    fileUrls?: string[] | null
    submittedAt?: string | null
  }
  revisions: SubmissionRevision[]
  evaluations: StudentEvaluationRecord[]
  canResubmit: boolean
  canRequestReassess: boolean
}

// ── 学生视角项目空间（GET /student/projects/{id}） ──────────────
export interface StudentProjectTask {
  id: string
  title: string
  description?: string | null
  stage?: string | null
  tier?: string | null
  deadline?: string | null
  maxScore: number
  submissionType?: string | null
  maxAttempts?: number | null
}

export interface StudentProjectResource {
  id: string
  title: string
  resType: string
  url?: string | null
  tier: string
  tierLabel: string
  stage?: string | null
  usageTip?: string | null
}

export interface StudentProjectProblem {
  context?: string | null
  object?: string | null
  audience?: string | null
  constraints?: string | null
  deliverable?: string | null
  usage?: string | null
}

export interface StudentProjectView {
  project: {
    id: string
    title: string
    description?: string | null
    status: string
  }
  problem: StudentProjectProblem | null
  tasks: StudentProjectTask[]
  resources: {
    foundation: StudentProjectResource[]
    enhancement: StudentProjectResource[]
    extension: StudentProjectResource[]
  }
}

// ── 成长档案（GET /student/growth） ────────────────────────────
export interface GrowthTrajectory {
  taskId: string
  taskTitle?: string | null
  submissionId: string
  reviewStatus: SubmissionReviewStatus
  attemptCount: number
  firstSubmittedAt?: string | null
  latestSubmittedAt?: string | null
  hasReassessment: boolean
}

export interface GrowthEvidenceSummary {
  totalEvaluations: number
  averageScore: number | null
  bySource: Record<string, number>
}

export interface GrowthPortfolio {
  trajectories: GrowthTrajectory[]
  evidenceSummary: GrowthEvidenceSummary
  note?: string | null
}

// ── 请求体（后端 Pydantic 为 snake_case，故请求体使用 snake_case） ──
export interface DraftSaveInput {
  task_id: string
  content?: string | null
  file_urls?: string[]
}

export interface IdempotentSubmitInput {
  task_id: string
  content?: string | null
  file_urls?: string[]
  idempotency_key: string
}

export interface ResubmitInput {
  content?: string | null
  file_urls?: string[]
  idempotency_key: string
}

export interface ReassessInput {
  reason: string
}

// ── 客户端草稿（localStorage 持久化结构） ──────────────────────
export interface TaskDraft {
  content: string
  fileUrls: string[]
  savedAt?: string
}

// ── 标签字典 ──────────────────────────────────────────────────
export const REVIEW_STATUS_LABELS: Record<SubmissionReviewStatus, string> = {
  draft: '草稿',
  submitted: '已提交',
  ai_reviewed: 'AI 已评',
  teacher_reviewed: '教师已评',
  returned: '已退回',
  resubmitted: '已订正',
  finalized: '已确认',
}

export const REVIEW_STATUS_TYPES: Record<SubmissionReviewStatus, string> = {
  draft: 'info',
  submitted: 'primary',
  ai_reviewed: 'warning',
  teacher_reviewed: 'primary',
  returned: 'danger',
  resubmitted: 'success',
  finalized: 'success',
}

export const TIER_LABELS: Record<string, string> = {
  foundation: '基础资源',
  enhancement: '进阶资源',
  extension: '拓展资源',
}

export const EVAL_SOURCE_LABELS: Record<string, string> = {
  teacher: '教师评价',
  peer: '同伴互评',
  ai: 'AI 评价',
  self: '自我评价',
}

export const EVAL_SOURCE_TYPES: Record<string, string> = {
  teacher: 'primary',
  peer: 'success',
  ai: 'warning',
  self: 'info',
}
