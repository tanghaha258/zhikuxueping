/**
 * 学生端订正状态机纯函数（计划 3.7.4 / Task 6）。
 *
 * 镜像后端 `app/modules/submissions/service.py` 的 _TRANSITIONS 状态机：
 *   draft → submitted → ai_reviewed / teacher_reviewed → returned → resubmitted → finalized
 *   finalized 为终态，二次评价走 reassess（创建新版本，状态回到 resubmitted）。
 *
 * 纯函数导出，便于单元测试状态流转；组件层据此控制按钮可见性与文案。
 */
import type { SubmissionReviewStatus } from './types'

// ── 状态机迁移表（与后端 _TRANSITIONS 对齐） ─────────────────────
const TRANSITIONS: Record<SubmissionReviewStatus, SubmissionReviewStatus[]> = {
  draft: ['submitted'],
  submitted: ['ai_reviewed', 'teacher_reviewed', 'returned'],
  ai_reviewed: ['teacher_reviewed', 'returned'],
  teacher_reviewed: ['returned', 'finalized'],
  returned: ['resubmitted'],
  resubmitted: ['teacher_reviewed', 'returned', 'finalized'],
  finalized: [], // 终态，二次评价走 reassess 流程，不计入状态机迁移
}

/** 判断从当前状态是否可迁移到目标状态。 */
export function canTransition(
  current: SubmissionReviewStatus,
  target: SubmissionReviewStatus,
): boolean {
  return TRANSITIONS[current]?.includes(target) ?? false
}

/** 学生是否可提交（仅 draft / returned 可发起提交或订正再提交）。 */
export function canSubmit(reviewStatus: SubmissionReviewStatus | undefined | null): boolean {
  return reviewStatus === 'draft' || reviewStatus === undefined || reviewStatus === null
}

/**
 * 学生是否可再提交（订正）。
 * 后端 ensure_can_resubmit：returned 或 finalized 可走 resubmit/reassess。
 * - returned：走 /resubmit（创建新版本，状态→resubmitted）。
 * - finalized：走 /reassess（二次评价，创建新版本，状态→resubmitted）。
 */
export function canResubmit(reviewStatus: SubmissionReviewStatus | undefined | null): boolean {
  return reviewStatus === 'returned'
}

/** 学生是否可发起二次评价（仅 finalized 可发起 reassess）。 */
export function canRequestReassess(
  reviewStatus: SubmissionReviewStatus | undefined | null,
): boolean {
  return reviewStatus === 'finalized'
}

/** 提交是否已进入终态（教师最终确认）。 */
export function isFinalized(reviewStatus: SubmissionReviewStatus | undefined | null): boolean {
  return reviewStatus === 'finalized'
}

/** 提交是否处于等待教师处理的状态（学生暂无可操作项）。 */
export function isPendingReview(
  reviewStatus: SubmissionReviewStatus | undefined | null,
): boolean {
  return (
    reviewStatus === 'submitted' ||
    reviewStatus === 'ai_reviewed' ||
    reviewStatus === 'teacher_reviewed' ||
    reviewStatus === 'resubmitted'
  )
}

/**
 * 计算学生在某提交状态下的可执行动作集合。
 * 用于反馈视图按钮可见性判断。
 */
export interface StudentActions {
  /** 可提交（首次或草稿）。 */
  canSubmit: boolean
  /** 可订正再提交（教师退回后）。 */
  canResubmit: boolean
  /** 可发起二次评价（教师最终确认后）。 */
  canRequestReassess: boolean
  /** 是否为终态。 */
  finalized: boolean
  /** 是否等待教师处理。 */
  pendingReview: boolean
}

export function resolveStudentActions(
  reviewStatus: SubmissionReviewStatus | undefined | null,
): StudentActions {
  return {
    canSubmit: canSubmit(reviewStatus),
    canResubmit: canResubmit(reviewStatus),
    canRequestReassess: canRequestReassess(reviewStatus),
    finalized: isFinalized(reviewStatus),
    pendingReview: isPendingReview(reviewStatus),
  }
}
