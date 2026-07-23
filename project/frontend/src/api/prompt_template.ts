import http from './index'
import type { ApiResponse } from '@/types'

export interface PromptTemplate {
  id: string
  name: string
  subject: string
  examType: string
  template: string
  description: string | null
  isActive: boolean
  createdAt: string | null
  updatedAt: string | null
}

export function listPromptTemplatesApi(params?: { subject?: string; examType?: string; isActive?: boolean }) {
  return http.get<ApiResponse<PromptTemplate[]>>('/prompt-templates', { params })
}

export function getActivePromptTemplateApi(subject: string, examType: string) {
  return http.get<ApiResponse<PromptTemplate | null>>('/prompt-templates/active', { params: { subject, exam_type: examType } })
}

export function createPromptTemplateApi(data: {
  name: string; subject: string; examType: string; template: string; description?: string; isActive?: boolean
}) {
  return http.post<ApiResponse<PromptTemplate>>('/prompt-templates', data)
}

export function updatePromptTemplateApi(id: string, data: Record<string, unknown>) {
  return http.put<ApiResponse<PromptTemplate>>(`/prompt-templates/${id}`, data)
}

export function deletePromptTemplateApi(id: string) {
  return http.delete<ApiResponse<null>>(`/prompt-templates/${id}`)
}
