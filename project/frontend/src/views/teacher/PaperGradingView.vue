<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getPaperApi, listSubmissionsApi, getPaperStatsApi, evaluatePaperApi } from '@/api/papers'
import type { Paper, PaperSubmission, PaperStats } from '@/types'

const route = useRoute()
const paperId = route.params.id as string

const paper = ref<Paper | null>(null)
const submissions = ref<PaperSubmission[]>([])
const stats = ref<PaperStats | null>(null)
const loading = ref(false)
const evalLoading = ref(false)

const statusMap: Record<string, string> = {
  pending: '待批改',
  graded: '已批改',
  reviewed: '已复核',
}

const statusType: Record<string, string> = {
  pending: 'info',
  graded: 'success',
  reviewed: 'primary',
}

const gradedCount = computed(() => submissions.value.filter(s => s.status !== 'pending').length)

async function fetchPaper() {
  try {
    const res = await getPaperApi(paperId)
    paper.value = res.data.data
  } catch {
    ElMessage.error('获取试卷信息失败')
  }
}

async function fetchSubmissions() {
  loading.value = true
  try {
    const res = await listSubmissionsApi(paperId)
    submissions.value = res.data.data
  } finally {
    loading.value = false
  }
}

async function fetchStats() {
  try {
    const res = await getPaperStatsApi(paperId)
    stats.value = res.data.data
  } catch { /* ignore */ }
}

async function handleEvaluate() {
  evalLoading.value = true
  try {
    const res = await evaluatePaperApi(paperId)
    ElMessage.success(`AI 批改完成：${res.data.data.completed}/${res.data.data.total}`)
    fetchSubmissions()
    fetchStats()
  } catch {
    ElMessage.error('AI 批改失败，请先设置答案与评分标准')
  } finally {
    evalLoading.value = false
  }
}

onMounted(() => {
  fetchPaper()
  fetchSubmissions()
  fetchStats()
})
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h2 class="page-title">{{ paper?.title || '试卷批改' }}</h2>
        <p class="page-desc" v-if="paper">状态：{{ paper.status }}</p>
      </div>
      <div class="header-actions">
        <el-button type="primary" :loading="evalLoading" @click="handleEvaluate" :disabled="!paper || paper.status === 'done'">
          <el-icon><MagicStick /></el-icon> AI 批改全部
        </el-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stats-row" v-if="stats">
      <el-col :span="6">
        <el-card shadow="never">
          <div class="stat-item">
            <span class="stat-label">总答卷</span>
            <span class="stat-value">{{ stats.total }}</span>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never">
          <div class="stat-item">
            <span class="stat-label">待批改</span>
            <span class="stat-value warn">{{ stats.pending }}</span>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never">
          <div class="stat-item">
            <span class="stat-label">已批改</span>
            <span class="stat-value success">{{ stats.graded }}</span>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never">
          <div class="stat-item">
            <span class="stat-label">平均分</span>
            <span class="stat-value primary">{{ stats.averageScore ?? '-' }}</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 答卷列表 -->
    <el-card shadow="never" class="table-card">
      <template #header>
        <span>答卷列表（{{ submissions.length }}）</span>
      </template>

      <el-table :data="submissions" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="studentId" label="学生 ID" width="200" />
        <el-table-column label="状态" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="statusType[row.status] || 'info'" size="small">
              {{ statusMap[row.status] || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="AI 评分" width="100" align="center">
          <template #default="{ row }">
            <span :style="{ color: row.aiScore !== null && row.aiScore !== undefined ? '#67c23a' : '#909399', fontWeight: 600 }">
              {{ row.aiScore !== null && row.aiScore !== undefined ? row.aiScore : '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="最终得分" width="100" align="center">
          <template #default="{ row }">
            <span :style="{ color: row.finalScore !== null && row.finalScore !== undefined ? '#409eff' : '#909399', fontWeight: 600 }">
              {{ row.finalScore !== null && row.finalScore !== undefined ? row.finalScore : '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="AI 评语" min-width="240">
          <template #default="{ row }">
            <span class="comment-text">{{ row.aiComment || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="提交时间" width="160">
          <template #default="{ row }">
            {{ row.createdAt ? new Date(row.createdAt).toLocaleString() : '-' }}
          </template>
        </el-table-column>
      </el-table>

      <div v-if="!loading && submissions.length === 0" class="empty-state">
        <el-empty description="暂无答卷，请先分发试卷" />
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 16px;
}
.page-desc {
  color: #909399;
  font-size: 13px;
  margin-top: 4px;
}
.header-actions {
  display: flex;
  gap: 8px;
}
.stats-row {
  margin-bottom: 16px;
}
.stat-item {
  text-align: center;
  padding: 8px 0;
}
.stat-label {
  display: block;
  font-size: 13px;
  color: #909399;
  margin-bottom: 4px;
}
.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #303133;
}
.stat-value.warn { color: #e6a23c; }
.stat-value.success { color: #67c23a; }
.stat-value.primary { color: #409eff; }
.comment-text {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  font-size: 13px;
  color: #606266;
}
</style>
