import http from './index'
import type {
  ApiResponse,
  Evaluation,
  EvaluationRecord,
  EvaluationRecordCreateForm,
  EvaluationRecordStatus,
  EvaluationRecordTransitionForm,
  LegacyEvaluation,
} from '@/types'

// ── 旧版评价（只读历史兼容，POST/PUT 已下线返回 410）──────────────
export function listTaskEvaluationsApi(taskId: string) {
  return http.get<ApiResponse<Evaluation[]>>(`/evaluations/task/${taskId}`)
}

export function listStudentEvaluationsApi(studentId: string) {
  return http.get<ApiResponse<Evaluation[]>>(`/evaluations/student/${studentId}`)
}

export function getEvaluationApi(id: string) {
  return http.get<ApiResponse<Evaluation>>(`/evaluations/${id}`)
}

/** 旧版简单评价列表（只读历史，标记 is_legacy=true）。 */
export function listLegacyEvaluationsApi(taskId: string) {
  return http.get<ApiResponse<LegacyEvaluation[]>>(
    '/evaluation-plans/legacy',
    { params: { task_id: taskId } },
  )
}

// ── 统一评价记录（EvaluationRecord，唯一新业务事实来源）─────────────
/** 列出评价记录（教师/管理员看全状态；学生仅看自己的已发布/定稿）。 */
export function listEvaluationRecordsApi(params: {
  project_id: string
  task_id?: string
  student_id?: string
  status?: EvaluationRecordStatus
}) {
  return http.get<ApiResponse<EvaluationRecord[]>>('/evaluation-plans/records', {
    params,
  })
}

/** 评价记录详情。 */
export function getEvaluationRecordApi(recordId: string) {
  return http.get<ApiResponse<EvaluationRecord>>(`/evaluation-plans/records/${recordId}`)
}

/** 创建评价记录（默认 DRAFT 状态）。 */
export function createEvaluationRecordApi(data: EvaluationRecordCreateForm) {
  return http.post<ApiResponse<EvaluationRecord>>('/evaluation-plans/records', data)
}

/** 评价记录状态机迁移（如 published、confirmed）。 */
export function transitionEvaluationRecordApi(
  recordId: string,
  data: EvaluationRecordTransitionForm,
) {
  return http.post<ApiResponse<EvaluationRecord>>(
    `/evaluation-plans/records/${recordId}/transition`,
    data,
  )
}

/**
 * 发布评价记录：状态迁移到 published。
 * 调用前需教师已完成确认（confirmed）；后端在发布时同步 Submission 投影。
 */
export function publishEvaluationRecordApi(recordId: string) {
  return transitionEvaluationRecordApi(recordId, { target: 'published' })
}

/**
 * 学生查看本人已发布评价记录（按 project_id 过滤）。
 * 后端策略仅返回 status in (published, finalized) 的记录。
 */
export function listMyPublishedEvaluationRecordsApi(projectId: string) {
  return listEvaluationRecordsApi({ project_id: projectId })
}
