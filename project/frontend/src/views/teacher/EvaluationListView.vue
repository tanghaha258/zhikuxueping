<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { listProjectsApi } from '@/api/projects'
import { listTasksApi } from '@/api/tasks'
import { listTaskSubmissionsApi, updateSubmissionApi } from '@/api/submissions'
import type { Project, Task, Submission } from '@/types'

const activeTab = ref('pending')

const projects = ref<Project[]>([])
const tasks = ref<Task[]>([])
const submissions = ref<Submission[]>([])
const loading = ref(false)
const selectedProjectId = ref('')
const selectedTaskId = ref('')
const scoringDialog = ref(false)
const scoringForm = ref({ score: 0, comment: '' })
const scoringSubmissionId = ref('')

const pendingSubmissions = computed(() => submissions.value.filter((s) => s.score === null || s.score === undefined))

async function fetchProjects() {
  const res = await listProjectsApi({ limit: 100 })
  projects.value = res.data.data.items
}

async function fetchTasks() {
  if (!selectedProjectId.value) {
    tasks.value = []
    submissions.value = []
    return
  }
  const res = await listTasksApi({ project_id: selectedProjectId.value })
  tasks.value = res.data.data.items
  if (tasks.value.length > 0) {
    selectedTaskId.value = tasks.value[0].id
    fetchSubmissions()
  }
}

async function fetchSubmissions() {
  if (!selectedTaskId.value) {
    submissions.value = []
    return
  }
  loading.value = true
  try {
    const res = await listTaskSubmissionsApi(selectedTaskId.value)
    submissions.value = res.data.data
  } finally {
    loading.value = false
  }
}

const filteredSubmissions = computed(() => {
  if (activeTab.value === 'pending') {
    return submissions.value.filter((s) => s.score === null || s.score === undefined)
  }
  return submissions.value.filter((s) => s.score !== null && s.score !== undefined)
})

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

onMounted(fetchProjects)
</script>

<template>
  <div class="page-container">
    <h2 class="page-title">多元评价</h2>

    <div class="search-bar">
      <el-select v-model="selectedProjectId" placeholder="选择项目" style="width: 300px" @change="fetchTasks" clearable>
        <el-option v-for="p in projects" :key="p.id" :label="p.title" :value="p.id" />
      </el-select>
      <el-select v-model="selectedTaskId" placeholder="选择任务" style="width: 300px" @change="fetchSubmissions" v-if="tasks.length > 0">
        <el-option v-for="t in tasks" :key="t.id" :label="t.title" :value="t.id" />
      </el-select>
    </div>

    <el-card shadow="never" v-if="selectedTaskId">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="待评价" name="pending" />
        <el-tab-pane label="已评价" name="completed" />
      </el-tabs>

      <el-table :data="filteredSubmissions" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="studentId" label="学生 ID" width="160" />
        <el-table-column label="提交内容" min-width="240">
          <template #default="{ row }">
            {{ row.content ? row.content.substring(0, 80) : '无内容' }}
          </template>
        </el-table-column>
        <el-table-column label="提交时间" width="160">
          <template #default="{ row }">
            {{ row.submittedAt ? new Date(row.submittedAt).toLocaleString() : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="评分" width="80" align="center">
          <template #default="{ row }">
            <span :style="{ color: row.score !== null && row.score !== undefined ? '#67c23a' : '#909399', fontWeight: 600 }">
              {{ row.score !== null && row.score !== undefined ? row.score : '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="openScoring(row)">
              {{ row.score !== null && row.score !== undefined ? '查看' : '评分' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="!loading && filteredSubmissions.length === 0" class="empty-state">
        <el-empty :description="activeTab === 'pending' ? '暂无待评价的提交' : '暂无已评价的提交'" />
      </div>
    </el-card>

    <el-card shadow="never" v-else>
      <el-empty description="请先选择项目和任务" />
    </el-card>

    <el-dialog v-model="scoringDialog" :title="scoringForm.score ? '查看/编辑评分' : '评分'" width="480px">
      <el-form label-position="top">
        <el-form-item label="分数" required>
          <el-input-number v-model="scoringForm.score" :min="0" :max="1000" />
        </el-form-item>
        <el-form-item label="评语">
          <el-input v-model="scoringForm.comment" type="textarea" :rows="4" placeholder="请输入评语" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="scoringDialog = false">取消</el-button>
        <el-button type="primary" @click="handleScore">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>
