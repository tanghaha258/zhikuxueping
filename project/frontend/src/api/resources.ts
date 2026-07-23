import http from './index'
import type {
  ApiResponse,
  Resource,
  ResourceCreateForm,
  ResourceTierCoverage,
  ResourceUpdateForm,
} from '@/types'

export function listResourcesApi(params: {
  project_id?: string
  tier?: string
  stage?: string
  review_status?: string
}) {
  return http.get<ApiResponse<Resource[]>>('/resources', { params })
}

/** 三级资源递进覆盖检查（计划 3.5.3）。 */
export function getResourceTierCoverageApi(projectId: string) {
  return http.get<ApiResponse<ResourceTierCoverage>>('/resources/tier-coverage', {
    params: { project_id: projectId },
  })
}

export function createResourceApi(data: ResourceCreateForm) {
  return http.post<ApiResponse<Resource>>('/resources', data)
}

export function getResourceApi(id: string) {
  return http.get<ApiResponse<Resource>>(`/resources/${id}`)
}

export function updateResourceApi(id: string, data: ResourceUpdateForm) {
  return http.put<ApiResponse<Resource>>(`/resources/${id}`, data)
}

export function deleteResourceApi(id: string) {
  return http.delete<ApiResponse<null>>(`/resources/${id}`)
}
