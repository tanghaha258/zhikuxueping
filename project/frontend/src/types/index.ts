export type UserRole =
  | 'admin'
  | 'school_admin'
  | 'teacher'
  | 'student'
  | 'parent'

export interface UserInfo {
  id: string
  username: string
  email: string
  displayName: string
  role: UserRole
  isActive: boolean
  schoolId?: string
  phone?: string
  createdAt?: string
}

export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  accessToken: string
  refreshToken: string
  tokenType: string
  expiresIn: number
  user: UserInfo
}

export interface RegisterRequest {
  username: string
  password: string
  email: string
  displayName: string
  role: UserRole
}

export interface ApiResponse<T = unknown> {
  code: number
  message: string
  data: T
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
}

export interface PaginationParams {
  page: number
  pageSize: number
}

export interface School {
  id: string
  name: string
  code?: string
  region?: string
  address?: string
  contactName?: string
  contactPhone?: string
  isActive: boolean
  createdAt?: string
}

export interface SchoolForm {
  name: string
  code?: string
  region?: string
  address?: string
  contactName?: string
  contactPhone?: string
}

export interface ClassItem {
  id: string
  schoolId: string
  grade: string
  name: string
  headTeacherId?: string
  isActive: boolean
  createdAt?: string
}

export interface ClassForm {
  name: string
  grade: string
  schoolId: string
  headTeacherId?: string
}

export interface Project {
  id: string
  title: string
  description?: string
  coverImageUrl?: string
  status: string
  creatorId: string
  schoolId?: string
  grade?: string
  startDate?: string
  endDate?: string
  isTemplate: boolean
  createdAt?: string
  subjectIds?: string[]
  classIds?: string[]
  // 核心闭环扩展字段（后端增量暴露，历史项目为空，向后兼容）
  projectType?: string
  coreSubjectId?: string
  reviewStatus?: string
  dataOrigin?: string
}

export interface ProjectCreateForm {
  title: string
  description?: string
  cover_image_url?: string
  grade?: string
  start_date?: string
  end_date?: string
  subject_ids?: string[]
  class_ids?: string[]
}

export interface ProjectUpdateForm {
  title?: string
  description?: string
  status?: string
  grade?: string
  start_date?: string
  end_date?: string
}

export interface ProjectStudent {
  id: string
  real_name: string
  class_id: string
  class_name: string
}

export interface Task {
  id: string
  projectId: string
  title: string
  description?: string
  taskType: string
  status: string
  maxScore: number
  deadline?: string
  createdBy: string
  createdAt?: string
  updatedAt?: string
  // 核心闭环扩展（计划 4.1）：阶段/分层/发布状态/提交类型/次数/定时
  stage?: string
  tier?: string
  publishStatus?: string
  submissionType?: string
  maxAttempts?: number
  scheduledAt?: string
}

export interface TaskCreateForm {
  project_id: string
  title: string
  description?: string
  task_type?: string
  max_score?: number
  deadline?: string
  student_ids?: string[]
  stage?: string
  tier?: string
  submission_type?: string
  max_attempts?: number
  scheduled_at?: string
}

export interface TaskUpdateForm {
  title?: string
  description?: string
  task_type?: string
  status?: string
  max_score?: number
  deadline?: string
  stage?: string
  tier?: string
  submission_type?: string
  max_attempts?: number
  scheduled_at?: string
}

export interface TaskAssignment {
  id: string
  taskId: string
  studentId: string
  assignedAt?: string
}

export interface Submission {
  id: string
  taskId: string
  studentId: string
  content?: string
  fileUrls?: string[]
  status: string
  score?: number
  comment?: string
  submittedAt?: string
  createdAt?: string
}

export interface SubmissionCreateForm {
  task_id: string
  content?: string
  file_urls?: string[]
}

export interface SubmissionUpdateForm {
  content?: string
  file_urls?: string[]
  status?: string
  score?: number
  comment?: string
}

export interface Evaluation {
  id: string
  taskId: string
  studentId: string
  evaluatorId: string
  score: number
  comment?: string
  evalType: string
  createdAt?: string
}

export interface EvaluationCreateForm {
  task_id: string
  student_id: string
  score: number
  comment?: string
  eval_type?: string
}

export interface EvaluationUpdateForm {
  score?: number
  comment?: string
}

// ── 统一评价记录（计划 Task 2 / 4.3）──────────────────────────────
/** 评价记录状态机：DRAFT→COLLECTING_EVIDENCE→PENDING_TEACHER_CONFIRMATION→CONFIRMED→PUBLISHED→APPEALED/RECHECKED→FINALIZED */
export type EvaluationRecordStatus =
  | 'draft'
  | 'collecting_evidence'
  | 'pending_teacher_confirmation'
  | 'confirmed'
  | 'published'
  | 'appealed'
  | 'rechecked'
  | 'finalized'

/** 评价来源：teacher / ai / self / peer */
export type EvaluationRecordSource = 'teacher' | 'ai' | 'self' | 'peer'

/** 评价主体类型：task / submission / project / artifact */
export type EvaluationSubjectType = 'task' | 'submission' | 'project' | 'artifact'

/** 评价记录（统一评价事实来源）。 */
export interface EvaluationRecord {
  id: string
  projectId: string
  taskId?: string
  studentId: string
  evaluatorId: string
  subjectType: EvaluationSubjectType
  subjectId: string
  source: EvaluationRecordSource
  status: EvaluationRecordStatus
  rubricId?: string
  totalScore?: number | null
  comment?: string | null
  confirmedBy?: string | null
  confirmedAt?: string | null
  publishedAt?: string | null
  createdAt?: string | null
  updatedAt?: string | null
}

/** 创建评价记录请求体（POST /api/v1/evaluation-plans/records）。 */
export interface EvaluationRecordCreateForm {
  project_id: string
  task_id?: string
  student_id: string
  evaluator_id: string
  subject_type?: EvaluationSubjectType
  subject_id: string
  source?: EvaluationRecordSource
  rubric_id?: string
  comment?: string
}

/** 评价状态机迁移请求体（POST /api/v1/evaluation-plans/records/{id}/transition）。 */
export interface EvaluationRecordTransitionForm {
  target: EvaluationRecordStatus
}

/** 旧版只读评价（GET /api/v1/evaluation-plans/legacy）。 */
export interface LegacyEvaluation {
  id: string
  task_id: string
  student_id: string
  evaluator_id: string
  score: number
  comment?: string | null
  eval_type: string
  is_legacy: true
  created_at?: string | null
}

export interface Resource {
  id: string
  projectId?: string
  title: string
  resType: string
  url?: string
  fileSize?: number
  uploadedBy: string
  createdAt?: string
  // 核心闭环扩展（计划 4.1）：层级/阶段/审核状态/来源等
  tier?: string
  stage?: string
  cognitiveLevel?: string
  readingLevel?: string
  prerequisites?: string
  reviewStatus?: string
  sourceType?: string
  sourceRef?: string
  usageTip?: string
}

export interface ResourceCreateForm {
  project_id?: string
  title: string
  res_type: string
  url?: string
  file_size?: number
  tier?: string
  stage?: string
  cognitive_level?: string
  reading_level?: string
  prerequisites?: string
  review_status?: string
  source_type?: string
  source_ref?: string
  usage_tip?: string
}

export interface SubjectItem {
  id: string
  name: string
  code?: string
  description?: string
  isActive: boolean
  sortOrder: number
}

export interface LessonPlanRequest {
  subject: string
  grade: string
  topic: string
  duration: number
  objectives?: string
  additional?: string
}

export interface LessonPlanResponse {
  content: string
  title: string
}

export interface ResourceUpdateForm {
  title?: string
  url?: string
  tier?: string
  stage?: string
  cognitive_level?: string
  reading_level?: string
  prerequisites?: string
  review_status?: string
  source_type?: string
  source_ref?: string
  usage_tip?: string
}

export interface AiProvider {
  id: string
  name: string
  apiUrl: string
  model: string
  apiKey: string
  status: string
  createdAt?: string
  updatedAt?: string
}

export interface TaskStats {
  activeProjects: number
  pendingEvaluation: number
  totalResources: number
  upcomingDeadlines: number
}

export interface DailyStat {
  date: string
  activeUsers: number
  newTasks: number
}

// 运营指标概览项（Task 8：对外指标展示公式/周期/样本量/来源/责任人）
export interface DashboardMetricOverviewItem {
  id: string
  name: string
  code: string
  formula: string
  period: string
  sampleSize?: number | null
  sourceTable?: string | null
  sourceOwner?: string | null
  responsiblePerson?: string | null
  value?: number | null
  valueCollectedAt?: string | null
}

export interface DashboardStats {
  teacherCount: number
  studentCount: number
  projectCount: number
  weeklyActiveUsers: number
  dailyStats: DailyStat[]
  recentActivities: { user: string; action: string; time: string }[]
  // Task 8 阶段验收：对外指标展示公式/周期/样本量/来源/责任人；默认仅真实数据
  metricOverview?: DashboardMetricOverviewItem[]
  metricCount?: number
  dataOriginFilter?: string
  updatedAt?: string
}

export interface Paper {
  id: string
  title: string
  teacherId: string
  classIds: string[]
  fileUrl?: string
  status: string
  createdAt?: string
  updatedAt?: string
}

export interface PaperCreateForm {
  title: string
  class_ids?: string[]
  file_url?: string
}

export interface PaperUpdateForm {
  title?: string
  class_ids?: string[]
  file_url?: string
  status?: string
}

export interface AnswerKeyQuestion {
  index: number
  type: string
  score: number
  answer: string
  rubric: string
}

export interface AnswerKeyUpsert {
  questions: AnswerKeyQuestion[]
  total_score: number
}

export interface AnswerKey {
  id: string
  paperId: string
  questions: AnswerKeyQuestion[]
  totalScore: number
  createdAt?: string
}

// ── 核心闭环扩展类型（计划 4.1/3.5/3.6）─────────────────────
/** 三级资源递进覆盖检查结果（计划 3.5.3）。 */
export interface ResourceTierCoverage {
  foundation: boolean
  enhancement: boolean
  extension: boolean
  counts: Record<string, number>
  missing: string[]
  total: number
}

/** 任务依赖关系（前驱→后继有向边）。 */
export interface TaskDependency {
  id: string
  predecessorId: string
  successorId: string
  createdAt?: string
}

/** 任务的直接前驱与后继列表。 */
export interface TaskDependencyListResponse {
  predecessors: TaskDependency[]
  successors: TaskDependency[]
}

/** 任务发布状态机迁移请求。 */
export interface TaskTransitionRequest {
  target: string
  scheduled_at?: string
}

/** 发布预览中的关联资源摘要。 */
export interface PublishPreviewResource {
  id: string
  title: string
  tier?: string
  stage?: string
  reviewStatus: string
}

/** 任务发布预览（计划 3.5.4）：不改变状态的发布前快照。 */
export interface TaskPublishPreview {
  task: Task
  assignedStudents: string[]
  resources: PublishPreviewResource[]
  dependenciesReady: boolean
  blockers: string[]
  warnings: string[]
}

export interface SectionItem {
  id: string
  label: string
  type: string
  instruction?: string
  sub_type?: string
  count: number
  score_per: number
  total: number
}

export interface PaperTemplate {
  id: string
  name: string
  subject: string
  grade: string
  examType: string
  totalScore: number
  sections: SectionItem[]
  isActive: boolean
  createdAt?: string
  updatedAt?: string
}

export interface PaperSubmission {
  id: string
  paperId: string
  studentId: string
  fileUrl?: string
  content?: string
  aiScore?: number
  finalScore?: number
  aiComment?: string
  status: string
  createdAt?: string
}

export interface Question {
  id: string
  subject: string
  grade: string
  questionType: string
  difficulty: number
  content: string
  options?: string | null
  answer?: string | null
  analysis?: string | null
  score: number
  knowledgePoints: string
  source: string
  status: string
  usageCount: number
  createdBy: string
  createdAt?: string
  updatedAt?: string
}

export interface QuestionCreateForm {
  subject: string
  grade: string
  question_type: string
  difficulty?: number
  content: string
  options?: string | null
  answer?: string | null
  analysis?: string | null
  score?: number
  knowledge_points?: string
}

export interface QuestionUpdateForm {
  subject?: string
  grade?: string
  question_type?: string
  difficulty?: number
  content?: string
  options?: string | null
  answer?: string | null
  analysis?: string | null
  score?: number
  knowledge_points?: string
  status?: string
}

export interface AiGenerateRequest {
  subject: string
  grade: string
  question_type: string
  knowledge_points?: string[]
  count?: number
  difficulty?: number
}

export interface SmartComposeRequest {
  subject: string
  grade: string
  template_id?: string
  difficulty?: string
  knowledge_points?: string[]
  total_score?: number
  sections?: string
  bank_ratio?: number
}

export interface BatchImportItem {
  subject: string
  grade: string
  question_type: string
  difficulty?: number
  content: string
  options?: string | null
  answer?: string | null
  analysis?: string | null
  score?: number
  knowledge_points?: string
}

export interface BatchImportRequest {
  questions: BatchImportItem[]
}

export interface BatchImportResponse {
  imported: number
  failed: number
  errors: string[]
}

export interface PaperStats {
  total: number
  pending: number
  graded: number
  reviewed: number
  averageScore: number | null
}
