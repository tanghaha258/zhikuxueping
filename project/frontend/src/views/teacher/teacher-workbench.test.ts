/**
 * 教师工作台纯逻辑测试（Task 5）。
 *
 * 覆盖三类：
 * 1. 标签计算：itemLabelOf 对各分区条目的展示标签回退逻辑。
 * 2. 分区映射：partitionWorkbench 的分区顺序、空数据、label 填充。
 * 3. 指标计算：computeWorkbenchMetrics 全部来自真实计数，不伪造。
 *
 * 纯函数测试，不挂载 Vue 组件，避免依赖路由与 HTTP 客户端。
 */
import { describe, expect, it } from 'vitest'
import {
  computeWorkbenchMetrics,
  emptyWorkbenchData,
  itemLabelOf,
  partitionWorkbench,
  type TeacherWorkbenchData,
  type WorkbenchItem,
} from './DashboardView.vue'

// ── 测试夹具 ────────────────────────────────────────────────────
function makeItem(overrides: Partial<WorkbenchItem> = {}): WorkbenchItem {
  return {
    id: 'item-1',
    projectId: 'proj-1',
    route: '/teacher/projects/proj-1/overview',
    ...overrides,
  }
}

function makeData(overrides: Partial<TeacherWorkbenchData> = {}): TeacherWorkbenchData {
  return { ...emptyWorkbenchData(), ...overrides }
}

// ============================================================
// 1. 标签计算：itemLabelOf
// ============================================================
describe('itemLabelOf 标签计算', () => {
  it('tasksToPublish 使用 title，缺失时回退', () => {
    expect(itemLabelOf('tasksToPublish', makeItem({ title: '草稿任务A' }))).toBe('草稿任务A')
    expect(itemLabelOf('tasksToPublish', makeItem({ title: undefined }))).toBe('未命名任务')
  })

  it('submissionsToReview 使用 taskTitle，缺失时回退', () => {
    expect(itemLabelOf('submissionsToReview', makeItem({ taskTitle: '提交任务B' }))).toBe('提交任务B')
    expect(itemLabelOf('submissionsToReview', makeItem({ taskTitle: undefined }))).toBe('待复核提交')
  })

  it('feedbackToPublish 拼接项目名与状态', () => {
    expect(itemLabelOf('feedbackToPublish', makeItem({ projectTitle: '项目X' }))).toBe('项目X · 评价待发布')
    expect(itemLabelOf('feedbackToPublish', makeItem({ projectTitle: undefined }))).toBe('评价待发布')
  })

  it('aiToReview 拼接场景与待确认标识', () => {
    expect(itemLabelOf('aiToReview', makeItem({ scene: '评分草稿' }))).toBe('评分草稿 · AI 待确认')
    expect(itemLabelOf('aiToReview', makeItem({ scene: undefined }))).toBe('AI 任务待确认')
  })

  it('deadlines 使用 title，缺失时回退', () => {
    expect(itemLabelOf('deadlines', makeItem({ title: '临期任务' }))).toBe('临期任务')
    expect(itemLabelOf('deadlines', makeItem({ title: undefined }))).toBe('临近截止任务')
  })

  it('learningAlerts 使用 message，缺失时回退', () => {
    expect(itemLabelOf('learningAlerts', makeItem({ message: '任务已发布但无提交' }))).toBe('任务已发布但无提交')
    expect(itemLabelOf('learningAlerts', makeItem({ message: undefined }))).toBe('学习预警')
  })
})

// ============================================================
// 2. 分区映射：partitionWorkbench
// ============================================================
describe('partitionWorkbench 分区映射', () => {
  it('空数据时各分区 items 为空数组，不伪造', () => {
    const sections = partitionWorkbench(emptyWorkbenchData())
    expect(sections).toHaveLength(6)
    for (const s of sections) {
      expect(s.items).toEqual([])
      expect(s.emptyHint).toBeTruthy()
    }
  })

  it('分区顺序固定：待发布→待复核→待发布评价→AI→截止→预警', () => {
    const sections = partitionWorkbench(emptyWorkbenchData())
    const keys = sections.map((s) => s.key)
    expect(keys).toEqual([
      'tasksToPublish',
      'submissionsToReview',
      'feedbackToPublish',
      'aiToReview',
      'deadlines',
      'learningAlerts',
    ])
  })

  it('每个分区条目被填充 label 字段', () => {
    const data = makeData({
      tasksToPublish: [makeItem({ id: 't1', title: '任务一' })],
      deadlines: [makeItem({ id: 'd1', title: '截止任务', daysLeft: 3 })],
    })
    const sections = partitionWorkbench(data)
    const tasks = sections.find((s) => s.key === 'tasksToPublish')!
    expect(tasks.items[0].label).toBe('任务一')
    const deadlines = sections.find((s) => s.key === 'deadlines')!
    expect(deadlines.items[0].label).toBe('截止任务')
  })

  it('不修改原始数据（不可变）', () => {
    const data = makeData({
      tasksToPublish: [makeItem({ id: 't1', title: '原始' })],
    })
    partitionWorkbench(data)
    // 原始条目不应被添加 label 字段
    expect(data.tasksToPublish[0].label).toBeUndefined()
  })

  it('activeProjects 不出现在待办分区中', () => {
    const data = makeData({
      activeProjects: [
        {
          id: 'p1',
          title: '活跃项目',
          status: 'active',
          currentPhase: 'design',
          currentPhaseLabel: '跨学科设计',
          completion: 0.3,
          route: '/teacher/projects/p1/overview',
        },
      ],
    })
    const sections = partitionWorkbench(data)
    // activeProjects 由组件单独渲染，不在 partitionWorkbench 的 6 个分区中
    expect(sections.some((s) => s.key === 'activeProjects')).toBe(false)
  })
})

// ============================================================
// 3. 指标计算：computeWorkbenchMetrics
// ============================================================
describe('computeWorkbenchMetrics 指标计算', () => {
  it('空数据时所有指标为 0', () => {
    const metrics = computeWorkbenchMetrics(emptyWorkbenchData())
    expect(metrics).toHaveLength(7)
    for (const m of metrics) {
      expect(m.value).toBe(0)
    }
  })

  it('指标标签顺序固定', () => {
    const metrics = computeWorkbenchMetrics(emptyWorkbenchData())
    const labels = metrics.map((m) => m.label)
    expect(labels).toEqual([
      '活跃项目',
      '待发布任务',
      '待复核提交',
      '待发布评价',
      'AI 待确认',
      '临近截止',
      '学习预警',
    ])
  })

  it('指标值来自真实计数，不伪造', () => {
    const data = makeData({
      activeProjects: [
        { id: 'p1', title: 'A', status: 'active', route: '/r1' },
        { id: 'p2', title: 'B', status: 'active', route: '/r2' },
      ],
      tasksToPublish: [makeItem({ id: 't1' }), makeItem({ id: 't2' }), makeItem({ id: 't3' })],
      submissionsToReview: [makeItem({ id: 's1' })],
      feedbackToPublish: [makeItem({ id: 'f1' }), makeItem({ id: 'f2' })],
      aiToReview: [],
      deadlines: [makeItem({ id: 'd1' })],
      learningAlerts: [makeItem({ id: 'la1' }), makeItem({ id: 'la2' }), makeItem({ id: 'la3' }), makeItem({ id: 'la4' })],
    })
    const metrics = computeWorkbenchMetrics(data)
    const map = Object.fromEntries(metrics.map((m) => [m.label, m.value]))
    expect(map['活跃项目']).toBe(2)
    expect(map['待发布任务']).toBe(3)
    expect(map['待复核提交']).toBe(1)
    expect(map['待发布评价']).toBe(2)
    expect(map['AI 待确认']).toBe(0)
    expect(map['临近截止']).toBe(1)
    expect(map['学习预警']).toBe(4)
  })
})

// ============================================================
// 4. emptyWorkbenchData 初始化
// ============================================================
describe('emptyWorkbenchData 空结构', () => {
  it('返回所有顶层字段且均为空数组', () => {
    const empty = emptyWorkbenchData()
    expect(empty.activeProjects).toEqual([])
    expect(empty.tasksToPublish).toEqual([])
    expect(empty.submissionsToReview).toEqual([])
    expect(empty.feedbackToPublish).toEqual([])
    expect(empty.aiToReview).toEqual([])
    expect(empty.deadlines).toEqual([])
    expect(empty.learningAlerts).toEqual([])
  })

  it('每次返回独立引用，不共享', () => {
    const a = emptyWorkbenchData()
    const b = emptyWorkbenchData()
    a.tasksToPublish.push(makeItem())
    expect(b.tasksToPublish).toHaveLength(0)
  })
})
