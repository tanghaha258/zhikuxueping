/**
 * 项目工作区纯逻辑测试（计划 Task 2.1）。
 *
 * 覆盖四类：
 * 1. 路由：resolveNextStep 在不同项目状态下的下一步入口、canEditDesign
 * 2. 草稿恢复：localStorage 草稿的写入、读取、清除与结构合并
 * 3. 步骤校验：validateStep 对每一步的硬错误与警告
 * 4. 服务端错误映射：mapServerError 对 422/409/通用错误的步骤定位
 *
 * 纯函数测试，不挂载 Vue 组件，避免依赖 Element Plus 与路由动态导入。
 */
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import {
  canEditDesign,
  clearDraft,
  draftKey,
  emptyDraft,
  loadDraft,
  mapServerError,
  resolveNextStep,
  saveDraft,
  validateStep,
} from './composables/useProjectWorkspace'
import type {
  ProjectDesignSnapshot,
  ProjectValidationResult,
  ProjectWizardDraft,
} from './types'

// ── 测试夹具 ────────────────────────────────────────────────────
function makeDraft(overrides: Partial<ProjectWizardDraft> = {}): ProjectWizardDraft {
  return { ...emptyDraft(), ...overrides }
}

function makeSnapshot(
  overrides: Partial<ProjectDesignSnapshot> = {},
): ProjectDesignSnapshot {
  return {
    problem: null,
    contributions: [],
    goals: [],
    indicators: [],
    evidencePlans: [],
    ...overrides,
  }
}

function makeValidation(
  overrides: Partial<ProjectValidationResult> = {},
): ProjectValidationResult {
  return {
    canActivate: false,
    blockers: [],
    warnings: [],
    completion: 0,
    details: {},
    ...overrides,
  }
}

// ── localStorage 隔离 ──────────────────────────────────────────
beforeEach(() => {
  localStorage.clear()
})

afterEach(() => {
  localStorage.clear()
})

// ============================================================
// 1. 路由：resolveNextStep 与 canEditDesign
// ============================================================
describe('resolveNextStep 路由建议', () => {
  const pid = 'proj-1'

  it('草稿且无真实问题 → 指向设计页完善问题', () => {
    const snap = makeSnapshot({ problem: null })
    const result = resolveNextStep(pid, 'draft', null, snap)
    expect(result.route).toBe(`/teacher/projects/${pid}/design`)
    expect(result.label).toBe('完善真实问题')
    expect(result.actionable).toBe(true)
  })

  it('草稿且有真实问题但缺核心学科 → 指向设计页完善贡献', () => {
    const snap = makeSnapshot({
      problem: { id: 'p', projectId: pid, context: 'ctx', isCurrent: true, version: 1 },
      contributions: [{ id: 'c', projectId: pid, subjectId: 's1', role: 'support' }],
    })
    const result = resolveNextStep(pid, 'draft', null, snap)
    expect(result.label).toBe('完善学科贡献')
    expect(result.reason).toContain('核心学科')
  })

  it('草稿且核心+支撑齐全但完整性有阻断 → 指向设计页补齐', () => {
    const snap = makeSnapshot({
      problem: { id: 'p', projectId: pid, context: 'ctx', isCurrent: true, version: 1 },
      contributions: [
        { id: 'c1', projectId: pid, subjectId: 's1', role: 'core' },
        { id: 'c2', projectId: pid, subjectId: 's2', role: 'support' },
      ],
    })
    const val = makeValidation({
      canActivate: false,
      blockers: [{ code: 'goal_without_indicator', field: 'goals', message: 'm' }],
    })
    const result = resolveNextStep(pid, 'draft', val, snap)
    expect(result.label).toBe('补齐缺失项')
    expect(result.reason).toContain('1')
  })

  it('草稿且设计完整 → 建议提交审核', () => {
    const snap = makeSnapshot({
      problem: { id: 'p', projectId: pid, context: 'ctx', isCurrent: true, version: 1 },
      contributions: [
        { id: 'c1', projectId: pid, subjectId: 's1', role: 'core' },
        { id: 'c2', projectId: pid, subjectId: 's2', role: 'support' },
      ],
    })
    const val = makeValidation({ canActivate: true, blockers: [], completion: 1 })
    const result = resolveNextStep(pid, 'draft', val, snap)
    expect(result.label).toBe('提交审核')
    expect(result.actionable).toBe(true)
  })

  it('pending_review 且可激活 → 建议激活', () => {
    const val = makeValidation({ canActivate: true, blockers: [], completion: 1 })
    const result = resolveNextStep(pid, 'pending_review', val, makeSnapshot())
    expect(result.label).toBe('激活项目')
  })

  it('pending_review 且不可激活 → 指向设计页补齐', () => {
    const val = makeValidation({ canActivate: false, blockers: [{ code: 'x', field: 'f', message: 'm' }] })
    const result = resolveNextStep(pid, 'pending_review', val, makeSnapshot())
    expect(result.label).toBe('补齐缺失项')
  })

  it('active → 继续任务链', () => {
    const result = resolveNextStep(pid, 'active', null, makeSnapshot())
    expect(result.label).toBe('继续任务链')
    expect(result.route).toBe(`/teacher/projects/${pid}/tasks`)
  })

  it('completed → 归档', () => {
    const result = resolveNextStep(pid, 'completed', null, makeSnapshot())
    expect(result.label).toBe('归档项目')
  })

  it('archived → 无可操作下一步', () => {
    const result = resolveNextStep(pid, 'archived', null, makeSnapshot())
    expect(result.actionable).toBe(false)
  })
})

describe('canEditDesign 设计可编辑性', () => {
  it('草稿与待审核可编辑', () => {
    expect(canEditDesign('draft')).toBe(true)
    expect(canEditDesign('pending_review')).toBe(true)
  })

  it('进行中/完成/归档不可编辑', () => {
    expect(canEditDesign('active')).toBe(false)
    expect(canEditDesign('completed')).toBe(false)
    expect(canEditDesign('archived')).toBe(false)
  })
})

// ============================================================
// 2. 草稿恢复
// ============================================================
describe('草稿恢复', () => {
  it('draftKey 拼装稳定', () => {
    expect(draftKey('new')).toBe('pws:draft:new')
    expect(draftKey('proj-1')).toBe('pws:draft:proj-1')
  })

  it('emptyDraft 返回结构完整且步骤为 0', () => {
    const d = emptyDraft()
    expect(d.step).toBe(0)
    expect(d.title).toBe('')
    expect(d.supportSubjectIds).toEqual([])
    expect(d.contributionNotes).toEqual({})
  })

  it('saveDraft/loadDraft 往返一致并附带 savedAt', () => {
    const d = makeDraft({ title: '我的项目', step: 2, coreSubjectId: 'sub-1' })
    saveDraft('new', d)
    const loaded = loadDraft('new')
    expect(loaded).not.toBeNull()
    expect(loaded!.title).toBe('我的项目')
    expect(loaded!.step).toBe(2)
    expect(loaded!.coreSubjectId).toBe('sub-1')
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
    // 模拟旧版本草稿缺少 goals 字段
    localStorage.setItem(
      draftKey('old'),
      JSON.stringify({ title: '旧项目', step: 1 }),
    )
    const loaded = loadDraft('old')
    expect(loaded).not.toBeNull()
    expect(loaded!.title).toBe('旧项目')
    expect(loaded!.goals).toEqual([])
    expect(loaded!.supportSubjectIds).toEqual([])
  })

  it('clearDraft 清除后 loadDraft 返回 null', () => {
    saveDraft('new', makeDraft())
    clearDraft('new')
    expect(loadDraft('new')).toBeNull()
  })
})

// ============================================================
// 3. 步骤校验
// ============================================================
describe('validateStep 步骤校验', () => {
  it('步骤 0：标题为空产生硬错误', () => {
    const d = makeDraft({ title: '' })
    const r = validateStep(0, d)
    expect(r.valid).toBe(false)
    expect(r.errors).toHaveLength(1)
    expect(r.errors[0].field).toBe('title')
  })

  it('步骤 0：标题非空但缺年级/班级仅警告', () => {
    const d = makeDraft({ title: '项目A' })
    const r = validateStep(0, d)
    expect(r.valid).toBe(true)
    expect(r.errors).toHaveLength(0)
    expect(r.warnings.length).toBeGreaterThanOrEqual(1)
  })

  it('步骤 1：情境为空仅警告不阻断', () => {
    const d = makeDraft({ problemContext: '' })
    const r = validateStep(1, d)
    expect(r.valid).toBe(true)
    expect(r.warnings.some((w) => w.field === 'problemContext')).toBe(true)
  })

  it('步骤 2：支撑学科与核心学科重复产生硬错误', () => {
    const d = makeDraft({
      coreSubjectId: 'sub-1',
      supportSubjectIds: ['sub-1', 'sub-2'],
    })
    const r = validateStep(2, d)
    expect(r.valid).toBe(false)
    expect(r.errors[0].field).toBe('supportSubjectIds')
  })

  it('步骤 2：缺核心与支撑学科仅警告', () => {
    const d = makeDraft()
    const r = validateStep(2, d)
    expect(r.valid).toBe(true)
    expect(r.warnings.length).toBe(2)
  })

  it('步骤 2：核心+支撑齐全且不重复 → 无错误无警告', () => {
    const d = makeDraft({ coreSubjectId: 'sub-1', supportSubjectIds: ['sub-2'] })
    const r = validateStep(2, d)
    expect(r.valid).toBe(true)
    expect(r.warnings).toHaveLength(0)
  })

  it('步骤 3：无目标仅警告', () => {
    const d = makeDraft({ goals: [] })
    const r = validateStep(3, d)
    expect(r.valid).toBe(true)
    expect(r.warnings[0].field).toBe('goals')
  })

  it('步骤 4：汇总步骤 0 与步骤 2 的硬错误', () => {
    const d = makeDraft({
      title: '',
      coreSubjectId: 's1',
      supportSubjectIds: ['s1'],
    })
    const r = validateStep(4, d)
    expect(r.valid).toBe(false)
    const fields = r.errors.map((e) => e.field)
    expect(fields).toContain('title')
    expect(fields).toContain('supportSubjectIds')
  })
})

// ============================================================
// 4. 服务端错误映射
// ============================================================
describe('mapServerError 服务端错误映射', () => {
  function makeAxiosError(status: number, data: unknown) {
    return {
      response: { status, data },
      message: 'Request failed',
    }
  }

  it('HTTP 422 按 detail.loc 定位字段与步骤', () => {
    const err = makeAxiosError(422, {
      detail: [{ loc: ['body', 'title'], msg: 'field required', type: 'value_error.missing' }],
    })
    const mapped = mapServerError(err)
    expect(mapped.fieldLevel).toBe(true)
    expect(mapped.step).toBe(0)
    expect(mapped.field).toBe('title')
    expect(mapped.status).toBe(422)
  })

  it('HTTP 422 学科字段定位到步骤 2', () => {
    const err = makeAxiosError(422, {
      detail: [{ loc: ['body', 'subject_id'], msg: 'bad', type: 'x' }],
    })
    const mapped = mapServerError(err)
    expect(mapped.step).toBe(2)
    expect(mapped.field).toBe('subject_id')
  })

  it('HTTP 409 学科冲突消息定位到步骤 2', () => {
    const err = makeAxiosError(409, {
      code: 40902,
      message: '学科贡献已存在，不能重复添加',
    })
    const mapped = mapServerError(err)
    expect(mapped.status).toBe(409)
    expect(mapped.code).toBe(40902)
    expect(mapped.step).toBe(2)
    expect(mapped.field).toBe('coreSubjectId')
  })

  it('HTTP 409 状态机非法跃迁定位到步骤 4', () => {
    const err = makeAxiosError(409, {
      code: 40901,
      message: '项目当前状态 draft 不允许激活，需先提交审核',
    })
    const mapped = mapServerError(err)
    expect(mapped.step).toBe(4)
    expect(mapped.fieldLevel).toBe(false)
  })

  it('HTTP 409 目标/指标缺失定位到步骤 3', () => {
    const err = makeAxiosError(409, {
      code: 40902,
      message: '学习目标缺少可观察指标，无法激活',
    })
    const mapped = mapServerError(err)
    expect(mapped.step).toBe(3)
    expect(mapped.field).toBe('goals')
  })

  it('无 response 的网络错误返回通用映射', () => {
    const err = new Error('Network Error')
    const mapped = mapServerError(err)
    expect(mapped.status).toBe(0)
    expect(mapped.step).toBeNull()
    expect(mapped.field).toBeNull()
    expect(mapped.fieldLevel).toBe(false)
    expect(mapped.message).toBe('Network Error')
  })

  it('HTTP 500 通用错误不定位步骤', () => {
    const err = makeAxiosError(500, { message: '服务器内部错误' })
    const mapped = mapServerError(err)
    expect(mapped.status).toBe(500)
    expect(mapped.step).toBeNull()
    expect(mapped.message).toBe('服务器内部错误')
  })
})
