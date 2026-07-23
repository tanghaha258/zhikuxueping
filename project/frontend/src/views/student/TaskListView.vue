<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { listProjectsApi } from '@/api/projects'
import { listMyTasksApi } from '@/api/tasks'
import { getMyTaskSubmissionApi } from '@/api/submissions'
import type { Project, Task, Submission } from '@/types'

const router = useRouter()

const activeTab = ref('all')
interface TaskItem extends Task {
  projectTitle?: string
  submission?: Submission | null
}
const tasks = ref<TaskItem[]>([])
const loading = ref(false)

const statusLabel: Record<string, string> = {
  pending: '待提交',
  in_progress: '进行中',
  submitted: '已提交',
  evaluated: '已批阅',
}

const statusType: Record<string, string> = {
  pending: 'info',
  in_progress: 'warning',
  submitted: 'primary',
  evaluated: 'success',
}

async function fetchData() {
  loading.value = true
  try {
    // Build project title lookup map
    const projRes = await listProjectsApi({ limit: 200 })
    const projectMap: Record<string, string> = {}
    for (const p of projRes.data.data.items) {
      projectMap[p.id] = p.title
    }

    // Get my assigned tasks
    const taskRes = await listMyTasksApi()
    const myTasks: TaskItem[] = taskRes.data.data.map((t: Task) => ({
      ...t,
      projectTitle: projectMap[t.projectId] || t.projectId,
    }))

    // Check submission status for each task
    for (const t of myTasks) {
      try {
        const subRes = await getMyTaskSubmissionApi(t.id)
        t.submission = subRes.data.data
      } catch {}
    }

    tasks.value = myTasks
  } finally {
    loading.value = false
  }
}

const filteredTasks = computed(() => {
  if (activeTab.value === 'all') return tasks.value
  return tasks.value.filter((t) => {
    if (activeTab.value === 'pending') return t.status === 'pending' || t.status === 'in_progress'
    return t.status === activeTab.value
  })
})

function getEffectiveStatus(task: TaskItem): string {
  if (task.submission?.score !== null && task.submission?.score !== undefined) return 'evaluated'
  if (task.submission?.status === 'submitted') return 'submitted'
  return task.status
}

function goToSubmit(taskId: string) {
  router.push(`/student/tasks/${taskId}/submit`)
}

onMounted(fetchData)
</script>

<script lang="ts">
import { computed } from 'vue'
</script>

<template>
  <div class="page-container">
    <h2 class="page-title">我的任务</h2>

    <el-card shadow="never">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="全部任务" name="all" />
        <el-tab-pane label="待提交" name="pending" />
        <el-tab-pane label="已提交" name="submitted" />
        <el-tab-pane label="已批阅" name="evaluated" />
      </el-tabs>

      <div v-if="loading" v-loading="loading" style="min-height: 200px;" />

      <div v-else-if="filteredTasks.length > 0" class="task-list">
        <el-card
          v-for="task in filteredTasks"
          :key="task.id"
          shadow="hover"
          class="task-card"
        >
          <div class="task-card-body">
            <div class="task-card-left">
              <h4 class="task-card-title">{{ task.title }}</h4>
              <div class="task-card-tags">
                <el-tag size="small" type="default">{{ task.projectTitle }}</el-tag>
                <el-tag size="small" type="info">{{ task.taskType === 'individual' ? '个人' : '小组' }}</el-tag>
              </div>
            </div>
            <div class="task-card-right">
              <el-tag :type="(statusType[getEffectiveStatus(task)] as any)" size="small">
                {{ statusLabel[getEffectiveStatus(task)] }}
              </el-tag>
              <span class="task-card-deadline">截止: {{ task.deadline ? new Date(task.deadline).toLocaleDateString() : '无' }}</span>
              <el-button
                v-if="getEffectiveStatus(task) === 'pending' || getEffectiveStatus(task) === 'in_progress'"
                type="primary"
                size="small"
                @click="goToSubmit(task.id)"
              >
                去提交
              </el-button>
              <el-button
                v-else
                text
                type="primary"
                size="small"
                @click="goToSubmit(task.id)"
              >
                查看详情
              </el-button>
            </div>
          </div>
        </el-card>
      </div>

      <div v-else class="empty-state">
        <el-empty description="暂无任务" />
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.task-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-top: 4px;
}
.task-card { border-radius: 8px; }
.task-card-body {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}
.task-card-left { flex: 1; min-width: 0; }
.task-card-title {
  font-size: 15px; font-weight: 500; color: #303133; margin: 0 0 8px;
}
.task-card-tags { display: flex; gap: 6px; flex-wrap: wrap; }
.task-card-right {
  display: flex; align-items: center; gap: 12px; flex-shrink: 0;
}
.task-card-deadline {
  font-size: 12px; color: #909399; white-space: nowrap;
}
</style>
