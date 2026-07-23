/**
 * 运营证据领域 API（计划 Task 8 / 验收 3.8.3）。
 *
 * 端点前缀：
 * - /api/v1/operational-evidence/metrics        指标 CRUD + 详情
 * - /api/v1/operational-evidence/metrics/:id/evidence   证据台账
 * - /api/v1/operational-evidence/exports/preview        导出预览（含脱敏）
 * - /api/v1/operational-evidence/exports/confirm        导出二次确认
 * - /api/v1/operational-evidence/exports               导出审计记录
 * - /api/v1/dashboard/operational-metrics/summary       驾驶舱指标汇总
 *
 * 默认仅返回真实数据（data_origin=real），不混入测试/演示/导入数据。
 */
import http from '@/api/index'
import type { ApiResponse } from '@/types'
import type {
  EvidenceLedger,
  EvidenceLedgerCreateInput,
  EvidenceLedgerListResponse,
  EvidenceLedgerQuery,
  ExportConfirmByIdInput,
  ExportConfirmInput,
  ExportPreviewInput,
  ExportPreviewResponse,
  ExportRecord,
  ExportRecordListResponse,
  OperationalMetric,
  OperationalMetricCreateInput,
  OperationalMetricDetail,
  OperationalMetricListResponse,
} from './types'
import type { DataOrigin, OperationalMetricPeriod } from './types'

// ── 运营指标 ──────────────────────────────────────────────────
export function listOperationalMetricsApi(params: {
  dataOrigin?: DataOrigin
  schoolId?: string
  period?: OperationalMetricPeriod
} = {}) {
  return http.get<ApiResponse<OperationalMetricListResponse>>(
    '/operational-evidence/metrics',
    {
      params: {
        data_origin: params.dataOrigin,
        school_id: params.schoolId,
        period: params.period,
      },
    },
  )
}

export function getOperationalMetricApi(metricId: string) {
  return http.get<ApiResponse<OperationalMetricDetail>>(
    `/operational-evidence/metrics/${metricId}`,
  )
}

export function createOperationalMetricApi(data: OperationalMetricCreateInput) {
  return http.post<ApiResponse<OperationalMetric>>(
    '/operational-evidence/metrics',
    data,
  )
}

// ── 证据台账 ──────────────────────────────────────────────────
export function listEvidenceByMetricApi(metricId: string) {
  return http.get<ApiResponse<{ items: EvidenceLedger[]; total: number }>>(
    `/operational-evidence/metrics/${metricId}/evidence`,
  )
}

export function registerEvidenceApi(
  metricId: string,
  data: EvidenceLedgerCreateInput,
) {
  return http.post<ApiResponse<EvidenceLedger>>(
    `/operational-evidence/metrics/${metricId}/evidence`,
    data,
  )
}

// ── 导出预览/二次确认/审计 ─────────────────────────────────────
export function previewExportApi(data: ExportPreviewInput) {
  return http.post<ApiResponse<ExportPreviewResponse>>(
    '/operational-evidence/exports/preview',
    data,
  )
}

export function confirmExportApi(data: ExportConfirmInput) {
  return http.post<ApiResponse<ExportRecord>>(
    '/operational-evidence/exports/confirm',
    data,
  )
}

export function listExportRecordsApi() {
  return http.get<ApiResponse<ExportRecordListResponse>>(
    '/operational-evidence/exports',
  )
}

// ── 驾驶舱指标汇总（接 dashboard 端点，默认仅真实数据）─────────
export function getOperationalMetricsSummaryApi(params: {
  dataOrigin?: DataOrigin
} = {}) {
  return http.get<ApiResponse<OperationalMetricListResponse>>(
    '/dashboard/operational-metrics/summary',
    {
      params: { data_origin: params.dataOrigin },
    },
  )
}

// ── 证据台账（通用，跨指标，来源追溯） ─────────────────────────
/**
 * 证据台账列表（GET /operational-evidence/evidence-ledger）。
 * 可按指标 id / code / 学校过滤，用于来源追溯。
 */
export function listEvidenceLedgerApi(params: EvidenceLedgerQuery = {}) {
  return http.get<ApiResponse<EvidenceLedgerListResponse>>(
    '/operational-evidence/evidence-ledger',
    {
      params: {
        metric_id: params.metricId,
        metric_code: params.metricCode,
        school_id: params.schoolId,
        limit: params.limit,
      },
    },
  )
}

// ── 二次确认导出（路径参数 preview_id 版本，Task 8 验收） ───────
/**
 * 二次确认导出（POST /operational-evidence/exports/{preview_id}/confirm）。
 * 与 confirmExportApi（body 传 exportId）不同，此处 previewId 在 URL 路径中。
 */
export function confirmExportByIdApi(
  previewId: string,
  data: ExportConfirmByIdInput = {},
) {
  return http.post<ApiResponse<ExportRecord>>(
    `/operational-evidence/exports/${previewId}/confirm`,
    data,
  )
}
