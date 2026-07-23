/**
 * 学情改进领域类型（计划 Task 7 / 验收 3.7）。
 *
 * 后端响应经过 http 拦截器 snake_case → camelCase 转换，
 * 故此处均使用 camelCase。对应后端 improvements / learning-profile 路由。
 *
 * 端点前缀：
 * - /api/v1/improvements                          学情改进建议 + 二次评价
 * - /api/v1/learning-profile/projects/:id/aggregations   目标/知识点/指标达成聚合
 */

// ── 枚举 ─────────────────────────────────────────────────────
export type SuggestionStatus =
  | 'pending'
  | 'adopted'
  | 'modified'
  | 'rejected'
  | 'converted'

export type SuggestionPriority = 'high' | 'medium' | 'low'

// ── 学情改进建议 ──────────────────────────────────────────────
/**
 * 每条建议必须引用一条正式证据（evidence_record_id），
 * 用于解释“为什么提出该改进”。
 */
export interface ImprovementSuggestion {
  id: string
  projectId: string
  /** 引用的正式学习证据记录 ID（创建时必填） */
  evidenceRecordId: string
  /** 证据摘要，便于在列表中展示引用依据 */
  evidenceSummary?: string | null
  /** 证据来源引用（如内容路径/URL） */
  evidenceRef?: string | null
  /** 建议类别，如“共性薄弱”“目标未达成”“分层支持” */
  category?: string | null
  title: string
  content: string
  priority?: SuggestionPriority | string | null
  status: SuggestionStatus | string
  /** 采用 / 修改 / 拒绝原因留痕 */
  reason?: string | null
  /** 修改时记录的修改说明 */
  modifications?: string | null
  /** 转换为改进任务后回写的任务 ID */
  convertedTaskId?: string | null
  createdBy: string
  createdAt?: string | null
  updatedAt?: string | null
  [key: string]: unknown
}

export interface ImprovementSuggestionListResponse {
  items: ImprovementSuggestion[]
  total: number
}

/** 创建建议输入。evidenceRecordId 必填，确保建议有据可依。 */
export interface ImprovementSuggestionCreateInput {
  projectId: string
  evidenceRecordId: string
  title: string
  content: string
  category?: string | null
  priority?: SuggestionPriority | null
  evidenceSummary?: string | null
  evidenceRef?: string | null
}

export interface SuggestionReasonInput {
  reason: string
}

export interface SuggestionModifyInput {
  reason: string
  modifications: string
}

/** 建议转改进任务结果。 */
export interface ConvertToTaskResult {
  taskId: string
  suggestionId?: string
  [key: string]: unknown
}

// ── 二次评价（前后对比） ──────────────────────────────────────
export interface EvaluationSnapshot {
  id: string
  score?: number | null
  comment?: string | null
  evaluatedAt?: string | null
  evaluatorId?: string | null
  taskId?: string | null
  studentId?: string | null
  [key: string]: unknown
}

export interface SecondEvaluationCreateInput {
  /** 对应后端 first_evaluation_id（请求体 camelCase） */
  firstEvaluationId: string
  taskId?: string | null
  studentId?: string | null
  evaluatorId?: string | null
  score?: number | null
  comment?: string | null
}

export interface SecondEvaluationComparison {
  first: EvaluationSnapshot | null
  second: EvaluationSnapshot | null
  /** 后-前 的分值变化 */
  delta: number | null
  /** 改进率（百分比 0-100 或小数 0-1） */
  improvementRate: number | null
  [key: string]: unknown
}

// ── 项目学情聚合（目标/知识点/指标达成） ─────────────────────
export interface GoalAchievement {
  goalId: string
  goalName: string
  /** 达成率，0-1 或 0-100，由视图归一化为百分比 */
  achievementRate: number
  studentCount?: number
}

export interface KnowledgePointAchievement {
  name: string
  masteryRate: number
  studentCount?: number
  averageScore?: number
}

export interface IndicatorAchievement {
  indicatorId: string
  observableBehavior: string
  achievementRate: number
}

export interface StageAchievement {
  stage: string
  label?: string
  achievementRate: number
  studentCount?: number
}

export interface ProjectLearningAggregations {
  goals: GoalAchievement[]
  knowledgePoints: KnowledgePointAchievement[]
  indicators: IndicatorAchievement[]
  stages: StageAchievement[]
  /** 班级共性薄弱点（知识点名称或描述） */
  weakPoints: string[]
  totalStudents?: number
  [key: string]: unknown
}

// ── 标签字典 ─────────────────────────────────────────────────
export const SUGGESTION_STATUS_LABELS: Record<string, string> = {
  pending: '待处理',
  adopted: '已采用',
  modified: '已修改',
  rejected: '已拒绝',
  converted: '已转任务',
}

export const SUGGESTION_STATUS_TYPES: Record<string, string> = {
  pending: 'warning',
  adopted: 'success',
  modified: 'primary',
  rejected: 'info',
  converted: 'success',
}

export const SUGGESTION_PRIORITY_LABELS: Record<string, string> = {
  high: '高',
  medium: '中',
  low: '低',
}

export const SUGGESTION_PRIORITY_TYPES: Record<string, string> = {
  high: 'danger',
  medium: 'warning',
  low: 'info',
}
