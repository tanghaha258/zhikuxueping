/**
 * 跨项目任务中心纯函数测试（计划 Task 9 Step 4）。
 *
 * 验收要点：
 * - 默认聚合所有可管理项目的待发布、进行中、临期、未提交、待关闭任务。
 * - 任务中心只负责分类与跳转，不保留独立创建正式任务入口（无第二套编辑逻辑）。
 * - 分类规则：draft/scheduled → to_publish；published/in_progress → in_progress；
 *   进行中且临期 → due_soon；进行中且有未提交学生 → unsubmitted；in_progress → to_close。
 */
import { describe, expect, it } from 'vitest'
import {
  DUE_SOON_DAYS,
  buildTaskCenterBuckets,
  categorizeTask,
  emptyTaskCenterBuckets,
  isDueSoon,
  type TaskCenterItem,
} from './TaskListView.vue'

// ── 测试夹具 ────────────────────────────────────────────────────
function makeItem(overrides: Partial<TaskCenterItem> = {}): TaskCenterItem {
  return {
    id: 't1',
    title: '任务',
    projectId: 'p1',
    projectTitle: '项目',
    taskType: 'individual',
    maxScore: 100,
    submissionCount: 0,
    totalStudents: 0,
    publishStatus: 'draft',
    ...overrides,
  }
}

const NOW = new Date('2026-07-24T00:00:00+08:00')

// ============================================================
// 1. 临期判定
// ============================================================
describe('isDueSoon 临期判定', () => {
  it('无截止时间返回 false', () => {
    expect(isDueSoon(undefined, NOW)).toBe(false)
  })

  it('非法时间返回 false', () => {
    expect(isDueSoon('not-a-date', NOW)).toBe(false)
  })

  it('已过期返回 false（不计入临期）', () => {
    expect(isDueSoon('2026-07-20T00:00:00+08:00', NOW)).toBe(false)
  })

  it('阈值内返回 true', () => {
    expect(isDueSoon('2026-07-26T00:00:00+08:00', NOW)).toBe(true)
  })

  it('超过阈值返回 false', () => {
    expect(isDueSoon('2026-08-01T00:00:00+08:00', NOW)).toBe(false)
  })

  it('自定义阈值生效', () => {
    expect(isDueSoon('2026-07-28T00:00:00+08:00', NOW, 7)).toBe(true)
    expect(DUE_SOON_DAYS).toBeGreaterThan(0)
  })
})

// ============================================================
// 2. 分类规则
// ============================================================
describe('categorizeTask 分类规则', () => {
  it('草稿任务仅归入待发布', () => {
    const cats = categorizeTask(makeItem({ publishStatus: 'draft' }), NOW)
    expect(cats).toEqual(['to_publish'])
  })

  it('定时任务归入待发布', () => {
    const cats = categorizeTask(makeItem({ publishStatus: 'scheduled' }), NOW)
    expect(cats).toEqual(['to_publish'])
  })

  it('已发布且无提交归入进行中与未提交', () => {
    const cats = categorizeTask(
      makeItem({ publishStatus: 'published', totalStudents: 3, submissionCount: 0 }),
      NOW,
    )
    expect(cats).toContain('in_progress')
    expect(cats).toContain('unsubmitted')
  })

  it('已发布且全部已提交不再归入未提交', () => {
    const cats = categorizeTask(
      makeItem({ publishStatus: 'published', totalStudents: 2, submissionCount: 2 }),
      NOW,
    )
    expect(cats).toContain('in_progress')
    expect(cats).not.toContain('unsubmitted')
  })

  it('无接收学生的已发布任务不归入未提交', () => {
    const cats = categorizeTask(
      makeItem({ publishStatus: 'published', totalStudents: 0, submissionCount: 0 }),
      NOW,
    )
    expect(cats).not.toContain('unsubmitted')
  })

  it('进行中且临期归入临期与待关闭', () => {
    const cats = categorizeTask(
      makeItem({
        publishStatus: 'in_progress',
        deadline: '2026-07-26T00:00:00+08:00',
        totalStudents: 1,
        submissionCount: 1,
      }),
      NOW,
    )
    expect(cats).toContain('due_soon')
    expect(cats).toContain('to_close')
  })

  it('已关闭任务不归入任何待办桶', () => {
    const cats = categorizeTask(makeItem({ publishStatus: 'closed' }), NOW)
    expect(cats).toEqual([])
  })

  it('已归档任务不归入任何待办桶', () => {
    const cats = categorizeTask(makeItem({ publishStatus: 'archived' }), NOW)
    expect(cats).toEqual([])
  })
})

// ============================================================
// 3. 桶构建：跨项目聚合，不复制第二套编辑逻辑
// ============================================================
describe('buildTaskCenterBuckets 跨项目聚合', () => {
  it('空数据返回空桶且无伪造', () => {
    const b = buildTaskCenterBuckets([], NOW)
    expect(b.to_publish).toEqual([])
    expect(b.in_progress).toEqual([])
    expect(b.due_soon).toEqual([])
    expect(b.unsubmitted).toEqual([])
    expect(b.to_close).toEqual([])
  })

  it('emptyTaskCenterBuckets 返回结构稳定的空桶', () => {
    const b = emptyTaskCenterBuckets()
    expect(Object.keys(b).sort()).toEqual(
      ['due_soon', 'in_progress', 'to_close', 'to_publish', 'unsubmitted'].sort(),
    )
  })

  it('跨项目任务归入对应桶并保留 project_id 与 project_title（用于跳转）', () => {
    const items = [
      makeItem({
        id: 'a',
        title: '草稿A',
        projectId: 'pa',
        projectTitle: '项目A',
        publishStatus: 'draft',
      }),
      makeItem({
        id: 'b',
        title: '进行B',
        projectId: 'pb',
        projectTitle: '项目B',
        publishStatus: 'published',
        totalStudents: 1,
        submissionCount: 0,
      }),
    ]
    const b = buildTaskCenterBuckets(items, NOW)
    expect(b.to_publish.map((i) => i.id)).toEqual(['a'])
    expect(b.in_progress.map((i) => i.id)).toEqual(['b'])
    expect(b.unsubmitted.map((i) => i.id)).toEqual(['b'])
    expect(b.to_publish[0].projectTitle).toBe('项目A')
    expect(b.in_progress[0].projectTitle).toBe('项目B')
  })

  it('不修改原始条目（任务中心不承担编辑写入）', () => {
    const items = [
      makeItem({ id: 'a', publishStatus: 'draft' }),
      makeItem({ id: 'b', publishStatus: 'in_progress', deadline: '2026-07-26T00:00:00+08:00' }),
    ]
    buildTaskCenterBuckets(items, NOW)
    // 原始条目字段保持不变
    expect(items[0].id).toBe('a')
    expect(items[0].publishStatus).toBe('draft')
    expect(items[1].publishStatus).toBe('in_progress')
  })

  it('同一任务可同时出现在多个待办桶（进行中+临期+未提交+待关闭）', () => {
    const items = [
      makeItem({
        id: 'x',
        publishStatus: 'in_progress',
        deadline: '2026-07-26T00:00:00+08:00',
        totalStudents: 2,
        submissionCount: 0,
      }),
    ]
    const b = buildTaskCenterBuckets(items, NOW)
    expect(b.in_progress.map((i) => i.id)).toContain('x')
    expect(b.due_soon.map((i) => i.id)).toContain('x')
    expect(b.unsubmitted.map((i) => i.id)).toContain('x')
    expect(b.to_close.map((i) => i.id)).toContain('x')
  })
})
