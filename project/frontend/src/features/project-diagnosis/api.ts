/**
 * 项目学情诊断 API 封装（Task 6）。
 *
 * 所有函数返回 axios 响应（拦截器已将 body 的 key 转为 camelCase），
 * 调用方通过 `res.data.data` 取业务数据。
 *
 * 端点对应后端 `app.modules.project_learning_insights.router`：
 * - GET    /projects/{project_id}/insights/latest
 * - POST   /projects/{project_id}/insights/generate
 * - POST   /projects/{project_id}/insights/{insight_id}/confirm
 *
 * 关键约束：
 * - latest 在无诊断时后端返回 data=null（前端不视为错误）。
 * - generate 在无证据时后端返回 insufficient_evidence 状态（前端不显示成功）。
 * - confirm 仅 draft 状态可确认；归档项目与无证据诊断返回 409。
 */
import http from '@/api'
import type { ApiResponse } from '@/types'
import type {
  InsightConfirmRequest,
  ProjectLearningInsight,
} from './types'

/** 拉取项目当前学情诊断；无诊断时后端返回 data=null。 */
export function getLatestInsightApi(projectId: string) {
  return http.get<ApiResponse<ProjectLearningInsight | null>>(
    `/projects/${projectId}/insights/latest`,
  )
}

/** 生成项目学情诊断；无证据时返回 insufficient_evidence，不抛错。 */
export function generateInsightApi(projectId: string) {
  return http.post<ApiResponse<ProjectLearningInsight>>(
    `/projects/${projectId}/insights/generate`,
  )
}

/** 确认项目学情诊断；teacherNote 留痕人工诊断依据。 */
export function confirmInsightApi(
  projectId: string,
  insightId: string,
  data: InsightConfirmRequest,
) {
  return http.post<ApiResponse<ProjectLearningInsight>>(
    `/projects/${projectId}/insights/${insightId}/confirm`,
    data,
  )
}
