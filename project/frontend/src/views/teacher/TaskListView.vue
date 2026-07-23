<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listProjectsApi } from '@/api/projects'
import { listTasksApi, deleteTaskApi, publishTaskApi, closeTaskApi } from '@/api/tasks'
import type { Task, Project } from '@/types'

const router = useRouter()

const tasks = ref<Task[]>([])
const projects = ref<Project[]>([])
const loading = ref(false)
const activeTab = ref('all')
const selectedProjectId = ref('')

const statusMap: Record<string, { label: string; type: string }> = {
  pending: { label: '待处理', type: 'info' },
  in_progress: { label: '进行中', type: 'warning' },
  submitted: { label: '已提交', type: 'primary' },
  evaluated: { label: '已评价', type: 'success' },
}

async function fetchProjects() {
  const res = await listProjectsApi({ limit: 100 })
  projects.value = res.data.data.items
}

async function fetchTasks() {
  loading.value = true
  try {
    if (!selectedProjectId.value) return
    const res = await listTasksApi({ project_id: selectedProjectId.value })
    tasks.value = res.data.data.items
  } finally {
    loading.value = false
  }
}

const filteredTasks = computed(() => {
  if (activeTab.value === 'all') return tasks.value
  return tasks.value.filter((t) => t.status === activeTab.value)
})

function onProjectChange() {
  if (selectedProjectId.value) fetchTasks()
  else tasks.value = []
}

function viewProject(projectId: string) {
  router.push(`/teacher/projects/${projectId}`)
}

async function handleDelete(id: string) {
  try {
    await ElMessageBox.confirm('确定要删除该任务吗？', '确认删除', { type: 'warning' })
    await deleteTaskApi(id)
    ElMessage.success('删除成功')
    fetchTasks()
  } catch {}
}

async function handlePublish(id: string) {
  try {
    await publishTaskApi(id)
    ElMessage.success('任务已发布')
    fetchTasks()
  } catch {}
}

async function handleClose(id: string) {
  try {
    await closeTaskApi(id)
    ElMessage.success('任务已关闭')
    fetchTasks()
  } catch {}
}

onMounted(fetchProjects)
</script>

<script lang="ts">
import { computed } from 'vue'
</script>

<template>
  <div class="page-container">
    <div class="flex-between" style="margin-bottom: 20px;">
      <h2 class="page-title" style="margin-bottom: 0;">任务管理</h2>
    </div>

    <div class="search-bar">
      <el-select v-model="selectedProjectId" placeholder="选择项目" style="width: 300px" @change="onProjectChange" clearable>
        <el-option v-for="p in projects" :key="p.id" :label="p.title" :value="p.id" />
      </el-select>
      <span style="color: #909399; font-size: 13px;" v-if="selectedProjectId">
        共 {{ tasks.length }} 个任务
      </span>
    </div>

    <el-card shadow="never" v-if="selectedProjectId">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="全部任务" name="all" />
        <el-tab-pane label="待处理" name="pending" />
        <el-tab-pane label="进行中" name="in_progress" />
        <el-tab-pane label="已提交" name="submitted" />
        <el-tab-pane label="已评价" name="evaluated" />
      </el-tabs>

      <el-table :data="filteredTasks" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="title" label="任务名称" min-width="200" />
        <el-table-column label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="row.taskType === 'individual' ? 'default' : 'success'" size="small">
              {{ row.taskType === 'individual' ? '个人' : '小组' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="(statusMap[row.status]?.type as any)" size="small">
              {{ statusMap[row.status]?.label || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="maxScore" label="满分" width="60" align="center" />
        <el-table-column label="截止日期" width="120">
          <template #default="{ row }">
            {{ row.deadline ? new Date(row.deadline).toLocaleDateString() : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="120">
          <template #default="{ row }">
            {{ row.createdAt ? new Date(row.createdAt).toLocaleDateString() : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === 'pending'" type="primary" size="small" @click="handlePublish(row.id)">发布</el-button>
            <el-button v-if="row.status === 'in_progress'" type="warning" size="small" @click="handleClose(row.id)">关闭</el-button>
            <el-button text type="primary" size="small" @click="viewProject(row.projectId)">所属项目</el-button>
            <el-button text type="danger" size="small" @click="handleDelete(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card shadow="never" v-else>
      <el-empty description="请先选择一个项目查看任务" />
    </el-card>
  </div>
</template>
