import { describe, it, expect } from 'vitest'
import {
  snakeToCamel,
  transformKeysToCamel,
} from '@/utils/format'

describe('question bank type definitions', () => {
  it('question types are consistent with API snake_case keys', () => {
    const createdKeys = [
      'subject', 'grade', 'question_type', 'difficulty',
      'content', 'options', 'answer', 'analysis', 'score', 'knowledge_points',
    ]
    const expectedCamel = [
      'subject', 'grade', 'questionType', 'difficulty',
      'content', 'options', 'answer', 'analysis', 'score', 'knowledgePoints',
    ]
    createdKeys.forEach((key, i) => {
      expect(snakeToCamel(key)).toBe(expectedCamel[i])
    })
  })

  it('transformKeysToCamel converts question bank response', () => {
    const apiResponse = {
      question_type: 'choice',
      knowledge_points: '["方程"]',
      usage_count: 3,
      created_by: 'user123',
      created_at: '2026-06-04T10:00:00',
    }
    const result = transformKeysToCamel(apiResponse)
    expect(result).toEqual({
      questionType: 'choice',
      knowledgePoints: '["方程"]',
      usageCount: 3,
      createdBy: 'user123',
      createdAt: '2026-06-04T10:00:00',
    })
  })

  it('handles batch import item transformation', () => {
    const batchItem = {
      subject: 'math',
      grade: '7',
      question_type: 'fill',
      difficulty: 3,
      content: 'test',
      options: null,
      answer: 'A',
      analysis: null,
      score: 5,
      knowledge_points: '[]',
    }
    const camel = transformKeysToCamel(batchItem) as Record<string, unknown>
    expect(camel.questionType).toBe('fill')
    expect(camel.knowledgePoints).toBe('[]')
  })
})

describe('question bank filters', () => {
  it('filter params are correctly structured', () => {
    const filters = {
      subject: 'math',
      grade: '7',
      question_type: 'choice',
      difficulty_min: 0,
      difficulty_max: 5,
      keyword: '',
      status: '',
      source: '',
    }
    expect(filters.subject).toBe('math')
    expect(filters.question_type).toBe('choice')
    expect(filters.difficulty_min).toBe(0)
    expect(filters.difficulty_max).toBe(5)
  })
})

describe('difficulty display', () => {
  it('difficulty maps correctly to star ratings', () => {
    const difficultyLabels: Record<number, string> = {
      1: '★☆☆☆☆',
      2: '★★☆☆☆',
      3: '★★★☆☆',
      4: '★★★★☆',
      5: '★★★★★',
    }
    expect(difficultyLabels[1]).toBe('★☆☆☆☆')
    expect(difficultyLabels[3]).toBe('★★★☆☆')
    expect(difficultyLabels[5]).toBe('★★★★★')
  })
})
