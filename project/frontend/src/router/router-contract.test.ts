/**
 * 路由合同测试（Task 4 / 计划 Step 1）。
 *
 * 守护以下不变量：
 * 1. 项目七阶段页面统一挂在项目工作区下，路由名与阶段一一对应。
 * 2. 旧版 /detail 入口安全重定向到项目总览，不再渲染第二套任务/资源/评价写入口。
 * 3. 项目阶段不出现在教师一级路由（一级侧栏只放工作台与能力中心）。
 *
 * 通过 vi.mock 隔离用户态，使认证守卫放行教师；不发起真实网络请求。
 * 说明：router.resolve 不跟随 redirect，故重定向断言一律走 router.push 实际导航。
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'

// ── mock 用户态：认证守卫放行教师 ───────────────────────────────
vi.mock('@/stores/user', () => ({
  useUserStore: () => ({
    isLoggedIn: true,
    userRole: 'teacher',
    homeRoute: '/teacher/dashboard',
    displayName: '测试教师',
    userInfo: { id: 't1', schoolId: 's1' },
    logout: vi.fn(),
  }),
}))

import router from './index'

beforeEach(async () => {
  // 每个用例前回到中立位置，避免上一个用例的导航残留影响断言
  await router.push('/teacher/dashboard').catch(() => {})
  await router.isReady()
})

describe('项目工作区阶段路由合同', () => {
  it('诊断阶段路由解析为 ProjectDiagnosis', () => {
    expect(router.resolve('/teacher/projects/p1/diagnosis').name).toBe('ProjectDiagnosis')
  })

  it('备课阶段路由解析为 ProjectPreparation', () => {
    expect(router.resolve('/teacher/projects/p1/preparation').name).toBe('ProjectPreparation')
  })

  it('学习证据阶段路由解析为 ProjectEvidence', () => {
    expect(router.resolve('/teacher/projects/p1/evidence').name).toBe('ProjectEvidence')
  })

  it('评价阶段路由解析为 ProjectEvaluation', () => {
    expect(router.resolve('/teacher/projects/p1/evaluation').name).toBe('ProjectEvaluation')
  })

  it('总览路由解析为 ProjectOverview', () => {
    expect(router.resolve('/teacher/projects/p1/overview').name).toBe('ProjectOverview')
  })

  it('裸项目路径导航后回退到 ProjectOverview', async () => {
    await router.push('/teacher/projects/p1')
    expect(router.currentRoute.value.name).toBe('ProjectOverview')
    expect(router.currentRoute.value.params.id).toBe('p1')
  })
})

describe('旧版项目详情入口安全重定向', () => {
  it('实际导航：push /detail 后当前路由为 ProjectOverview 并保留参数', async () => {
    await router.push('/teacher/projects/p1/detail')
    expect(router.currentRoute.value.name).toBe('ProjectOverview')
    expect(router.currentRoute.value.params.id).toBe('p1')
  })

  it('/detail 路径不再解析为 ProjectDetail 命名路由', () => {
    // 旧组件路由已移除：resolve 不再命中名为 ProjectDetail 的记录
    expect(router.resolve('/teacher/projects/p1/detail').name).not.toBe('ProjectDetail')
  })

  it('不再存在可命名的 ProjectDetail 路由', () => {
    expect(() => router.resolve({ name: 'ProjectDetail', params: { id: 'p1' } })).toThrow()
  })
})

describe('项目阶段不出现在教师一级路由', () => {
  it('诊断/备课/证据/评价不是 /teacher 下的顶层路由', () => {
    // 这些阶段必须挂在工作区父路由 /teacher/projects/:id 下，而非 /teacher 一级
    expect(router.resolve('/teacher/diagnosis').name).not.toBe('ProjectDiagnosis')
    expect(router.resolve('/teacher/preparation').name).not.toBe('ProjectPreparation')
    expect(router.resolve('/teacher/evidence').name).not.toBe('ProjectEvidence')
    expect(router.resolve('/teacher/evaluation').name).not.toBe('ProjectEvaluation')
  })

  it('工作台与能力中心仍可解析', () => {
    expect(router.resolve('/teacher/dashboard').name).toBe('TeacherDashboard')
    expect(router.resolve('/teacher/projects').name).toBe('ProjectList')
    expect(router.resolve('/teacher/lesson-plans').name).toBe('LessonPlan')
    expect(router.resolve('/teacher/tasks').name).toBe('TaskList')
    expect(router.resolve('/teacher/evaluations').name).toBe('EvaluationList')
    expect(router.resolve('/teacher/resources').name).toBe('ResourceList')
    expect(router.resolve('/teacher/question-bank').name).toBe('QuestionBank')
  })
})
