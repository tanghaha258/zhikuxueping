/**
 * 学生空间领域 API（Task 6 / 计划 3.7）。
 *
 * 端点前缀：/api/v1/student
 * （http 实例 baseURL 已配置 /api/v1）
 *
 * 约定：
 * - 请求体使用 snake_case（后端 Pydantic 字段为 snake_case，无全局别名）。
 * - 响应体经 http 拦截器自动转为 camelCase，调用方通过 `res.data.data` 取业务数据。
 */
import http from '@/api/index'
import type { ApiResponse } from '@/types'
import type {
  DraftSaveInput,
  GrowthPortfolio,
  IdempotentSubmitInput,
  IdempotentSubmitResult,
  ReassessInput,
  ResubmitInput,
  StudentFeedbackView,
  StudentProjectView,
  StudentSubmission,
  SubmissionRevision,
} from './types'

// ── 草稿与提交（计划 3.7.3） ───────────────────────────────────
export function saveDraftApi(data: DraftSaveInput) {
  return http.post<ApiResponse<StudentSubmission>>('/student/drafts', data)
}

export function idempotentSubmitApi(data: IdempotentSubmitInput) {
  return http.post<ApiResponse<IdempotentSubmitResult>>('/student/submissions', data)
}

export function resubmitApi(submissionId: string, data: ResubmitInput) {
  return http.post<ApiResponse<IdempotentSubmitResult>>(
    `/student/submissions/${submissionId}/resubmit`,
    data,
  )
}

export function requestReassessApi(submissionId: string, data: ReassessInput) {
  return http.post<ApiResponse<StudentSubmission>>(
    `/student/submissions/${submissionId}/reassess`,
    data,
  )
}

// ── 版本记录与反馈（计划 3.7.4） ───────────────────────────────
export function listRevisionsApi(submissionId: string) {
  return http.get<ApiResponse<SubmissionRevision[]>>(
    `/student/submissions/${submissionId}/revisions`,
  )
}

export function getStudentFeedbackApi(submissionId: string) {
  return http.get<ApiResponse<StudentFeedbackView>>(
    `/student/submissions/${submissionId}/feedback`,
  )
}

// ── 学生项目空间（计划 3.7.2） ─────────────────────────────────
export function getStudentProjectApi(projectId: string) {
  return http.get<ApiResponse<StudentProjectView>>(
    `/student/projects/${projectId}`,
  )
}

// ── 成长档案（计划 3.7.5） ─────────────────────────────────────
export function getGrowthPortfolioApi() {
  return http.get<ApiResponse<GrowthPortfolio>>('/student/growth')
}
