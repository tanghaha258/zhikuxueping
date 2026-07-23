<script setup lang="ts">
/**
 * StudentDashboard - 学生工作台（Task 6 / 计划 3.7）。
 *
 * 首页三栏：项目概览、待办任务、近期反馈。
 * 全部基于真实接口数据，不使用静态占位或伪造累计积分。
 * - 项目概览：学生可见项目卡片，点击进入项目空间（/student/projects/:id）。
 * - 待办任务：未提交或退回待订正的任务，点击进入提交页。
 * - 近期反馈：订正轨迹中非草稿的最近记录，点击进入反馈视图。
 */
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { listProjectsApi } from '@/api/projects'
import { listMyTasksApi } from '@/api/tasks'
import { getGrowthPortfolioApi } from '@/features/student-space/api'
import {
  REVIEW_STATUS_LABELS,
  REVIEW_STATUS_TYPES,
} from '@/features/student-space/types'
import type {
  GrowthTrajectory,
  SubmissionReviewStatus,
} from '@/features/student-space/types'
import type { Project, Task } from '@/types'

const router = useRouter()
const userStore = useUserStore()

interface StatItem {
  title: string
  value: number
  icon: string
  color: string
}

const loading = ref(false)
const projects = ref<Project[]>([])
const tasks = ref<Task[]>([])
const trajectories = ref<GrowthTrajectory[]>([])

const stats = ref<StatItem[]>([
  { title: '待办任务', value: 0, icon: 'List', color: '#409EFF' },
  { title: '待批阅', value: 0, icon: 'View', color: '#E6A23C' },
  { title: '待订正', value: 0, icon: 'EditPen', color: '#F56C6C' },
  { title: '已完成', value: 0, icon: 'CircleCheck', color: '#67C23A' },
])

// ── 任务 → 项目标题映射 ───────────────────────────────────────
const projectMap = computed<Record<string, Project>>(() => {
  const m: Record<string, Project> = {}
  for (const p of projects.value) m[p.id] = p
  return m
})

const taskProjectMap = computed<Record<string, Project>>(() => {
  const m: Record<string, Project> = {}
  for (const t of tasks.value) {
    const p = projectMap.value[t.projectId]
    if (p) m[t.id] = p
  }
  return m
})

const trajectoryByTask = computed<Record<string, GrowthTrajectory>>(() => {
  const m: Record<string, GrowthTrajectory> = {}
  for (const tr of trajectories.value) m[tr.taskId] = tr
  return m
})

// ── 待办任务：无提交轨迹或轨迹为 draft/returned ─────────────────
const pendingTasks = computed(() =>
  tasks.value
    .map((t) => {
      const tr = trajectoryByTask.value[t.id]
      const status: SubmissionReviewStatus | undefined = tr?.reviewStatus
      const isPending =
        !tr || status === 'draft' || status === 'returned'
      return { task: t, trajectory: tr, isPending }
    })
    .filter((x) => x.isPending)
    .slice(0, 5),
)

// ── 近期反馈：非草稿的轨迹，按最近提交倒序 ─────────────────────
const recentFeedback = computed(() =>
  trajectories.value
    .filter((t) => t.reviewStatus !== 'draft')
    .slice()
    .sort((a, b) => {
      const ta = a.latestSubmittedAt ? Date.parse(a.latestSubmittedAt) : 0
      const tb = b.latestSubmittedAt ? Date.parse(b.latestSubmittedAt) : 0
      return tb - ta
    })
    .slice(0, 4),
)

// ── 项目概览：进行中或待审核的项目 ─────────────────────────────
const visibleProjects = computed(() =>
  projects.value
    .filter((p) => p.status === 'active' || p.status === 'pending_review')
    .slice(0, 6),
)

function goToProject(projectId: string) {
  router.push(`/student/projects/${projectId}`)
}

function goToSubmit(taskId: string) {
  router.push(`/student/tasks/${taskId}/submit`)
}

function goToFeedback(submissionId: string) {
  router.push(`/student/submissions/${submissionId}/feedback`)
}

function formatStatus(status: SubmissionReviewStatus | undefined): string {
  if (!status) return '待提交'
  return REVIEW_STATUS_LABELS[status] || status
}

function statusTagType(status: SubmissionReviewStatus | undefined): string {
  if (!status) return 'info'
  return REVIEW_STATUS_TYPES[status] || 'info'
}

async function fetchData() {
  loading.value = true
  try {
    const [projRes, taskRes] = await Promise.all([
      listProjectsApi({ limit: 200 }).catch(() => null),
      listMyTasksApi().catch(() => null),
    ])
    projects.value = projRes?.data?.data?.items || []
    tasks.value = taskRes?.data?.data || []

    // 成长档案接口提供订正轨迹（学生角色）；家长视角优雅降级
    const growthRes = await getGrowthPortfolioApi().catch(() => null)
    trajectories.value = growthRes?.data?.data?.trajectories || []
  } finally {
    loading.value = false
  }

  // 统计：基于真实轨迹计算
  const pendingCount = pendingTasks.value.length
  const awaitingReview = trajectories.value.filter((t) =>
    ['submitted', 'ai_reviewed', 'teacher_reviewed', 'resubmitted'].includes(
      t.reviewStatus,
    ),
  ).length
  const toCorrect = trajectories.value.filter(
    (t) => t.reviewStatus === 'returned',
  ).length
  const done = trajectories.value.filter(
    (t) => t.reviewStatus === 'finalized',
  ).length
  stats.value[0].value = pendingCount
  stats.value[1].value = awaitingReview
  stats.value[2].value = toCorrect
  stats.value[3].value = done
}

onMounted(fetchData)
</script>

<template>
  <div class="page-container" v-loading="loading">
    <!-- 欢迎区域 -->
    <div class="welcome-section">
      <div>
        <h2 class="welcome-title">你好，{{ userStore.displayName }}同学</h2>
        <p class="welcome-desc">保持学习节奏，今天也要加油哦！</p>
      </div>
      <el-button type="primary" @click="router.push('/student/tasks')">
        查看全部任务
      </el-button>
    </div>

    <!-- 统计卡片（真实数据，无伪造积分） -->
    <div class="stat-cards">
      <el-card v-for="stat in stats" :key="stat.title" shadow="hover" class="stat-card">
        <div class="stat-card-inner">
          <div class="stat-info">
            <p class="stat-value">{{ stat.value }}</p>
            <p class="stat-title">{{ stat.title }}</p>
          </div>
          <el-icon :size="40" :color="stat.color">
            <component :is="stat.icon" />
          </el-icon>
        </div>
      </el-card>
    </div>

    <!-- 项目概览 -->
    <el-card id="projects" shadow="never" class="page-section">
      <template #header>
        <div class="flex-between">
          <span class="card-title">项目概览</span>
          <span class="card-hint">点击项目进入项目空间</span>
        </div>
      </template>

      <div v-if="visibleProjects.length > 0" class="project-grid">
        <div
          v-for="p in visibleProjects"
          :key="p.id"
          class="project-card"
          @click="goToProject(p.id)"
        >
          <div class="project-card-header">
            <span class="project-title">{{ p.title }}</span>
            <el-tag
              size="small"
              :type="p.status === 'active' ? 'success' : 'warning'"
            >
              {{ p.status === 'active' ? '进行中' : '待审核' }}
            </el-tag>
          </div>
          <p class="project-desc">{{ p.description || '暂无描述' }}</p>
          <div v-if="p.grade" class="project-meta">年级：{{ p.grade }}</div>
        </div>
      </div>
      <el-empty v-else description="暂无可参与的项目" :image-size="60" />
    </el-card>

    <!-- 待办任务 + 近期反馈 -->
    <div class="two-col">
      <!-- 待办任务 -->
      <el-card shadow="never">
        <template #header>
          <div class="flex-between">
            <span class="card-title">待办任务</span>
            <el-link type="primary" :underline="false" @click="router.push('/student/tasks')">
              查看全部
            </el-link>
          </div>
        </template>

        <div v-for="item in pendingTasks" :key="item.task.id" class="task-item">
          <div class="task-info">
            <p class="task-name">{{ item.task.title }}</p>
            <div class="task-tags">
              <el-tag size="small" type="default">
                {{ taskProjectMap[item.task.id]?.title || '未关联项目' }}
              </el-tag>
              <el-tag size="small" :type="statusTagType(item.trajectory?.reviewStatus)">
                {{ formatStatus(item.trajectory?.reviewStatus) }}
              </el-tag>
            </div>
          </div>
          <el-button
            type="primary"
            size="small"
            @click="goToSubmit(item.task.id)"
          >
            {{ item.trajectory?.reviewStatus === 'returned' ? '去订正' : '去提交' }}
          </el-button>
        </div>

        <el-empty v-if="pendingTasks.length === 0" description="暂无待办任务" :image-size="60" />
      </el-card>

      <!-- 近期反馈 -->
      <el-card shadow="never">
        <template #header>
          <span class="card-title">近期反馈</span>
        </template>

        <div v-for="fb in recentFeedback" :key="fb.submissionId" class="feedback-item">
          <div class="feedback-header">
            <el-tag size="small" :type="statusTagType(fb.reviewStatus)">
              {{ formatStatus(fb.reviewStatus) }}
            </el-tag>
            <span v-if="fb.attemptCount > 1" class="feedback-attempt">
              第 {{ fb.attemptCount }} 次订正
            </span>
          </div>
          <p class="feedback-task">{{ fb.taskTitle || '任务' }}</p>
          <div class="feedback-footer">
            <span class="feedback-time">
              {{ fb.latestSubmittedAt ? new Date(fb.latestSubmittedAt).toLocaleDateString() : '—' }}
            </span>
            <el-link type="primary" :underline="false" @click="goToFeedback(fb.submissionId)">
              查看反馈
            </el-link>
          </div>
        </div>

        <el-empty v-if="recentFeedback.length === 0" description="暂无反馈记录" :image-size="60" />
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.welcome-section {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
  gap: 12px;
  flex-wrap: wrap;
}

.welcome-title {
  font-size: 22px;
  font-weight: 600;
  color: #303133;
  margin: 0;
}

.welcome-desc {
  font-size: 14px;
  color: #909399;
  margin: 6px 0 0;
}

.stat-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.stat-card {
  border-radius: 8px;
}

.stat-card-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.stat-value {
  font-size: 32px;
  font-weight: 700;
  color: #303133;
  margin: 0;
}

.stat-title {
  font-size: 14px;
  color: #909399;
  margin: 4px 0 0;
}

.page-section {
  margin-bottom: 20px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
}

.card-hint {
  font-size: 12px;
  color: #909399;
}

.flex-between {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.project-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.project-card {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.project-card:hover {
  border-color: #409eff;
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.12);
}

.project-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.project-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.project-desc {
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
  margin: 0 0 8px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.project-meta {
  font-size: 12px;
  color: #909399;
}

.two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.task-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid #f0f0f0;
  gap: 12px;
}

.task-item:last-child {
  border-bottom: none;
}

.task-info {
  flex: 1;
  min-width: 0;
}

.task-name {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
  margin: 0 0 6px;
}

.task-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.feedback-item {
  padding: 12px 0;
  border-bottom: 1px solid #f0f0f0;
}

.feedback-item:last-child {
  border-bottom: none;
}

.feedback-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.feedback-attempt {
  font-size: 12px;
  color: #e6a23c;
}

.feedback-task {
  font-size: 14px;
  color: #303133;
  margin: 0 0 6px;
}

.feedback-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.feedback-time {
  font-size: 12px;
  color: #909399;
}

/* 平板 1024x768 */
@media (max-width: 1024px) {
  .project-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

/* 移动端 390x844 */
@media (max-width: 768px) {
  .stat-cards {
    grid-template-columns: repeat(2, 1fr);
  }
  .project-grid {
    grid-template-columns: 1fr;
  }
  .two-col {
    grid-template-columns: 1fr;
  }
  .welcome-title {
    font-size: 18px;
  }
}
</style>
