import { describe, it, expect } from 'vitest'
import {
  snakeToCamel,
  transformKeysToCamel,
  formatDate,
  truncateText,
  getRoleColor,
} from '@/utils/format'

describe('snakeToCamel', () => {
  it('converts snake_case to camelCase', () => {
    expect(snakeToCamel('hello_world')).toBe('helloWorld')
  })

  it('handles single word', () => {
    expect(snakeToCamel('hello')).toBe('hello')
  })

  it('handles multiple underscores', () => {
    expect(snakeToCamel('a_b_c_d')).toBe('aBCD')
  })

  it('handles empty string', () => {
    expect(snakeToCamel('')).toBe('')
  })
})

describe('transformKeysToCamel', () => {
  it('converts object keys', () => {
    const input = { user_name: 'Alice', user_age: 25 }
    const expected = { userName: 'Alice', userAge: 25 }
    expect(transformKeysToCamel(input)).toEqual(expected)
  })

  it('handles nested objects', () => {
    const input = { user_info: { first_name: 'Bob' } }
    const expected = { userInfo: { firstName: 'Bob' } }
    expect(transformKeysToCamel(input)).toEqual(expected)
  })

  it('handles arrays', () => {
    const input = [{ item_name: 'foo' }, { item_name: 'bar' }]
    const expected = [{ itemName: 'foo' }, { itemName: 'bar' }]
    expect(transformKeysToCamel(input)).toEqual(expected)
  })

  it('returns null/undefined as-is', () => {
    expect(transformKeysToCamel(null)).toBeNull()
    expect(transformKeysToCamel(undefined)).toBeUndefined()
  })

  it('preserves Date objects', () => {
    const d = new Date('2026-01-01')
    expect(transformKeysToCamel(d)).toBe(d)
  })

  it('handles primitive values', () => {
    expect(transformKeysToCamel(42)).toBe(42)
    expect(transformKeysToCamel('hello')).toBe('hello')
    expect(transformKeysToCamel(true)).toBe(true)
  })
})

describe('formatDate', () => {
  it('formats date string with default format', () => {
    expect(formatDate('2026-06-04T10:30:00')).toBe('2026-06-04 10:30:00')
  })

  it('formats Date object', () => {
    const d = new Date(2026, 5, 4, 10, 30, 0)
    expect(formatDate(d)).toBe('2026-06-04 10:30:00')
  })

  it('returns "-" for null/undefined', () => {
    expect(formatDate(null)).toBe('-')
    expect(formatDate(undefined)).toBe('-')
  })

  it('returns "-" for invalid date', () => {
    expect(formatDate('not-a-date')).toBe('-')
  })

  it('supports custom format', () => {
    expect(formatDate('2026-06-04', 'YYYY/MM/DD')).toBe('2026/06/04')
  })
})

describe('truncateText', () => {
  it('returns full text when shorter than max', () => {
    expect(truncateText('hello', 10)).toBe('hello')
  })

  it('truncates with default suffix', () => {
    expect(truncateText('hello world', 5)).toBe('hello...')
  })

  it('truncates with custom suffix', () => {
    expect(truncateText('hello world', 5, '!')).toBe('hello!')
  })

  it('handles empty string', () => {
    expect(truncateText('', 5)).toBe('')
  })

  it('handles null/undefined', () => {
    expect(truncateText(undefined as unknown as string, 5)).toBe('')
  })
})

describe('getRoleColor', () => {
  it('returns correct color for admin', () => {
    expect(getRoleColor('admin')).toBe('#E74C3C')
  })

  it('returns correct color for teacher', () => {
    expect(getRoleColor('teacher')).toBe('#3498DB')
  })

  it('returns correct color for student', () => {
    expect(getRoleColor('student')).toBe('#2ECC71')
  })

  it('returns default color for unknown role', () => {
    expect(getRoleColor('unknown')).toBe('#909399')
  })
})
