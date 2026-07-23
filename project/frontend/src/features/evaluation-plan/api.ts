/**
 * 评价计划领域 API（计划 Task 4）。
 *
 * 端点前缀：/api/v1/evaluation-plans
 * 覆盖量规版本管理、维度 CRUD、证据、评价记录、评分、
 * 复核队列、教师确认、提交状态机、旧版评价列表。
 */
import http from '@/api/index'
import type { ApiResponse } from '@/types'
import type {
  EvaluationPlanSnapshot,
  EvaluationPlanValidationResult,
  EvaluationRecord,
  EvaluationRecordCreateForm,
  EvaluationScore,
  EvaluationScoreCreateForm,
  EvaluationScoreUpdateForm,
  EvidenceArtifact,
  EvidenceArtifactCreateForm,
  LegacyEvaluation,
  ReviewConfirmRequest,
  ReviewConfirmResult,
  ReviewQueueItem,
  Rubric,
  RubricCreateForm,
  RubricCriterion,
  RubricCriterionCreateForm,
  RubricCriterionUpdateForm,
  RubricPublishResult,
  SubmissionTransitionResult,
  TransitionRequest,
} from './types'

// ── 量规版本管理 ──────────────────────────────────────────────
export function createRubricApi(data: RubricCreateForm) {
  return http.post<ApiResponse<Rubric>>('/evaluation-plans/rubrics', data)
}

export function publishRubricApi(rubricId: string) {
  return http.post<ApiResponse<RubricPublishResult>>(`/evaluation-plans/rubrics/${rubricId}/publish`)
}

export function archiveRubricApi(rubricId: string) {
  return http.post<ApiResponse<{ id: string; status: string }>>(`/evaluation-plans/rubrics/${rubricId}/archive`)
}

// ── 量规维度 ──────────────────────────────────────────────────
export function addCriterionApi(data: RubricCriterionCreateForm) {
  return http.post<ApiResponse<RubricCriterion>>('/evaluation-plans/criteria', data)
}

export function updateCriterionApi(criterionId: string, data: RubricCriterionUpdateForm) {
  return http.put<ApiResponse<RubricCriterion>>(`/evaluation-plans/criteria/${criterionId}`, data)
}

export function deleteCriterionApi(criterionId: string) {
  return http.delete<ApiResponse<null>>(`/evaluation-plans/criteria/${criterionId}`)
}

export function listCriteriaApi(rubricId: string) {
  return http.get<ApiResponse<RubricCriterion[]>>('/evaluation-plans/criteria', {
    params: { rubric_id: rubricId },
  })
}

// ── 证据 ──────────────────────────────────────────────────────
export function addArtifactApi(data: EvidenceArtifactCreateForm) {
  return http.post<ApiResponse<EvidenceArtifact>>('/evaluation-plans/artifacts', data)
}

export function listArtifactsApi(projectId: string) {
  return http.get<ApiResponse<EvidenceArtifact[]>>('/evaluation-plans/artifacts', {
    params: { project_id: projectId },
  })
}

// ── 评价计划快照 + 完整性校验 ──────────────────────────────────
export function getPlanSnapshotApi(projectId: string) {
  return http.get<ApiResponse<EvaluationPlanSnapshot>>('/evaluation-plans/snapshot', {
    params: { project_id: projectId },
  })
}

export function validatePlanApi(projectId: string) {
  return http.get<ApiResponse<EvaluationPlanValidationResult>>('/evaluation-plans/validate', {
    params: { project_id: projectId },
  })
}

// ── 评价记录 ──────────────────────────────────────────────────
export function createRecordApi(data: EvaluationRecordCreateForm) {
  return http.post<ApiResponse<EvaluationRecord>>('/evaluation-plans/records', data)
}

export function listRecordsApi(params: {
  project_id: string
  task_id?: string
  student_id?: string
  status?: string
}) {
  return http.get<ApiResponse<EvaluationRecord[]>>('/evaluation-plans/records', { params })
}

export function getRecordApi(recordId: string) {
  return http.get<ApiResponse<EvaluationRecord>>(`/evaluation-plans/records/${recordId}`)
}

export function transitionRecordApi(recordId: string, data: TransitionRequest) {
  return http.post<ApiResponse<EvaluationRecord>>(`/evaluation-plans/records/${recordId}/transition`, data)
}

// ── 分维度评分 ────────────────────────────────────────────────
export function addScoreApi(data: EvaluationScoreCreateForm) {
  return http.post<ApiResponse<EvaluationScore>>('/evaluation-plans/scores', data)
}

export function updateScoreApi(scoreId: string, data: EvaluationScoreUpdateForm) {
  return http.put<ApiResponse<EvaluationScore>>(`/evaluation-plans/scores/${scoreId}`, data)
}

export function listScoresApi(recordId: string) {
  return http.get<ApiResponse<EvaluationScore[]>>('/evaluation-plans/scores', {
    params: { record_id: recordId },
  })
}

// ── 复核队列 + 教师确认 ────────────────────────────────────────
export function getReviewQueueApi(params: { project_id: string; task_id?: string }) {
  return http.get<ApiResponse<ReviewQueueItem[]>>('/evaluation-plans/review-queue', { params })
}

export function confirmReviewApi(submissionId: string, data: ReviewConfirmRequest) {
  return http.post<ApiResponse<ReviewConfirmResult>>(`/evaluation-plans/review-queue/${submissionId}/confirm`, data)
}

// ── 提交状态机 ────────────────────────────────────────────────
export function transitionSubmissionApi(submissionId: string, data: TransitionRequest) {
  return http.post<ApiResponse<SubmissionTransitionResult>>(`/evaluation-plans/submissions/${submissionId}/transition`, data)
}

// ── 旧版评价 ──────────────────────────────────────────────────
export function listLegacyEvaluationsApi(taskId: string) {
  return http.get<ApiResponse<LegacyEvaluation[]>>('/evaluation-plans/legacy', {
    params: { task_id: taskId },
  })
}
