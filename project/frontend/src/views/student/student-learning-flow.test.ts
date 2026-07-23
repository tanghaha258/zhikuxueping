/**
 * 学生端学习流转纯逻辑测试（Task 6 / 计划 3.7）。
 *
 * 覆盖三类：
 * 1. 状态流转：订正状态机迁移、可提交/可订正/可二次评价判断。
 * 2. 自动保存：localStorage 草稿的写入、读取、清除、合并与损坏容错。
 * 3. 幂等提交键：UUID 生成、同任务复用、清除后重新生成。
 *
 * 纯函数测试，不挂载 Vue 组件，避免依赖 Element Plus 与路由动态导入。
 */
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import {
  acquireIdempotencyKey,
  clearDraft,
  clearIdempotencyKey,
  draftKey,
  emptyDraft,
  generateIdempotencyKey,
  hasDraftContent,
  idempotencyKeyStorageKey,
  loadDraft,
  peekIdempotencyKey,
  saveDraft,
} from '@/features/student-space/draft'
import {
  canRequestReassess,
  canResubmit,
  canSubmit,
  canTransition,
  isFinalized,
  isPendingReview,
  resolveStudentActions,
} from '@/features/student-space/flow'
import type { SubmissionReviewStatus, TaskDraft } from '@/features/student-space/types'

// ── localStorage / sessionStorage 隔离 ──────────────────────────
beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
})

afterEach(() => {
  localStorage.clear()
  sessionStorage.clear()
})

// ============================================================
// 1. 状态流转（flow.ts）
// ============================================================
describe('订正状态机迁移', () => {
  it('draft → submitted 合法', () => {
    expect(canTransition('draft', 'submitted')).toBe(true)
  })

  it('draft → finalized 非法（不可跨态）', () => {
    expect(canTransition('draft', 'finalized')).toBe(false)
  })

  it('submitted → ai_reviewed / teacher_reviewed / returned 均合法', () => {
    expect(canTransition('submitted', 'ai_reviewed')).toBe(true)
    expect(canTransition('submitted', 'teacher_reviewed')).toBe(true)
    expect(canTransition('submitted', 'returned')).toBe(true)
  })

  it('teacher_reviewed → returned / finalized 合法', () => {
    expect(canTransition('teacher_reviewed', 'returned')).toBe(true)
    expect(canTransition('teacher_reviewed', 'finalized')).toBe(true)
  })

  it('returned → resubmitted 合法（学生订正再提交）', () => {
    expect(canTransition('returned', 'resubmitted')).toBe(true)
  })

  it('returned → submitted 非法（必须走 resubmitted）', () => {
    expect(canTransition('returned', 'submitted')).toBe(false)
  })

  it('resubmitted → teacher_reviewed / returned / finalized 合法', () => {
    expect(canTransition('resubmitted', 'teacher_reviewed')).toBe(true)
    expect(canTransition('resubmitted', 'returned')).toBe(true)
    expect(canTransition('resubmitted', 'finalized')).toBe(true)
  })

  it('finalized 为终态，无可迁移目标', () => {
    const targets: SubmissionReviewStatus[] = [
      'draft',
      'submitted',
      'ai_reviewed',
      'teacher_reviewed',
      'returned',
      'resubmitted',
      'finalized',
    ]
    for (const t of targets) {
      expect(canTransition('finalized', t)).toBe(false)
    }
  })
})

describe('学生可执行动作判断', () => {
  it('无提交时可提交（首次）', () => {
    expect(canSubmit(undefined)).toBe(true)
    expect(canSubmit(null)).toBe(true)
  })

  it('draft 状态可提交', () => {
    expect(canSubmit('draft')).toBe(true)
  })

  it('submitted 状态不可提交（等待批阅）', () => {
    expect(canSubmit('submitted')).toBe(false)
    expect(canSubmit('ai_reviewed')).toBe(false)
    expect(canSubmit('teacher_reviewed')).toBe(false)
  })

  it('returned 状态不可直接提交（走订正再提交流程）', () => {
    // canSubmit 仅 draft/无提交；returned 通过 canResubmit 判断
    expect(canSubmit('returned')).toBe(false)
  })

  it('returned 状态可订正再提交', () => {
    expect(canResubmit('returned')).toBe(true)
  })

  it('非 returned 状态不可订正再提交', () => {
    expect(canResubmit('submitted')).toBe(false)
    expect(canResubmit('finalized')).toBe(false)
    expect(canResubmit('draft')).toBe(false)
  })

  it('finalized 状态可发起二次评价', () => {
    expect(canRequestReassess('finalized')).toBe(true)
  })

  it('非 finalized 状态不可发起二次评价', () => {
    expect(canRequestReassess('submitted')).toBe(false)
    expect(canRequestReassess('returned')).toBe(false)
    expect(canRequestReassess('resubmitted')).toBe(false)
  })

  it('isFinalized 仅 finalized 为真', () => {
    expect(isFinalized('finalized')).toBe(true)
    expect(isFinalized('resubmitted')).toBe(false)
    expect(isFinalized(undefined)).toBe(false)
  })

  it('isPendingReview 覆盖等待教师处理的状态', () => {
    expect(isPendingReview('submitted')).toBe(true)
    expect(isPendingReview('ai_reviewed')).toBe(true)
    expect(isPendingReview('teacher_reviewed')).toBe(true)
    expect(isPendingReview('resubmitted')).toBe(true)
    expect(isPendingReview('draft')).toBe(false)
    expect(isPendingReview('returned')).toBe(false)
    expect(isPendingReview('finalized')).toBe(false)
  })
})

describe('resolveStudentActions 动作集合', () => {
  it('draft：仅可提交', () => {
    const a = resolveStudentActions('draft')
    expect(a.canSubmit).toBe(true)
    expect(a.canResubmit).toBe(false)
    expect(a.canRequestReassess).toBe(false)
    expect(a.finalized).toBe(false)
    expect(a.pendingReview).toBe(false)
  })

  it('submitted：等待批阅，无学生可操作项', () => {
    const a = resolveStudentActions('submitted')
    expect(a.canSubmit).toBe(false)
    expect(a.canResubmit).toBe(false)
    expect(a.canRequestReassess).toBe(false)
    expect(a.finalized).toBe(false)
    expect(a.pendingReview).toBe(true)
  })

  it('returned：可订正再提交', () => {
    const a = resolveStudentActions('returned')
    expect(a.canResubmit).toBe(true)
    expect(a.canSubmit).toBe(false)
    expect(a.pendingReview).toBe(false)
  })

  it('finalized：可二次评价，标记终态', () => {
    const a = resolveStudentActions('finalized')
    expect(a.canRequestReassess).toBe(true)
    expect(a.finalized).toBe(true)
    expect(a.pendingReview).toBe(false)
  })

  it('无提交状态：仅可提交', () => {
    const a = resolveStudentActions(undefined)
    expect(a.canSubmit).toBe(true)
    expect(a.finalized).toBe(false)
  })
})

// ============================================================
// 2. 自动保存（draft.ts）
// ============================================================
describe('localStorage 草稿自动保存', () => {
  it('draftKey 按 task_id 隔离且稳定', () => {
    expect(draftKey('task-1')).toBe('student:draft:task-1')
    expect(draftKey('task-2')).toBe('student:draft:task-2')
  })

  it('emptyDraft 返回空白结构', () => {
    const d = emptyDraft()
    expect(d.content).toBe('')
    expect(d.fileUrls).toEqual([])
  })

  it('saveDraft/loadDraft 往返一致并附带 savedAt', () => {
    const d: TaskDraft = { content: '我的作答', fileUrls: ['https://x/a.pdf'] }
    saveDraft('task-1', d)
    const loaded = loadDraft('task-1')
    expect(loaded).not.toBeNull()
    expect(loaded!.content).toBe('我的作答')
    expect(loaded!.fileUrls).toEqual(['https://x/a.pdf'])
    expect(loaded!.savedAt).toBeTruthy()
  })

  it('loadDraft 对不存在的键返回 null', () => {
    expect(loadDraft('missing')).toBeNull()
  })

  it('loadDraft 对损坏 JSON 返回 null 而不抛出', () => {
    localStorage.setItem(draftKey('bad'), '{not json')
    expect(loadDraft('bad')).toBeNull()
  })

  it('loadDraft 与旧草稿合并，避免缺字段', () => {
    localStorage.setItem(
      draftKey('old'),
      JSON.stringify({ content: '旧内容' }),
    )
    const loaded = loadDraft('old')
    expect(loaded).not.toBeNull()
    expect(loaded!.content).toBe('旧内容')
    expect(loaded!.fileUrls).toEqual([])
  })

  it('clearDraft 清除后 loadDraft 返回 null', () => {
    saveDraft('task-1', { content: 'x', fileUrls: [] })
    clearDraft('task-1')
    expect(loadDraft('task-1')).toBeNull()
  })

  it('hasDraftContent 对空草稿返回 false', () => {
    expect(hasDraftContent(null)).toBe(false)
    expect(hasDraftContent({ content: '', fileUrls: [] })).toBe(false)
    expect(hasDraftContent({ content: '   ', fileUrls: [] })).toBe(false)
  })

  it('hasDraftContent 对有内容或附件返回 true', () => {
    expect(hasDraftContent({ content: '作答', fileUrls: [] })).toBe(true)
    expect(hasDraftContent({ content: '', fileUrls: ['a.pdf'] })).toBe(true)
  })

  it('不同 task_id 草稿互不干扰', () => {
    saveDraft('task-a', { content: 'A', fileUrls: [] })
    saveDraft('task-b', { content: 'B', fileUrls: ['b.pdf'] })
    expect(loadDraft('task-a')!.content).toBe('A')
    expect(loadDraft('task-b')!.content).toBe('B')
    expect(loadDraft('task-b')!.fileUrls).toEqual(['b.pdf'])
    clearDraft('task-a')
    expect(loadDraft('task-a')).toBeNull()
    expect(loadDraft('task-b')).not.toBeNull()
  })
})

// ============================================================
// 3. 幂等提交键（draft.ts）
// ============================================================
describe('幂等提交键', () => {
  it('generateIdempotencyKey 生成合法 UUID v4 格式', () => {
    const key = generateIdempotencyKey()
    // UUID v4 格式：8-4-4-4-12，第 3 段以 4 开头，第 4 段以 8/9/a/b 开头
    expect(key).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
    )
  })

  it('generateIdempotencyKey 每次生成不同值', () => {
    const keys = new Set<string>()
    for (let i = 0; i < 50; i++) keys.add(generateIdempotencyKey())
    expect(keys.size).toBe(50)
  })

  it('idempotencyKeyStorageKey 按 task_id 隔离', () => {
    expect(idempotencyKeyStorageKey('task-1')).toBe('student:idem:task-1')
  })

  it('acquireIdempotencyKey 首次生成并暂存', () => {
    const key = acquireIdempotencyKey('task-1')
    expect(key).toMatch(/^[0-9a-f-]+$/)
    expect(peekIdempotencyKey('task-1')).toBe(key)
  })

  it('acquireIdempotencyKey 同任务多次调用返回同一键（重复点击去重）', () => {
    const k1 = acquireIdempotencyKey('task-1')
    const k2 = acquireIdempotencyKey('task-1')
    const k3 = acquireIdempotencyKey('task-1')
    expect(k1).toBe(k2)
    expect(k2).toBe(k3)
  })

  it('不同任务幂等键相互独立', () => {
    const k1 = acquireIdempotencyKey('task-a')
    const k2 = acquireIdempotencyKey('task-b')
    expect(k1).not.toBe(k2)
    expect(peekIdempotencyKey('task-a')).toBe(k1)
    expect(peekIdempotencyKey('task-b')).toBe(k2)
  })

  it('clearIdempotencyKey 后再次 acquire 生成新键', () => {
    const k1 = acquireIdempotencyKey('task-1')
    clearIdempotencyKey('task-1')
    expect(peekIdempotencyKey('task-1')).toBeNull()
    const k2 = acquireIdempotencyKey('task-1')
    expect(k2).not.toBe(k1)
  })

  it('peekIdempotencyKey 对未暂存任务返回 null', () => {
    expect(peekIdempotencyKey('never')).toBeNull()
  })

  it('模拟提交流程：acquire → 提交 → clear → 下次提交生成新键', () => {
    // 第一次提交尝试
    const firstAttemptKey = acquireIdempotencyKey('task-submit')
    expect(firstAttemptKey).toBeTruthy()

    // 重复点击提交（同一会话）复用同一键
    expect(acquireIdempotencyKey('task-submit')).toBe(firstAttemptKey)

    // 提交成功后清除
    clearIdempotencyKey('task-submit')
    expect(peekIdempotencyKey('task-submit')).toBeNull()

    // 下一次提交生成全新键
    const secondAttemptKey = acquireIdempotencyKey('task-submit')
    expect(secondAttemptKey).not.toBe(firstAttemptKey)
  })
})

// ============================================================
// 4. 端到端状态流转场景（综合）
// ============================================================
describe('学习改进闭环状态场景', () => {
  it('完整闭环：提交 → 教师退回 → 订正 → 最终确认 → 二次评价', () => {
    // 1. 学生首次提交：draft → submitted
    expect(canTransition('draft', 'submitted')).toBe(true)
    expect(canSubmit('draft')).toBe(true)

    // 2. 教师批阅后退回：submitted → returned
    expect(canTransition('submitted', 'returned')).toBe(true)
    // 学生此时可订正再提交
    expect(canResubmit('returned')).toBe(true)

    // 3. 学生订正再提交：returned → resubmitted
    expect(canTransition('returned', 'resubmitted')).toBe(true)

    // 4. 教师复核后最终确认：resubmitted → finalized
    expect(canTransition('resubmitted', 'finalized')).toBe(true)
    expect(isFinalized('finalized')).toBe(true)

    // 5. 学生发起二次评价：finalized 可 reassess（后端创建新版本回到 resubmitted）
    expect(canRequestReassess('finalized')).toBe(true)
    // 二次评价后状态回到 resubmitted，等待教师再次复核
    expect(canTransition('resubmitted', 'teacher_reviewed')).toBe(true)
  })

  it('学生不能从已提交状态自行修改（submitted 不可提交）', () => {
    const actions = resolveStudentActions('submitted')
    expect(actions.canSubmit).toBe(false)
    expect(actions.canResubmit).toBe(false)
    expect(actions.canRequestReassess).toBe(false)
    expect(actions.pendingReview).toBe(true)
  })

  it('草稿自动保存 + 幂等键配合：刷新后草稿恢复、幂等键保留', () => {
    // 学生编辑中，自动保存草稿
    saveDraft('task-flow', { content: '正在作答...', fileUrls: [] })
    const idemKey = acquireIdempotencyKey('task-flow')

    // 模拟刷新：草稿与幂等键均从 storage 恢复
    const restoredDraft = loadDraft('task-flow')
    const restoredKey = peekIdempotencyKey('task-flow')
    expect(restoredDraft!.content).toBe('正在作答...')
    expect(restoredKey).toBe(idemKey)

    // 提交时复用同一幂等键（重复点击去重）
    expect(acquireIdempotencyKey('task-flow')).toBe(idemKey)

    // 提交成功后清理
    clearDraft('task-flow')
    clearIdempotencyKey('task-flow')
    expect(loadDraft('task-flow')).toBeNull()
    expect(peekIdempotencyKey('task-flow')).toBeNull()
  })
})
