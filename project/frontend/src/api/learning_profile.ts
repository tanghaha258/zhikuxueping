import http from './index'
import type { ApiResponse } from '@/types'

// ============================================================
// 学情 API
// ============================================================

/**
 * 获取班级学情
 * @param classId 班级 ID
 * @param subject 学科代码
 */
export function getClassLearningProfile(classId: string, subject: string) {
  return http.get<ApiResponse<ClassLearningProfile>>(`/learning-profile/classes/${classId}`, {
    params: { subject },
  })
}

/**
 * 获取学生个人学情
 * @param studentId 学生 ID
 * @param subject 学科代码
 */
export function getStudentLearningProfile(studentId: string, subject: string) {
  return http.get<ApiResponse<StudentLearningProfile>>(`/learning-profile/students/${studentId}`, {
    params: { subject },
  })
}

/**
 * 生成班级学情报告
 * @param classId 班级 ID
 * @param subject 学科代码
 */
export function generateClassReport(classId: string, subject: string) {
  return http.post<ApiResponse<ClassReport>>(`/learning-profile/classes/${classId}/report`, { subject })
}

/**
 * 获取班级学情报告列表
 * @param classId 班级 ID
 * @param params 额外查询参数
 */
export function getClassReports(classId: string, params?: Record<string, any>) {
  return http.get<ApiResponse<{ items: ClassReport[]; total: number }>>(
    `/learning-profile/classes/${classId}/reports`,
    { params },
  )
}

/**
 * 获取班级学生学情列表（概览表格数据）
 * @param classId 班级 ID
 * @param subject 学科代码
 */
export function getClassStudentList(classId: string, subject: string) {
  return http.get<ApiResponse<ClassStudentSummary[]>>(
    `/learning-profile/classes/${classId}/students`,
    { params: { subject } },
  )
}

/**
 * 获取知识点掌握度数据
 * @param classId 班级 ID
 * @param subject 学科代码
 */
export function getKnowledgePointStats(classId: string, subject: string) {
  return http.get<ApiResponse<KnowledgePointStat[]>>(
    `/learning-profile/classes/${classId}/knowledge-stats`,
    { params: { subject } },
  )
}

// ============================================================
// 类型定义
// ============================================================

export interface ClassLearningProfile {
  classId: string
  className: string
  subject: string
  totalStudents: number
  averageScore: number
  masteryLevel: number        // 整体掌握度 0-100
  masteryDistribution: {
    excellent: number           // 优秀人数
    good: number                // 良好人数
    normal: number              // 一般人数
    weak: number                // 薄弱人数
  }
  strongPoints: string[]       // 优势知识点
  weakPoints: string[]         // 薄弱知识点
  teachingSuggestions: TeachingSuggestion[]
  knowledgePointStats: KnowledgePointStat[]
}

export interface TeachingSuggestion {
  category: string             // 建议类别
  title: string                // 建议标题
  content: string              // 建议内容
  priority: 'high' | 'medium' | 'low'
}

export interface KnowledgePointStat {
  name: string                 // 知识点名称
  masteryRate: number          // 掌握率 0-100
  studentCount: number         // 涉及学生数
  averageScore: number         // 平均分
  trend: 'up' | 'down' | 'stable'
}

export interface StudentLearningProfile {
  studentId: string
  studentName: string
  subject: string
  totalScore: number
  averageScore: number
  rank: number
  masteryLevel: number
  knowledgePointStats: KnowledgePointStat[]
  weakPoints: string[]
  strongPoints: string[]
}

export interface ClassReport {
  id: string
  classId: string
  subject: string
  generatedAt: string
  summary: string
  overallScore: number
  knowledgeAnalysis: string
  teachingAdvice: string
}

export interface ClassStudentSummary {
  studentId: string
  studentName: string
  averageScore: number
  rank: number
  masteryLevel: number
  strongPoints: string[]
  weakPoints: string[]
  trend: 'up' | 'down' | 'stable'
}
