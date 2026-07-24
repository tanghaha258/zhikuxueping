/**
 * 工具上下文链接 API 封装（Task 8）。
 *
 * 端点对应后端 ``app.modules.resources.router`` 的 /resources/context-links：
 * - POST   /resources/context-links           关联独立资产到项目
 * - GET    /resources/context-links           按 project_id 或 artifact 查询引用
 * - DELETE /resources/context-links/{link_id} 取消关联（只删引用，不删资产）
 *
 * 设计要点（spec 第 7 节）：
 * - independent 模式不发请求，直接返回 null。
 * - project 模式发送 snake_case payload，placement 由资产类型推导或调用方覆盖。
 * - 响应经 HTTP 拦截器转为 camelCase。
 */
import http from '@/api'
import type { ApiResponse } from '@/types'
import {
  isProjectContext,
  placementForArtifact,
  type ArtifactType,
  type ContextLink,
  type ToolContext,
  type ToolContextError,
  type UnlinkResult,
} from './types'
import type { AxiosError } from 'axios'

/**
 * 关联独立工具资产到项目指定位置。
 *
 * - independent 模式：不发请求，返回 null（独立资产不强制关联项目）。
 * - project 模式：placement 默认由资产类型推导，placementOverride 可覆盖。
 */
export function linkContextApi(
  artifactType: ArtifactType,
  artifactId: string,
  context: ToolContext,
  placementOverride?: string,
): Promise<ContextLink | null> {
  if (!isProjectContext(context)) {
    return Promise.resolve(null)
  }
  const placement = placementOverride ?? placementForArtifact(artifactType)
  const body = {
    artifact_type: artifactType,
    artifact_id: artifactId,
    project_id: context.projectId,
    placement,
    phase: context.phase,
    task_id: context.taskId ?? null,
    goal_id: context.goalId ?? null,
  }
  return http
    .post<ApiResponse<ContextLink>>('/resources/context-links', body)
    .then((res) => res.data.data)
}

/** 取消关联：只删引用，不删资产本体或文件。 */
export function unlinkContextApi(linkId: string): Promise<UnlinkResult> {
  return http
    .delete<ApiResponse<UnlinkResult>>(`/resources/context-links/${linkId}`)
    .then((res) => res.data.data)
}

/** 按项目列出上下文引用；跨校读 403。 */
export function listContextLinksByProjectApi(
  projectId: string,
  artifactType?: ArtifactType,
): Promise<ContextLink[]> {
  return http
    .get<ApiResponse<ContextLink[]>>('/resources/context-links', {
      params: {
        project_id: projectId,
        artifact_type: artifactType,
      },
    })
    .then((res) => res.data.data)
}

/** 按资产列出一项资产的所有项目引用。 */
export function listContextLinksByArtifactApi(
  artifactType: ArtifactType,
  artifactId: string,
): Promise<ContextLink[]> {
  return http
    .get<ApiResponse<ContextLink[]>>('/resources/context-links', {
      params: {
        artifact_type: artifactType,
        artifact_id: artifactId,
      },
    })
    .then((res) => res.data.data)
}

/**
 * 将网络/业务错误映射为可观察的 ToolContextError 快照。
 * - 403 → forbidden=true（跨校关联拒绝）
 * - 404 → notFound=true
 * - 409 → 重复挂载冲突
 * - 无响应 → status=0 网络错误
 */
export function mapToolContextError(err: unknown): ToolContextError {
  const axiosErr = err as AxiosError<{ code?: number; message?: string }>
  const status = axiosErr.response?.status ?? 0
  const data = axiosErr.response?.data ?? {}
  const code = typeof data.code === 'number' ? data.code : null
  const message = data.message ?? (status === 0 ? '网络错误' : '请求失败')

  return {
    status,
    code,
    message,
    forbidden: status === 403,
    notFound: status === 404,
  }
}
