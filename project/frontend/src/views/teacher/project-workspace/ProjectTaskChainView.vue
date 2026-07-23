<script setup lang="ts">
/**
 * ProjectTaskChainView - 三阶段任务链与发布预览（计划 Task 3.6）。
 *
 * - 按 stage（课前/课中/课后）三列展示任务，每列含任务卡片。
 * - 任务卡片展示层级、发布状态、提交类型、截止时间、最大次数与依赖关系。
 * - 教师可新建/编辑任务（含 stage/tier/submission_type/max_attempts/deadline）。
 * - 依赖管理：添加/删除前驱；后端负责环检测、跨项目、日期冲突校验，前端展示错误。
 * - 发布状态机 transition（DRAFT→SCHEDULED/PUBLISHED→IN_PROGRESS→CLOSED→ARCHIVED）。
 * - 发布预览对话框：分配学生、关联资源、依赖就绪、阻塞与警告，不改变状态。
 * - 项目进入 active/completed/archived 后任务结构只读，但发布状态迁移仍可用。
 */
import { computed, inject, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  addTaskDependencyApi,
  createTaskApi,
  deleteTaskApi,
  getPublishPreviewApi,
  listTaskAssignmentsApi,
  listTaskDependenciesApi,
  listTasksApi,
  removeTaskDependencyApi,
  setTaskAssignmentsApi,
  transitionTaskApi,
  updateTaskApi,
} from '@/api/tasks'
import { listProjectStudentsApi } from '@/api/projects'
import { canEditDesign } from '@/features/project-workspace/composables/useProjectWorkspace'
import { mapServerError } from '@/features/project-workspace/composables/useProjectWorkspace'
import type {
  Project,
  ProjectStudent,
  Task,
  TaskDependency,
  TaskDependencyListResponse,
  TaskPublishPreview,
} from '@/types'

type Ref<T> = import('vue').Ref<T>

const route = useRoute()
const projectId = computed(() => route.params.id as string)
const project = inject<Ref<Project | null>>('workspaceProject')

// 项目结构（任务字段）只在 draft/designing 可编辑；发布状态迁移独立判断
const structEditable = computed(() =>
  canEditDesign(project?.value?.status || 'draft'),
)

// ── 常量映射 ───────────────────────────────────────────────
const STAGE_ORDER = ['pre_class', 'in_class', 'post_class'] as const
const STAGE_LABELS: Record<string, string> = {
  pre_class: '课前',
  in_class: '课中',
  post_class: '课后',
}
const TIER_LABELS: Record<string, string> = {
  foundation: '基础',
  enhancement: '提升',
  extension: '拓展',
}
const TIER_TAG_TYPE: Record<string, string> = {
  foundation: 'info',
  enhancement: 'warning',
  extension: 'danger',
}
const PUBLISH_LABELS: Record<string, string> = {
  draft: '草稿',
  scheduled: '已定时',
  published: '已发布',
  in_progress: '进行中',
  closed: '已关闭',
  archived: '已归档',
}
const PUBLISH_TAG_TYPE: Record<string, string> = {
  draft: 'info',
  scheduled: 'warning',
  published: 'success',
  in_progress: 'success',
  closed: 'info',
  archived: 'info',
}
const SUBMISSION_LABELS: Record<string, string> = {
  text: '文本',
  file: '文件',
  link: '链接',
  artifact: '作品',
  reflection: '反思',
}

// ── 发布状态机（计划 4.3）──────────────────────────────────
const PUBLISH_TRANSITIONS: Record<string, string[]> = {
  draft: ['scheduled', 'published'],
  scheduled: ['published', 'draft'],
  published: ['in_progress', 'closed', 'archived'],
  in_progress: ['closed', 'archived'],
  closed: ['archived'],
  archived: [],
}

function availableTransitions(current: string): string[] {
  return PUBLISH_TRANSITIONS[current] || []
}

// ── 数据 ───────────────────────────────────────────────────
const tasks = ref<Task[]>([])
const loading = ref(false)
const dependencyMap = ref<Record<string, TaskDependencyListResponse>>({})
const projectStudents = ref<ProjectStudent[]>([])

async function loadTasks() {
  loading.value = true
  try {
    const res = await listTasksApi({ project_id: projectId.value, limit: 500 })
    tasks.value = res.data.data.items
    // 并行加载每个任务的依赖
    await Promise.all(
      tasks.value.map(async (t) => {
        try {
          const dep = await listTaskDependenciesApi(t.id)
          dependencyMap.value[t.id] = dep.data.data
        } catch {
          // 单点失败不阻塞
        }
      }),
    )
  } catch (e) {
    ElMessage.error('加载任务失败')
  } finally {
    loading.value = false
  }
}

async function loadProjectStudents() {
  try {
    const res = await listProjectStudentsApi(projectId.value)
    projectStudents.value = res.data.data
  } catch (e) {
    const mapped = mapServerError(e)
    ElMessage.error(mapped.message)
  }
}

// 按班级分组的学生
const studentsByClass = computed(() => {
  const groups: Record<string, { classId: string; className: string; students: ProjectStudent[] }> = {}
  for (const s of projectStudents.value) {
    if (!groups[s.class_id]) {
      groups[s.class_id] = { classId: s.class_id, className: s.class_name, students: [] }
    }
    groups[s.class_id].students.push(s)
  }
  return Object.values(groups)
})

const byStage = computed(() => {
  const groups: Record<string, Task[]> = {
    pre_class: [],
    in_class: [],
    post_class: [],
  }
  const unassigned: Task[] = []
  for (const t of tasks.value) {
    if (t.stage && groups[t.stage]) groups[t.stage].push(t)
    else unassigned.push(t)
  }
  return { groups, unassigned }
})

function taskTitle(id: string): string {
  return tasks.value.find((t) => t.id === id)?.title || id.slice(0, 8)
}

function taskPublishLabel(t: Task): string {
  return PUBLISH_LABELS[t.publishStatus || 'draft'] || t.publishStatus || '草稿'
}

function taskPublishTag(t: Task): string {
  return PUBLISH_TAG_TYPE[t.publishStatus || 'draft'] || 'info'
}

// ── 新建/编辑任务对话框 ────────────────────────────────────
const taskDialogVisible = ref(false)
const taskDialogMode = ref<'create' | 'edit'>('create')
const taskForm = ref({
  id: '',
  title: '',
  description: '',
  task_type: 'assignment',
  max_score: 100,
  deadline: '',
  stage: 'pre_class' as string,
  tier: 'foundation' as string,
  submission_type: 'text' as string,
  max_attempts: 1,
  scheduled_at: '',
  student_ids: [] as string[],
})
const presetStage = ref<string>('')

function openCreateTask(stage?: string) {
  taskDialogMode.value = 'create'
  presetStage.value = stage || ''
  taskForm.value = {
    id: '', title: '', description: '', task_type: 'assignment',
    max_score: 100, deadline: '',
    stage: stage || 'pre_class',
    tier: 'foundation',
    submission_type: 'text',
    max_attempts: 1,
    scheduled_at: '',
    student_ids: [],
  }
  taskDialogVisible.value = true
}

async function openEditTask(t: Task) {
  taskDialogMode.value = 'edit'
  presetStage.value = ''
  // 加载已分配学生
  let assignedIds: string[] = []
  try {
    const res = await listTaskAssignmentsApi(t.id)
    assignedIds = res.data.data.map((a) => a.studentId)
  } catch {
    // 忽略，按空分配处理
  }
  taskForm.value = {
    id: t.id,
    title: t.title,
    description: t.description || '',
    task_type: t.taskType || 'assignment',
    max_score: t.maxScore ?? 100,
    deadline: t.deadline || '',
    stage: t.stage || 'pre_class',
    tier: t.tier || 'foundation',
    submission_type: t.submissionType || 'text',
    max_attempts: t.maxAttempts ?? 1,
    scheduled_at: t.scheduledAt || '',
    student_ids: assignedIds,
  }
  taskDialogVisible.value = true
}

// ── 学生选择辅助 ───────────────────────────────────────────
const selectedStudentCount = computed(() => taskForm.value.student_ids.length)

function toggleStudent(studentId: string) {
  const idx = taskForm.value.student_ids.indexOf(studentId)
  if (idx >= 0) {
    taskForm.value.student_ids.splice(idx, 1)
  } else {
    taskForm.value.student_ids.push(studentId)
  }
}

function toggleClassStudents(classId: string) {
  const group = studentsByClass.value.find((g) => g.classId === classId)
  if (!group) return
  const allSelected = group.students.every((s) => taskForm.value.student_ids.includes(s.id))
  if (allSelected) {
    // 取消该班级全部
    taskForm.value.student_ids = taskForm.value.student_ids.filter(
      (id) => !group.students.some((s) => s.id === id),
    )
  } else {
    // 选中该班级未选学生
    for (const s of group.students) {
      if (!taskForm.value.student_ids.includes(s.id)) {
        taskForm.value.student_ids.push(s.id)
      }
    }
  }
}

function selectAllStudents() {
  taskForm.value.student_ids = projectStudents.value.map((s) => s.id)
}

function clearAllStudents() {
  taskForm.value.student_ids = []
}

function isClassFullySelected(classId: string): boolean {
  const group = studentsByClass.value.find((g) => g.classId === classId)
  if (!group || group.students.length === 0) return false
  return group.students.every((s) => taskForm.value.student_ids.includes(s.id))
}

function studentName(studentId: string): string {
  return projectStudents.value.find((s) => s.id === studentId)?.real_name || studentId.slice(0, 8)
}

async function submitTaskForm() {
  if (!taskForm.value.title.trim()) {
    ElMessage.warning('请填写任务标题')
    return
  }
  const f = { ...taskForm.value }
  const payload: Record<string, unknown> = {
    title: f.title,
    description: f.description || undefined,
    task_type: f.task_type,
    max_score: f.max_score,
    deadline: f.deadline || undefined,
    stage: f.stage,
    tier: f.tier,
    submission_type: f.submission_type,
    max_attempts: f.max_attempts,
  }
  try {
    if (taskDialogMode.value === 'create') {
      await createTaskApi({ project_id: projectId.value, ...payload, student_ids: f.student_ids } as any)
      ElMessage.success('任务已创建（默认草稿状态）')
    } else {
      await updateTaskApi(f.id, payload as any)
      // 编辑模式下通过独立接口更新分配
      await setTaskAssignmentsApi(f.id, f.student_ids)
      ElMessage.success('任务已更新')
    }
    taskDialogVisible.value = false
    await loadTasks()
  } catch (e) {
    const mapped = mapServerError(e)
    ElMessage.error(mapped.message)
  }
}

async function removeTask(t: Task) {
  try {
    await ElMessageBox.confirm(`确认删除任务「${t.title}」？依赖关系将一并删除。`, '删除确认', {
      type: 'warning',
    })
    await deleteTaskApi(t.id)
    ElMessage.success('已删除')
    await loadTasks()
  } catch (e) {
    if (e === 'cancel') return
    const mapped = mapServerError(e)
    ElMessage.error(mapped.message)
  }
}

// ── 依赖管理对话框 ─────────────────────────────────────────
const depDialogVisible = ref(false)
const depTask = ref<Task | null>(null)
const depSelectedPredecessor = ref<string>('')

function openDepDialog(t: Task) {
  depTask.value = t
  depSelectedPredecessor.value = ''
  depDialogVisible.value = true
}

const candidatePredecessors = computed(() => {
  if (!depTask.value) return []
  const existing = new Set(
    (dependencyMap.value[depTask.value.id]?.predecessors || []).map((d) => d.predecessorId),
  )
  // 候选前驱：同项目其他任务，且不能是自身，且尚未建立该前驱关系
  return tasks.value.filter(
    (t) => t.id !== depTask.value!.id && !existing.has(t.id),
  )
})

async function addPredecessor() {
  if (!depTask.value || !depSelectedPredecessor.value) {
    ElMessage.warning('请选择前驱任务')
    return
  }
  try {
    await addTaskDependencyApi(depTask.value.id, depSelectedPredecessor.value)
    ElMessage.success('已添加依赖')
    const dep = await listTaskDependenciesApi(depTask.value.id)
    dependencyMap.value[depTask.value.id] = dep.data.data
    depSelectedPredecessor.value = ''
  } catch (e) {
    const mapped = mapServerError(e)
    ElMessage.error(mapped.message)
  }
}

async function removePredecessor(successorId: string, predecessorId: string) {
  try {
    await removeTaskDependencyApi(successorId, predecessorId)
    ElMessage.success('已移除依赖')
    const dep = await listTaskDependenciesApi(successorId)
    dependencyMap.value[successorId] = dep.data.data
  } catch (e) {
    const mapped = mapServerError(e)
    ElMessage.error(mapped.message)
  }
}

// ── 发布状态迁移对话框 ─────────────────────────────────────
const transitionDialogVisible = ref(false)
const transitionTask = ref<Task | null>(null)
const transitionTarget = ref<string>('')
const transitionScheduledAt = ref<string>('')

function openTransitionDialog(t: Task) {
  const opts = availableTransitions(t.publishStatus || 'draft')
  if (opts.length === 0) {
    ElMessage.info('当前状态为终态，无可迁移目标')
    return
  }
  transitionTask.value = t
  transitionTarget.value = opts[0]
  transitionScheduledAt.value = t.scheduledAt || ''
  transitionDialogVisible.value = true
}

const transitionOptions = computed(() => {
  if (!transitionTask.value) return []
  return availableTransitions(transitionTask.value.publishStatus || 'draft').map(
    (v) => ({ value: v, label: PUBLISH_LABELS[v] || v }),
  )
})

async function submitTransition() {
  if (!transitionTask.value || !transitionTarget.value) return
  const payload: { target: string; scheduled_at?: string } = {
    target: transitionTarget.value,
  }
  if (transitionTarget.value === 'scheduled') {
    if (!transitionScheduledAt.value) {
      ElMessage.warning('定时发布需要填写计划时间')
      return
    }
    payload.scheduled_at = transitionScheduledAt.value
  }
  // 发布确认（Task 1）：展示学生名单与资源数，确认后再发布
  if (transitionTarget.value === 'published') {
    let previewData: TaskPublishPreview | null = null
    try {
      const res = await getPublishPreviewApi(transitionTask.value.id)
      previewData = res.data.data
    } catch (e) {
      const mapped = mapServerError(e)
      ElMessage.error(mapped.message)
      return
    }
    if (previewData && previewData.blockers.length > 0) {
      ElMessage.error(`无法发布：${previewData.blockers.join('；')}`)
      return
    }
    const studentCount = previewData?.assignedStudents.length || 0
    const resourceCount = previewData?.resources.length || 0
    const deadlineText = transitionTask.value.deadline || '未设置'
    try {
      await ElMessageBox.confirm(
        `确认发布任务「${transitionTask.value.title}」？\n` +
        `接收学生：${studentCount} 人\n` +
        `关联资源：${resourceCount} 项\n` +
        `截止时间：${deadlineText}`,
        '发布确认',
        { type: 'warning', confirmButtonText: '确认发布', cancelButtonText: '取消' },
      )
    } catch {
      return // 用户取消
    }
  }
  try {
    await transitionTaskApi(transitionTask.value.id, payload)
    ElMessage.success('状态已迁移')
    transitionDialogVisible.value = false
    await loadTasks()
  } catch (e) {
    const mapped = mapServerError(e)
    ElMessage.error(mapped.message)
  }
}

// ── 发布预览对话框 ─────────────────────────────────────────
const previewVisible = ref(false)
const previewLoading = ref(false)
const preview = ref<TaskPublishPreview | null>(null)

async function quickPublish(t: Task) {
  // 快捷发布（Task 1）：先检查发布预览阻断，无学生时提示并不调用接口
  let previewData: TaskPublishPreview | null = null
  try {
    const res = await getPublishPreviewApi(t.id)
    previewData = res.data.data
  } catch (e) {
    const mapped = mapServerError(e)
    ElMessage.error(mapped.message)
    return
  }
  if (previewData && previewData.blockers.length > 0) {
    if (previewData.assignedStudents.length === 0) {
      ElMessage.warning('请至少选择一名学生')
    } else {
      ElMessage.error(`无法发布：${previewData.blockers.join('；')}`)
    }
    return
  }
  const studentCount = previewData?.assignedStudents.length || 0
  const resourceCount = previewData?.resources.length || 0
  const deadlineText = t.deadline || '未设置'
  try {
    await ElMessageBox.confirm(
      `确认发布任务「${t.title}」？\n` +
      `接收学生：${studentCount} 人\n` +
      `关联资源：${resourceCount} 项\n` +
      `截止时间：${deadlineText}`,
      '发布确认',
      { type: 'warning', confirmButtonText: '确认发布', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await transitionTaskApi(t.id, { target: 'published' })
    ElMessage.success('任务已发布')
    await loadTasks()
  } catch (e) {
    const mapped = mapServerError(e)
    ElMessage.error(mapped.message)
  }
}

async function openPublishPreview(t: Task) {
  previewVisible.value = true
  previewLoading.value = true
  preview.value = null
  try {
    const res = await getPublishPreviewApi(t.id)
    preview.value = res.data.data
  } catch (e) {
    const mapped = mapServerError(e)
    ElMessage.error(mapped.message)
  } finally {
    previewLoading.value = false
  }
}

const previewTask = computed(() => preview.value?.task || null)

onMounted(() => {
  loadTasks()
  loadProjectStudents()
})
</script>

<template>
  <div class="task-chain-view" v-loading="loading">
    <!-- 只读提示 -->
    <div v-if="!structEditable" class="readonly-bar">
      项目当前状态为「{{ project?.status }}」，任务结构只读；发布状态迁移仍可用
    </div>

    <!-- 工具栏 -->
    <div class="toolbar">
      <span class="hint">按教学阶段组织任务链，前置任务完成后方可推进后续阶段</span>
      <el-button type="primary" :disabled="!structEditable" @click="openCreateTask()">
        新建任务
      </el-button>
    </div>

    <!-- 三列布局：课前/课中/课后 -->
    <div class="stage-columns">
      <el-card
        v-for="stage in STAGE_ORDER"
        :key="stage"
        class="stage-column"
        shadow="never"
      >
        <template #header>
          <div class="stage-header">
            <span class="stage-name">{{ STAGE_LABELS[stage] }}</span>
            <span class="stage-count">{{ byStage.groups[stage].length }} 项</span>
            <el-button
              text
              size="small"
              type="primary"
              :disabled="!structEditable"
              @click="openCreateTask(stage)"
            >
              + 新建
            </el-button>
          </div>
        </template>
        <div v-if="byStage.groups[stage].length === 0" class="empty-cell">
          暂无{{ STAGE_LABELS[stage] }}任务
        </div>
        <div
          v-for="t in byStage.groups[stage]"
          :key="t.id"
          class="task-card"
        >
          <div class="task-title-row">
            <span class="task-title">{{ t.title }}</span>
            <el-tag size="small" :type="(taskPublishTag(t) as any)">
              {{ taskPublishLabel(t) }}
            </el-tag>
          </div>
          <div class="task-meta">
            <el-tag size="small" :type="(TIER_TAG_TYPE[t.tier || 'foundation'] as any)">
              {{ TIER_LABELS[t.tier || 'foundation'] || t.tier || '未分层' }}
            </el-tag>
            <span v-if="t.submissionType" class="meta-text">
              提交：{{ SUBMISSION_LABELS[t.submissionType] || t.submissionType }}
            </span>
            <span v-if="t.maxAttempts && t.maxAttempts > 1" class="meta-text">
              最多 {{ t.maxAttempts }} 次
            </span>
            <span v-if="t.deadline" class="meta-text">截止：{{ t.deadline }}</span>
          </div>
          <div v-if="t.description" class="task-desc">{{ t.description }}</div>

          <!-- 依赖关系 -->
          <div class="deps-section">
            <div class="deps-label">前置依赖：</div>
            <div
              v-if="!dependencyMap[t.id]?.predecessors?.length"
              class="deps-empty"
            >
              无
            </div>
            <div
              v-for="d in dependencyMap[t.id]?.predecessors || []"
              :key="d.id"
              class="dep-item"
            >
              <span class="dep-title">{{ taskTitle(d.predecessorId) }}</span>
              <el-button
                v-if="structEditable"
                text
                size="small"
                type="danger"
                @click="removePredecessor(t.id, d.predecessorId)"
              >
                移除
              </el-button>
            </div>
          </div>

          <!-- 操作 -->
          <div class="task-actions">
            <el-button text size="small" :disabled="!structEditable" @click="openEditTask(t)">
              编辑
            </el-button>
            <el-button text size="small" :disabled="!structEditable" @click="openDepDialog(t)">
              依赖
            </el-button>
            <el-button text size="small" type="primary" @click="openPublishPreview(t)">
              发布预览
            </el-button>
            <el-button
              v-if="(t.publishStatus || 'draft') === 'draft' || (t.publishStatus || 'draft') === 'scheduled'"
              text
              size="small"
              type="success"
              data-test="publish-task"
              @click="quickPublish(t)"
            >
              发布
            </el-button>
            <el-button
              text
              size="small"
              type="warning"
              :disabled="availableTransitions(t.publishStatus || 'draft').length === 0"
              @click="openTransitionDialog(t)"
            >
              状态迁移
            </el-button>
            <el-button text size="small" type="danger" :disabled="!structEditable" @click="removeTask(t)">
              删除
            </el-button>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 未分阶段任务 -->
    <el-card v-if="byStage.unassigned.length > 0" class="unassigned-card" shadow="never">
      <template #header>未分阶段任务（历史任务，建议补充阶段）</template>
      <div class="unassigned-list">
        <div v-for="t in byStage.unassigned" :key="t.id" class="task-card inline">
          <span class="task-title">{{ t.title }}</span>
          <el-tag size="small" :type="(taskPublishTag(t) as any)">
            {{ taskPublishLabel(t) }}
          </el-tag>
          <el-button text size="small" :disabled="!structEditable" @click="openEditTask(t)">
            补充阶段
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- 新建/编辑任务对话框 -->
    <el-dialog
      v-model="taskDialogVisible"
      :title="taskDialogMode === 'create' ? '新建任务' : '编辑任务'"
      width="600px"
    >
      <el-form :model="taskForm" label-width="90px" label-position="right">
        <el-form-item label="标题" required>
          <el-input v-model="taskForm.title" placeholder="任务标题" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="taskForm.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="教学阶段">
          <el-select v-model="taskForm.stage" style="width: 100%">
            <el-option label="课前" value="pre_class" />
            <el-option label="课中" value="in_class" />
            <el-option label="课后" value="post_class" />
          </el-select>
        </el-form-item>
        <el-form-item label="层级">
          <el-select v-model="taskForm.tier" style="width: 100%">
            <el-option label="基础" value="foundation" />
            <el-option label="提升" value="enhancement" />
            <el-option label="拓展" value="extension" />
          </el-select>
        </el-form-item>
        <el-form-item label="提交类型">
          <el-select v-model="taskForm.submission_type" style="width: 100%">
            <el-option label="文本" value="text" />
            <el-option label="文件" value="file" />
            <el-option label="链接" value="link" />
            <el-option label="作品" value="artifact" />
            <el-option label="反思" value="reflection" />
          </el-select>
        </el-form-item>
        <el-form-item label="最大次数">
          <el-input-number v-model="taskForm.max_attempts" :min="1" :max="10" />
        </el-form-item>
        <el-form-item label="最大分数">
          <el-input-number v-model="taskForm.max_score" :min="0" :max="1000" />
        </el-form-item>
        <el-form-item label="截止时间">
          <el-input v-model="taskForm.deadline" placeholder="YYYY-MM-DD 或 ISO 时间" />
        </el-form-item>
        <el-form-item label="任务类型">
          <el-input v-model="taskForm.task_type" placeholder="assignment/quiz/..." />
        </el-form-item>
      </el-form>

      <!-- 接收对象（Task 1）：学生分配选择区 -->
      <div class="recipients-section" data-test="recipients-section">
        <div class="recipients-header">
          <span class="recipients-title">接收对象</span>
          <el-tag size="small" :type="selectedStudentCount > 0 ? 'success' : 'danger'">
            已选择 {{ selectedStudentCount }} 名学生
          </el-tag>
        </div>
        <div v-if="projectStudents.length === 0" class="recipients-empty" data-test="recipients-empty">
          当前项目未关联班级，或班级中暂无启用学生。请先在项目中关联含学生的班级。
        </div>
        <div v-else class="recipients-actions">
          <el-button size="small" @click="selectAllStudents">全选</el-button>
          <el-button size="small" @click="clearAllStudents">清空</el-button>
        </div>
        <div v-for="g in studentsByClass" :key="g.classId" class="class-group">
          <div class="class-group-header">
            <el-checkbox
              :model-value="isClassFullySelected(g.classId)"
              @change="toggleClassStudents(g.classId)"
            >
              {{ g.className }}（{{ g.students.length }} 人）
            </el-checkbox>
          </div>
          <div class="student-grid">
            <el-checkbox
              v-for="s in g.students"
              :key="s.id"
              :model-value="taskForm.student_ids.includes(s.id)"
              @change="toggleStudent(s.id)"
            >
              {{ s.real_name }}
            </el-checkbox>
          </div>
        </div>
      </div>

      <template #footer>
        <el-button @click="taskDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :disabled="selectedStudentCount === 0 && taskDialogMode === 'create'"
          @click="submitTaskForm"
        >
          确定
        </el-button>
      </template>
    </el-dialog>

    <!-- 依赖管理对话框 -->
    <el-dialog v-model="depDialogVisible" title="管理前置依赖" width="520px">
      <div v-if="depTask" class="dep-dialog-body">
        <div class="dep-current-task">
          当前任务：<strong>{{ depTask.title }}</strong>
        </div>
        <div class="dep-existing">
          <div class="deps-label">已建立的前置依赖：</div>
          <div
            v-if="!dependencyMap[depTask.id]?.predecessors?.length"
            class="deps-empty"
          >
            暂无
          </div>
          <div
            v-for="d in dependencyMap[depTask.id]?.predecessors || []"
            :key="d.id"
            class="dep-item"
          >
            <span class="dep-title">{{ taskTitle(d.predecessorId) }}</span>
            <el-button text size="small" type="danger" @click="removePredecessor(depTask.id, d.predecessorId)">
              移除
            </el-button>
          </div>
        </div>
        <el-divider />
        <div class="dep-add">
          <div class="deps-label">添加前置依赖：</div>
          <el-select
            v-model="depSelectedPredecessor"
            placeholder="选择前驱任务"
            filterable
            style="width: 100%"
          >
            <el-option
              v-for="c in candidatePredecessors"
              :key="c.id"
              :label="`${c.title}（${STAGE_LABELS[c.stage || ''] || '未分阶段'}·${PUBLISH_LABELS[c.publishStatus || 'draft'] || c.publishStatus}）`"
              :value="c.id"
            />
          </el-select>
          <el-button
            type="primary"
            :disabled="!depSelectedPredecessor"
            @click="addPredecessor"
            style="margin-top: 8px"
          >
            添加
          </el-button>
        </div>
        <div class="dep-hint">
          后端将校验：自环、跨项目、重复、环检测（DFS）、日期冲突（前驱截止不能晚于后继截止）。
        </div>
      </div>
    </el-dialog>

    <!-- 发布状态迁移对话框 -->
    <el-dialog v-model="transitionDialogVisible" title="发布状态迁移" width="440px">
      <div v-if="transitionTask" class="transition-body">
        <div class="dep-current-task">
          任务：<strong>{{ transitionTask.title }}</strong>
          <el-tag size="small" style="margin-left: 8px">
            当前：{{ taskPublishLabel(transitionTask) }}
          </el-tag>
        </div>
        <el-form label-width="90px" style="margin-top: 16px">
          <el-form-item label="目标状态">
            <el-select v-model="transitionTarget" style="width: 100%">
              <el-option
                v-for="opt in transitionOptions"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item v-if="transitionTarget === 'scheduled'" label="计划时间" required>
            <el-input v-model="transitionScheduledAt" placeholder="YYYY-MM-DDTHH:mm:ss" />
          </el-form-item>
        </el-form>
        <div class="dep-hint">
          状态机：草稿→{定时,发布}；定时→{发布,草稿}；发布→{进行中,关闭,归档}；进行中→{关闭,归档}；关闭→{归档}；归档为终态。非法迁移返回 409。
        </div>
      </div>
      <template #footer>
        <el-button @click="transitionDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitTransition">迁移</el-button>
      </template>
    </el-dialog>

    <!-- 发布预览对话框 -->
    <el-dialog v-model="previewVisible" title="发布预览（不改变状态）" width="640px">
      <div v-loading="previewLoading" class="preview-body">
        <template v-if="preview">
          <div class="preview-section">
            <div class="preview-section-title">任务</div>
            <div class="preview-task">
              <strong>{{ previewTask?.title }}</strong>
              <el-tag size="small" style="margin-left: 8px" :type="(taskPublishTag(previewTask!) as any)">
                {{ taskPublishLabel(previewTask!) }}
              </el-tag>
              <el-tag size="small" style="margin-left: 4px" :type="(TIER_TAG_TYPE[previewTask?.tier || 'foundation'] as any)">
                {{ TIER_LABELS[previewTask?.tier || 'foundation'] || '未分层' }}
              </el-tag>
            </div>
          </div>

          <div class="preview-section">
            <div class="preview-section-title">分配学生（{{ preview.assignedStudents.length }} 人）</div>
            <div v-if="preview.assignedStudents.length === 0" class="preview-empty">无分配学生</div>
            <div v-else class="preview-students">
              <el-tag v-for="(sid, i) in preview.assignedStudents" :key="i" size="small" style="margin: 2px">
                {{ sid.slice(0, 8) }}
              </el-tag>
            </div>
          </div>

          <div class="preview-section">
            <div class="preview-section-title">关联资源（{{ preview.resources.length }} 项）</div>
            <div v-if="preview.resources.length === 0" class="preview-empty">无关联资源（按 stage+tier 匹配）</div>
            <div v-else class="preview-resources">
              <div v-for="r in preview.resources" :key="r.id" class="preview-resource">
                <span>{{ r.title }}</span>
                <el-tag size="small" style="margin-left: 8px">
                  {{ TIER_LABELS[r.tier || ''] || r.tier || '未分层' }}
                </el-tag>
                <el-tag size="small" style="margin-left: 4px">
                  {{ PUBLISH_LABELS[r.reviewStatus] || r.reviewStatus }}
                </el-tag>
              </div>
            </div>
          </div>

          <div class="preview-section">
            <div class="preview-section-title">依赖就绪</div>
            <el-tag :type="preview.dependenciesReady ? 'success' : 'warning'">
              {{ preview.dependenciesReady ? '所有前置任务已评价完成' : '存在未完成的前置任务' }}
            </el-tag>
          </div>

          <div v-if="preview.blockers.length > 0" class="preview-section">
            <div class="preview-section-title">阻塞（{{ preview.blockers.length }}）</div>
            <ul class="preview-list">
              <li v-for="(b, i) in preview.blockers" :key="i" class="blocker">{{ b }}</li>
            </ul>
          </div>

          <div v-if="preview.warnings.length > 0" class="preview-section">
            <div class="preview-section-title">警告（{{ preview.warnings.length }}）</div>
            <ul class="preview-list">
              <li v-for="(w, i) in preview.warnings" :key="i" class="warning">{{ w }}</li>
            </ul>
          </div>
        </template>
      </div>
      <template #footer>
        <el-button @click="previewVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.task-chain-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.readonly-bar {
  padding: 8px 12px;
  background: #fdf6ec;
  color: #e6a23c;
  font-size: 13px;
  border-radius: 4px;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.hint {
  font-size: 13px;
  color: #909399;
}

.stage-columns {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.stage-column {
  border: 1px solid #e6e8eb;
}

.stage-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  color: #303133;
}

.stage-name {
  font-size: 15px;
}

.stage-count {
  font-size: 12px;
  color: #909399;
  font-weight: 400;
}

.stage-header .el-button {
  margin-left: auto;
}

.empty-cell {
  padding: 24px 0;
  text-align: center;
  color: #c0c4cc;
  font-size: 13px;
}

.task-card {
  padding: 12px 0;
  border-bottom: 1px solid #f0f0f0;
}

.task-card:last-child {
  border-bottom: none;
}

.task-card.inline {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
}

.task-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}

.task-title {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
  flex: 1;
}

.task-card.inline .task-title {
  flex: 1;
}

.task-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #909399;
  flex-wrap: wrap;
  margin-bottom: 4px;
}

.meta-text {
  color: #909399;
}

.task-desc {
  font-size: 12px;
  color: #606266;
  background: #f7f8fa;
  padding: 4px 8px;
  border-radius: 4px;
  margin-bottom: 6px;
}

.deps-section {
  margin-top: 6px;
  padding: 6px 8px;
  background: #fafafa;
  border-radius: 4px;
}

.deps-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}

.deps-empty {
  font-size: 12px;
  color: #c0c4cc;
}

.dep-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 2px 0;
  font-size: 12px;
}

.dep-title {
  color: #606266;
}

.task-actions {
  margin-top: 8px;
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.unassigned-card {
  border: 1px dashed #dcdfe6;
}

.unassigned-list {
  display: flex;
  flex-direction: column;
}

/* 对话框内部 */
.dep-dialog-body,
.transition-body,
.preview-body {
  font-size: 13px;
}

.dep-current-task {
  margin-bottom: 12px;
  color: #303133;
}

.dep-existing {
  margin-bottom: 8px;
}

.dep-add {
  margin-top: 8px;
}

.dep-hint {
  margin-top: 12px;
  padding: 8px;
  background: #f4f4f5;
  border-radius: 4px;
  font-size: 12px;
  color: #909399;
  line-height: 1.6;
}

.preview-section {
  margin-bottom: 16px;
}

.preview-section-title {
  font-weight: 600;
  color: #303133;
  margin-bottom: 8px;
  font-size: 13px;
}

.preview-task {
  display: flex;
  align-items: center;
}

.preview-empty {
  color: #c0c4cc;
  font-size: 12px;
}

.preview-students {
  display: flex;
  flex-wrap: wrap;
  gap: 2px;
}

.preview-resources {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.preview-resource {
  display: flex;
  align-items: center;
  padding: 4px 8px;
  background: #f7f8fa;
  border-radius: 4px;
  font-size: 12px;
}

.preview-list {
  margin: 0;
  padding-left: 20px;
  font-size: 12px;
  line-height: 1.8;
}

.preview-list .blocker {
  color: #f56c6c;
}

.preview-list .warning {
  color: #e6a23c;
}

@media (max-width: 1024px) {
  .stage-columns {
    grid-template-columns: 1fr;
  }
}

/* 接收对象选择区（Task 1） */
.recipients-section {
  margin-top: 16px;
  padding: 12px;
  border: 1px solid #e6e8eb;
  border-radius: 6px;
  background: #fafbfc;
}

.recipients-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.recipients-title {
  font-weight: 600;
  font-size: 14px;
  color: #303133;
}

.recipients-empty {
  font-size: 13px;
  color: #909399;
  padding: 8px 0;
}

.recipients-actions {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}

.class-group {
  margin-bottom: 8px;
  padding: 8px;
  background: #fff;
  border-radius: 4px;
  border: 1px solid #f0f0f0;
}

.class-group-header {
  margin-bottom: 6px;
}

.student-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  padding-left: 24px;
}
</style>
