/**
 * 学情改进领域 API（计划 Task 7 / 验收 3.7）。
 *
 * 端点前缀：
 * - /api/v1/improvements                              改进建议 + 二次评价
 * - /api/v1/learning-profile/projects/:id/aggregations   项目达成聚合
 *
 * 所有函数返回 axios 响应（拦截器已将 body 的 key 转为 camelCase），
 * 调用方通过 `res.data.data` 取业务数据。
 *
 * 约定：请求体使用 camelCase（与既有 features 一致），
 * 查询参数使用 snake_case（匹配后端 query 参数名）。
 */
import http from '@/api/index'
import type { ApiResponse } from '@/types'
import type {
  ConvertToTaskResult,
  ImprovementSuggestion,
  ImprovementSuggestionCreateInput,
  ImprovementSuggestionListResponse,
  ProjectLearningAggregations,
  SecondEvaluationComparison,
  SecondEvaluationCreateInput,
  SuggestionModifyInput,
  SuggestionReasonInput,
} from './types'

// ── 改进建议 ──────────────────────────────────────────────────
/** 1. 建议列表（按项目过滤） */
export function listSuggestionsApi(projectId: string) {
  return http.get<ApiResponse<ImprovementSuggestionListResponse>>(
    '/improvements/suggestions',
    {
      params: { project_id: projectId },
    },
  )
}

/** 2. 创建建议（必须引用 evidence_record_id） */
export function createSuggestionApi(data: ImprovementSuggestionCreateInput) {
  return http.post<ApiResponse<ImprovementSuggestion>>(
    '/improvements/suggestions',
    data,
  )
}

/** 3. 采用建议（原因留痕） */
export function adoptSuggestionApi(
  suggestionId: string,
  data: SuggestionReasonInput,
) {
  return http.post<ApiResponse<ImprovementSuggestion>>(
    `/improvements/suggestions/${suggestionId}/adopt`,
    data,
  )
}

/** 4. 修改建议（原因 + 修改说明留痕） */
export function modifySuggestionApi(
  suggestionId: string,
  data: SuggestionModifyInput,
) {
  return http.post<ApiResponse<ImprovementSuggestion>>(
    `/improvements/suggestions/${suggestionId}/modify`,
    data,
  )
}

/** 5. 拒绝建议（原因留痕） */
export function rejectSuggestionApi(
  suggestionId: string,
  data: SuggestionReasonInput,
) {
  return http.post<ApiResponse<ImprovementSuggestion>>(
    `/improvements/suggestions/${suggestionId}/reject`,
    data,
  )
}

/** 6. 建议转改进任务 */
export function convertSuggestionToTaskApi(suggestionId: string) {
  return http.post<ApiResponse<ConvertToTaskResult>>(
    `/improvements/suggestions/${suggestionId}/convert-to-task`,
  )
}

// ── 二次评价（前后对比） ──────────────────────────────────────
/** 7. 创建二次评价（firstEvaluationId 必填） */
export function createSecondEvaluationApi(data: SecondEvaluationCreateInput) {
  return http.post<ApiResponse<{ id: string; [key: string]: unknown }>>(
    '/improvements/second-evaluations',
    data,
  )
}

/** 8. 前后对比 */
export function getSecondEvaluationComparisonApi(secondEvaluationId: string) {
  return http.get<ApiResponse<SecondEvaluationComparison>>(
    `/improvements/second-evaluations/${secondEvaluationId}/comparison`,
  )
}

// ── 项目学情聚合 ─────────────────────────────────────────────
/** 9. 目标/知识点/指标达成聚合 */
export function getProjectAggregationsApi(projectId: string) {
  return http.get<ApiResponse<ProjectLearningAggregations>>(
    `/learning-profile/projects/${projectId}/aggregations`,
  )
}
