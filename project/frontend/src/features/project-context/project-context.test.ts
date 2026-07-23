/**
 * 统一项目上下文 store 与纯函数测试（Task 3）。
 *
 * 覆盖四类：
 * 1. 纯函数：缓存判定、阶段更新、错误映射、阶段查找与当前阶段。
 * 2. store 缓存复用：同项目复用缓存，不重复请求；force 强制刷新。
 * 3. store 网络错误可观察：403/404/网络错误映射到 error 状态。
 * 4. store 阶段操作：complete/reopen 用返回值就地更新缓存。
 *
 * 使用 vi.mock 隔离 api 模块，避免真实网络请求；不挂载 Vue 组件。
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { AxiosError } from 'axios'

// ── mock api 模块（vi.hoisted 确保 vi.mock 工厂可访问）─────────
const apiMocks = vi.hoisted(() => ({
  getProjectContextApi: vi.fn(),
  getProjectTimelineApi: vi.fn(),
  completePhaseApi: vi.fn(),
  reopenPhaseApi: vi.fn(),
}))
vi.mock('./api', () => apiMocks)

import {
  applyPhaseUpdate,
  currentActivePhase,
  findPhase,
  mapContextError,
  shouldReuseCache,
  useProjectContextStore,
} from './store'
import type {
  ProjectWorkspaceContext,
  ProjectWorkspacePhase,
} from './types'

// ── 测试夹具 ────────────────────────────────────────────────────
function makePhase(
  phase: ProjectWorkspacePhase['phase'],
  status: ProjectWorkspacePhase['status'] = 'not_started',
  overrides: Partial<ProjectWorkspacePhase> = {},
): ProjectWorkspacePhase {
  return {
    phase,
    status,
    completedAt: null,
    reopenedAt: null,
    reopenedBy: null,
    reopenReason: null,
    ...overrides,
  }
}

function makeContext(
  overrides: Partial<ProjectWorkspaceContext> = {},
): ProjectWorkspaceContext {
  return {
    project: {
      id: 'proj-1',
      title: '测试项目',
      description: null,
      status: 'active',
      creatorId: 'user-1',
      schoolId: 'school-1',
      grade: '七年级',
      startDate: null,
      endDate: null,
      projectType: null,
      coreSubjectId: null,
      reviewStatus: null,
      classIds: [],
      subjectIds: [],
      createdAt: null,
    },
    phases: [
      makePhase('diagnosis', 'completed', { completedAt: '2026-07-01T00:00:00Z' }),
      makePhase('design', 'completed', { completedAt: '2026-07-02T00:00:00Z' }),
      makePhase('preparation', 'in_progress'),
      makePhase('implementation', 'not_started'),
      makePhase('evaluation', 'not_started'),
      makePhase('improvement', 'not_started'),
      makePhase('closure', 'not_started'),
    ],
    permissions: {
      canView: true,
      canManage: true,
      canReopen: false,
      isArchived: false,
    },
    blockers: [],
    warnings: [],
    counts: {
      tasks: 0,
      publishedTasks: 0,
      submissions: 0,
      evaluations: 0,
      unpublishedEvaluations: 0,
      students: 0,
      aiJobs: 0,
      pendingAiReviews: 0,
    },
    actions: [],
    nextAction: null,
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
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-07-24T12:00:00Z').getTime())
})

afterEach(() => {
  vi.useRealTimers()
})

// ============================================================
// 1. 纯函数
// ============================================================
describe('shouldReuseCache 缓存判定', () => {
  it('项目 ID 变化时返回 false', () => {
    expect(shouldReuseCache('proj-1', 'proj-2', Date.now())).toBe(false)
  })

  it('currentProjectId 为 null 时返回 false', () => {
    expect(shouldReuseCache(null, 'proj-1', Date.now())).toBe(false)
  })

  it('同项目且未过期时返回 true', () => {
    const now = Date.now()
    expect(shouldReuseCache('proj-1', 'proj-1', now)).toBe(true)
  })

  it('同项目但超过 TTL 返回 false', () => {
    const now = Date.now()
    const stale = now - 31_000 // 默认 TTL 30s
    expect(shouldReuseCache('proj-1', 'proj-1', stale)).toBe(false)
  })

  it('同项目且刚好在 TTL 边界内返回 true', () => {
    const now = Date.now()
    const edge = now - 29_000
    expect(shouldReuseCache('proj-1', 'proj-1', edge)).toBe(true)
  })

  it('lastLoadedAt 为 0 时返回 false', () => {
    expect(shouldReuseCache('proj-1', 'proj-1', 0)).toBe(false)
  })

  it('自定义 maxAgeMs 生效', () => {
    const now = Date.now()
    const stale = now - 5_000
    expect(shouldReuseCache('proj-1', 'proj-1', stale, 10_000)).toBe(true)
    expect(shouldReuseCache('proj-1', 'proj-1', stale, 3_000)).toBe(false)
  })
})

describe('applyPhaseUpdate 阶段更新', () => {
  it('用返回值替换对应阶段，保持其他阶段不变', () => {
    const phases = [
      makePhase('diagnosis', 'completed'),
      makePhase('design', 'in_progress'),
      makePhase('preparation', 'not_started'),
    ]
    const updated = makePhase('design', 'completed', { completedAt: '2026-07-03T00:00:00Z' })
    const result = applyPhaseUpdate(phases, updated)
    expect(result).toHaveLength(3)
    expect(result[1].status).toBe('completed')
    expect(result[1].completedAt).toBe('2026-07-03T00:00:00Z')
    // 其他阶段保持不变
    expect(result[0]).toEqual(phases[0])
    expect(result[2]).toEqual(phases[2])
  })

  it('返回新数组，不修改原数组', () => {
    const phases = [makePhase('diagnosis', 'in_progress')]
    const updated = makePhase('diagnosis', 'completed')
    const result = applyPhaseUpdate(phases, updated)
    expect(result).not.toBe(phases)
    expect(phases[0].status).toBe('in_progress')
  })

  it('未匹配到阶段时返回原样长度的新数组', () => {
    const phases = [makePhase('diagnosis', 'in_progress')]
    const updated = makePhase('closure', 'completed')
    const result = applyPhaseUpdate(phases, updated)
    expect(result).toHaveLength(1)
    expect(result[0].status).toBe('in_progress')
  })
})

describe('findPhase 阶段查找', () => {
  it('找到对应阶段返回对象', () => {
    const phases = [makePhase('diagnosis', 'completed'), makePhase('design', 'in_progress')]
    const found = findPhase(phases, 'design')
    expect(found).not.toBeNull()
    expect(found!.phase).toBe('design')
    expect(found!.status).toBe('in_progress')
  })

  it('未找到返回 null', () => {
    const phases = [makePhase('diagnosis', 'completed')]
    expect(findPhase(phases, 'closure')).toBeNull()
  })

  it('空数组返回 null', () => {
    expect(findPhase([], 'diagnosis')).toBeNull()
  })
})

describe('currentActivePhase 当前阶段', () => {
  it('返回第一个未完成的阶段', () => {
    const phases = [
      makePhase('diagnosis', 'completed'),
      makePhase('design', 'completed'),
      makePhase('preparation', 'in_progress'),
      makePhase('implementation', 'not_started'),
    ]
    const active = currentActivePhase(phases)
    expect(active).not.toBeNull()
    expect(active!.phase).toBe('preparation')
  })

  it('全部完成返回 null', () => {
    const phases = [
      makePhase('diagnosis', 'completed'),
      makePhase('design', 'completed'),
      makePhase('preparation', 'completed'),
    ]
    expect(currentActivePhase(phases)).toBeNull()
  })

  it('blocked 阶段也视为未完成', () => {
    const phases = [makePhase('diagnosis', 'blocked')]
    expect(currentActivePhase(phases)!.phase).toBe('diagnosis')
  })
})

describe('mapContextError 错误映射', () => {
  it('403 映射为权限错误', () => {
    const err = makeAxiosError(403, { code: 40301, message: '无权访问该项目' })
    const mapped = mapContextError(err)
    expect(mapped.status).toBe(403)
    expect(mapped.forbidden).toBe(true)
    expect(mapped.notFound).toBe(false)
    expect(mapped.code).toBe(40301)
    expect(mapped.message).toBe('无权访问该项目')
  })

  it('404 映射为未找到', () => {
    const err = makeAxiosError(404, { message: '项目不存在' })
    const mapped = mapContextError(err)
    expect(mapped.status).toBe(404)
    expect(mapped.notFound).toBe(true)
    expect(mapped.forbidden).toBe(false)
  })

  it('无 response 的网络错误映射为 status=0', () => {
    const err = new Error('Network Error') as unknown
    const mapped = mapContextError(err)
    expect(mapped.status).toBe(0)
    expect(mapped.message).toBe('网络错误')
    expect(mapped.forbidden).toBe(false)
    expect(mapped.notFound).toBe(false)
    expect(mapped.code).toBeNull()
  })

  it('500 通用错误不标记权限/未找到', () => {
    const err = makeAxiosError(500, { message: '服务器内部错误' })
    const mapped = mapContextError(err)
    expect(mapped.status).toBe(500)
    expect(mapped.forbidden).toBe(false)
    expect(mapped.notFound).toBe(false)
  })

  it('有 code 但无 message 时回退到默认消息', () => {
    const err = makeAxiosError(409, { code: 40901 })
    const mapped = mapContextError(err)
    expect(mapped.code).toBe(40901)
    expect(mapped.message).toBe('请求失败')
  })
})

// ============================================================
// 2. store 缓存复用
// ============================================================
describe('store 缓存复用', () => {
  it('首次加载调用 API 并缓存上下文', async () => {
    const ctx = makeContext()
    apiMocks.getProjectContextApi.mockResolvedValue({ data: { data: ctx } })
    const store = useProjectContextStore()

    await store.loadContext('proj-1')

    expect(apiMocks.getProjectContextApi).toHaveBeenCalledTimes(1)
    expect(apiMocks.getProjectContextApi).toHaveBeenCalledWith('proj-1')
    expect(store.currentContext).toEqual(ctx)
    expect(store.currentProjectId).toBe('proj-1')
    expect(store.hasContext).toBe(true)
    expect(store.loading).toBe(false)
    expect(store.error).toBeNull()
  })

  it('同项目在 TTL 内复用缓存，不重复请求', async () => {
    const ctx = makeContext()
    apiMocks.getProjectContextApi.mockResolvedValue({ data: { data: ctx } })
    const store = useProjectContextStore()

    await store.loadContext('proj-1')
    await store.loadContext('proj-1')

    expect(apiMocks.getProjectContextApi).toHaveBeenCalledTimes(1)
  })

  it('项目 ID 变化时重新请求', async () => {
    const ctx1 = makeContext()
    const ctx2 = makeContext({ project: { ...ctx1.project, id: 'proj-2' } })
    apiMocks.getProjectContextApi
      .mockResolvedValueOnce({ data: { data: ctx1 } })
      .mockResolvedValueOnce({ data: { data: ctx2 } })
    const store = useProjectContextStore()

    await store.loadContext('proj-1')
    await store.loadContext('proj-2')

    expect(apiMocks.getProjectContextApi).toHaveBeenCalledTimes(2)
    expect(store.currentProjectId).toBe('proj-2')
    expect(store.currentContext?.project.id).toBe('proj-2')
  })

  it('force=true 强制刷新即使同项目', async () => {
    const ctx = makeContext()
    apiMocks.getProjectContextApi.mockResolvedValue({ data: { data: ctx } })
    const store = useProjectContextStore()

    await store.loadContext('proj-1')
    await store.loadContext('proj-1', true)

    expect(apiMocks.getProjectContextApi).toHaveBeenCalledTimes(2)
  })

  it('refreshContext 强制刷新当前项目', async () => {
    const ctx = makeContext()
    apiMocks.getProjectContextApi.mockResolvedValue({ data: { data: ctx } })
    const store = useProjectContextStore()

    await store.loadContext('proj-1')
    await store.refreshContext()

    expect(apiMocks.getProjectContextApi).toHaveBeenCalledTimes(2)
  })

  it('refreshContext 无当前项目时不请求', async () => {
    const store = useProjectContextStore()
    await store.refreshContext()
    expect(apiMocks.getProjectContextApi).not.toHaveBeenCalled()
  })

  it('TTL 过期后重新请求', async () => {
    const ctx = makeContext()
    apiMocks.getProjectContextApi.mockResolvedValue({ data: { data: ctx } })
    const store = useProjectContextStore()

    await store.loadContext('proj-1')
    expect(apiMocks.getProjectContextApi).toHaveBeenCalledTimes(1)

    // 推进时间超过 TTL（30s）
    vi.advanceTimersByTime(31_000)
    await store.loadContext('proj-1')
    expect(apiMocks.getProjectContextApi).toHaveBeenCalledTimes(2)
  })

  it('clear 清除缓存', async () => {
    const ctx = makeContext()
    apiMocks.getProjectContextApi.mockResolvedValue({ data: { data: ctx } })
    const store = useProjectContextStore()

    await store.loadContext('proj-1')
    store.clear()

    expect(store.hasContext).toBe(false)
    expect(store.currentProjectId).toBeNull()
    expect(store.currentContext).toBeNull()
    expect(store.lastLoadedAt).toBe(0)
  })
})

// ============================================================
// 3. store 网络错误可观察
// ============================================================
describe('store 网络错误可观察', () => {
  it('403 权限错误设置 error 且 forbidden=true', async () => {
    apiMocks.getProjectContextApi.mockRejectedValue(
      makeAxiosError(403, { code: 40301, message: '无权访问该项目' }),
    )
    const store = useProjectContextStore()

    await expect(store.loadContext('proj-1')).rejects.toBeDefined()
    expect(store.error).not.toBeNull()
    expect(store.error!.forbidden).toBe(true)
    expect(store.error!.status).toBe(403)
    expect(store.loading).toBe(false)
    expect(store.hasContext).toBe(false)
  })

  it('404 未找到错误设置 error 且 notFound=true', async () => {
    apiMocks.getProjectContextApi.mockRejectedValue(
      makeAxiosError(404, { message: '项目不存在' }),
    )
    const store = useProjectContextStore()

    await expect(store.loadContext('proj-1')).rejects.toBeDefined()
    expect(store.error!.notFound).toBe(true)
    expect(store.error!.status).toBe(404)
  })

  it('网络错误（无响应）设置 error status=0', async () => {
    apiMocks.getProjectContextApi.mockRejectedValue(new Error('Network Error'))
    const store = useProjectContextStore()

    await expect(store.loadContext('proj-1')).rejects.toBeDefined()
    expect(store.error!.status).toBe(0)
    expect(store.error!.message).toBe('网络错误')
  })

  it('错误后再次加载成功时清除 error', async () => {
    const ctx = makeContext()
    apiMocks.getProjectContextApi
      .mockRejectedValueOnce(makeAxiosError(403, { message: '无权访问' }))
      .mockResolvedValueOnce({ data: { data: ctx } })
    const store = useProjectContextStore()

    await expect(store.loadContext('proj-1', true)).rejects.toBeDefined()
    expect(store.error).not.toBeNull()

    await store.loadContext('proj-1', true)
    expect(store.error).toBeNull()
    expect(store.hasContext).toBe(true)
  })
})

// ============================================================
// 4. store 阶段操作
// ============================================================
describe('store 阶段操作', () => {
  it('completePhase 用返回值就地更新缓存', async () => {
    const ctx = makeContext()
    apiMocks.getProjectContextApi.mockResolvedValue({ data: { data: ctx } })
    const updatedPhase = makePhase('preparation', 'completed', {
      completedAt: '2026-07-04T00:00:00Z',
    })
    apiMocks.completePhaseApi.mockResolvedValue({ data: { data: updatedPhase } })
    const store = useProjectContextStore()

    await store.loadContext('proj-1')
    // 确认初始状态
    expect(store.currentContext!.phases[2].status).toBe('in_progress')

    await store.completePhase('preparation')

    expect(apiMocks.completePhaseApi).toHaveBeenCalledWith('proj-1', 'preparation')
    expect(store.currentContext!.phases[2].status).toBe('completed')
    expect(store.currentContext!.phases[2].completedAt).toBe('2026-07-04T00:00:00Z')
    // 其他阶段不变
    expect(store.currentContext!.phases[0].status).toBe('completed')
    expect(store.currentContext!.phases[3].status).toBe('not_started')
    // 不重新拉取整个上下文
    expect(apiMocks.getProjectContextApi).toHaveBeenCalledTimes(1)
  })

  it('reopenPhase 用返回值就地更新缓存', async () => {
    const ctx = makeContext()
    apiMocks.getProjectContextApi.mockResolvedValue({ data: { data: ctx } })
    const reopenedPhase = makePhase('diagnosis', 'in_progress', {
      reopenedAt: '2026-07-05T00:00:00Z',
      reopenedBy: 'user-1',
      reopenReason: '需补充学情数据',
    })
    apiMocks.reopenPhaseApi.mockResolvedValue({ data: { data: reopenedPhase } })
    const store = useProjectContextStore()

    await store.loadContext('proj-1')
    // 确认初始状态
    expect(store.currentContext!.phases[0].status).toBe('completed')

    await store.reopenPhase('diagnosis', '需补充学情数据')

    expect(apiMocks.reopenPhaseApi).toHaveBeenCalledWith('proj-1', 'diagnosis', '需补充学情数据')
    expect(store.currentContext!.phases[0].status).toBe('in_progress')
    expect(store.currentContext!.phases[0].reopenedBy).toBe('user-1')
    expect(store.currentContext!.phases[0].reopenReason).toBe('需补充学情数据')
    // 不重新拉取整个上下文
    expect(apiMocks.getProjectContextApi).toHaveBeenCalledTimes(1)
  })

  it('completePhase 失败时设置 error 且不更新缓存', async () => {
    const ctx = makeContext()
    apiMocks.getProjectContextApi.mockResolvedValue({ data: { data: ctx } })
    apiMocks.completePhaseApi.mockRejectedValue(
      makeAxiosError(409, { code: 40901, message: '阶段已完成，无需重复标记' }),
    )
    const store = useProjectContextStore()

    await store.loadContext('proj-1')
    const originalStatus = store.currentContext!.phases[2].status

    await expect(store.completePhase('preparation')).rejects.toBeDefined()
    expect(store.error).not.toBeNull()
    expect(store.error!.status).toBe(409)
    // 缓存未被修改
    expect(store.currentContext!.phases[2].status).toBe(originalStatus)
  })

  it('无当前项目或上下文时阶段操作不请求', async () => {
    const store = useProjectContextStore()
    await store.completePhase('preparation')
    await store.reopenPhase('diagnosis')
    expect(apiMocks.completePhaseApi).not.toHaveBeenCalled()
    expect(apiMocks.reopenPhaseApi).not.toHaveBeenCalled()
  })
})

// ============================================================
// 5. store getters
// ============================================================
describe('store getters', () => {
  it('activePhase 返回第一个未完成阶段', async () => {
    const ctx = makeContext()
    apiMocks.getProjectContextApi.mockResolvedValue({ data: { data: ctx } })
    const store = useProjectContextStore()

    await store.loadContext('proj-1')
    expect(store.activePhase?.phase).toBe('preparation')
  })

  it('isArchived 反映归档状态', async () => {
    const ctx = makeContext({
      permissions: { canView: true, canManage: false, canReopen: true, isArchived: true },
    })
    apiMocks.getProjectContextApi.mockResolvedValue({ data: { data: ctx } })
    const store = useProjectContextStore()

    await store.loadContext('proj-1')
    expect(store.isArchived).toBe(true)
    expect(store.canManage).toBe(false)
  })

  it('hasBlockers 反映阻断项', async () => {
    const ctx = makeContext({
      blockers: [{ code: 'missing_core_subject', field: 'contributions', message: '缺核心学科', phase: 'design' }],
    })
    apiMocks.getProjectContextApi.mockResolvedValue({ data: { data: ctx } })
    const store = useProjectContextStore()

    await store.loadContext('proj-1')
    expect(store.hasBlockers).toBe(true)
  })
})

// ============================================================
// 6. timeline 加载
// ============================================================
describe('store timeline 加载', () => {
  it('loadTimeline 拉取并存储时间线事件', async () => {
    const events = [
      {
        type: 'project_created' as const,
        label: '项目创建',
        timestamp: '2026-07-01T00:00:00Z',
        phase: null,
        actor: 'user-1',
      },
      {
        type: 'phase_completed' as const,
        label: '阶段完成',
        timestamp: '2026-07-02T00:00:00Z',
        phase: 'diagnosis' as const,
        actor: 'user-1',
      },
    ]
    apiMocks.getProjectTimelineApi.mockResolvedValue({ data: { data: events } })
    const store = useProjectContextStore()

    await store.loadTimeline('proj-1')

    expect(apiMocks.getProjectTimelineApi).toHaveBeenCalledWith('proj-1')
    expect(store.timeline).toEqual(events)
  })

  it('loadTimeline 失败时设置 error', async () => {
    apiMocks.getProjectTimelineApi.mockRejectedValue(
      makeAxiosError(403, { message: '无权访问' }),
    )
    const store = useProjectContextStore()

    await expect(store.loadTimeline('proj-1')).rejects.toBeDefined()
    expect(store.error).not.toBeNull()
    expect(store.error!.forbidden).toBe(true)
  })
})
