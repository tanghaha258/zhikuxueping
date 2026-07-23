import http from './index'
import type { ApiResponse, DashboardStats } from '@/types'

export function getDashboardStatsApi() {
  return http.get<ApiResponse<DashboardStats>>('/dashboard/stats')
}
