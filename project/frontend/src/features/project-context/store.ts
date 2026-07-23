/**
 * 统一项目上下文 Pinia store（Task 3）。
 *
 * 设计要点（计划 Task 3 交付合同）：
 * - 仅缓存当前项目上下文；子页复用同一上下文，不重复拉项目详情。
 * - 同一项目在缓存有效期内复用，避免重复请求；force 可强制刷新。
 * - 网络错误可观察：error 状态供 UI 渲染错误条，区分权限/未找到/通用错误。
 * - 阶段完成/重开后用真实返回值就地更新缓存，不重新拉取整个上下文。
 *
 * 纯函数（shouldReuseCache / applyPhaseUpdate / mapContextError / findPhase /
 * currentActivePhase）单独导出，便于在不挂载 Pinia 的情况下单元测试。
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import type { AxiosError } from 'axios'
import {
  completePhaseApi,
  getProjectContextApi,
  getProjectTimelineApi,
  reopenPhaseApi,
} from './api'
import type {
  ContextError,
  PhaseKey,
  ProjectWorkspaceContext,
  ProjectWorkspacePhase,
  ProjectWorkspaceTimelineEvent,
} from './types'

/** 缓存有效期（毫秒）；同项目在此期间复用缓存，避免重复请求。 */
const CACHE_TTL_MS = 30_000

// ============================================================
// 纯函数：缓存判定 / 阶段更新 / 错误映射
// ============================================================

/**
 * 判断是否可复用已缓存的上下文。
 *
 * - 项目 ID 变化时必须重新拉取。
 * - 缓存超过 maxAgeMs 时视为过期。
 * - 无缓存时返回 false。
 */
export function shouldReuseCache(
  currentProjectId: string | null,
  requestedProjectId: string,
  lastLoadedAt: number,
  maxAgeMs: number = CACHE_TTL_MS,
): boolean {
  if (!currentProjectId || currentProjectId !== requestedProjectId) return false
  if (!lastLoadedAt) return false
  return Date.now() - lastLoadedAt < maxAgeMs
}

/**
 * 用阶段操作返回的最新阶段数据就地更新 phases 数组（不可变更新）。
 *
 * 阶段操作（complete/reopen）后端返回单个更新后的阶段，无需重新拉取整个上下文。
 */
export function applyPhaseUpdate(
  phases: ProjectWorkspacePhase[],
  updated: ProjectWorkspacePhase,
): ProjectWorkspacePhase[] {
  return phases.map((p) => (p.phase === updated.phase ? { ...updated } : p))
}

/** 按阶段 key 查找阶段；未找到返回 null。 */
export function findPhase(
  phases: ProjectWorkspacePhase[],
  phase: PhaseKey,
): ProjectWorkspacePhase | null {
  return phases.find((p) => p.phase === phase) ?? null
}

/** 返回第一个未完成的阶段（按固定顺序）；全部完成返回 null。 */
export function currentActivePhase(
  phases: ProjectWorkspacePhase[],
): ProjectWorkspacePhase | null {
  return phases.find((p) => p.status !== 'completed') ?? null
}

/**
 * 将 axios 错误映射为可观察的 ContextError，供 UI 渲染错误条。
 *
 * 区分：
 * - 403：权限错误（无权/跨校访问）
 * - 404：项目未找到
 * - 0：网络错误（无响应）
 * - 其他：通用错误
 */
export function mapContextError(error: unknown): ContextError {
  const axiosErr = error as AxiosError<{ code?: number; message?: string }>
  const status = axiosErr?.response?.status ?? 0
  const data = axiosErr?.response?.data as { code?: number; message?: string } | undefined
  // 仅使用后端返回的 message；无响应时按状态码给出默认消息，
  // 不使用 axiosErr.message（如 'Request failed' 等内部消息对用户无意义）。
  const message = data?.message || (status === 0 ? '网络错误' : '请求失败')
  return {
    status,
    code: data?.code ?? null,
    message,
    forbidden: status === 403,
    notFound: status === 404,
  }
}

// ============================================================
// Pinia store
// ============================================================
export const useProjectContextStore = defineStore('projectContext', () => {
  // ── State ───────────────────────────────────────────────────
  const currentContext = ref<ProjectWorkspaceContext | null>(null)
  const currentProjectId = ref<string | null>(null)
  const loading = ref(false)
  const error = ref<ContextError | null>(null)
  const lastLoadedAt = ref(0)
  const timeline = ref<ProjectWorkspaceTimelineEvent[]>([])

  // ── Getters ─────────────────────────────────────────────────
  const hasContext = computed(() => currentContext.value !== null)
  const isArchived = computed(() => currentContext.value?.permissions.isArchived ?? false)
  const canManage = computed(() => currentContext.value?.permissions.canManage ?? false)
  const activePhase = computed(() =>
    currentContext.value ? currentActivePhase(currentContext.value.phases) : null,
  )
  const primaryAction = computed(() => currentContext.value?.nextAction ?? null)
  const hasBlockers = computed(
    () => (currentContext.value?.blockers.length ?? 0) > 0,
  )

  // ── Actions ─────────────────────────────────────────────────

  /**
   * 加载项目上下文。
   *
   * 默认复用缓存（同项目 + TTL 内）；force=true 强制刷新。
   * 子页调用此方法获取上下文，store 自动避免重复请求。
   */
  async function loadContext(projectId: string, force = false): Promise<void> {
    if (!force && shouldReuseCache(currentProjectId.value, projectId, lastLoadedAt.value)) {
      return
    }
    loading.value = true
    error.value = null
    try {
      const res = await getProjectContextApi(projectId)
      currentContext.value = res.data.data
      currentProjectId.value = projectId
      lastLoadedAt.value = Date.now()
    } catch (e) {
      error.value = mapContextError(e)
      throw e
    } finally {
      loading.value = false
    }
  }

  /** 强制刷新当前项目上下文。 */
  async function refreshContext(): Promise<void> {
    if (!currentProjectId.value) return
    await loadContext(currentProjectId.value, true)
  }

  /** 拉取项目时间线事件（不长期缓存，每次调用都请求）。 */
  async function loadTimeline(projectId: string): Promise<void> {
    try {
      const res = await getProjectTimelineApi(projectId)
      timeline.value = res.data.data
    } catch (e) {
      error.value = mapContextError(e)
      throw e
    }
  }

  /** 标记阶段完成；用返回值就地更新缓存。 */
  async function completePhase(phase: PhaseKey): Promise<void> {
    if (!currentProjectId.value || !currentContext.value) return
    try {
      const res = await completePhaseApi(currentProjectId.value, phase)
      currentContext.value = {
        ...currentContext.value,
        phases: applyPhaseUpdate(currentContext.value.phases, res.data.data),
      }
      error.value = null
    } catch (e) {
      error.value = mapContextError(e)
      throw e
    }
  }

  /** 重新开放已完成阶段；用返回值就地更新缓存。 */
  async function reopenPhase(phase: PhaseKey, reason?: string | null): Promise<void> {
    if (!currentProjectId.value || !currentContext.value) return
    try {
      const res = await reopenPhaseApi(currentProjectId.value, phase, reason)
      currentContext.value = {
        ...currentContext.value,
        phases: applyPhaseUpdate(currentContext.value.phases, res.data.data),
      }
      error.value = null
    } catch (e) {
      error.value = mapContextError(e)
      throw e
    }
  }

  /** 清除缓存（离开项目工作区时调用）。 */
  function clear(): void {
    currentContext.value = null
    currentProjectId.value = null
    loading.value = false
    error.value = null
    lastLoadedAt.value = 0
    timeline.value = []
  }

  return {
    // state
    currentContext,
    currentProjectId,
    loading,
    error,
    lastLoadedAt,
    timeline,
    // getters
    hasContext,
    isArchived,
    canManage,
    activePhase,
    primaryAction,
    hasBlockers,
    // actions
    loadContext,
    refreshContext,
    loadTimeline,
    completePhase,
    reopenPhase,
    clear,
  }
})
