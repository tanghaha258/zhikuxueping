import http from './index'
import type { ApiResponse, SubjectItem } from '@/types'

export function listSubjectsApi() {
  return http.get<ApiResponse<SubjectItem[]>>('/subjects')
}
