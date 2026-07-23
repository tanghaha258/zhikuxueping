// ============================================================
// 常量定义
// ============================================================

/** 角色名称映射 */
export const ROLE_LABELS: Record<string, string> = {
  admin: '系统管理员',
  school_admin: '学校管理员',
  teacher: '教师',
  student: '学生',
  parent: '家长',
}

/** 角色对应的首页路由 */
export const ROLE_HOME_ROUTES: Record<string, string> = {
  admin: '/admin/dashboard',
  school_admin: '/admin/dashboard',
  teacher: '/teacher/dashboard',
  student: '/student/dashboard',
  parent: '/student/dashboard',
}

/** 项目状态映射 */
export const PROJECT_STATUS_LABELS: Record<string, string> = {
  draft: '草稿',
  pending_review: '待审核',
  active: '进行中',
  completed: '已完成',
  archived: '已归档',
}

/** 项目状态标签类型 */
export const PROJECT_STATUS_TYPES: Record<string, string> = {
  draft: 'info',
  pending_review: 'warning',
  active: 'primary',
  completed: 'success',
  archived: 'info',
}

/** 项目审核状态映射（独立于生命周期 status） */
export const PROJECT_REVIEW_STATUS_LABELS: Record<string, string> = {
  draft: '设计草稿',
  pending_review: '待审核',
  approved: '已通过',
  returned: '已退回',
  published: '已发布',
  archived: '已归档',
}

/** 任务状态映射 */
export const TASK_STATUS_LABELS: Record<string, string> = {
  pending: '待处理',
  in_progress: '进行中',
  submitted: '已提交',
  evaluated: '已评价',
}

/** 任务状态标签类型 */
export const TASK_STATUS_TYPES: Record<string, string> = {
  pending: 'info',
  in_progress: 'warning',
  submitted: 'primary',
  evaluated: 'success',
}

/** 评价类型映射 */
export const EVALUATION_TYPE_LABELS: Record<string, string> = {
  self: '自评',
  peer: '互评',
  teacher: '教师评价',
  ai: 'AI 评价',
}

/** 资源类型映射 */
export const RESOURCE_TYPE_LABELS: Record<string, string> = {
  document: '文档',
  video: '视频',
  image: '图片',
  link: '链接',
  other: '其他',
}

/** localStorage 键名常量 */
export const STORAGE_KEYS = {
  TOKEN: 'cross_subject_token',
  REFRESH_TOKEN: 'cross_subject_refresh_token',
  USER_INFO: 'cross_subject_user_info',
  REMEMBERED_USERNAME: 'cross_subject_remembered_username',
} as const
