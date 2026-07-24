/**
 * 项目学情诊断 Pinia store 与纯函数（Task 6）。
 *
 * 设计要点（计划 Task 6 交付合同）：
 * - 仅缓存当前项目的最新诊断；与项目上下文 store 解耦，避免重复加载项目详情。
 * - latest 在无诊断时后端返回 data=null，前端 currentInsight 置 null 且不报错。
 * - generate 在无证据时返回 insufficient_evidence 状态，lastActionSucceeded=false，
 *   UI 显示"导入前测/先发布任务"入口而非成功提示。
 * - AI 失败（5xx/网络错误）必须转人工诊断：shouldFallbackToManual=true，不显示成功。
 * - confirm 仅 draft 状态可确认；归档项目与无证据诊断返回 409，不更新本地状态。
 *
 * 纯函数（hasEvidence / canConfirmInsight / formatSourceCounts / mapDiagnosisError）
 * 单独导出，便于在不挂载 Pinia 的情况下单元测试。
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import type { AxiosError } from 'axios'
import {
  confirmInsightApi,
  generateInsightApi,
  getLatestInsightApi,
} from './api'
import type {
  DiagnosisError,
  FormattedSource,
  InsightConfirmRequest,
  InsightSourceCounts,
  ProjectLearningInsight,
} from './types'

/** 缓存有效期（毫秒）；同项目在此期间复用缓存，避免重复请求。 */
const CACHE_TTL_MS = 30_000

// ============================================================
// 纯函数
// ============================================================

/**
 * 判断诊断是否基于真实证据。
 *
 * - currentInsight 为 null 时返回 false。
 * - 状态为 insufficient_evidence 时返回 false（即使计数非零，后端保证此时计数为 0）。
 * - 任一来源计数大于 0 时返回 true。
 */
export function hasEvidence(
  insight: ProjectLearningInsight | null,
): boolean {
  if (!insight) return false
  if (insight.status === 'insufficient_evidence') return false
  const counts = insight.sourceCounts
  return (
    counts.preTest > 0 ||
    counts.submissions > 0 ||
    counts.evaluations > 0 ||
    counts.questionAnswers > 0
  )
}

/**
 * 判断诊断是否可由教师确认。
 *
 * - currentInsight 为 null 时返回 false。
 * - 仅 draft 状态可确认；insufficient_evidence/confirmed/stale 均不可。
 */
export function canConfirmInsight(
  insight: ProjectLearningInsight | null,
): boolean {
  if (!insight) return false
  return insight.status === 'draft'
}

/**
 * 将来源计数格式化为可读标签与计数列表，用于 UI 展示。
 *
 * 顺序固定：前测 → 任务提交 → 已发布评价 → 题目作答。
 */
export function formatSourceCounts(
  counts: InsightSourceCounts,
): FormattedSource[] {
  return [
    { label: '前测', count: counts.preTest },
    { label: '任务提交', count: counts.submissions },
    { label: '已发布评价', count: counts.evaluations },
    { label: '题目作答', count: counts.questionAnswers },
  ]
}

/**
 * 将 axios 错误映射为可观察的 DiagnosisError，供 UI 渲染错误条与人工诊断提示。
 *
 * 区分：
 * - 403：权限错误（无权/跨校访问）
 * - 404：诊断记录不存在
 * - 409：业务冲突（归档只读/无证据不可确认/重复确认）
 * - 0：网络错误（无响应）
 * - 其他：通用错误
 */
export function mapDiagnosisError(error: unknown): DiagnosisError {
  const axiosErr = error as AxiosError<{ code?: number; message?: string }>
  const status = axiosErr?.response?.status ?? 0
  const data = axiosErr?.response?.data as
    | { code?: number; message?: string }
    | undefined
  // 仅使用后端返回的 message；无响应时按状态码给出默认消息，
  // 不使用 axiosErr.message（如 'Request failed' 等内部消息对用户无意义）。
  const message = data?.message || (status === 0 ? '网络错误' : '请求失败')
  return {
    status,
    code: data?.code ?? null,
    message,
    forbidden: status === 403,
    notFound: status === 404,
    conflict: status === 409,
  }
}

// ============================================================
// 内部：缓存判定
// ============================================================
function shouldReuseCache(
  currentProjectId: string | null,
  requestedProjectId: string,
  lastLoadedAt: number,
  maxAgeMs: number = CACHE_TTL_MS,
): boolean {
  if (!currentProjectId || currentProjectId !== requestedProjectId) return false
  if (!lastLoadedAt) return false
  return Date.now() - lastLoadedAt < maxAgeMs
}

// ============================================================
// Pinia store
// ============================================================
export const useProjectDiagnosisStore = defineStore('projectDiagnosis', () => {
  // ── State ───────────────────────────────────────────────────
  const currentInsight = ref<ProjectLearningInsight | null>(null)
  const currentProjectId = ref<string | null>(null)
  const loading = ref(false)
  const generating = ref(false)
  const confirming = ref(false)
  const error = ref<DiagnosisError | null>(null)
  const lastLoadedAt = ref(0)
  /**
   * 最近一次写操作（generate/confirm），用于 UI 区分错误条来源。
   * - 'generate'：生成失败时显示"转人工诊断"提示
   * - 'confirm'：确认失败时显示具体冲突原因
   */
  const lastAction = ref<'generate' | 'confirm' | null>(null)
  /** 最近一次写操作是否成功；generate 在 insufficient_evidence 时为 false。 */
  const lastActionSucceeded = ref(false)

  // ── Getters ─────────────────────────────────────────────────
  const hasInsight = computed(() => currentInsight.value !== null)
  const evidenceMissing = computed(
    () => currentInsight.value?.status === 'insufficient_evidence',
  )
  const canConfirm = computed(() => canConfirmInsight(currentInsight.value))
  const hasSegments = computed(
    () => (currentInsight.value?.segments.length ?? 0) > 0,
  )
  /**
   * 是否应转人工诊断：仅在 generate 失败后为 true，其他写操作或无操作时为 false。
   * reset 在任何成功 generate/confirm 后复位。
   */
  const shouldFallbackToManual = computed(
    () =>
      lastAction.value === 'generate' &&
      lastActionSucceeded.value === false &&
      error.value !== null,
  )

  // ── Actions ─────────────────────────────────────────────────

  /**
   * 拉取项目当前学情诊断。
   *
   * 默认复用缓存（同项目 + TTL 内）；force=true 强制刷新。
   * 后端无诊断时返回 data=null，前端不视为错误。
   */
  async function loadLatest(projectId: string, force = false): Promise<void> {
    if (
      !force &&
      shouldReuseCache(currentProjectId.value, projectId, lastLoadedAt.value)
    ) {
      return
    }
    loading.value = true
    error.value = null
    try {
      const res = await getLatestInsightApi(projectId)
      currentInsight.value = res.data.data
      currentProjectId.value = projectId
      lastLoadedAt.value = Date.now()
    } catch (e) {
      error.value = mapDiagnosisError(e)
      throw e
    } finally {
      loading.value = false
    }
  }

  /** 强制刷新当前项目最新诊断。 */
  async function refreshLatest(): Promise<void> {
    if (!currentProjectId.value) return
    await loadLatest(currentProjectId.value, true)
  }

  /**
   * 生成项目学情诊断。
   *
   * 关键约束：
   * - 无证据时后端返回 insufficient_evidence 状态，lastActionSucceeded=false，
   *   UI 应显示"导入前测/先发布任务"入口而非成功提示。
   * - AI 失败（5xx/网络错误）抛错，shouldFallbackToManual=true，UI 应提示转人工诊断。
   * - 成功（draft 状态）后用返回值就地更新 currentInsight。
   */
  async function generate(
    projectId: string,
  ): Promise<ProjectLearningInsight> {
    generating.value = true
    error.value = null
    lastAction.value = 'generate'
    lastActionSucceeded.value = false
    try {
      const res = await generateInsightApi(projectId)
      currentInsight.value = res.data.data
      currentProjectId.value = projectId
      lastLoadedAt.value = Date.now()
      // 无证据诊断不视为成功生成可用的诊断
      lastActionSucceeded.value = res.data.data.status !== 'insufficient_evidence'
      return res.data.data
    } catch (e) {
      error.value = mapDiagnosisError(e)
      throw e
    } finally {
      generating.value = false
    }
  }

  /**
   * 确认项目学情诊断。
   *
   * - teacherNote 为空字符串时规范化为 null（与后端一致）。
   * - 仅 draft 状态可确认；后端返回 409 时不更新本地状态。
   * - 成功后用返回值就地更新 currentInsight。
   */
  async function confirm(
    insightId: string,
    teacherNote: string | null,
  ): Promise<ProjectLearningInsight> {
    if (!currentProjectId.value) {
      throw new Error('无当前项目，无法确认诊断')
    }
    confirming.value = true
    error.value = null
    lastAction.value = 'confirm'
    lastActionSucceeded.value = false
    const note =
      teacherNote && teacherNote.trim() ? teacherNote.trim() : null
    const body: InsightConfirmRequest = { teacherNote: note }
    try {
      const res = await confirmInsightApi(
        currentProjectId.value,
        insightId,
        body,
      )
      currentInsight.value = res.data.data
      lastActionSucceeded.value = true
      return res.data.data
    } catch (e) {
      error.value = mapDiagnosisError(e)
      throw e
    } finally {
      confirming.value = false
    }
  }

  /** 清除缓存（离开项目工作区时调用）。 */
  function clear(): void {
    currentInsight.value = null
    currentProjectId.value = null
    loading.value = false
    generating.value = false
    confirming.value = false
    error.value = null
    lastLoadedAt.value = 0
    lastAction.value = null
    lastActionSucceeded.value = false
  }

  return {
    // state
    currentInsight,
    currentProjectId,
    loading,
    generating,
    confirming,
    error,
    lastLoadedAt,
    lastAction,
    lastActionSucceeded,
    // getters
    hasInsight,
    evidenceMissing,
    canConfirm,
    hasSegments,
    shouldFallbackToManual,
    // actions
    loadLatest,
    refreshLatest,
    generate,
    confirm,
    clear,
  }
})
