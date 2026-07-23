import axios from 'axios'
import type { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'
import {
  clearSession,
  notifySessionExpired,
  readSession,
  updateSessionTokens,
} from '@/shared/auth/session'
import { STORAGE_KEYS } from '@/utils/constants'
import { transformKeysToCamel } from '@/utils/format'

const http: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

let isRefreshing = false
let pendingRequests: Array<{
  resolve: (token: string) => void
  reject: (err: unknown) => void
}> = []

function getRefreshToken(): string | null {
  return readSession()?.refreshToken || localStorage.getItem(STORAGE_KEYS.REFRESH_TOKEN)
}

async function doRefresh(): Promise<string> {
  const refreshToken = getRefreshToken()
  if (!refreshToken) throw new Error('no refresh token')

  const response = await axios.post('/api/v1/auth/refresh', { refresh_token: refreshToken })
  const data = transformKeysToCamel(response.data) as Record<string, any>
  const body = data?.data || {}
  const accessToken: string = body.accessToken
  const nextRefreshToken: string = body.refreshToken

  updateSessionTokens(accessToken, nextRefreshToken)
  return accessToken
}

function onRefreshSuccess(token: string) {
  pendingRequests.forEach(({ resolve }) => resolve(token))
  pendingRequests = []
}

function onRefreshFailed(error: unknown) {
  pendingRequests.forEach(({ reject }) => reject(error))
  pendingRequests = []
  clearSession()
  notifySessionExpired()
}

http.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem(STORAGE_KEYS.TOKEN)
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error: AxiosError) => Promise.reject(error),
)

http.interceptors.response.use(
  (response) => {
    if (response.data) {
      response.data = transformKeysToCamel(response.data)
    }
    const { code, message } = response.data || {}
    if (code !== undefined && code !== 0 && code !== 200) {
      ElMessage.error(message || '请求失败')
      return Promise.reject(new Error(message || '请求失败'))
    }
    return response
  },
  async (error: AxiosError) => {
    const status = error.response?.status
    const data = error.response?.data as Record<string, unknown> | undefined
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean }

    if (status === 401 && originalRequest && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise<string>((resolve, reject) => {
          pendingRequests.push({ resolve, reject })
        }).then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`
          return http(originalRequest)
        })
      }

      originalRequest._retry = true
      isRefreshing = true

      try {
        const token = await doRefresh()
        onRefreshSuccess(token)
        originalRequest.headers.Authorization = `Bearer ${token}`
        return http(originalRequest)
      } catch (refreshError) {
        onRefreshFailed(refreshError)
        ElMessage.error('登录已过期，请重新登录')
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    switch (status) {
      case 403:
        ElMessage.error('没有权限执行此操作')
        break
      case 404:
        ElMessage.error('请求的资源不存在')
        break
      case 500:
        ElMessage.error('服务器内部错误')
        break
      default:
        if (status !== 401) {
          ElMessage.error((data?.message as string) || error.message || '网络错误')
        }
        break
    }

    return Promise.reject(error)
  },
)

export default http
