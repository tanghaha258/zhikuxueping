<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { listProjectsApi } from '@/api/projects'
import { listTasksApi } from '@/api/tasks'
import { listTaskSubmissionsApi, updateSubmissionApi } from '@/api/submissions'
import { evaluateSubmissionApi, evaluateBatchApi } from '@/api/ai'
import type { EvaluateResult } from '@/api/ai'
import type { Project, Task, Submission } from '@/types'

const activeTab = ref('pending')

const projects = ref<Project[]>([])
const tasks = ref<Task[]>([])
const submissions = ref<Submission[]>([])
const loading = ref(false)
const selectedProjectId = ref('')
const selectedTaskId = ref('')

// AI evaluate state
const aiDialogVisible = ref(false)
const aiResult = ref<EvaluateResult | null>(null)
const aiLoading = ref(false)
const aiBatchLoading = ref(false)
const currentEvalSubmissionId = ref('')

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

// AI evaluate single
async function aiEvaluate(submissionId: string) {
  currentEvalSubmissionId.value = submissionId
  aiLoading.value = true
  aiDialogVisible.value = true
  try {
    const res = await evaluateSubmissionApi(submissionId)
    aiResult.value = res.data.data
  } catch {
    aiResult.value = null
    ElMessage.error('AI 批改失败')
  } finally {
    aiLoading.value = false
  }
}

// AI evaluate next (auto-flow)
async function aiEvaluateNext() {
  const pending = pendingSubmissions.value
  const idx = pending.findIndex((s) => s.id === currentEvalSubmissionId.value)
  if (idx < pending.length - 1) {
    await aiEvaluate(pending[idx + 1].id)
  } else {
    ElMessage.success('所有待评提交已批改完成')
    aiDialogVisible.value = false
  }
}

// Adopt score
async function adoptScore() {
  if (!aiResult.value || !currentEvalSubmissionId.value) return
  try {
    await updateSubmissionApi(currentEvalSubmissionId.value, {
      score: aiResult.value.totalScore,
      comment: aiResult.value.overallComment,
    })
    ElMessage.success('评分已采纳')
    aiDialogVisible.value = false
    fetchSubmissions()
  } catch {
    ElMessage.error('采纳失败')
  }
}

// Batch evaluate
async function aiBatchEvaluate() {
  if (!selectedTaskId.value) return
  aiBatchLoading.value = true
  try {
    const res = await evaluateBatchApi(selectedTaskId.value)
    ElMessage.success(`批量批改完成：${res.data.data.completed} 份`)
    fetchSubmissions()
  } catch {
    ElMessage.error('批量批改失败')
  } finally {
    aiBatchLoading.value = false
  }
}

onMounted(fetchProjects)
</script>

<template>
  <div class="page-container">
    <h2 class="page-title">AI 批改</h2>

    <div class="search-bar">
      <el-select v-model="selectedProjectId" placeholder="选择项目" style="width: 300px" @change="fetchTasks" clearable>
        <el-option v-for="p in projects" :key="p.id" :label="p.title" :value="p.id" />
      </el-select>
      <el-select v-model="selectedTaskId" placeholder="选择任务" style="width: 300px" @change="fetchSubmissions" v-if="tasks.length > 0">
        <el-option v-for="t in tasks" :key="t.id" :label="t.title" :value="t.id" />
      </el-select>
      <el-button :loading="aiBatchLoading" @click="aiBatchEvaluate" :disabled="!selectedTaskId" type="primary">AI 批量批改</el-button>
    </div>

    <el-card shadow="never" v-if="selectedTaskId">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="待批改" name="pending" />
        <el-tab-pane label="已批改" name="completed" />
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
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="aiEvaluate(row.id)">
              <el-icon><MagicStick /></el-icon> AI 批改
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="!loading && filteredSubmissions.length === 0" class="empty-state">
        <el-empty :description="activeTab === 'pending' ? '暂无待批改的提交' : '暂无已批改的提交'" />
      </div>
    </el-card>

    <el-card shadow="never" v-else>
      <el-empty description="请先选择项目和任务" />
    </el-card>

    <!-- AI 批改结果对话框 -->
    <el-dialog v-model="aiDialogVisible" title="AI 批改结果" width="520px">
      <div v-loading="aiLoading">
        <div v-if="aiResult">
          <div v-for="d in aiResult.dimensions" :key="d.name" class="dimension-row">
            <span>{{ d.name }}</span>
            <span>{{ d.score }} 分</span>
            <p>{{ d.comment }}</p>
          </div>
          <el-divider />
          <div class="total-row">
            <strong>总分：{{ aiResult.totalScore }}</strong>
          </div>
          <p>{{ aiResult.overallComment }}</p>
        </div>
      </div>
      <template #footer>
        <el-button @click="aiDialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="adoptScore" :disabled="!aiResult">采纳评分</el-button>
        <el-button @click="aiEvaluate(currentEvalSubmissionId)" :disabled="aiLoading">重新批改</el-button>
        <el-button @click="aiEvaluateNext" :disabled="!aiResult">批改下一个</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.dimension-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}
.dimension-row span:first-child {
  font-weight: 600;
  min-width: 80px;
}
.dimension-row span:nth-child(2) {
  color: #409eff;
  font-weight: 600;
}
.dimension-row p {
  margin: 4px 0 0;
  color: #606266;
  font-size: 13px;
  width: 100%;
}
.total-row {
  text-align: right;
  font-size: 16px;
}
</style>
