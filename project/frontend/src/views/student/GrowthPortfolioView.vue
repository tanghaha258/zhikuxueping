<script setup lang="ts">
/**
 * GrowthPortfolioView - 学生成长档案（Task 6 / 计划 3.7.5）。
 *
 * 展示：
 * - 证据摘要：已发布评价总数、平均分、按来源分布（不公开横向排名）。
 * - 订正轨迹：每个提交线程的订正次数、状态、是否经过二次评价。
 * - 改进轨迹：高亮有多次订正或二次评价的线程，体现学习改进过程。
 *
 * 数据来自 GET /student/growth；缺失周期显示"未采集"，不补零。
 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getGrowthPortfolioApi } from '@/features/student-space/api'
import {
  EVAL_SOURCE_LABELS,
  REVIEW_STATUS_LABELS,
  REVIEW_STATUS_TYPES,
} from '@/features/student-space/types'
import type {
  GrowthPortfolio as PortfolioData,
  GrowthTrajectory,
} from '@/features/student-space/types'

const router = useRouter()

const data = ref<PortfolioData | null>(null)
const loading = ref(false)

const trajectories = computed<GrowthTrajectory[]>(() => data.value?.trajectories || [])
const evidenceSummary = computed(() => data.value?.evidenceSummary || null)
const note = computed(() => data.value?.note || '')

// ── 改进轨迹：有多次订正或二次评价的线程 ───────────────────────
const improvementTrajectories = computed(() =>
  trajectories.value.filter((t) => t.attemptCount > 1 || t.hasReassessment),
)

// ── 轨迹按最近提交倒序 ───────────────────────────────────────
const sortedTrajectories = computed(() =>
  trajectories.value
    .slice()
    .sort((a, b) => {
      const ta = a.latestSubmittedAt ? Date.parse(a.latestSubmittedAt) : 0
      const tb = b.latestSubmittedAt ? Date.parse(b.latestSubmittedAt) : 0
      return tb - ta
    }),
)

const sourceBreakdown = computed(() => {
  const bySource = evidenceSummary.value?.bySource || {}
  return Object.entries(bySource).map(([key, count]) => ({
    source: key,
    label: EVAL_SOURCE_LABELS[key] || key,
    count,
  }))
})

const averageScoreDisplay = computed(() => {
  const score = evidenceSummary.value?.averageScore
  if (score === null || score === undefined) return '未采集'
  return score.toFixed(1)
})

function statusLabel(status: string): string {
  return REVIEW_STATUS_LABELS[status as keyof typeof REVIEW_STATUS_LABELS] || status
}

function statusType(status: string): string {
  return REVIEW_STATUS_TYPES[status as keyof typeof REVIEW_STATUS_TYPES] || 'info'
}

function formatTime(t?: string | null): string {
  return t ? new Date(t).toLocaleDateString() : '—'
}

function goToFeedback(submissionId: string) {
  router.push(`/student/submissions/${submissionId}/feedback`)
}

async function fetchData() {
  loading.value = true
  try {
    const res = await getGrowthPortfolioApi()
    data.value = res.data.data
  } catch {
    ElMessage.error('加载成长档案失败')
  } finally {
    loading.value = false
  }
}

onMounted(fetchData)
</script>

<template>
  <div class="page-container" v-loading="loading">
    <h2 class="page-title">成长档案</h2>

    <!-- 证据摘要 -->
    <el-card shadow="never" class="page-section">
      <template #header>
        <span class="card-title">证据摘要</span>
      </template>
      <div class="summary-grid">
        <div class="summary-item">
          <div class="summary-value">{{ evidenceSummary?.totalEvaluations ?? 0 }}</div>
          <div class="summary-label">已发布评价</div>
        </div>
        <div class="summary-item">
          <div class="summary-value">{{ averageScoreDisplay }}</div>
          <div class="summary-label">平均分</div>
        </div>
        <div class="summary-item">
          <div class="summary-value">{{ trajectories.length }}</div>
          <div class="summary-label">提交线程</div>
        </div>
        <div class="summary-item">
          <div class="summary-value">{{ improvementTrajectories.length }}</div>
          <div class="summary-label">改进轨迹</div>
        </div>
      </div>

      <div v-if="sourceBreakdown.length > 0" class="source-breakdown">
        <span class="source-title">评价来源分布</span>
        <div class="source-list">
          <el-tag
            v-for="s in sourceBreakdown"
            :key="s.source"
            type="info"
            class="source-tag"
          >
            {{ s.label }}：{{ s.count }}
          </el-tag>
        </div>
      </div>

      <el-alert
        v-if="note"
        type="info"
        :closable="false"
        show-icon
        style="margin-top: 12px;"
      >
        <div>{{ note }}</div>
      </el-alert>
    </el-card>

    <!-- 改进轨迹 -->
    <el-card v-if="improvementTrajectories.length > 0" shadow="never" class="page-section">
      <template #header>
        <span class="card-title">改进轨迹（{{ improvementTrajectories.length }}）</span>
      </template>
      <p class="section-desc">以下任务经过多次订正或二次评价，体现了你的改进过程：</p>
      <div class="trajectory-list">
        <div
          v-for="t in improvementTrajectories"
          :key="t.submissionId"
          class="trajectory-card highlight"
          @click="goToFeedback(t.submissionId)"
        >
          <div class="trajectory-header">
            <span class="trajectory-title">{{ t.taskTitle || '任务' }}</span>
            <el-tag size="small" :type="statusType(t.reviewStatus) as any">
              {{ statusLabel(t.reviewStatus) }}
            </el-tag>
          </div>
          <div class="trajectory-meta">
            <span>订正 {{ t.attemptCount }} 次</span>
            <el-tag v-if="t.hasReassessment" size="small" type="warning">含二次评价</el-tag>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 全部订正轨迹 -->
    <el-card shadow="never" class="page-section">
      <template #header>
        <span class="card-title">订正轨迹（{{ trajectories.length }}）</span>
      </template>
      <div v-if="sortedTrajectories.length > 0" class="trajectory-list">
        <div
          v-for="t in sortedTrajectories"
          :key="t.submissionId"
          class="trajectory-card"
          @click="goToFeedback(t.submissionId)"
        >
          <div class="trajectory-header">
            <span class="trajectory-title">{{ t.taskTitle || '任务' }}</span>
            <el-tag size="small" :type="statusType(t.reviewStatus) as any">
              {{ statusLabel(t.reviewStatus) }}
            </el-tag>
          </div>
          <div class="trajectory-meta">
            <span>订正 {{ t.attemptCount }} 次</span>
            <span>首次：{{ formatTime(t.firstSubmittedAt) }}</span>
            <span>最近：{{ formatTime(t.latestSubmittedAt) }}</span>
            <el-tag v-if="t.hasReassessment" size="small" type="warning">二次评价</el-tag>
          </div>
        </div>
      </div>
      <el-empty v-else description="暂无订正轨迹" :image-size="60" />
    </el-card>
  </div>
</template>

<style scoped>
.page-title {
  font-size: 22px;
  font-weight: 600;
  color: #303133;
  margin: 0 0 20px;
}

.page-section {
  margin-bottom: 20px;
  border-radius: 8px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
}

.section-desc {
  font-size: 13px;
  color: #909399;
  margin: 0 0 12px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.summary-item {
  text-align: center;
  background: #f5f7fa;
  border-radius: 8px;
  padding: 16px 8px;
}

.summary-value {
  font-size: 28px;
  font-weight: 700;
  color: #303133;
}

.summary-label {
  font-size: 13px;
  color: #909399;
  margin-top: 6px;
}

.source-breakdown {
  margin-top: 16px;
}

.source-title {
  font-size: 13px;
  color: #606266;
  font-weight: 500;
  display: block;
  margin-bottom: 8px;
}

.source-list {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.source-tag {
  font-size: 13px;
}

.trajectory-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.trajectory-card {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.trajectory-card:hover {
  border-color: #409eff;
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.1);
}

.trajectory-card.highlight {
  border-left: 3px solid #67c23a;
}

.trajectory-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.trajectory-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.trajectory-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  color: #909399;
  flex-wrap: wrap;
}

/* 平板与移动端响应式 */
@media (max-width: 1024px) {
  .summary-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .summary-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .summary-value {
    font-size: 22px;
  }
  .trajectory-meta {
    gap: 8px;
  }
}
</style>
