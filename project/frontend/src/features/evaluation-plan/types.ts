/**
 * 评价计划领域类型（计划 Task 4 / 验收标准 4）。
 *
 * 后端响应经过 http 拦截器 snake_case → camelCase 转换，
 * 故此处均使用 camelCase。
 */

// ── 量规等级 ──────────────────────────────────────────────────
export interface RubricLevel {
  level: string
  score: number
  description: string
}

// ── 量规 ──────────────────────────────────────────────────────
export interface Rubric {
  id: string
  projectId: string
  version: number
  isCurrent: boolean
  status: string // draft | published | archived
  createdBy: string
  createdAt?: string | null
}

export interface RubricCreateForm {
  projectId: string
  createdBy: string
}

export interface RubricPublishResult {
  rubric: Rubric
  blockers: string[]
  warnings: string[]
}

// ── 量规维度 ──────────────────────────────────────────────────
export interface RubricCriterion {
  id: string
  rubricId: string
  indicatorId?: string | null
  dimension: string
  weight: number
  aiWeight: number
  levels: RubricLevel[]
}

export interface RubricCriterionCreateForm {
  rubricId: string
  indicatorId?: string | null
  dimension: string
  weight: number
  aiWeight?: number
  levels?: RubricLevel[]
}

export interface RubricCriterionUpdateForm {
  indicatorId?: string | null
  dimension?: string
  weight?: number
  aiWeight?: number
  levels?: RubricLevel[]
}

// ── 证据 ──────────────────────────────────────────────────────
export interface EvidenceArtifact {
  id: string
  projectId: string
  submissionId?: string | null
  indicatorId: string
  planId?: string | null
  sourceType: string
  contentRef: string
  collectedBy: string
  collectedAt: string
  createdAt?: string | null
}

export interface EvidenceArtifactCreateForm {
  projectId: string
  submissionId?: string | null
  indicatorId: string
  planId?: string | null
  sourceType: string
  contentRef: string
  collectedBy: string
  collectedAt?: string | null
}

// ── 评价记录 ──────────────────────────────────────────────────
export interface EvaluationRecord {
  id: string
  projectId: string
  taskId?: string | null
  studentId: string
  evaluatorId: string
  subjectType: string
  subjectId: string
  source: string
  status: string
  rubricId?: string | null
  totalScore?: number | null
  comment?: string | null
  confirmedBy?: string | null
  confirmedAt?: string | null
  publishedAt?: string | null
  createdAt?: string | null
  updatedAt?: string | null
}

export interface EvaluationRecordCreateForm {
  projectId: string
  taskId?: string | null
  studentId: string
  evaluatorId: string
  subjectType?: string
  subjectId: string
  source?: string
  rubricId?: string | null
  comment?: string | null
}

// ── 分维度评分 ────────────────────────────────────────────────
export interface EvaluationScore {
  id: string
  recordId: string
  criterionId: string
  suggestedScore?: number | null
  finalScore?: number | null
  evidenceRef?: string | null
  aiConfidence?: number | null
  differenceReason?: string | null
}

export interface EvaluationScoreCreateForm {
  recordId: string
  criterionId: string
  suggestedScore?: number | null
  finalScore?: number | null
  evidenceRef?: string | null
  aiConfidence?: number | null
  differenceReason?: string | null
}

export interface EvaluationScoreUpdateForm {
  finalScore?: number | null
  evidenceRef?: string | null
  differenceReason?: string | null
}

// ── 状态机迁移 ────────────────────────────────────────────────
export interface TransitionRequest {
  target: string
}

// ── 完整性校验 ────────────────────────────────────────────────
export interface EvaluationPlanValidationResult {
  ready: boolean
  blockers: string[]
  warnings: string[]
  aiWeightNonzero: boolean
  goalsWithoutIndicators: string[]
  criteriaWithoutLevelDescription: string[]
  missingRequiredEvidence: string[]
}

// ── 评价计划快照 ──────────────────────────────────────────────
export interface EvaluationPlanSnapshot {
  rubric: Rubric | null
  criteria: RubricCriterion[]
  goals: Record<string, unknown>[]
  indicators: Record<string, unknown>[]
  evidencePlans: Record<string, unknown>[]
  evidenceArtifacts: EvidenceArtifact[]
  validation: EvaluationPlanValidationResult
}

// ── 复核队列 ──────────────────────────────────────────────────
export interface ReviewQueueItem {
  submissionId: string
  taskId: string
  studentId: string
  reviewStatus: string
  recordId?: string | null
  reasons: string[]
  aiConfidence?: number | null
  totalScore?: number | null
}

export interface ReviewConfirmRequest {
  scores: Array<{
    criterionId: string
    finalScore?: number | null
    evidenceRef?: string | null
    differenceReason?: string | null
  }>
  totalScore?: number | null
  comment?: string | null
  differenceReason?: string | null
}

export interface ReviewConfirmResult {
  record: EvaluationRecord
  submissionId: string
  reviewStatus: string
}

// ── 旧版评价 ──────────────────────────────────────────────────
export interface LegacyEvaluation {
  id: string
  taskId: string
  studentId: string
  evaluatorId: string
  score: number
  comment?: string | null
  evalType: string
  isLegacy: boolean
  createdAt?: string | null
}

// ── 提交状态机迁移结果 ────────────────────────────────────────
export interface SubmissionTransitionResult {
  id: string
  reviewStatus: string
  status: string
}
