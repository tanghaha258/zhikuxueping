/**
 * 学生端任务草稿与幂等键工具（纯函数）。
 *
 * 单独导出以便在不挂载 Vue 组件的情况下单元测试（计划 3.7.3）。
 * - localStorage 草稿：按 task_id 持久化作答内容与附件，支持往返、合并、损坏容错。
 * - 幂等提交键：每次提交生成新 UUID，同一提交尝试内复用同一键，
 *   重复点击 / 网络重试不生成重复版本（后端按 idempotency_key 去重）。
 */
import type { TaskDraft } from './types'

// ── 草稿键 ────────────────────────────────────────────────────
const DRAFT_PREFIX = 'student:draft:'

/** 草稿在 localStorage 中的键，按 task_id 隔离。 */
export function draftKey(taskId: string): string {
  return `${DRAFT_PREFIX}${taskId}`
}

/** 创建一份空白草稿。 */
export function emptyDraft(): TaskDraft {
  return { content: '', fileUrls: [] }
}

/** 读取草稿；不存在或解析失败返回 null。与当前结构合并，避免旧草稿缺字段。 */
export function loadDraft(taskId: string): TaskDraft | null {
  try {
    const raw = localStorage.getItem(draftKey(taskId))
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<TaskDraft>
    return { ...emptyDraft(), ...parsed }
  } catch {
    return null
  }
}

/** 写入草稿，附加 savedAt。 */
export function saveDraft(taskId: string, draft: TaskDraft): void {
  const payload: TaskDraft = { ...draft, savedAt: new Date().toISOString() }
  localStorage.setItem(draftKey(taskId), JSON.stringify(payload))
}

/** 清除草稿（提交成功后调用）。 */
export function clearDraft(taskId: string): void {
  localStorage.removeItem(draftKey(taskId))
}

/** 判断草稿是否有实质内容（内容非空或存在附件）。 */
export function hasDraftContent(draft: TaskDraft | null): boolean {
  if (!draft) return false
  return draft.content.trim().length > 0 || draft.fileUrls.length > 0
}

// ── 幂等提交键 ────────────────────────────────────────────────
const IDEMPOTENCY_PREFIX = 'student:idem:'

/** 当前任务待提交的幂等键在 sessionStorage 中的键。 */
export function idempotencyKeyStorageKey(taskId: string): string {
  return `${IDEMPOTENCY_PREFIX}${taskId}`
}

/**
 * 生成一个新的 UUID v4 幂等键。
 *
 * 优先使用原生 crypto.randomUUID()；测试环境或不支持时回退到
 * 基于 getRandomValues 的手写 v4 生成，确保跨环境可用。
 */
export function generateIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return fallbackUuidV4()
}

/** 读取当前任务待提交的幂等键；不存在返回 null。 */
export function peekIdempotencyKey(taskId: string): string | null {
  return sessionStorage.getItem(idempotencyKeyStorageKey(taskId))
}

/**
 * 取出当前任务的幂等键；不存在则生成并暂存。
 *
 * 同一提交会话内多次调用（如重复点击提交按钮）返回同一键，
 * 保证后端去重；提交成功后通过 clearIdempotencyKey 清除，
 * 下一次提交会生成新键。
 */
export function acquireIdempotencyKey(taskId: string): string {
  const existing = peekIdempotencyKey(taskId)
  if (existing) return existing
  const fresh = generateIdempotencyKey()
  sessionStorage.setItem(idempotencyKeyStorageKey(taskId), fresh)
  return fresh
}

/** 清除当前任务的幂等键（提交成功后调用）。 */
export function clearIdempotencyKey(taskId: string): void {
  sessionStorage.removeItem(idempotencyKeyStorageKey(taskId))
}

// ── UUID v4 回退实现 ──────────────────────────────────────────
function fallbackUuidV4(): string {
  const bytes = new Uint8Array(16)
  if (typeof crypto !== 'undefined' && typeof crypto.getRandomValues === 'function') {
    crypto.getRandomValues(bytes)
  } else {
    // Math 回退（非密码学安全，幂等键场景可接受）
    for (let i = 0; i < 16; i++) bytes[i] = Math.floor(Math.random() * 256)
  }
  // RFC 4122 v4：version 与 variant 位
  bytes[6] = (bytes[6] & 0x0f) | 0x40
  bytes[8] = (bytes[8] & 0x3f) | 0x80
  const hex: string[] = []
  for (let i = 0; i < 16; i++) hex.push(bytes[i].toString(16).padStart(2, '0'))
  return `${hex[0]}${hex[1]}${hex[2]}${hex[3]}-${hex[4]}${hex[5]}-${hex[6]}${hex[7]}-${hex[8]}${hex[9]}-${hex[10]}${hex[11]}${hex[12]}${hex[13]}${hex[14]}${hex[15]}`
}
