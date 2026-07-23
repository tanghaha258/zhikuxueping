import http from './index'
import type { ApiResponse, PaginatedResponse, Project, ProjectCreateForm, ProjectStudent, ProjectUpdateForm } from '@/types'

export function listProjectsApi(params: {
  skip?: number
  limit?: number
  keyword?: string
  status?: string
  grade?: string
  creator_id?: string
}) {
  return http.get<ApiResponse<PaginatedResponse<Project>>>('/projects', { params })
}

export function createProjectApi(data: ProjectCreateForm) {
  return http.post<ApiResponse<Project>>('/projects', data)
}

export function getProjectApi(id: string) {
  return http.get<ApiResponse<Project>>(`/projects/${id}`)
}

export function listProjectStudentsApi(projectId: string) {
  return http.get<ApiResponse<ProjectStudent[]>>(`/projects/${projectId}/students`)
}

export function updateProjectApi(id: string, data: ProjectUpdateForm) {
  return http.put<ApiResponse<Project>>(`/projects/${id}`, data)
}

export function deleteProjectApi(id: string) {
  return http.delete<ApiResponse<null>>(`/projects/${id}`)
}
