/**
 * AI 内容治理领域类型（计划 Task 5 / 验收标准 3.5.6）。
 *
 * 后端响应经过 http 拦截器 snake_case → camelCase 转换，
 * 故此处均使用 camelCase。对应后端 `app/schemas/ai_job.py`。
 */

// ── 枚举（后端按 name 存储，前端使用小写字面量） ───────────────
export type AiJobScene =
  | 'lesson_plan'
  | 'paper'
  | 'grading'
  | 'design'
  | 'rubric'
  | 'task_sheet'

export type AiJobStatus =
  | 'created'
  | 'queued'
  | 'running'
  | 'succeeded'
  | 'failed'
  | 'reviewed'
  | 'adopted'
  | 'rejected'

export type SchemaStatus = 'valid' | 'invalid' | 'skipped'

export type AdoptionStatus = 'adopted' | 'partially_adopted' | 'rejected'

export type IssueStatus = 'open' | 'resolved' | 'wontfix'

export type QualitySeverity = 'blocker' | 'warning' | 'suggestion'

export type QualityRuleCode =
  | 'subject_mismatch'
  | 'unused_contribution'
  | 'missing_stage'
  | 'missing_resource_tier'
  | 'missing_evaluation'
  | 'timeout'
  | 'invalid_output'
  | 'provider_unavailable'
  | 'safety_blocked'

// ── AI 任务 ──────────────────────────────────────────────────
export interface AiJob {
  id: string
  projectId: string
  scene: string
  status: string
  outputType: string
  providerId?: string | null
  providerModel?: string | null
  promptVersion?: string | null
  inputSummary?: Record<string, unknown> | null
  errorCode?: string | null
  errorMessage?: string | null
  durationMs?: number | null
  initiatedBy: string
  taskId?: string | null
  submissionId?: string | null
  reviewedBy?: string | null
  reviewedAt?: string | null
  adoptedBy?: string | null
  adoptedAt?: string | null
  adoptedVersionId?: string | null
  createdAt?: string | null
  updatedAt?: string | null
}

export interface AiJobCreateInput {
  projectId: string
  scene: AiJobScene
  outputType: string
  taskId?: string | null
  submissionId?: string | null
}

// ── 输出版本 ──────────────────────────────────────────────────
export interface AiOutputVersion {
  id: string
  jobId: string
  version: number
  content?: string | null
  contentType: string
  schemaStatus: string
  schemaErrors?: unknown[] | null
  adoptionStatus: string
  isFinal: boolean
  teacherNote?: string | null
  regeneratedFrom?: string | null
  createdAt?: string | null
}

// ── 质量问题 ──────────────────────────────────────────────────
export interface QualityIssue {
  id: string
  jobId?: string | null
  versionId?: string | null
  severity: string
  ruleCode: string
  objectRef: string
  message: string
  status: string
  resolution?: string | null
  resolvedBy?: string | null
  resolvedAt?: string | null
  createdAt?: string | null
}

// ── 聚合响应 ──────────────────────────────────────────────────
export interface AiJobDetail {
  job: AiJob
  versions: AiOutputVersion[]
  issues: QualityIssue[]
  openBlockers: number
}

export interface AiJobListResponse {
  items: AiJob[]
  total: number
}

// ── 请求体 ──────────────────────────────────────────────────
export interface AiJobReviewInput {
  note?: string
}

export interface AiJobAdoptInput {
  versionId: string
  adoptionStatus: AdoptionStatus
  note?: string
}

export interface AiJobRegenerateInput {
  note?: string
  baseVersionId?: string
}

export interface QualityIssueResolveInput {
  resolution: string
  status?: IssueStatus
}

// ── 场景与输出类型选项（计划 3.5.6） ───────────────────────────
export const SCENE_OPTIONS: { value: AiJobScene; label: string }[] = [
  { value: 'design', label: '教学设计' },
  { value: 'lesson_plan', label: '教案' },
  { value: 'paper', label: '题目/试卷' },
  { value: 'rubric', label: '量规' },
  { value: 'task_sheet', label: '任务单' },
  { value: 'grading', label: '评分' },
]

export const OUTPUT_TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: '教学设计', label: '教学设计' },
  { value: '教案', label: '教案' },
  { value: 'PPT大纲', label: 'PPT 大纲' },
  { value: '任务单', label: '任务单' },
  { value: '量规', label: '量规' },
  { value: '题目', label: '题目' },
  { value: '试卷', label: '试卷' },
  { value: '评分结果', label: '评分结果' },
]

// ── 标签字典 ──────────────────────────────────────────────────
export const JOB_STATUS_LABELS: Record<string, string> = {
  created: '已创建',
  queued: '排队中',
  running: '执行中',
  succeeded: '已成功',
  failed: '已失败',
  reviewed: '已审核',
  adopted: '已采用',
  rejected: '已拒绝',
}

export const JOB_STATUS_TYPES: Record<string, string> = {
  created: 'info',
  queued: 'info',
  running: 'warning',
  succeeded: 'success',
  failed: 'danger',
  reviewed: 'primary',
  adopted: 'success',
  rejected: 'info',
}

export const SCHEMA_STATUS_LABELS: Record<string, string> = {
  valid: '结构有效',
  invalid: '结构无效',
  skipped: '未校验',
}

export const SCHEMA_STATUS_TYPES: Record<string, string> = {
  valid: 'success',
  invalid: 'danger',
  skipped: 'info',
}

export const ADOPTION_STATUS_LABELS: Record<string, string> = {
  adopted: '已采用',
  partially_adopted: '部分采用',
  rejected: '已退回',
  pending: '待采用',
}

export const ADOPTION_STATUS_TYPES: Record<string, string> = {
  adopted: 'success',
  partially_adopted: 'warning',
  rejected: 'info',
  pending: 'info',
}

export const ISSUE_STATUS_LABELS: Record<string, string> = {
  open: '待处理',
  resolved: '已处理',
  wontfix: '不予处理',
}

export const ISSUE_STATUS_TYPES: Record<string, string> = {
  open: 'danger',
  resolved: 'success',
  wontfix: 'info',
}

export const SEVERITY_LABELS: Record<string, string> = {
  blocker: '阻断',
  warning: '警告',
  suggestion: '建议',
}

export const SEVERITY_TYPES: Record<string, string> = {
  blocker: 'danger',
  warning: 'warning',
  suggestion: 'info',
}

export const RULE_CODE_LABELS: Record<string, string> = {
  subject_mismatch: '学科拼盘',
  unused_contribution: '贡献未使用',
  missing_stage: '三阶段缺失',
  missing_resource_tier: '资源层级缺失',
  missing_evaluation: '评价缺失',
  timeout: '执行超时',
  invalid_output: '结构无效',
  provider_unavailable: 'Provider 不可用',
  safety_blocked: '内容拦截',
}
