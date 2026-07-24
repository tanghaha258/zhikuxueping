/**
 * 项目学情诊断领域纯函数与 store 测试（Task 6）。
 *
 * 覆盖四类：
 * 1. 纯函数：证据判定、可确认判定、错误映射、来源格式化。
 * 2. store loadLatest：首次拉取 / 复用缓存 / 项目变化重新拉取 / force 刷新 / 404 不视为错误（无诊断）。
 * 3. store generate：成功更新当前诊断；insufficient_evidence 不显示成功；AI 失败转人工诊断。
 * 4. store confirm：成功将状态转为 confirmed；无证据诊断不可确认；归档只读。
 *
 * 使用 vi.mock 隔离 api 模块，避免真实网络请求；不挂载 Vue 组件。
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { AxiosError } from 'axios'

// ── mock api 模块（vi.hoisted 确保 vi.mock 工厂可访问）─────────
const apiMocks = vi.hoisted(() => ({
  getLatestInsightApi: vi.fn(),
  generateInsightApi: vi.fn(),
  confirmInsightApi: vi.fn(),
}))
vi.mock('@/features/project-diagnosis/api', () => apiMocks)

import {
  canConfirmInsight,
  formatSourceCounts,
  hasEvidence,
  mapDiagnosisError,
  useProjectDiagnosisStore,
} from '@/features/project-diagnosis/store'
import type {
  InsightSegment,
  InsightSourceCounts,
  InsightWeakPoint,
  ProjectLearningInsight,
} from '@/features/project-diagnosis/types'

// ── 测试夹具 ────────────────────────────────────────────────────
function makeCounts(overrides: Partial<InsightSourceCounts> = {}): InsightSourceCounts {
  return {
    preTest: 0,
    submissions: 0,
    evaluations: 0,
    questionAnswers: 0,
    ...overrides,
  }
}

function makeSegment(overrides: Partial<InsightSegment> = {}): InsightSegment {
  return {
    name: '掌握',
    studentCount: 0,
    masteryRange: [0.8, 1.0],
    ...overrides,
  }
}

function makeWeakPoint(overrides: Partial<InsightWeakPoint> = {}): InsightWeakPoint {
  return {
    area: '基础掌握待巩固',
    studentCount: 0,
    avgMastery: 0.4,
    ...overrides,
  }
}

function makeInsight(
  overrides: Partial<ProjectLearningInsight> = {},
): ProjectLearningInsight {
  return {
    id: 'insight-1',
    projectId: 'proj-1',
    status: 'draft',
    segments: [],
    overallMastery: null,
    weakPoints: [],
    teachingSuggestions: [],
    sourceCounts: makeCounts(),
    evidenceCutoff: '2026-07-24T10:00:00Z',
    generatedAt: '2026-07-24T10:00:00Z',
    generatedBy: 'user-1',
    confirmedBy: null,
    confirmedAt: null,
    teacherNote: null,
    isCurrent: true,
    ...overrides,
  }
}

function makeAxiosError(
  status: number,
  data: { code?: number; message?: string } = {},
): AxiosError {
  return {
    response: { status, data },
    message: 'Request failed',
  } as unknown as AxiosError
}

// ── Pinia 隔离 ─────────────────────────────────────────────────
beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

afterEach(() => {
  vi.restoreAllMocks()
})

// ============================================================
// 1. 纯函数
// ============================================================
describe('hasEvidence 证据判定', () => {
  it('所有来源都为 0 时返回 false', () => {
    const insight = makeInsight({ sourceCounts: makeCounts() })
    expect(hasEvidence(insight)).toBe(false)
  })

  it('任一来源大于 0 时返回 true', () => {
    const insight = makeInsight({
      sourceCounts: makeCounts({ preTest: 1 }),
    })
    expect(hasEvidence(insight)).toBe(true)
  })

  it('已发布评价存在时返回 true', () => {
    const insight = makeInsight({
      sourceCounts: makeCounts({ evaluations: 5 }),
    })
    expect(hasEvidence(insight)).toBe(true)
  })

  it('currentInsight 为 null 时返回 false', () => {
    expect(hasEvidence(null)).toBe(false)
  })

  it('insufficient_evidence 状态时返回 false（即使有计数）', () => {
    // 后端在无证据时返回 insufficient_evidence 且所有计数为 0；
    // 此处显式断言：状态为 insufficient_evidence 时不可视为有证据。
    const insight = makeInsight({
      status: 'insufficient_evidence',
      sourceCounts: makeCounts(),
    })
    expect(hasEvidence(insight)).toBe(false)
  })
})

describe('canConfirmInsight 可确认判定', () => {
  it('draft 状态可确认', () => {
    expect(canConfirmInsight(makeInsight({ status: 'draft' }))).toBe(true)
  })

  it('insufficient_evidence 状态不可确认', () => {
    expect(
      canConfirmInsight(makeInsight({ status: 'insufficient_evidence' })),
    ).toBe(false)
  })

  it('confirmed 状态不可重复确认', () => {
    expect(canConfirmInsight(makeInsight({ status: 'confirmed' }))).toBe(false)
  })

  it('stale 状态不可确认', () => {
    expect(canConfirmInsight(makeInsight({ status: 'stale' }))).toBe(false)
  })

  it('currentInsight 为 null 时返回 false', () => {
    expect(canConfirmInsight(null)).toBe(false)
  })
})

describe('formatSourceCounts 来源格式化', () => {
  it('返回四类来源的可读标签与计数', () => {
    const counts = makeCounts({
      preTest: 3,
      submissions: 12,
      evaluations: 8,
      questionAnswers: 25,
    })
    const result = formatSourceCounts(counts)
    expect(result).toEqual([
      { label: '前测', count: 3 },
      { label: '任务提交', count: 12 },
      { label: '已发布评价', count: 8 },
      { label: '题目作答', count: 25 },
    ])
  })

  it('所有来源为 0 时返回零计数', () => {
    const result = formatSourceCounts(makeCounts())
    expect(result).toHaveLength(4)
    expect(result.every((r) => r.count === 0)).toBe(true)
  })
})

describe('mapDiagnosisError 错误映射', () => {
  it('403 映射为权限错误', () => {
    const err = makeAxiosError(403, { code: 40301, message: '无权访问该项目' })
    const mapped = mapDiagnosisError(err)
    expect(mapped.status).toBe(403)
    expect(mapped.forbidden).toBe(true)
    expect(mapped.notFound).toBe(false)
    expect(mapped.code).toBe(40301)
    expect(mapped.message).toBe('无权访问该项目')
  })

  it('404 映射为未找到', () => {
    const err = makeAxiosError(404, { message: '诊断记录不存在' })
    const mapped = mapDiagnosisError(err)
    expect(mapped.status).toBe(404)
    expect(mapped.notFound).toBe(true)
    expect(mapped.forbidden).toBe(false)
  })

  it('409 映射为业务冲突（如归档只读/重复确认）', () => {
    const err = makeAxiosError(409, { code: 40901, message: '项目已归档，不可生成诊断' })
    const mapped = mapDiagnosisError(err)
    expect(mapped.status).toBe(409)
    expect(mapped.conflict).toBe(true)
    expect(mapped.code).toBe(40901)
    expect(mapped.message).toBe('项目已归档，不可生成诊断')
  })

  it('无 response 的网络错误映射为 status=0', () => {
    const err = new Error('Network Error') as unknown
    const mapped = mapDiagnosisError(err)
    expect(mapped.status).toBe(0)
    expect(mapped.message).toBe('网络错误')
    expect(mapped.forbidden).toBe(false)
    expect(mapped.notFound).toBe(false)
    expect(mapped.conflict).toBe(false)
  })

  it('500 通用错误不标记权限/未找到/冲突', () => {
    const err = makeAxiosError(500, { message: '服务器内部错误' })
    const mapped = mapDiagnosisError(err)
    expect(mapped.status).toBe(500)
    expect(mapped.forbidden).toBe(false)
    expect(mapped.notFound).toBe(false)
    expect(mapped.conflict).toBe(false)
  })

  it('有 code 但无 message 时回退到默认消息', () => {
    const err = makeAxiosError(409, { code: 40902 })
    const mapped = mapDiagnosisError(err)
    expect(mapped.code).toBe(40902)
    expect(mapped.message).toBe('请求失败')
  })
})

// ============================================================
// 2. store loadLatest
// ============================================================
describe('store loadLatest 拉取当前诊断', () => {
  it('首次拉取调用 API 并缓存诊断', async () => {
    const insight = makeInsight()
    apiMocks.getLatestInsightApi.mockResolvedValue({ data: { data: insight } })
    const store = useProjectDiagnosisStore()

    await store.loadLatest('proj-1')

    expect(apiMocks.getLatestInsightApi).toHaveBeenCalledTimes(1)
    expect(apiMocks.getLatestInsightApi).toHaveBeenCalledWith('proj-1')
    expect(store.currentInsight).toEqual(insight)
    expect(store.currentProjectId).toBe('proj-1')
    expect(store.hasInsight).toBe(true)
    expect(store.loading).toBe(false)
    expect(store.error).toBeNull()
  })

  it('同项目在 TTL 内复用缓存，不重复请求', async () => {
    const insight = makeInsight()
    apiMocks.getLatestInsightApi.mockResolvedValue({ data: { data: insight } })
    const store = useProjectDiagnosisStore()

    await store.loadLatest('proj-1')
    await store.loadLatest('proj-1')

    expect(apiMocks.getLatestInsightApi).toHaveBeenCalledTimes(1)
  })

  it('项目 ID 变化时重新请求', async () => {
    const insight1 = makeInsight()
    const insight2 = makeInsight({ id: 'insight-2', projectId: 'proj-2' })
    apiMocks.getLatestInsightApi
      .mockResolvedValueOnce({ data: { data: insight1 } })
      .mockResolvedValueOnce({ data: { data: insight2 } })
    const store = useProjectDiagnosisStore()

    await store.loadLatest('proj-1')
    await store.loadLatest('proj-2')

    expect(apiMocks.getLatestInsightApi).toHaveBeenCalledTimes(2)
    expect(store.currentProjectId).toBe('proj-2')
    expect(store.currentInsight?.id).toBe('insight-2')
  })

  it('force=true 强制刷新即使同项目', async () => {
    const insight = makeInsight()
    apiMocks.getLatestInsightApi.mockResolvedValue({ data: { data: insight } })
    const store = useProjectDiagnosisStore()

    await store.loadLatest('proj-1')
    await store.loadLatest('proj-1', true)

    expect(apiMocks.getLatestInsightApi).toHaveBeenCalledTimes(2)
  })

  it('refreshLatest 强制刷新当前项目', async () => {
    const insight = makeInsight()
    apiMocks.getLatestInsightApi.mockResolvedValue({ data: { data: insight } })
    const store = useProjectDiagnosisStore()

    await store.loadLatest('proj-1')
    await store.refreshLatest()

    expect(apiMocks.getLatestInsightApi).toHaveBeenCalledTimes(2)
  })

  it('refreshLatest 无当前项目时不请求', async () => {
    const store = useProjectDiagnosisStore()
    await store.refreshLatest()
    expect(apiMocks.getLatestInsightApi).not.toHaveBeenCalled()
  })

  it('404 不视为错误，currentInsight 置为 null', async () => {
    // 后端 latest 在无诊断时返回 data=null；前端不显示错误条。
    apiMocks.getLatestInsightApi.mockResolvedValue({ data: { data: null } })
    const store = useProjectDiagnosisStore()

    await store.loadLatest('proj-1')

    expect(store.currentInsight).toBeNull()
    expect(store.hasInsight).toBe(false)
    expect(store.error).toBeNull()
    expect(store.loading).toBe(false)
  })

  it('403 权限错误设置 error 且 forbidden=true', async () => {
    apiMocks.getLatestInsightApi.mockRejectedValue(
      makeAxiosError(403, { code: 40301, message: '无权访问该项目' }),
    )
    const store = useProjectDiagnosisStore()

    await expect(store.loadLatest('proj-1')).rejects.toBeDefined()
    expect(store.error).not.toBeNull()
    expect(store.error!.forbidden).toBe(true)
    expect(store.error!.status).toBe(403)
    expect(store.loading).toBe(false)
    expect(store.hasInsight).toBe(false)
  })

  it('网络错误（无响应）设置 error status=0', async () => {
    apiMocks.getLatestInsightApi.mockRejectedValue(new Error('Network Error'))
    const store = useProjectDiagnosisStore()

    await expect(store.loadLatest('proj-1')).rejects.toBeDefined()
    expect(store.error!.status).toBe(0)
    expect(store.error!.message).toBe('网络错误')
  })

  it('clear 清除缓存', async () => {
    const insight = makeInsight()
    apiMocks.getLatestInsightApi.mockResolvedValue({ data: { data: insight } })
    const store = useProjectDiagnosisStore()

    await store.loadLatest('proj-1')
    store.clear()

    expect(store.hasInsight).toBe(false)
    expect(store.currentProjectId).toBeNull()
    expect(store.currentInsight).toBeNull()
  })
})

// ============================================================
// 3. store generate
// ============================================================
describe('store generate 生成诊断', () => {
  it('有证据时生成 draft 诊断并更新缓存', async () => {
    const generated = makeInsight({
      status: 'draft',
      segments: [
        makeSegment({ name: '掌握', studentCount: 5 }),
        makeSegment({ name: '基本掌握', studentCount: 8 }),
        makeSegment({ name: '待提升', studentCount: 3 }),
      ],
      overallMastery: 0.72,
      weakPoints: [makeWeakPoint({ studentCount: 3 })],
      teachingSuggestions: ['为 3 名待提升学生设计基础巩固任务'],
      sourceCounts: makeCounts({ evaluations: 16 }),
    })
    apiMocks.generateInsightApi.mockResolvedValue({ data: { data: generated } })
    const store = useProjectDiagnosisStore()

    const result = await store.generate('proj-1')

    expect(apiMocks.generateInsightApi).toHaveBeenCalledWith('proj-1')
    expect(result.status).toBe('draft')
    expect(store.currentInsight).toEqual(generated)
    expect(store.lastAction).toBe('generate')
    expect(store.lastActionSucceeded).toBe(true)
  })

  it('无证据时生成 insufficient_evidence 诊断，不显示成功', async () => {
    // 关键约束：无证据时不能伪成功；UI 应显示"导入前测/先发布任务"入口。
    const insufficient = makeInsight({
      status: 'insufficient_evidence',
      segments: [],
      overallMastery: null,
      weakPoints: [],
      teachingSuggestions: [],
      sourceCounts: makeCounts(),
    })
    apiMocks.generateInsightApi.mockResolvedValue({ data: { data: insufficient } })
    const store = useProjectDiagnosisStore()

    const result = await store.generate('proj-1')

    expect(result.status).toBe('insufficient_evidence')
    expect(result.segments).toEqual([])
    expect(store.currentInsight).toEqual(insufficient)
    expect(store.lastAction).toBe('generate')
    // 无证据不视为成功生成可用的诊断
    expect(store.lastActionSucceeded).toBe(false)
    expect(store.evidenceMissing).toBe(true)
  })

  it('归档项目返回 409 时设置 conflict 错误且不显示成功', async () => {
    apiMocks.generateInsightApi.mockRejectedValue(
      makeAxiosError(409, { code: 40901, message: '项目已归档，不可生成诊断' }),
    )
    const store = useProjectDiagnosisStore()

    await expect(store.generate('proj-1')).rejects.toBeDefined()
    expect(store.error).not.toBeNull()
    expect(store.error!.conflict).toBe(true)
    expect(store.error!.status).toBe(409)
    expect(store.lastAction).toBe('generate')
    expect(store.lastActionSucceeded).toBe(false)
  })

  it('AI 失败（500）必须转人工诊断且不显示成功', async () => {
    // 关键约束：AI 失败不可显示成功；UI 应提示转人工诊断。
    apiMocks.generateInsightApi.mockRejectedValue(
      makeAxiosError(500, { message: 'AI 服务不可用' }),
    )
    const store = useProjectDiagnosisStore()

    await expect(store.generate('proj-1')).rejects.toBeDefined()
    expect(store.error).not.toBeNull()
    expect(store.error!.status).toBe(500)
    expect(store.lastAction).toBe('generate')
    expect(store.lastActionSucceeded).toBe(false)
    expect(store.shouldFallbackToManual).toBe(true)
  })

  it('生成中设置 generating=true，结束后复位', async () => {
    const generated = makeInsight({ status: 'draft' })
    apiMocks.generateInsightApi.mockResolvedValue({ data: { data: generated } })
    const store = useProjectDiagnosisStore()

    expect(store.generating).toBe(false)
    const promise = store.generate('proj-1')
    expect(store.generating).toBe(true)
    await promise
    expect(store.generating).toBe(false)
  })
})

// ============================================================
// 4. store confirm
// ============================================================
describe('store confirm 确认诊断', () => {
  it('draft 诊断确认成功后状态转为 confirmed', async () => {
    const confirmed = makeInsight({
      status: 'confirmed',
      confirmedBy: 'user-1',
      confirmedAt: '2026-07-24T11:00:00Z',
      teacherNote: '与班组教师共同复核',
    })
    apiMocks.getLatestInsightApi.mockResolvedValue({
      data: { data: makeInsight({ status: 'draft' }) },
    })
    apiMocks.confirmInsightApi.mockResolvedValue({ data: { data: confirmed } })
    const store = useProjectDiagnosisStore()

    // 前置：当前缓存中存在 draft 诊断
    await store.loadLatest('proj-1')
    const result = await store.confirm('insight-1', '与班组教师共同复核')

    expect(apiMocks.confirmInsightApi).toHaveBeenCalledWith('proj-1', 'insight-1', {
      teacherNote: '与班组教师共同复核',
    })
    expect(result.status).toBe('confirmed')
    expect(store.currentInsight?.status).toBe('confirmed')
    expect(store.currentInsight?.teacherNote).toBe('与班组教师共同复核')
    expect(store.lastAction).toBe('confirm')
    expect(store.lastActionSucceeded).toBe(true)
  })

  it('无 teacherNote 时传 null', async () => {
    const confirmed = makeInsight({ status: 'confirmed', teacherNote: null })
    apiMocks.confirmInsightApi.mockResolvedValue({ data: { data: confirmed } })
    apiMocks.getLatestInsightApi.mockResolvedValue({
      data: { data: makeInsight({ status: 'draft' }) },
    })
    const store = useProjectDiagnosisStore()

    await store.loadLatest('proj-1')
    await store.confirm('insight-1', null)

    expect(apiMocks.confirmInsightApi).toHaveBeenCalledWith('proj-1', 'insight-1', {
      teacherNote: null,
    })
  })

  it('空字符串 teacherNote 规范化为 null', async () => {
    const confirmed = makeInsight({ status: 'confirmed', teacherNote: null })
    apiMocks.confirmInsightApi.mockResolvedValue({ data: { data: confirmed } })
    apiMocks.getLatestInsightApi.mockResolvedValue({
      data: { data: makeInsight({ status: 'draft' }) },
    })
    const store = useProjectDiagnosisStore()

    await store.loadLatest('proj-1')
    await store.confirm('insight-1', '   ')

    expect(apiMocks.confirmInsightApi).toHaveBeenCalledWith('proj-1', 'insight-1', {
      teacherNote: null,
    })
  })

  it('无证据诊断确认返回 409，不更新状态', async () => {
    apiMocks.confirmInsightApi.mockRejectedValue(
      makeAxiosError(409, {
        code: 40901,
        message: '无证据诊断不可确认为正式结论，请先导入前测或发布任务',
      }),
    )
    apiMocks.getLatestInsightApi.mockResolvedValue({
      data: { data: makeInsight({ status: 'insufficient_evidence' }) },
    })
    const store = useProjectDiagnosisStore()

    await store.loadLatest('proj-1')
    await expect(store.confirm('insight-1', null)).rejects.toBeDefined()

    expect(store.error).not.toBeNull()
    expect(store.error!.conflict).toBe(true)
    expect(store.currentInsight?.status).toBe('insufficient_evidence')
    expect(store.lastActionSucceeded).toBe(false)
  })

  it('归档项目确认返回 409，不更新状态', async () => {
    apiMocks.confirmInsightApi.mockRejectedValue(
      makeAxiosError(409, { code: 40901, message: '项目已归档，不可确认诊断' }),
    )
    apiMocks.getLatestInsightApi.mockResolvedValue({
      data: { data: makeInsight({ status: 'draft' }) },
    })
    const store = useProjectDiagnosisStore()

    await store.loadLatest('proj-1')
    await expect(store.confirm('insight-1', null)).rejects.toBeDefined()

    expect(store.error!.conflict).toBe(true)
    expect(store.currentInsight?.status).toBe('draft')
    expect(store.lastActionSucceeded).toBe(false)
  })

  it('确认中设置 confirming=true，结束后复位', async () => {
    const confirmed = makeInsight({ status: 'confirmed' })
    apiMocks.confirmInsightApi.mockResolvedValue({ data: { data: confirmed } })
    apiMocks.getLatestInsightApi.mockResolvedValue({
      data: { data: makeInsight({ status: 'draft' }) },
    })
    const store = useProjectDiagnosisStore()

    await store.loadLatest('proj-1')
    expect(store.confirming).toBe(false)
    const promise = store.confirm('insight-1', null)
    expect(store.confirming).toBe(true)
    await promise
    expect(store.confirming).toBe(false)
  })
})

// ============================================================
// 5. store getters
// ============================================================
describe('store getters', () => {
  it('evidenceMissing 在 insufficient_evidence 状态时为 true', async () => {
    apiMocks.getLatestInsightApi.mockResolvedValue({
      data: { data: makeInsight({ status: 'insufficient_evidence' }) },
    })
    const store = useProjectDiagnosisStore()
    await store.loadLatest('proj-1')
    expect(store.evidenceMissing).toBe(true)
  })

  it('evidenceMissing 在 draft 状态时为 false', async () => {
    apiMocks.getLatestInsightApi.mockResolvedValue({
      data: { data: makeInsight({ status: 'draft' }) },
    })
    const store = useProjectDiagnosisStore()
    await store.loadLatest('proj-1')
    expect(store.evidenceMissing).toBe(false)
  })

  it('evidenceMissing 在无诊断时为 false', () => {
    const store = useProjectDiagnosisStore()
    expect(store.evidenceMissing).toBe(false)
  })

  it('canConfirm 在 draft 状态时为 true', async () => {
    apiMocks.getLatestInsightApi.mockResolvedValue({
      data: { data: makeInsight({ status: 'draft' }) },
    })
    const store = useProjectDiagnosisStore()
    await store.loadLatest('proj-1')
    expect(store.canConfirm).toBe(true)
  })

  it('canConfirm 在无诊断时为 false', () => {
    const store = useProjectDiagnosisStore()
    expect(store.canConfirm).toBe(false)
  })

  it('hasSegments 在 segments 非空时为 true', async () => {
    apiMocks.getLatestInsightApi.mockResolvedValue({
      data: {
        data: makeInsight({
          status: 'draft',
          segments: [makeSegment(), makeSegment({ name: '待提升' })],
        }),
      },
    })
    const store = useProjectDiagnosisStore()
    await store.loadLatest('proj-1')
    expect(store.hasSegments).toBe(true)
  })

  it('hasSegments 在 segments 为空时为 false', async () => {
    apiMocks.getLatestInsightApi.mockResolvedValue({
      data: { data: makeInsight({ status: 'draft', segments: [] }) },
    })
    const store = useProjectDiagnosisStore()
    await store.loadLatest('proj-1')
    expect(store.hasSegments).toBe(false)
  })

  it('shouldFallbackToManual 在生成失败后为 true', async () => {
    apiMocks.generateInsightApi.mockRejectedValue(
      makeAxiosError(500, { message: 'AI 服务不可用' }),
    )
    const store = useProjectDiagnosisStore()
    await expect(store.generate('proj-1')).rejects.toBeDefined()
    expect(store.shouldFallbackToManual).toBe(true)
  })

  it('shouldFallbackToManual 在生成成功后复位为 false', async () => {
    apiMocks.generateInsightApi
      .mockRejectedValueOnce(makeAxiosError(500, { message: 'AI 服务不可用' }))
      .mockResolvedValueOnce({ data: { data: makeInsight({ status: 'draft' }) } })
    const store = useProjectDiagnosisStore()
    await expect(store.generate('proj-1')).rejects.toBeDefined()
    expect(store.shouldFallbackToManual).toBe(true)
    await store.generate('proj-1')
    expect(store.shouldFallbackToManual).toBe(false)
  })
})
