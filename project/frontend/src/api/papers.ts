import http from './index'
import type { ApiResponse, Paper, PaperCreateForm, PaperUpdateForm, AnswerKeyUpsert, AnswerKey, PaperSubmission, PaperStats } from '@/types'

export function listPapersApi(params?: { skip?: number; limit?: number }) {
  return http.get<ApiResponse<{ items: Paper[]; total: number }>>('/papers', { params })
}

export function createPaperApi(data: PaperCreateForm) {
  return http.post<ApiResponse<Paper>>('/papers', data)
}

export function getPaperApi(id: string) {
  return http.get<ApiResponse<Paper>>(`/papers/${id}`)
}

export function updatePaperApi(id: string, data: PaperUpdateForm) {
  return http.put<ApiResponse<Paper>>(`/papers/${id}`, data)
}

export function deletePaperApi(id: string) {
  return http.delete<ApiResponse<null>>(`/papers/${id}`)
}

export function setAnswerKeyApi(paperId: string, data: AnswerKeyUpsert) {
  return http.post<ApiResponse<AnswerKey>>(`/papers/${paperId}/answer-key`, data)
}

export function getAnswerKeyApi(paperId: string) {
  return http.get<ApiResponse<AnswerKey>>(`/papers/${paperId}/answer-key`)
}

export function distributePaperApi(paperId: string) {
  return http.post<ApiResponse<{ distributed: number }>>(`/papers/${paperId}/distribute`)
}

export function listSubmissionsApi(paperId: string) {
  return http.get<ApiResponse<PaperSubmission[]>>(`/papers/${paperId}/submissions`)
}

export function getPaperStatsApi(paperId: string) {
  return http.get<ApiResponse<PaperStats>>(`/papers/${paperId}/stats`)
}

export function evaluatePaperApi(paperId: string) {
  return http.post<ApiResponse<{ total: number; completed: number }>>(`/papers/${paperId}/evaluate`)
}
