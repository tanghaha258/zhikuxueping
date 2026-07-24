/**
 * 项目学情诊断领域类型（Task 6）。
 *
 * 字段命名与后端 `app.schemas.project_learning_insight` 对齐；HTTP 拦截器已将
 * snake_case 自动转为 camelCase，因此前端类型统一使用 camelCase。
 *
 * 诊断状态机：
 * - draft：草稿（基于真实证据生成，待教师确认）
 * - insufficient_evidence：无证据（不可确认，需先导入前测/发布任务）
 * - confirmed：教师已确认为正式学情结论
 * - stale：项目数据更新后诊断失效（需重新生成）
 *
 * 关键约束：无证据时返回 insufficient_evidence 与空 segments，绝不生成随机画像或伪成功。
 */

// ── 诊断状态机 ──────────────────────────────────────────────────
export type InsightStatus =
  | 'draft'
  | 'insufficient_evidence'
  | 'confirmed'
  | 'stale'

// ── 来源计数 ────────────────────────────────────────────────────
/** 四类数据来源计数，不伪造。 */
export interface InsightSourceCounts {
  /** 前测（关联到项目的 Paper 中 status=pre_test 的）。 */
  preTest: number
  /** 任务提交（项目下任务的 Submission）。 */
  submissions: number
  /** 已发布评价（学生可见的 EvaluationRecord）。 */
  evaluations: number
  /** 题目作答（PaperSubmission 关联到项目班级）。 */
  questionAnswers: number
}

// ── 分层与薄弱点 ────────────────────────────────────────────────
/** 学生分层建议：基于真实评价分数分组，非随机生成。 */
export interface InsightSegment {
  name: string
  studentCount: number
  /** [下限, 上限]，掌握度 0-1。 */
  masteryRange?: [number, number] | null
}

/** 薄弱点：来自真实低分组学生，非模拟。 */
export interface InsightWeakPoint {
  area: string
  studentCount: number
  /** 平均掌握度 0-1。 */
  avgMastery?: number | null
}

// ── 诊断实体 ────────────────────────────────────────────────────
/** 项目学情诊断响应：聚合来源、快照与确认状态。 */
export interface ProjectLearningInsight {
  id: string
  projectId: string
  status: InsightStatus
  segments: InsightSegment[]
  /** 整体掌握度 0-1；无证据或无已发布评价时为 null。 */
  overallMastery: number | null
  weakPoints: InsightWeakPoint[]
  teachingSuggestions: string[]
  sourceCounts: InsightSourceCounts
  /** 证据截止时间（生成时的数据库快照时间）。 */
  evidenceCutoff: string | null
  generatedAt: string | null
  generatedBy: string | null
  confirmedBy: string | null
  confirmedAt: string | null
  /** 教师确认时的人工诊断留痕（AI 失败时强制走人工诊断的依据）。 */
  teacherNote: string | null
  isCurrent: boolean
}

// ── 请求体 ──────────────────────────────────────────────────────
/** 教师确认诊断请求体；teacherNote 留痕人工诊断依据。 */
export interface InsightConfirmRequest {
  /** null 或空字符串后端会规范化为 null。 */
  teacherNote: string | null
}

// ── 网络错误观察 ────────────────────────────────────────────────
/** 可观察的网络/业务错误快照，供 UI 渲染错误条与人工诊断提示。 */
export interface DiagnosisError {
  /** HTTP 状态码；网络错误为 0。 */
  status: number
  /** 后端业务错误码（如有）。 */
  code: number | null
  message: string
  /** 是否为权限错误（403/跨校访问）。 */
  forbidden: boolean
  /** 是否为未找到（404）。 */
  notFound: boolean
  /** 是否为业务冲突（409：归档只读/无证据不可确认/重复确认）。 */
  conflict: boolean
}

// ── 来源格式化（用于 UI 展示） ──────────────────────────────────
/** 单个来源的可读标签与计数。 */
export interface FormattedSource {
  label: string
  count: number
}
