import { describe, it, expect } from 'vitest'
import {
  ROLE_LABELS,
  ROLE_HOME_ROUTES,
  PROJECT_STATUS_LABELS,
  TASK_STATUS_LABELS,
  STORAGE_KEYS,
} from '@/utils/constants'

describe('ROLE_LABELS', () => {
  it('contains all roles', () => {
    expect(Object.keys(ROLE_LABELS)).toEqual(
      expect.arrayContaining(['admin', 'school_admin', 'teacher', 'student', 'parent'])
    )
  })

  it('maps admin correctly', () => {
    expect(ROLE_LABELS.admin).toBe('系统管理员')
  })

  it('maps teacher correctly', () => {
    expect(ROLE_LABELS.teacher).toBe('教师')
  })
})

describe('ROLE_HOME_ROUTES', () => {
  it('sends admin to admin dashboard', () => {
    expect(ROLE_HOME_ROUTES.admin).toBe('/admin/dashboard')
  })

  it('sends teacher to teacher dashboard', () => {
    expect(ROLE_HOME_ROUTES.teacher).toBe('/teacher/dashboard')
  })
})

describe('PROJECT_STATUS_LABELS', () => {
  it('maps all statuses', () => {
    expect(PROJECT_STATUS_LABELS.draft).toBe('草稿')
    expect(PROJECT_STATUS_LABELS.active).toBe('进行中')
    expect(PROJECT_STATUS_LABELS.completed).toBe('已完成')
    expect(PROJECT_STATUS_LABELS.archived).toBe('已归档')
  })
})

describe('TASK_STATUS_LABELS', () => {
  it('maps all statuses', () => {
    expect(TASK_STATUS_LABELS.pending).toBe('待处理')
    expect(TASK_STATUS_LABELS.in_progress).toBe('进行中')
    expect(TASK_STATUS_LABELS.submitted).toBe('已提交')
    expect(TASK_STATUS_LABELS.evaluated).toBe('已评价')
  })
})

describe('STORAGE_KEYS', () => {
  it('has all keys', () => {
    expect(STORAGE_KEYS.TOKEN).toBe('cross_subject_token')
    expect(STORAGE_KEYS.REFRESH_TOKEN).toBe('cross_subject_refresh_token')
    expect(STORAGE_KEYS.USER_INFO).toBe('cross_subject_user_info')
  })
})
