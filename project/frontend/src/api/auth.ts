import http from './index'
import type { ApiResponse, LoginRequest, LoginResponse, UserInfo } from '@/types'

export function loginApi(data: LoginRequest) {
  return http.post<ApiResponse<LoginResponse>>('/auth/login', data)
}

export function registerApi(data: {
  username: string
  password: string
  email: string
  displayName: string
  role: string
}) {
  return http.post<ApiResponse<null>>('/auth/register', data)
}

export function getUserInfoApi() {
  return http.get<ApiResponse<UserInfo>>('/auth/me')
}

export function refreshTokenApi(refreshToken: string) {
  return http.post<ApiResponse<{ accessToken: string; refreshToken: string; expiresIn: number }>>('/auth/refresh', {
    refresh_token: refreshToken,
  })
}

export function logoutApi() {
  return http.post<ApiResponse<null>>('/auth/logout')
}

export function updateProfileApi(data: { display_name?: string; email?: string; phone?: string }) {
  return http.put<ApiResponse<UserInfo>>('/auth/me', data)
}

export function changePasswordApi(data: { old_password: string; new_password: string }) {
  return http.put<ApiResponse<null>>('/auth/me/password', data)
}
