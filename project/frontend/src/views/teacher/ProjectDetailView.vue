<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getProjectApi, updateProjectApi } from '@/api/projects'
import { listTasksApi, createTaskApi, deleteTaskApi } from '@/api/tasks'
import { listResourcesApi, createResourceApi, deleteResourceApi } from '@/api/resources'
import { listTaskSubmissionsApi, updateSubmissionApi } from '@/api/submissions'
import { listStudentEvaluationsApi } from '@/api/evaluations'
import { useUserStore } from '@/stores/user'
import type { Project, Task, TaskCreateForm, Resource, ResourceCreateForm, Submission, Evaluation, EvaluationCreateForm } from '@/types'
import { formatDate } from '@/utils/format'

const route = useRoute()
const userStore = useUserStore()
const projectId = route.params.id as string

const activeTab = ref('tasks')

const project = ref<Project | null>(null)
const loading = ref(false)

const tasks = ref<Task[]>([])
const tasksLoading = ref(false)
const showTaskDialog = ref(false)
const taskForm = ref<TaskCreateForm>({
  project_id: projectId,
  title: '',
  description: '',
  task_type: 'individual',
  max_score: 100,
  deadline: undefined,
  student_ids: [],
})
const taskCreating = ref(false)

const resources = ref<Resource[]>([])
const resourcesLoading = ref(false)
const showResourceDialog = ref(false)
const resourceForm = ref<ResourceCreateForm>({
  project_id: projectId,
  title: '',
  res_type: 'document',
  url: '',
})
const resourceCreating = ref(false)

const submissions = ref<Submission[]>([])
const submissionsLoading = ref(false)
const selectedTaskId = ref('')
const scoringDialog = ref(false)
const scoringForm = ref({ score: 0, comment: '' })
const scoringSubmissionId = ref('')

const evaluations = ref<Evaluation[]>([])
const evaluationsLoading = ref(false)

const statusMap: Record<string, { label: string; type: string }> = {
  draft: { label: '草稿', type: 'info' },
  active: { label: '进行中', type: 'primary' },
  completed: { label: '已完成', type: 'success' },
  archived: { label: '已归档', type: 'warning' },
}

const taskStatusMap: Record<string, { label: string; type: string }> = {
  pending: { label: '待处理', type: 'info' },
  in_progress: { label: '进行中', type: 'warning' },
  submitted: { label: '已提交', type: 'primary' },
  evaluated: { label: '已评价', type: 'success' },
}

async function fetchProject() {
  loading.value = true
  try {
    const res = await getProjectApi(projectId)
    project.value = res.data.data
  } finally {
    loading.value = false
  }
}

async function fetchTasks() {
  tasksLoading.value = true
  try {
    const res = await listTasksApi({ project_id: projectId })
    tasks.value = res.data.data.items
  } finally {
    tasksLoading.value = false
  }
}

async function fetchResources() {
  resourcesLoading.value = true
  try {
    const res = await listResourcesApi({ project_id: projectId })
    resources.value = res.data.data
  } finally {
    resourcesLoading.value = false
  }
}

async function fetchSubmissions() {
  if (!selectedTaskId.value) {
    submissions.value = []
    return
  }
  submissionsLoading.value = true
  try {
    const res = await listTaskSubmissionsApi(selectedTaskId.value)
    submissions.value = res.data.data
  } finally {
    submissionsLoading.value = false
  }
}

async function fetchEvaluations() {
  evaluationsLoading.value = true
  try {
    const res = await listStudentEvaluationsApi(userStore.userInfo?.id || '')
    evaluations.value = res.data.data
  } finally {
    evaluationsLoading.value = false
  }
}

function onTabChange(tab: string) {
  if (tab === 'tasks' && tasks.value.length === 0) fetchTasks()
  if (tab === 'resources' && resources.value.length === 0) fetchResources()
  if (tab === 'evaluations' && evaluations.value.length === 0) fetchEvaluations()
}

function openTaskDialog() {
  taskForm.value = { project_id: projectId, title: '', description: '', task_type: 'individual', max_score: 100, deadline: undefined, student_ids: [] }
  showTaskDialog.value = true
}

async function handleCreateTask() {
  if (!taskForm.value.title.trim()) {
    ElMessage.warning('请输入任务名称')
    return
  }
  taskCreating.value = true
  try {
    await createTaskApi(taskForm.value)
    ElMessage.success('创建成功')
    showTaskDialog.value = false
    fetchTasks()
  } finally {
    taskCreating.value = false
  }
}

async function handleDeleteTask(id: string) {
  try {
    await ElMessageBox.confirm('确定要删除该任务吗？', '确认删除', { type: 'warning' })
    await deleteTaskApi(id)
    ElMessage.success('删除成功')
    fetchTasks()
  } catch {}
}

function selectTaskForEval(taskId: string) {
  selectedTaskId.value = taskId
  activeTab.value = 'evaluations'
  fetchSubmissions()
}

function openScoring(sub: Submission) {
  scoringSubmissionId.value = sub.id
  scoringForm.value = { score: sub.score || 0, comment: sub.comment || '' }
  scoringDialog.value = true
}

async function handleScore() {
  try {
    await updateSubmissionApi(scoringSubmissionId.value, {
      score: scoringForm.value.score,
      comment: scoringForm.value.comment,
    })
    ElMessage.success('评分成功')
    scoringDialog.value = false
    fetchSubmissions()
  } catch {}
}

function openResourceDialog() {
  resourceForm.value = { project_id: projectId, title: '', res_type: 'document', url: '' }
  showResourceDialog.value = true
}

async function handleCreateResource() {
  if (!resourceForm.value.title.trim()) {
    ElMessage.warning('请输入资源名称')
    return
  }
  resourceCreating.value = true
  try {
    await createResourceApi(resourceForm.value)
    ElMessage.success('创建成功')
    showResourceDialog.value = false
    fetchResources()
  } finally {
    resourceCreating.value = false
  }
}

async function handleDeleteResource(id: string) {
  try {
    await ElMessageBox.confirm('确定要删除该资源吗？', '确认删除', { type: 'warning' })
    await deleteResourceApi(id)
    ElMessage.success('删除成功')
    fetchResources()
  } catch {}
}

const resourceTypeMap: Record<string, string> = {
  document: '文档', video: '视频', image: '图片', link: '链接', other: '其他',
}

onMounted(() => {
  fetchProject()
  fetchTasks()
})
</script>

<template>
  <div class="page-container">
    <div class="flex-between" style="margin-bottom: 16px;">
      <div>
        <el-link :underline="false" href="#/teacher/projects" style="margin-bottom: 8px; display: inline-block;">
          <el-icon><ArrowLeft /></el-icon> 返回项目列表
        </el-link>
        <h2 class="page-title" style="margin-bottom: 4px;">{{ project?.title || '加载中...' }}</h2>
        <div class="project-meta" v-if="project">
          <el-tag size="small" :type="(statusMap[project.status]?.type as any)">{{ statusMap[project.status]?.label }}</el-tag>
          <span class="meta-item">{{ project.subjectIds?.join(' · ') || '-' }}</span>
          <span class="meta-item">{{ project.grade || '-' }}</span>
          <span class="meta-item">创建时间: {{ formatDate(project.createdAt, 'YYYY-MM-DD') }}</span>
        </div>
      </div>
      <div class="flex" style="gap: 8px;">
        <el-button :icon="Edit">编辑</el-button>
      </div>
    </div>

    <el-card shadow="never" class="page-section" v-if="project">
      <p class="project-desc">{{ project.description || '暂无描述' }}</p>
    </el-card>

    <el-card shadow="never" class="page-section">
      <el-tabs v-model="activeTab" @tab-change="onTabChange">
        <!-- 任务 Tab -->
        <el-tab-pane label="项目任务" name="tasks">
          <div class="flex-between" style="margin-bottom: 12px;">
            <span style="color: #909399; font-size: 14px;">共 {{ tasks.length }} 个任务</span>
            <el-button type="primary" size="small" :icon="Plus" @click="openTaskDialog">创建任务</el-button>
          </div>
          <el-table :data="tasks" v-loading="tasksLoading" stripe style="width: 100%">
            <el-table-column prop="title" label="任务名称" min-width="180" />
            <el-table-column label="类型" width="80">
              <template #default="{ row }">
                <el-tag :type="row.taskType === 'individual' ? 'default' : 'success'" size="small">
                  {{ row.taskType === 'individual' ? '个人' : '小组' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="(taskStatusMap[row.status]?.type as any)" size="small">
                  {{ taskStatusMap[row.status]?.label || row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="满分" width="60" align="center" prop="maxScore" />
            <el-table-column label="截止日期" width="120">
              <template #default="{ row }">{{ formatDate(row.deadline, 'YYYY-MM-DD') }}</template>
            </el-table-column>
            <el-table-column label="操作" width="160" fixed="right">
              <template #default="{ row }">
                <el-button text type="primary" size="small" @click="selectTaskForEval(row.id)">评价</el-button>
                <el-button text type="primary" size="small">编辑</el-button>
                <el-button text type="danger" size="small" @click="handleDeleteTask(row.id)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div v-if="!tasksLoading && tasks.length === 0" class="empty-state">
            <el-empty description="暂无任务，请先创建项目任务" />
          </div>
        </el-tab-pane>

        <!-- 评价 Tab -->
        <el-tab-pane label="评价管理" name="evaluations">
          <div style="margin-bottom: 12px;">
            <span style="font-size: 14px; color: #909399;">选择任务：</span>
            <el-select v-model="selectedTaskId" placeholder="选择要评价的任务" style="width: 300px" @change="fetchSubmissions">
              <el-option v-for="t in tasks" :key="t.id" :label="t.title" :value="t.id" />
            </el-select>
          </div>
          <el-table :data="submissions" v-loading="submissionsLoading" stripe style="width: 100%">
            <el-table-column prop="studentId" label="学生 ID" min-width="160" />
            <el-table-column label="提交内容" min-width="200">
              <template #default="{ row }">{{ row.content ? row.content.substring(0, 50) + '...' : '无内容' }}</template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="row.score !== null && row.score !== undefined ? 'success' : 'info'" size="small">
                  {{ row.score !== null && row.score !== undefined ? '已评分' : '待评分' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="评分" width="80" align="center" prop="score" />
            <el-table-column label="操作" width="100" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" size="small" @click="openScoring(row)">
                  {{ row.score !== null && row.score !== undefined ? '查看' : '评分' }}
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          <div v-if="!submissionsLoading && submissions.length === 0" class="empty-state">
            <el-empty :description="selectedTaskId ? '暂无提交记录' : '请先选择一个任务'" />
          </div>
        </el-tab-pane>

        <!-- 资源 Tab -->
        <el-tab-pane label="项目资源" name="resources">
          <div class="flex-between" style="margin-bottom: 12px;">
            <span style="color: #909399; font-size: 14px;">共 {{ resources.length }} 个资源</span>
            <el-button type="primary" size="small" :icon="Plus" @click="openResourceDialog">添加资源</el-button>
          </div>
          <el-table :data="resources" v-loading="resourcesLoading" stripe style="width: 100%">
            <el-table-column prop="title" label="资源名称" min-width="200">
              <template #default="{ row }">
                <div class="flex" style="align-items: center; gap: 8px;">
                  <el-icon :size="16" color="#409EFF"><Document /></el-icon>
                  {{ row.title }}
                </div>
              </template>
            </el-table-column>
            <el-table-column label="类型" width="100">
              <template #default="{ row }">{{ resourceTypeMap[row.resType] || row.resType }}</template>
            </el-table-column>
            <el-table-column label="上传时间" width="120">
              <template #default="{ row }">{{ formatDate(row.createdAt, 'YYYY-MM-DD') }}</template>
            </el-table-column>
            <el-table-column label="操作" width="100" fixed="right">
              <template #default="{ row }">
                <el-button text type="danger" size="small" @click="handleDeleteResource(row.id)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div v-if="!resourcesLoading && resources.length === 0" class="empty-state">
            <el-empty description="暂无资源" />
          </div>
        </el-tab-pane>

        <!-- 成员 Tab -->
        <el-tab-pane label="项目成员" name="members">
          <div class="empty-state">
            <el-empty description="成员管理功能开发中" />
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 创建任务对话框 -->
    <el-dialog v-model="showTaskDialog" title="创建任务" width="520px">
      <el-form label-position="top">
        <el-form-item label="任务名称" required>
          <el-input v-model="taskForm.title" placeholder="请输入任务名称" />
        </el-form-item>
        <el-form-item label="任务描述">
          <el-input v-model="taskForm.description" type="textarea" :rows="3" placeholder="请输入任务描述" />
        </el-form-item>
        <el-form-item label="任务类型">
          <el-radio-group v-model="taskForm.task_type">
            <el-radio value="individual">个人任务</el-radio>
            <el-radio value="group">小组任务</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="满分">
          <el-input-number v-model="taskForm.max_score" :min="0" :max="1000" />
        </el-form-item>
        <el-form-item label="截止日期">
          <el-date-picker v-model="taskForm.deadline" type="date" placeholder="选择日期" style="width: 100%" value-format="YYYY-MM-DDTHH:mm:ss" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showTaskDialog = false">取消</el-button>
        <el-button type="primary" :loading="taskCreating" @click="handleCreateTask">创建</el-button>
      </template>
    </el-dialog>

    <!-- 评分对话框 -->
    <el-dialog v-model="scoringDialog" title="评分" width="480px">
      <el-form label-position="top">
        <el-form-item label="分数" required>
          <el-input-number v-model="scoringForm.score" :min="0" :max="1000" />
        </el-form-item>
        <el-form-item label="评语">
          <el-input v-model="scoringForm.comment" type="textarea" :rows="3" placeholder="请输入评语" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="scoringDialog = false">取消</el-button>
        <el-button type="primary" @click="handleScore">保存评分</el-button>
      </template>
    </el-dialog>

    <!-- 添加资源对话框 -->
    <el-dialog v-model="showResourceDialog" title="添加资源" width="480px">
      <el-form label-position="top">
        <el-form-item label="资源名称" required>
          <el-input v-model="resourceForm.title" placeholder="请输入资源名称" />
        </el-form-item>
        <el-form-item label="资源类型">
          <el-select v-model="resourceForm.res_type" style="width: 100%">
            <el-option label="文档" value="document" />
            <el-option label="视频" value="video" />
            <el-option label="图片" value="image" />
            <el-option label="链接" value="link" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="URL">
          <el-input v-model="resourceForm.url" placeholder="资源链接或路径" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showResourceDialog = false">取消</el-button>
        <el-button type="primary" :loading="resourceCreating" @click="handleCreateResource">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.project-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 8px;
}
.meta-item {
  font-size: 13px;
  color: #909399;
}
.project-desc {
  font-size: 14px;
  color: #606266;
  line-height: 1.8;
  margin: 0;
}
</style>
