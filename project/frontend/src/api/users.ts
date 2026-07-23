import http from './index'
import type { ApiResponse, PaginatedResponse, UserInfo } from '@/types'

export interface UserCreateForm {
  username: string
  password: string
  email: string
  display_name: string
  role: string
  school_id?: string
}

export interface UserUpdateForm {
  email?: string
  display_name?: string
  role?: string
  school_id?: string
  is_active?: boolean
}

export function listUsersApi(params: {
  skip?: number
  limit?: number
  keyword?: string
  role?: string
  is_active?: boolean | null
}) {
  return http.get<ApiResponse<PaginatedResponse<UserInfo>>>('/users', { params })
}

export function getUserApi(id: string) {
  return http.get<ApiResponse<UserInfo>>(`/users/${id}`)
}

export function createUserApi(data: UserCreateForm) {
  return http.post<ApiResponse<UserInfo>>('/users', data)
}

export function updateUserApi(id: string, data: UserUpdateForm) {
  return http.patch<ApiResponse<UserInfo>>(`/users/${id}`, data)
}

export function toggleUserStatusApi(id: string) {
  return http.patch<ApiResponse<UserInfo>>(`/users/${id}/status`)
}
