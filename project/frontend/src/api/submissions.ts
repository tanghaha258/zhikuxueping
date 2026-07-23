import http from './index'
import type { ApiResponse, Submission, SubmissionCreateForm, SubmissionUpdateForm } from '@/types'

export function submitTaskApi(data: SubmissionCreateForm) {
  return http.post<ApiResponse<Submission>>('/submissions', data)
}

export function listMySubmissionsApi() {
  return http.get<ApiResponse<Submission[]>>('/submissions/my')
}

export function getMyTaskSubmissionApi(taskId: string) {
  return http.get<ApiResponse<Submission | null>>(`/submissions/task/${taskId}/my`)
}

export function listTaskSubmissionsApi(taskId: string) {
  return http.get<ApiResponse<Submission[]>>(`/submissions/task/${taskId}`)
}

export function getSubmissionApi(id: string) {
  return http.get<ApiResponse<Submission>>(`/submissions/${id}`)
}

export function updateSubmissionApi(id: string, data: SubmissionUpdateForm) {
  return http.patch<ApiResponse<Submission>>(`/submissions/${id}`, data)
}

export function uploadFileApi(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return http.post<ApiResponse<{ url: string; filename: string; size: number }>>('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}
