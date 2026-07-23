/**
 * 运营证据领域类型（计划 Task 8 / 验收 3.8.3）。
 *
 * 后端响应经过 http 拦截器 snake_case → camelCase 转换，
 * 故此处均使用 camelCase。对应后端 `app/schemas/operational_evidence.py`。
 */

// ── 枚举 ─────────────────────────────────────────────────────
export type DataOrigin = 'real' | 'test' | 'demo' | 'imported'

export type OperationalMetricPeriod =
  | 'daily'
  | 'weekly'
  | 'monthly'
  | 'quarterly'
  | 'annual'
  | 'ad_hoc'

export type ExportStatus = 'pending' | 'previewed' | 'confirmed' | 'failed' | 'revoked'

// ── 运营指标 ──────────────────────────────────────────────────
export interface OperationalMetric {
  id: string
  name: string
  code: string
  formula: string
  period: OperationalMetricPeriod | string
  sampleSize?: number | null
  sourceTable?: string | null
  sourceOwner?: string | null
  responsiblePerson?: string | null
  dataOrigin?: DataOrigin | string
  value?: number | null
  valueCollectedAt?: string | null
  schoolId?: string | null
  createdAt?: string | null
  updatedAt?: string | null
}

export interface OperationalMetricDetail {
  metric: OperationalMetric
  evidence: EvidenceLedger[]
}

export interface OperationalMetricListResponse {
  items: OperationalMetric[]
  total: number
}

export interface OperationalMetricCreateInput {
  name: string
  code: string
  formula: string
  period: OperationalMetricPeriod
  sampleSize?: number | null
  sourceTable?: string | null
  sourceOwner?: string | null
  responsiblePerson?: string | null
  dataOrigin?: DataOrigin
  value?: number | null
  valueCollectedAt?: string | null
  schoolId?: string | null
}

// ── 证据台账 ──────────────────────────────────────────────────
export interface EvidenceLedger {
  id: string
  metricId: string
  evidenceRef: string
  evidenceSummary?: string | null
  collectedAt: string
  verifiedBy?: string | null
  createdAt?: string | null
}

export interface EvidenceLedgerCreateInput {
  metricId: string
  evidenceRef: string
  evidenceSummary?: string
  collectedAt: string
}

// ── 导出 ─────────────────────────────────────────────────────
export interface ExportRecord {
  id: string
  exporterId: string
  scopeSchoolId?: string | null
  metricIds?: string | null
  anonymized: boolean
  status: ExportStatus | string
  auditNote?: string | null
  confirmedAt?: string | null
  payloadRef?: string | null
  createdAt?: string | null
  updatedAt?: string | null
}

export interface ExportPreviewInput {
  metricIds: string[]
  anonymized: boolean
  schoolId?: string | null
}

export interface ExportConfirmInput {
  exportId: string
  auditNote?: string
}

export interface ExportPreviewResponse {
  export: ExportRecord
  metrics: OperationalMetric[]
  evidence: EvidenceLedger[]
  anonymizationExamples: string[]
}

export interface ExportRecordListResponse {
  items: ExportRecord[]
  total: number
}

// ── 驾驶舱运营指标概览（dashboard.stats 响应扩展） ────────────
export interface DashboardMetricOverviewItem {
  id: string
  name: string
  code: string
  formula: string
  period: OperationalMetricPeriod | string
  sampleSize?: number | null
  sourceTable?: string | null
  sourceOwner?: string | null
  responsiblePerson?: string | null
  value?: number | null
  valueCollectedAt?: string | null
}

// ── 标签字典 ─────────────────────────────────────────────────
export const DATA_ORIGIN_LABELS: Record<string, string> = {
  real: '真实',
  test: '测试',
  demo: '演示',
  imported: '导入',
}

export const DATA_ORIGIN_TYPES: Record<string, string> = {
  real: 'success',
  test: 'warning',
  demo: 'info',
  imported: 'info',
}

export const PERIOD_LABELS: Record<string, string> = {
  daily: '日',
  weekly: '周',
  monthly: '月',
  quarterly: '季',
  annual: '年',
  ad_hoc: '按需',
}

export const EXPORT_STATUS_LABELS: Record<string, string> = {
  pending: '待预览',
  previewed: '已预览',
  confirmed: '已确认',
  failed: '失败',
  revoked: '已撤销',
}

// ── 证据台账（通用，跨指标） ─────────────────────────────────
/** 证据台账查询参数（来源追溯用） */
export interface EvidenceLedgerQuery {
  metricId?: string
  /** 按指标 code 过滤（与 metricId 二选一） */
  metricCode?: string
  schoolId?: string
  limit?: number
}

export interface EvidenceLedgerListResponse {
  items: EvidenceLedger[]
  total: number
}

// ── 二次确认导出（路径参数 preview_id 版本） ─────────────────
/**
 * 路径参数二次确认导出请求体。
 * exportId 已在 URL 路径中（/exports/{preview_id}/confirm），故 body 仅含审计备注。
 */
export interface ExportConfirmByIdInput {
  auditNote?: string
}

export const EXPORT_STATUS_TYPES: Record<string, string> = {
  pending: 'info',
  previewed: 'warning',
  confirmed: 'success',
  failed: 'danger',
  revoked: 'info',
}
