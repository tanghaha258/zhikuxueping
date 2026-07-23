import http from './index'
import type { ApiResponse } from '@/types'

export function listTemplatesApi(params?: { subject?: string; grade?: string; skip?: number; limit?: number }) {
  return http.get<ApiResponse<{ items: any[]; total: number }>>('/paper-generator/templates', { params })
}

export function createTemplateApi(data: {
  name: string
  subject: string
  grade: string
  exam_type?: string
  total_score?: number
  sections?: string  // JSON string
}) {
  return http.post<ApiResponse<any>>('/paper-generator/templates', data)
}

export function updateTemplateApi(id: string, data: Record<string, any>) {
  return http.put<ApiResponse<any>>(`/paper-generator/templates/${id}`, data)
}

export function syncTemplateApi(id: string) {
  return http.post<ApiResponse<any>>(`/paper-generator/templates/${id}/sync`)
}

export function getTemplateApi(id: string) {
  return http.get<ApiResponse<any>>(`/paper-generator/templates/${id}`)
}

export function generatePaperApi(data: {
  subject: string
  grade: string
  template_id?: string
  title?: string
  difficulty?: string
  knowledge_points?: string[]
  sections?: string     // JSON string of SectionItem[]
  exam_type?: string    // quiz|midterm|final|general
}) {
  return http.post<ApiResponse<any>>('/paper-generator/generate', data)
}

export function listGeneratedPapersApi(params?: { skip?: number; limit?: number }) {
  return http.get<ApiResponse<{ items: any[]; total: number }>>('/paper-generator/papers', { params })
}

export function getGeneratedPaperApi(id: string) {
  return http.get<ApiResponse<any>>(`/paper-generator/papers/${id}`)
}

export function updateGeneratedPaperApi(id: string, data: any) {
  return http.put<ApiResponse<any>>(`/paper-generator/papers/${id}`, data)
}

export function finalizePaperApi(id: string) {
  return http.post<ApiResponse<any>>(`/paper-generator/papers/${id}/finalize`)
}

export function exportPaperApi(id: string, format = 'html') {
  return http.post<any>(`/paper-generator/papers/${id}/export`, null, {
    params: { format },
    responseType: format === 'html' ? 'text' : 'blob',
  })
}

export function deleteGeneratedPaperApi(id: string) {
  return http.delete<ApiResponse<any>>(`/paper-generator/papers/${id}`)
}

export function listKnowledgePointsApi(params?: { subject?: string; grade?: string }) {
  return http.get<ApiResponse<any[]>>('/paper-generator/knowledge-points', { params })
}

export function formatPaperApi(paperId: string, data: { template_type: string; subject: string }) {
  return http.post<ApiResponse<any>>(`/paper-generator/papers/${paperId}/format`, data)
}

export function getFormattedPaperApi(paperId: string) {
  return http.get<ApiResponse<any>>(`/paper-generator/papers/${paperId}/formatted`)
}

export function updateFormattedPaperApi(paperId: string, data: { formatted_html: string; template_config?: string }) {
  return http.put<ApiResponse<any>>(`/paper-generator/papers/${paperId}/formatted`, data)
}
