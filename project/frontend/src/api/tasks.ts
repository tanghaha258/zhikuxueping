import http from './index'
import type {
  ApiResponse,
  PaginatedResponse,
  Task,
  TaskCreateForm,
  TaskDependency,
  TaskDependencyListResponse,
  TaskPublishPreview,
  TaskTransitionRequest,
  TaskUpdateForm,
  TaskAssignment,
  TaskStats,
} from '@/types'

export function listTasksApi(params: {
  project_id: string
  skip?: number
  limit?: number
  stage?: string
  tier?: string
  publish_status?: string
}) {
  return http.get<ApiResponse<PaginatedResponse<Task>>>('/tasks', { params })
}

export function listMyTasksApi() {
  return http.get<ApiResponse<Task[]>>('/tasks/my')
}

export function createTaskApi(data: TaskCreateForm) {
  return http.post<ApiResponse<Task>>('/tasks', data)
}

export function getTaskApi(id: string) {
  return http.get<ApiResponse<Task>>(`/tasks/${id}`)
}

export function updateTaskApi(id: string, data: TaskUpdateForm) {
  return http.put<ApiResponse<Task>>(`/tasks/${id}`, data)
}

export function deleteTaskApi(id: string) {
  return http.delete<ApiResponse<null>>(`/tasks/${id}`)
}

export function listTaskAssignmentsApi(taskId: string) {
  return http.get<ApiResponse<TaskAssignment[]>>(`/tasks/${taskId}/assignments`)
}

export function setTaskAssignmentsApi(taskId: string, studentIds: string[]) {
  return http.post<ApiResponse<TaskAssignment[]>>(
    `/tasks/${taskId}/assignments`,
    { student_ids: studentIds },
  )
}

export function publishTaskApi(id: string) {
  return http.post<ApiResponse<Task>>(`/tasks/${id}/publish`)
}

export function closeTaskApi(id: string) {
  return http.post<ApiResponse<Task>>(`/tasks/${id}/close`)
}

export function getTaskStatsApi() {
  return http.get<ApiResponse<TaskStats>>('/tasks/stats')
}

// ── 核心闭环扩展：依赖管理（计划 3.5.4）──────────────────────
export function addTaskDependencyApi(successorId: string, predecessorId: string) {
  return http.post<ApiResponse<TaskDependency>>(
    `/tasks/${successorId}/dependencies`,
    { predecessor_id: predecessorId },
  )
}

export function removeTaskDependencyApi(successorId: string, predecessorId: string) {
  return http.delete<ApiResponse<null>>(
    `/tasks/${successorId}/dependencies/${predecessorId}`,
  )
}

export function listTaskDependenciesApi(taskId: string) {
  return http.get<ApiResponse<TaskDependencyListResponse>>(
    `/tasks/${taskId}/dependencies`,
  )
}

// ── 核心闭环扩展：发布状态机与预览（计划 4.3/3.5.4）──────────
export function transitionTaskApi(taskId: string, data: TaskTransitionRequest) {
  return http.post<ApiResponse<Task>>(`/tasks/${taskId}/transition`, data)
}

export function getPublishPreviewApi(taskId: string) {
  return http.get<ApiResponse<TaskPublishPreview>>(
    `/tasks/${taskId}/publish-preview`,
  )
}
