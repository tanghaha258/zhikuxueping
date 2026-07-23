/**
 * AI 内容治理领域 API（计划 Task 5 / 验收标准 3.5.6）。
 *
 * 端点前缀：
 * - /api/v1/ai-jobs        治理主接口（任务/版本/质量问题）
 * - /api/v1/ai/lesson-plan/from-project    基于项目上下文备课
 * - /api/v1/ai/evaluate/{submission_id}/governed    治理层评分
 * - /api/v1/paper-generator/generate-governed    治理层出卷
 *
 * 所有函数返回 axios 响应（拦截器已将 body 的 key 转为 camelCase），
 * 调用方通过 `res.data.data` 取业务数据。
 */
import http from '@/api/index'
import type { ApiResponse } from '@/types'
import type {
  AiJob,
  AiJobAdoptInput,
  AiJobCreateInput,
  AiJobDetail,
  AiJobListResponse,
  AiJobRegenerateInput,
  AiJobReviewInput,
  QualityIssue,
  QualityIssueResolveInput,
} from './types'

// ── AI 任务 ──────────────────────────────────────────────────
export function listAiJobsApi(params: {
  projectId?: string
  scene?: string
  status?: string
} = {}) {
  return http.get<ApiResponse<AiJobListResponse>>('/ai-jobs', {
    params: {
      project_id: params.projectId,
      scene: params.scene,
      status: params.status,
    },
  })
}

export function createAiJobApi(data: AiJobCreateInput) {
  return http.post<ApiResponse<AiJob>>('/ai-jobs', data)
}

export function getAiJobApi(jobId: string) {
  return http.get<ApiResponse<AiJobDetail>>(`/ai-jobs/${jobId}`)
}

export function transitionAiJobApi(jobId: string, target: string) {
  return http.post<ApiResponse<AiJob>>(`/ai-jobs/${jobId}/transition`, {
    target,
  })
}

export function retryAiJobApi(jobId: string) {
  return http.post<ApiResponse<AiJob>>(`/ai-jobs/${jobId}/retry`)
}

export function reviewAiJobApi(jobId: string, data: AiJobReviewInput) {
  return http.post<ApiResponse<AiJob>>(`/ai-jobs/${jobId}/review`, data)
}

export function adoptAiJobApi(jobId: string, data: AiJobAdoptInput) {
  return http.post<ApiResponse<AiJob>>(`/ai-jobs/${jobId}/adopt`, data)
}

export function regenerateAiJobApi(jobId: string, data: AiJobRegenerateInput) {
  return http.post<ApiResponse<AiJobDetail>>(`/ai-jobs/${jobId}/regenerate`, data)
}

// ── 质量问题 ──────────────────────────────────────────────────
export function resolveQualityIssueApi(
  issueId: string,
  data: QualityIssueResolveInput,
) {
  return http.post<ApiResponse<QualityIssue>>(
    `/ai-jobs/quality-issues/${issueId}/resolve`,
    data,
  )
}

// ── 场景化快捷入口（治理层封装） ──────────────────────────────
export function generateLessonPlanFromProjectApi(projectId: string) {
  return http.post<ApiResponse<AiJobDetail>>('/ai/lesson-plan/from-project', {
    project_id: projectId,
  })
}

export function evaluateSubmissionGovernedApi(submissionId: string) {
  return http.post<ApiResponse<AiJobDetail>>(
    `/ai/evaluate/${submissionId}/governed`,
  )
}

export function generatePaperGovernedApi(projectId: string, outputType = '试卷') {
  return http.post<ApiResponse<AiJobDetail>>(
    '/paper-generator/generate-governed',
    {
      project_id: projectId,
      output_type: outputType,
    },
  )
}
