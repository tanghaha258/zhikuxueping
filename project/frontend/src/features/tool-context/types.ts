/**
 * 工具上下文领域类型与纯函数（Task 8）。
 *
 * ContextPicker 数据合同（计划 Task 8 Step 2）：
 * - independent：独立模式，不关联项目，不得伪造项目 ID。
 * - project：项目模式，必须提供 projectId 与 phase；可选 taskId/goalId。
 *
 * 与后端 ``app.modules.tool_context`` 对齐：
 * - ProjectPhase 对应后端 PHASES（diagnosis…closure）。
 * - ArtifactType 对应后端 ARTIFACT_TYPES。
 * - ContextLink 字段经 HTTP 拦截器转为 camelCase。
 */

// ── 项目阶段（与后端 PHASES 单一来源一致）──────────────────────
export const PROJECT_PHASES = [
  'diagnosis',
  'design',
  'preparation',
  'implementation',
  'evaluation',
  'improvement',
  'closure',
] as const

export type ProjectPhase = (typeof PROJECT_PHASES)[number]

// ── 资产类型（与后端 ARTIFACT_TYPES 一致）──────────────────────
export const ARTIFACT_TYPES = [
  'lesson_plan',
  'resource',
  'paper',
  'ai_output',
  'question_bank',
] as const

export type ArtifactType = (typeof ARTIFACT_TYPES)[number]

/**
 * ContextPicker 数据合同。
 * - independent：独立工具，不关联项目。
 * - project：关联到项目指定阶段；taskId/goalId 可选。
 */
export type ToolContext =
  | { mode: 'independent' }
  | {
      mode: 'project'
      projectId: string
      phase: ProjectPhase
      taskId?: string
      goalId?: string
    }

/** project 模式上下文（用于类型守卫窄化）。 */
export type ProjectContext = Extract<ToolContext, { mode: 'project' }>

/** 上下文校验结果。 */
export interface ToolContextValidation {
  valid: boolean
  error: string | null
}

/** ContextLink 响应（camelCase，经拦截器转换）。 */
export interface ContextLink {
  id: string
  artifactType: string
  artifactId: string
  projectId: string
  phase: string | null
  placement: string
  taskId: string | null
  goalId: string | null
  contextSnapshot: Record<string, unknown> | null
  createdBy: string | null
}

/** 取消关联响应（camelCase，经拦截器转换）。 */
export interface UnlinkResult {
  artifactType: string
  artifactId: string
  preserved: boolean
}

/** 可观察的网络/业务错误快照，供 UI 渲染错误条。 */
export interface ToolContextError {
  /** HTTP 状态码；网络错误为 0。 */
  status: number
  /** 后端业务错误码（如有）。 */
  code: number | null
  message: string
  /** 是否为权限错误（403/跨校访问）。 */
  forbidden: boolean
  /** 是否为未找到（404）。 */
  notFound: boolean
}

// ── 纯函数 ─────────────────────────────────────────────────────

/** 类型守卫：是否为 project 模式上下文。 */
export function isProjectContext(ctx: ToolContext): ctx is ProjectContext {
  return ctx.mode === 'project'
}

/**
 * 校验 ContextPicker 合同：
 * - independent 模式不得携带 projectId（运行时脏数据拒绝）。
 * - project 模式必须有非空 projectId 与合法 phase。
 */
export function validateToolContext(ctx: ToolContext): ToolContextValidation {
  if (ctx.mode === 'independent') {
    // 运行时脏数据：独立模式不得伪造项目 ID
    const dirty = (ctx as Record<string, unknown>).projectId
    if (dirty !== undefined && dirty !== null && dirty !== '') {
      return {
        valid: false,
        error: '独立模式不得携带项目 ID',
      }
    }
    return { valid: true, error: null }
  }

  if (ctx.mode === 'project') {
    if (!ctx.projectId || ctx.projectId.trim() === '') {
      return { valid: false, error: '项目模式必须提供 projectId' }
    }
    if (!ctx.phase || ctx.phase.trim() === '') {
      return { valid: false, error: '项目模式必须提供 phase' }
    }
    if (!PROJECT_PHASES.includes(ctx.phase)) {
      return {
        valid: false,
        error: `非法的项目阶段: ${ctx.phase}`,
      }
    }
    return { valid: true, error: null }
  }

  return { valid: false, error: '未知的上下文模式' }
}

/**
 * 根据资产类型推导默认 placement（与后端 PLACEMENTS 对齐）。
 * 调用方可通过 placementOverride 覆盖默认值（如试卷作为前测/后测）。
 */
export function placementForArtifact(artifactType: ArtifactType): string {
  switch (artifactType) {
    case 'lesson_plan':
      return 'lesson_plan'
    case 'resource':
      return 'resource'
    case 'ai_output':
      return 'ai_draft'
    case 'paper':
      return 'pre_test'
    case 'question_bank':
      return 'task_sheet'
    default:
      return 'resource'
  }
}
