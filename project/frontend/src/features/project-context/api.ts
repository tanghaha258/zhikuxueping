/**
 * 统一项目上下文 API 封装（Task 3）。
 *
 * 所有函数返回 axios 响应（拦截器已将 body 的 key 转为 camelCase），
 * 调用方通过 `res.data.data` 取业务数据。
 *
 * 端点对应后端 `app.modules.project_workspace.router`：
 * - GET    /project-workspace/{project_id}/context
 * - GET    /project-workspace/{project_id}/timeline
 * - POST   /project-workspace/{project_id}/phases/{phase}/complete
 * - POST   /project-workspace/{project_id}/phases/{phase}/reopen
 */
import http from '@/api'
import type { ApiResponse } from '@/types'
import type {
  PhaseKey,
  PhaseReopenRequest,
  ProjectWorkspaceContext,
  ProjectWorkspacePhase,
  ProjectWorkspaceTimelineEvent,
} from './types'

/** 拉取统一项目上下文。 */
export function getProjectContextApi(projectId: string) {
  return http.get<ApiResponse<ProjectWorkspaceContext>>(
    `/project-workspace/${projectId}/context`,
  )
}

/** 拉取项目时间线事件。 */
export function getProjectTimelineApi(projectId: string) {
  return http.get<ApiResponse<ProjectWorkspaceTimelineEvent[]>>(
    `/project-workspace/${projectId}/timeline`,
  )
}

/** 标记指定阶段完成。 */
export function completePhaseApi(projectId: string, phase: PhaseKey) {
  return http.post<ApiResponse<ProjectWorkspacePhase>>(
    `/project-workspace/${projectId}/phases/${phase}/complete`,
  )
}

/** 重新开放已完成阶段；reason 留痕便于审计。 */
export function reopenPhaseApi(
  projectId: string,
  phase: PhaseKey,
  reason?: string | null,
) {
  const body: PhaseReopenRequest = reason ? { reason } : {}
  return http.post<ApiResponse<ProjectWorkspacePhase>>(
    `/project-workspace/${projectId}/phases/${phase}/reopen`,
    body,
  )
}
