import http from './index'
import type { ApiResponse, School, ClassItem } from '@/types'

export function listSchoolsApi(params?: { skip?: number; limit?: number }) {
  return http.get<ApiResponse<School[]>>('/schools', { params })
}

export function getSchoolApi(id: string) {
  return http.get<ApiResponse<School>>(`/schools/${id}`)
}

export function listClassesBySchoolApi(schoolId: string, params?: { skip?: number; limit?: number }) {
  return http.get<ApiResponse<ClassItem[]>>(`/schools/${schoolId}/classes`, { params })
}

export function createClassApi(schoolId: string, data: { name: string; grade: string; head_teacher_id?: string }) {
  return http.post<ApiResponse<ClassItem>>(`/schools/${schoolId}/classes`, data)
}

export function getClassApi(classId: string) {
  return http.get<ApiResponse<ClassItem>>(`/schools/classes/${classId}`)
}

export function updateClassApi(classId: string, data: { name?: string; grade?: string; head_teacher_id?: string }) {
  return http.put<ApiResponse<ClassItem>>(`/schools/classes/${classId}`, data)
}

export function deleteClassApi(classId: string) {
  return http.delete<ApiResponse<null>>(`/schools/classes/${classId}`)
}
