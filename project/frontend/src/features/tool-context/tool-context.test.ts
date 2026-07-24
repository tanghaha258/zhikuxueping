/**
 * 工具上下文链接测试（Task 8）。
 *
 * 覆盖 spec 第 7 节与计划 Task 8 验收项：
 * 1. ContextPicker 数据合同：independent 模式不得伪造项目 ID；
 *    project 模式必须 projectId + phase；phase 必须为合法枚举。
 * 2. placementForArtifact：资产类型到默认 placement 的推导。
 * 3. linkContextApi：independent 不发请求；project 调用 POST /resources/context-links
 *    并发送 snake_case payload；placementOverride 可覆盖默认。
 * 4. unlinkContextApi：DELETE /resources/context-links/{id}。
 * 5. listContextLinksByProjectApi / listContextLinksByArtifactApi：GET 查询。
 * 6. mapToolContextError：400/403/404/409/网络错误映射。
 *
 * 使用 vi.mock 隔离 @/api http 客户端，避免真实网络请求；不挂载 Vue 组件。
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { AxiosError } from 'axios'

// ── mock @/api http 客户端（vi.hoisted 确保 vi.mock 工厂可访问）─────
const httpMocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  delete: vi.fn(),
}))
vi.mock('@/api', () => ({ default: httpMocks }))

import {
  linkContextApi,
  listContextLinksByArtifactApi,
  listContextLinksByProjectApi,
  mapToolContextError,
  unlinkContextApi,
} from './api'
import {
  isProjectContext,
  placementForArtifact,
  validateToolContext,
} from './types'
import type { ArtifactType, ContextLink, ToolContext } from './types'

// ── 测试夹具 ────────────────────────────────────────────────────
function makeLink(overrides: Partial<ContextLink> = {}): ContextLink {
  return {
    id: 'link-1',
    artifactType: 'resource',
    artifactId: 'asset-1',
    projectId: 'proj-1',
    phase: 'preparation',
    placement: 'resource',
    taskId: null,
    goalId: null,
    contextSnapshot: null,
    createdBy: 'user-1',
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

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  vi.restoreAllMocks()
})

// ============================================================
// 1. isProjectContext 类型守卫
// ============================================================
describe('isProjectContext 类型守卫', () => {
  it('independent 模式返回 false', () => {
    const ctx: ToolContext = { mode: 'independent' }
    expect(isProjectContext(ctx)).toBe(false)
  })

  it('project 模式返回 true', () => {
    const ctx: ToolContext = {
      mode: 'project',
      projectId: 'proj-1',
      phase: 'preparation',
    }
    expect(isProjectContext(ctx)).toBe(true)
  })
})

// ============================================================
// 2. validateToolContext 合同校验
// ============================================================
describe('validateToolContext 合同校验', () => {
  it('independent 模式合法', () => {
    const result = validateToolContext({ mode: 'independent' })
    expect(result.valid).toBe(true)
    expect(result.error).toBeNull()
  })

  it('independent 模式不得伪造 projectId（运行时脏数据被拒绝）', () => {
    // 模拟运行时脏数据：独立模式携带 projectId 必须被拒绝
    const dirty = { mode: 'independent', projectId: 'proj-1' } as unknown as ToolContext
    const result = validateToolContext(dirty)
    expect(result.valid).toBe(false)
    expect(result.error).toBeTruthy()
  })

  it('project 模式合法', () => {
    const result = validateToolContext({
      mode: 'project',
      projectId: 'proj-1',
      phase: 'preparation',
    })
    expect(result.valid).toBe(true)
    expect(result.error).toBeNull()
  })

  it('project 模式缺 projectId 无效', () => {
    const ctx = {
      mode: 'project',
      phase: 'preparation',
    } as unknown as ToolContext
    expect(validateToolContext(ctx).valid).toBe(false)
  })

  it('project 模式空 projectId 无效', () => {
    const ctx = {
      mode: 'project',
      projectId: '',
      phase: 'preparation',
    } as unknown as ToolContext
    expect(validateToolContext(ctx).valid).toBe(false)
  })

  it('project 模式缺 phase 无效', () => {
    const ctx = {
      mode: 'project',
      projectId: 'proj-1',
    } as unknown as ToolContext
    expect(validateToolContext(ctx).valid).toBe(false)
  })

  it('project 模式空 phase 无效', () => {
    const ctx = {
      mode: 'project',
      projectId: 'proj-1',
      phase: '',
    } as unknown as ToolContext
    expect(validateToolContext(ctx).valid).toBe(false)
  })

  it('project 模式非法 phase 无效', () => {
    const ctx = {
      mode: 'project',
      projectId: 'proj-1',
      phase: 'not_a_phase',
    } as unknown as ToolContext
    expect(validateToolContext(ctx).valid).toBe(false)
  })

  it('project 模式可选 taskId/goalId 合法', () => {
    const result = validateToolContext({
      mode: 'project',
      projectId: 'proj-1',
      phase: 'implementation',
      taskId: 'task-1',
      goalId: 'goal-1',
    })
    expect(result.valid).toBe(true)
  })

  it('project 模式所有合法 phase 通过', () => {
    const phases = [
      'diagnosis',
      'design',
      'preparation',
      'implementation',
      'evaluation',
      'improvement',
      'closure',
    ] as const
    for (const phase of phases) {
      expect(
        validateToolContext({ mode: 'project', projectId: 'p', phase }).valid,
      ).toBe(true)
    }
  })
})

// ============================================================
// 3. placementForArtifact 资产位置推导
// ============================================================
describe('placementForArtifact 资产位置推导', () => {
  const cases: Array<[ArtifactType, string]> = [
    ['lesson_plan', 'lesson_plan'],
    ['resource', 'resource'],
    ['ai_output', 'ai_draft'],
    ['paper', 'pre_test'],
    ['question_bank', 'task_sheet'],
  ]
  for (const [type, placement] of cases) {
    it(`${type} → ${placement}`, () => {
      expect(placementForArtifact(type)).toBe(placement)
    })
  }
})

// ============================================================
// 4. linkContextApi 关联资产
// ============================================================
describe('linkContextApi 关联资产', () => {
  it('independent 模式不调用 API，返回 null', async () => {
    const ctx: ToolContext = { mode: 'independent' }
    const result = await linkContextApi('resource', 'asset-1', ctx)
    expect(result).toBeNull()
    expect(httpMocks.post).not.toHaveBeenCalled()
  })

  it('project 模式调用 POST /resources/context-links，payload 含推导 placement', async () => {
    const link = makeLink()
    httpMocks.post.mockResolvedValue({ data: { data: link } })
    const ctx: ToolContext = {
      mode: 'project',
      projectId: 'proj-1',
      phase: 'preparation',
    }

    const result = await linkContextApi('resource', 'asset-1', ctx)

    expect(httpMocks.post).toHaveBeenCalledTimes(1)
    expect(httpMocks.post).toHaveBeenCalledWith('/resources/context-links', {
      artifact_type: 'resource',
      artifact_id: 'asset-1',
      project_id: 'proj-1',
      placement: 'resource',
      phase: 'preparation',
      task_id: null,
      goal_id: null,
    })
    expect(result).toEqual(link)
  })

  it('project 模式 placementOverride 覆盖默认 placement', async () => {
    const link = makeLink({ placement: 'pre_test' })
    httpMocks.post.mockResolvedValue({ data: { data: link } })
    const ctx: ToolContext = {
      mode: 'project',
      projectId: 'proj-1',
      phase: 'preparation',
    }

    await linkContextApi('resource', 'asset-1', ctx, 'pre_test')

    expect(httpMocks.post).toHaveBeenCalledWith('/resources/context-links', {
      artifact_type: 'resource',
      artifact_id: 'asset-1',
      project_id: 'proj-1',
      placement: 'pre_test',
      phase: 'preparation',
      task_id: null,
      goal_id: null,
    })
  })

  it('project 模式 payload 含 taskId/goalId', async () => {
    const link = makeLink({ taskId: 't-1', goalId: 'g-1' })
    httpMocks.post.mockResolvedValue({ data: { data: link } })
    const ctx: ToolContext = {
      mode: 'project',
      projectId: 'proj-1',
      phase: 'implementation',
      taskId: 't-1',
      goalId: 'g-1',
    }

    await linkContextApi('lesson_plan', 'plan-1', ctx)

    expect(httpMocks.post).toHaveBeenCalledWith('/resources/context-links', {
      artifact_type: 'lesson_plan',
      artifact_id: 'plan-1',
      project_id: 'proj-1',
      placement: 'lesson_plan',
      phase: 'implementation',
      task_id: 't-1',
      goal_id: 'g-1',
    })
  })

  it('lesson_plan 资产默认 placement 为 lesson_plan', async () => {
    httpMocks.post.mockResolvedValue({ data: { data: makeLink() } })
    const ctx: ToolContext = {
      mode: 'project',
      projectId: 'proj-1',
      phase: 'preparation',
    }

    await linkContextApi('lesson_plan', 'plan-1', ctx)

    const body = httpMocks.post.mock.calls[0][1] as Record<string, unknown>
    expect(body.placement).toBe('lesson_plan')
  })
})

// ============================================================
// 5. unlinkContextApi 取消关联
// ============================================================
describe('unlinkContextApi 取消关联', () => {
  it('调用 DELETE /resources/context-links/{id}', async () => {
    // 拦截器已将响应 key 转为 camelCase
    const unlinkResult = {
      artifactType: 'resource',
      artifactId: 'asset-1',
      preserved: true,
    }
    httpMocks.delete.mockResolvedValue({ data: { data: unlinkResult } })

    const result = await unlinkContextApi('link-1')

    expect(httpMocks.delete).toHaveBeenCalledTimes(1)
    expect(httpMocks.delete).toHaveBeenCalledWith('/resources/context-links/link-1')
    expect(result).toEqual({
      artifactType: 'resource',
      artifactId: 'asset-1',
      preserved: true,
    })
  })
})

// ============================================================
// 6. listContextLinksByProjectApi 按项目列出
// ============================================================
describe('listContextLinksByProjectApi 按项目列出', () => {
  it('调用 GET /resources/context-links?project_id=...', async () => {
    const links = [makeLink()]
    httpMocks.get.mockResolvedValue({ data: { data: links } })

    const result = await listContextLinksByProjectApi('proj-1')

    expect(httpMocks.get).toHaveBeenCalledTimes(1)
    expect(httpMocks.get).toHaveBeenCalledWith('/resources/context-links', {
      params: { project_id: 'proj-1', artifact_type: undefined },
    })
    expect(result).toEqual(links)
  })

  it('带 artifactType 时附加 artifact_type 参数', async () => {
    httpMocks.get.mockResolvedValue({ data: { data: [] } })

    await listContextLinksByProjectApi('proj-1', 'lesson_plan')

    expect(httpMocks.get).toHaveBeenCalledWith('/resources/context-links', {
      params: { project_id: 'proj-1', artifact_type: 'lesson_plan' },
    })
  })

  it('跨校 403 错误向上抛出', async () => {
    httpMocks.get.mockRejectedValue(makeAxiosError(403, { message: '无权访问' }))

    await expect(listContextLinksByProjectApi('proj-1')).rejects.toBeDefined()
  })
})

// ============================================================
// 7. listContextLinksByArtifactApi 按资产列出
// ============================================================
describe('listContextLinksByArtifactApi 按资产列出', () => {
  it('调用 GET /resources/context-links?artifact_type=...&artifact_id=...', async () => {
    const links = [makeLink()]
    httpMocks.get.mockResolvedValue({ data: { data: links } })

    const result = await listContextLinksByArtifactApi('resource', 'asset-1')

    expect(httpMocks.get).toHaveBeenCalledTimes(1)
    expect(httpMocks.get).toHaveBeenCalledWith('/resources/context-links', {
      params: { artifact_type: 'resource', artifact_id: 'asset-1' },
    })
    expect(result).toEqual(links)
  })
})

// ============================================================
// 8. mapToolContextError 错误映射
// ============================================================
describe('mapToolContextError 错误映射', () => {
  it('400 映射为 status=400', () => {
    const err = makeAxiosError(400, { message: '参数错误' })
    const mapped = mapToolContextError(err)
    expect(mapped.status).toBe(400)
    expect(mapped.forbidden).toBe(false)
    expect(mapped.notFound).toBe(false)
    expect(mapped.message).toBe('参数错误')
  })

  it('403 映射为 forbidden=true（跨校关联拒绝）', () => {
    const err = makeAxiosError(403, { code: 40301, message: '无权访问该项目' })
    const mapped = mapToolContextError(err)
    expect(mapped.status).toBe(403)
    expect(mapped.forbidden).toBe(true)
    expect(mapped.notFound).toBe(false)
    expect(mapped.code).toBe(40301)
  })

  it('404 映射为 notFound=true', () => {
    const err = makeAxiosError(404, { message: '引用不存在' })
    const mapped = mapToolContextError(err)
    expect(mapped.status).toBe(404)
    expect(mapped.notFound).toBe(true)
    expect(mapped.forbidden).toBe(false)
  })

  it('409 映射为冲突（重复挂载）', () => {
    const err = makeAxiosError(409, { code: 40901, message: '已存在引用' })
    const mapped = mapToolContextError(err)
    expect(mapped.status).toBe(409)
    expect(mapped.code).toBe(40901)
    expect(mapped.forbidden).toBe(false)
    expect(mapped.notFound).toBe(false)
  })

  it('网络错误（无响应）映射为 status=0', () => {
    const err = new Error('Network Error') as unknown
    const mapped = mapToolContextError(err)
    expect(mapped.status).toBe(0)
    expect(mapped.message).toBe('网络错误')
    expect(mapped.forbidden).toBe(false)
    expect(mapped.notFound).toBe(false)
    expect(mapped.code).toBeNull()
  })

  it('有 code 但无 message 时回退到默认消息', () => {
    const err = makeAxiosError(409, { code: 40901 })
    const mapped = mapToolContextError(err)
    expect(mapped.code).toBe(40901)
    expect(mapped.message).toBe('请求失败')
  })
})
