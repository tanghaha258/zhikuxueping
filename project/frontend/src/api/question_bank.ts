import http from './index'
import type { ApiResponse } from '@/types'

export function listQuestionsApi(params?: Record<string, any>) {
  return http.get<ApiResponse<{ items: any[]; total: number }>>('/question-bank/questions', { params })
}

export function createQuestionApi(data: Record<string, any>) {
  return http.post<ApiResponse<any>>('/question-bank/questions', data)
}

export function getQuestionApi(id: string) {
  return http.get<ApiResponse<any>>(`/question-bank/questions/${id}`)
}

export function updateQuestionApi(id: string, data: Record<string, any>) {
  return http.put<ApiResponse<any>>(`/question-bank/questions/${id}`, data)
}

export function deleteQuestionApi(id: string) {
  return http.delete<ApiResponse<any>>(`/question-bank/questions/${id}`)
}

export function aiGenerateQuestionsApi(data: Record<string, any>) {
  return http.post<ApiResponse<any>>('/question-bank/ai-generate', data)
}

export function batchImportQuestionsApi(data: Record<string, any>) {
  return http.post<ApiResponse<any>>('/question-bank/batch-import', data)
}

export function smartComposeApi(data: Record<string, any>) {
  return http.post<ApiResponse<any>>('/paper-generator/smart-compose', data)
}

/** 获取题库质量统计 */
export function getQuestionQualityStats() {
  return http.get<ApiResponse<any>>('/question-bank/quality/stats')
}

/** 获取题目质量详情 */
export function getQuestionQuality(id: string) {
  return http.get<ApiResponse<any>>(`/question-bank/${id}/quality`)
}
