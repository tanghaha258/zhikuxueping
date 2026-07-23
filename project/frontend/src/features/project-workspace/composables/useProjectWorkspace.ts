/**
 * 项目工作区组合式函数与纯工具。
 *
 * 纯函数（draft*、validateStep、mapServerError、resolveNextStep、canEditDesign）
 * 单独导出，便于在不挂载 Vue 组件的情况下单元测试（计划 Task 2.1）。
 * `useProjectWorkspace` 负责加载项目与设计快照、自动保存与离开保护。
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import type { AxiosError } from 'axios'
import {
  getDesignSnapshotApi,
  validateActivationApi,
} from '../api'
import type {
  ProjectDesignSnapshot,
  ProjectValidationResult,
  ProjectWizardDraft,
  SaveStatus,
  StepValidationResult,
  MappedServerError,
  WizardStep,
} from '../types'
import { WIZARD_STEPS } from '../types'

// ============================================================
// 纯函数：草稿恢复
// ============================================================

const DRAFT_PREFIX = 'pws:draft:'

/** 草稿在 localStorage 中的键。向导使用 'new'，设计页使用 projectId。 */
export function draftKey(id: string): string {
  return `${DRAFT_PREFIX}${id}`
}

/** 创建一份空白向导草稿。 */
export function emptyDraft(): ProjectWizardDraft {
  return {
    title: '',
    description: '',
    grade: '',
    classIds: [],
    collaboratorIds: [],
    startDate: undefined,
    endDate: undefined,
    coverImageUrl: undefined,
    problemContext: '',
    problemObject: '',
    problemAudience: '',
    problemConstraints: '',
    problemDeliverable: '',
    problemUsage: '',
    coreSubjectId: '',
    supportSubjectIds: [],
    contributionNotes: {},
    goals: [],
    step: 0,
  }
}

/** 读取草稿；不存在或解析失败返回 null。 */
export function loadDraft(id: string): ProjectWizardDraft | null {
  try {
    const raw = localStorage.getItem(draftKey(id))
    if (!raw) return null
    const parsed = JSON.parse(raw) as ProjectWizardDraft
    // 与当前草稿结构合并，避免旧草稿缺字段
    return { ...emptyDraft(), ...parsed }
  } catch {
    return null
  }
}

/** 写入草稿，附加 savedAt。 */
export function saveDraft(id: string, draft: ProjectWizardDraft): void {
  const payload: ProjectWizardDraft = { ...draft, savedAt: new Date().toISOString() }
  localStorage.setItem(draftKey(id), JSON.stringify(payload))
}

/** 清除草稿。 */
export function clearDraft(id: string): void {
  localStorage.removeItem(draftKey(id))
}

// ============================================================
// 纯函数：步骤校验
// ============================================================

/**
 * 校验某一步骤的草稿。
 *
 * 依据计划 3.4：草稿允许暂缺字段，因此除"基本信息-标题"（后端必填）
 * 为硬错误外，其余步骤仅返回警告，不阻断前进。返回的 errors/warnings
 * 均带 field 路径，供向导定位到具体字段。
 */
export function validateStep(
  step: number,
  draft: ProjectWizardDraft,
): StepValidationResult {
  const errors: StepValidationResult['errors'] = []
  const warnings: StepValidationResult['warnings'] = []

  if (step === 0) {
    if (!draft.title.trim()) {
      errors.push({ field: 'title', message: '项目名称不能为空' })
    }
    if (!draft.grade) {
      warnings.push({ field: 'grade', message: '建议选择年级' })
    }
    if (draft.classIds.length === 0) {
      warnings.push({ field: 'classIds', message: '建议选择参与班级' })
    }
  }

  if (step === 1) {
    if (!draft.problemContext.trim()) {
      warnings.push({ field: 'problemContext', message: '真实问题情境建议填写' })
    }
    if (!draft.problemDeliverable.trim()) {
      warnings.push({ field: 'problemDeliverable', message: '建议明确最终成果' })
    }
  }

  if (step === 2) {
    if (!draft.coreSubjectId) {
      warnings.push({
        field: 'coreSubjectId',
        message: '正式项目需指定唯一核心学科',
      })
    }
    if (draft.supportSubjectIds.length === 0) {
      warnings.push({
        field: 'supportSubjectIds',
        message: '跨学科项目需至少一门支撑学科',
      })
    }
    const dup = draft.supportSubjectIds.find((s) => s === draft.coreSubjectId)
    if (dup) {
      errors.push({
        field: 'supportSubjectIds',
        message: '支撑学科不能与核心学科重复',
      })
    }
  }

  if (step === 3) {
    if (draft.goals.length === 0) {
      warnings.push({ field: 'goals', message: '建议至少添加一条学习目标' })
    }
  }

  if (step === 4) {
    // 确认步骤：汇总所有硬错误
    const s0 = validateStep(0, draft)
    const s2 = validateStep(2, draft)
    errors.push(...s0.errors, ...s2.errors)
  }

  return { valid: errors.length === 0, errors, warnings }
}

// ============================================================
// 纯函数：服务端错误映射
// ============================================================

interface BackendErrorBody {
  code?: number
  message?: string
  data?: unknown
  detail?: Array<{ loc: (string | number)[]; msg: string; type?: string }>
}

/**
 * 将 axios 错误映射为面向向导的结构化错误。
 *
 * - HTTP 422（FastAPI 校验错误）：按 detail[0].loc 定位字段与步骤。
 * - HTTP 409（状态机/完整性）：按 message 关键词定位步骤。
 * - 其他：返回 step=null, field=null 的通用错误。
 */
export function mapServerError(err: unknown): MappedServerError {
  const e = err as AxiosError<BackendErrorBody>
  const status = e.response?.status ?? 0
  const body = e.response?.data ?? {}
  const code = typeof body.code === 'number' ? body.code : null
  const message = body.message || e.message || '请求失败'

  // 422 字段级校验错误
  if (status === 422 && body.detail && body.detail.length > 0) {
    const first = body.detail[0]
    const field = first.loc && first.loc.length > 1 ? String(first.loc[first.loc.length - 1]) : null
    return {
      fieldLevel: true,
      step: fieldToStep(field),
      field,
      message: first.msg || message,
      status,
      code,
    }
  }

  // 409 状态机/完整性错误，按消息关键词定位
  const msg = message
  let step: number | null = null
  let field: string | null = null
  if (/学科|核心|支撑|贡献/.test(msg)) {
    step = 2
    field = 'coreSubjectId'
  } else if (/问题|情境/.test(msg)) {
    step = 1
    field = 'problemContext'
  } else if (/目标|指标|证据/.test(msg)) {
    step = 3
    field = 'goals'
  } else if (/状态|激活|审核|pending_review|draft/.test(msg)) {
    step = 4
  }

  return {
    fieldLevel: step !== null && field !== null,
    step,
    field,
    message: msg,
    status,
    code,
  }
}

function fieldToStep(field: string | null): number | null {
  if (!field) return null
  if (['title', 'description', 'grade', 'class_ids', 'classIds', 'start_date', 'startDate', 'end_date', 'endDate'].includes(field)) {
    return 0
  }
  if (['context', 'object', 'audience', 'constraints', 'deliverable', 'usage', 'problemContext'].includes(field)) {
    return 1
  }
  if (['subject_id', 'subjectId', 'role', 'coreSubjectId', 'supportSubjectIds'].includes(field)) {
    return 2
  }
  if (['goal_type', 'goalType', 'name', 'observable_behavior', 'observableBehavior', 'indicator_id', 'indicatorId', 'stage', 'evidence_type', 'evidenceType'].includes(field)) {
    return 3
  }
  return null
}

// ============================================================
// 纯函数：下一步入口
// ============================================================

export interface NextStepSuggestion {
  /** 目标路由路径（相对 /teacher/projects/{id}/...） */
  route: string
  /** 按钮文案 */
  label: string
  /** 推荐理由 */
  reason: string
  /** 是否可执行（false 表示当前已无下一步或被阻断） */
  actionable: boolean
}

/**
 * 依据项目状态、完整性与设计快照，给出确定性下一步建议。
 *
 * 规则（计划 3.5.1：下一步建议仅基于确定性规则产生）：
 * - draft 且未填写真实问题 → 去设计页填问题
 * - draft 且缺少核心/支撑学科 → 去设计页填贡献
 * - draft 且设计完整 → 提交审核
 * - pending_review → 等待审核（不可操作）或激活
 * - active 且有未完成阶段任务 → 去任务链
 * - active 且任务完成 → 去评价计划
 * - completed → 归档
 * - archived → 无下一步
 */
export function resolveNextStep(
  projectId: string,
  projectStatus: string,
  validation: ProjectValidationResult | null,
  snapshot: ProjectDesignSnapshot | null,
): NextStepSuggestion {
  const base = `/teacher/projects/${projectId}`
  const designRoute = `${base}/design`

  if (projectStatus === 'draft') {
    if (!snapshot?.problem?.context) {
      return {
        route: designRoute,
        label: '完善真实问题',
        reason: '项目尚未描述真实问题情境',
        actionable: true,
      }
    }
    const hasCore = snapshot.contributions.some((c) => c.role === 'core')
    const hasSupport = snapshot.contributions.some((c) => c.role === 'support')
    if (!hasCore || !hasSupport) {
      return {
        route: designRoute,
        label: '完善学科贡献',
        reason: '需指定唯一核心学科与至少一门支撑学科',
        actionable: true,
      }
    }
    if (validation && validation.blockers.length > 0) {
      return {
        route: designRoute,
        label: '补齐缺失项',
        reason: `仍有 ${validation.blockers.length} 项阻断问题`,
        actionable: true,
      }
    }
    return {
      route: `${base}/overview`,
      label: '提交审核',
      reason: '设计已完整，可提交审核进入待激活状态',
      actionable: true,
    }
  }

  if (projectStatus === 'pending_review') {
    if (validation && validation.canActivate) {
      return {
        route: `${base}/overview`,
        label: '激活项目',
        reason: '项目已通过完整性校验，可激活',
        actionable: true,
      }
    }
    return {
      route: designRoute,
      label: '补齐缺失项',
      reason: '完整性校验未通过，无法激活',
      actionable: true,
    }
  }

  if (projectStatus === 'active') {
    return {
      route: `${base}/tasks`,
      label: '继续任务链',
      reason: '项目进行中，配置三阶段任务',
      actionable: true,
    }
  }

  if (projectStatus === 'completed') {
    return {
      route: `${base}/overview`,
      label: '归档项目',
      reason: '项目已完成，可归档并归入案例库',
      actionable: true,
    }
  }

  if (projectStatus === 'archived') {
    return {
      route: `${base}/overview`,
      label: '已归档',
      reason: '项目已归档，只读查看',
      actionable: false,
    }
  }

  return {
    route: base,
    label: '查看项目',
    reason: '',
    actionable: false,
  }
}

/** 项目设计是否可编辑（与后端 ensure_design_editable 一致）。 */
export function canEditDesign(projectStatus: string): boolean {
  return projectStatus === 'draft' || projectStatus === 'pending_review'
}

// ============================================================
// 组合式函数：项目工作区状态
// ============================================================

export interface UseProjectWorkspaceOptions {
  projectId: string
  /** 自动保存间隔（毫秒），默认 30s */
  autosaveIntervalMs?: number
}

export function useProjectWorkspace(options: UseProjectWorkspaceOptions) {
  const { projectId, autosaveIntervalMs = 30000 } = options

  const snapshot = ref<ProjectDesignSnapshot | null>(null)
  const validation = ref<ProjectValidationResult | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const saveStatus = ref<SaveStatus>('idle')
  const lastSavedAt = ref<string | null>(null)

  let timer: ReturnType<typeof setInterval> | null = null
  let pendingSnapshot: ProjectDesignSnapshot | null = null

  async function load() {
    loading.value = true
    error.value = null
    try {
      const [snapRes, valRes] = await Promise.all([
        getDesignSnapshotApi(projectId),
        validateActivationApi(projectId).catch(() => null),
      ])
      snapshot.value = snapRes.data.data
      pendingSnapshot = snapshot.value
      if (valRes) {
        validation.value = valRes.data.data
      }
    } catch (e) {
      error.value = (e as Error).message
    } finally {
      loading.value = false
    }
  }

  /**
   * 标记工作区有未保存的设计变更，触发自动保存计时重置。
   * 实际持久化由设计页通过具体 API（upsertProblemApi 等）完成；
   * 此处仅维护保存状态机供布局展示"保存中/已保存/保存失败"。
   */
  function markDirty() {
    if (saveStatus.value === 'saved') saveStatus.value = 'saving'
  }

  function markSaved() {
    saveStatus.value = 'saved'
    lastSavedAt.value = new Date().toISOString()
  }

  function markError(message: string) {
    error.value = message
    saveStatus.value = 'error'
  }

  function startAutosave() {
    stopAutosave()
    timer = setInterval(() => {
      // 自动保存仅在 saving 状态触发；saved/idle 不重复写入
      if (saveStatus.value === 'saving' && pendingSnapshot) {
        // 设计页通过显式 API 保存；此处仅刷新状态展示
        markSaved()
      }
    }, autosaveIntervalMs)
  }

  function stopAutosave() {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }

  /** 离开保护：存在未保存变更时提示。 */
  function shouldBlockLeave(): boolean {
    return saveStatus.value === 'saving'
  }

  onMounted(() => {
    load()
    startAutosave()
  })

  onBeforeUnmount(() => {
    stopAutosave()
  })

  const completion = computed(() => validation.value?.completion ?? 0)
  const blockers = computed(() => validation.value?.blockers ?? [])
  const nextStep = computed(() =>
    resolveNextStep(
      projectId,
      // projectStatus 由布局传入；此处用 validation 推断不够，留待布局注入
      'draft',
      validation.value,
      snapshot.value,
    ),
  )

  return {
    snapshot,
    validation,
    loading,
    error,
    saveStatus,
    lastSavedAt,
    completion,
    blockers,
    nextStep,
    load,
    markDirty,
    markSaved,
    markError,
    shouldBlockLeave,
    canEditDesign,
  }
}

export { WIZARD_STEPS }
export type { WizardStep }
