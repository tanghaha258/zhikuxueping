/**
 * 项目工作区 API 封装。
 *
 * 所有函数返回 axios 响应（拦截器已将 body 的 key 转为 camelCase），
 * 调用方通过 `res.data.data` 取业务数据。
 *
 * 端点对应后端：
 * - `app.modules.projects.router` 状态机接口
 * - `app.modules.project_designs.router` 项目设计 CRUD 与聚合快照
 */
import http from '@/api'
import type { ApiResponse } from '@/types'
import type {
  ProjectDesignSnapshot,
  ProjectProblem,
  ProjectValidationResult,
  SubjectContribution,
  SubjectRole,
  LearningGoal,
  GoalType,
  EvaluationIndicator,
  EvidencePlan,
  TeachingStage,
  EvidenceType,
  EvidenceCollector,
} from './types'

// ── 项目状态机 ──────────────────────────────────────────────────
export function submitForReviewApi(projectId: string) {
  return http.post<ApiResponse<unknown>>(
    `/projects/${projectId}/submit-for-review`,
  )
}

export function validateActivationApi(projectId: string) {
  return http.post<ApiResponse<ProjectValidationResult>>(
    `/projects/${projectId}/validate-activation`,
  )
}

export function activateProjectApi(projectId: string) {
  return http.post<ApiResponse<unknown>>(`/projects/${projectId}/activate`)
}

// ── 项目设计聚合快照 ────────────────────────────────────────────
export function getDesignSnapshotApi(projectId: string) {
  return http.get<ApiResponse<ProjectDesignSnapshot>>(
    `/projects/${projectId}/design`,
  )
}

// ── 真实问题 ────────────────────────────────────────────────────
export interface ProblemUpsertInput {
  context: string
  object?: string | null
  audience?: string | null
  constraints?: string | null
  deliverable?: string | null
  usage?: string | null
}

export function upsertProblemApi(projectId: string, data: ProblemUpsertInput) {
  return http.put<ApiResponse<ProjectProblem>>(
    `/projects/${projectId}/design/problem`,
    data,
  )
}

export function patchProblemApi(
  projectId: string,
  data: Partial<ProblemUpsertInput>,
) {
  return http.patch<ApiResponse<ProjectProblem>>(
    `/projects/${projectId}/design/problem`,
    data,
  )
}

// ── 学科贡献 ────────────────────────────────────────────────────
export interface ContributionInput {
  subjectId: string
  role: SubjectRole
  knowledge?: string | null
  thinking?: string | null
  inquiry?: string | null
  removalImpact?: string | null
}

export function listContributionsApi(projectId: string) {
  return http.get<ApiResponse<SubjectContribution[]>>(
    `/projects/${projectId}/design/contributions`,
  )
}

export function addContributionApi(projectId: string, data: ContributionInput) {
  return http.post<ApiResponse<SubjectContribution>>(
    `/projects/${projectId}/design/contributions`,
    data,
  )
}

export function patchContributionApi(
  projectId: string,
  contributionId: string,
  data: Omit<ContributionInput, 'subjectId' | 'role'>,
) {
  return http.patch<ApiResponse<SubjectContribution>>(
    `/projects/${projectId}/design/contributions/${contributionId}`,
    data,
  )
}

export function removeContributionApi(
  projectId: string,
  contributionId: string,
) {
  return http.delete<ApiResponse<null>>(
    `/projects/${projectId}/design/contributions/${contributionId}`,
  )
}

// ── 学习目标 ────────────────────────────────────────────────────
export interface GoalInput {
  goalType: GoalType
  name: string
  description?: string | null
  scope?: string | null
}

export function addGoalApi(projectId: string, data: GoalInput) {
  return http.post<ApiResponse<LearningGoal>>(
    `/projects/${projectId}/design/goals`,
    data,
  )
}

export function patchGoalApi(
  projectId: string,
  goalId: string,
  data: Partial<GoalInput>,
) {
  return http.patch<ApiResponse<LearningGoal>>(
    `/projects/${projectId}/design/goals/${goalId}`,
    data,
  )
}

export function removeGoalApi(projectId: string, goalId: string) {
  return http.delete<ApiResponse<null>>(
    `/projects/${projectId}/design/goals/${goalId}`,
  )
}

// ── 评价指标 ────────────────────────────────────────────────────
export interface IndicatorInput {
  goalId: string
  observableBehavior: string
  levelRule?: string | null
}

export function addIndicatorApi(projectId: string, data: IndicatorInput) {
  return http.post<ApiResponse<EvaluationIndicator>>(
    `/projects/${projectId}/design/indicators`,
    data,
  )
}

export function patchIndicatorApi(
  projectId: string,
  indicatorId: string,
  data: Partial<IndicatorInput>,
) {
  return http.patch<ApiResponse<EvaluationIndicator>>(
    `/projects/${projectId}/design/indicators/${indicatorId}`,
    data,
  )
}

export function removeIndicatorApi(projectId: string, indicatorId: string) {
  return http.delete<ApiResponse<null>>(
    `/projects/${projectId}/design/indicators/${indicatorId}`,
  )
}

// ── 证据计划 ────────────────────────────────────────────────────
export interface EvidencePlanInput {
  indicatorId: string
  stage: TeachingStage
  evidenceType: EvidenceType
  collector: EvidenceCollector
  required?: boolean
  description?: string | null
}

export function addEvidencePlanApi(
  projectId: string,
  data: EvidencePlanInput,
) {
  return http.post<ApiResponse<EvidencePlan>>(
    `/projects/${projectId}/design/evidence-plans`,
    data,
  )
}

export function patchEvidencePlanApi(
  projectId: string,
  planId: string,
  data: Partial<EvidencePlanInput>,
) {
  return http.patch<ApiResponse<EvidencePlan>>(
    `/projects/${projectId}/design/evidence-plans/${planId}`,
    data,
  )
}

export function removeEvidencePlanApi(projectId: string, planId: string) {
  return http.delete<ApiResponse<null>>(
    `/projects/${projectId}/design/evidence-plans/${planId}`,
  )
}
