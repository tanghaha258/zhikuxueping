<script setup lang="ts">
/**
 * 跨项目任务中心（Task 9）。
 *
 * - 默认聚合所有可管理项目的待发布、进行中、临期、未提交、待关闭任务。
 * - 任务中心只负责分类与跳转，不保留独立创建正式任务入口（无第二套编辑逻辑）。
 * - 编辑动作跳转到项目工作台，由项目任务链页承载创建/编辑。
 */
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getTaskCenterApi } from '@/api/tasks'
import type { TaskCenterItemDTO } from '@/api/tasks'
// DUE_SOON_DAYS / buildTaskCenterBuckets / emptyTaskCenterBuckets /
// TaskCenterItem / TaskCenterBuckets 由下方 <script lang="ts"> 块导出，
// 同一 SFC 模块内 <script setup> 可直接访问，无需自引用导入。

const router = useRouter()
const loading = ref(false)
const buckets = ref<TaskCenterBuckets>(emptyTaskCenterBuckets())

const PUBLISH_STATUS_LABELS: Record<string, string> = {
  draft: '草稿',
  scheduled: '定时',
  published: '已发布',
  in_progress: '进行中',
  closed: '已关闭',
  archived: '已归档',
}

const PUBLISH_STATUS_TYPES: Record<string, string> = {
  draft: 'info',
  scheduled: 'warning',
  published: 'primary',
  in_progress: 'success',
  closed: '',
  archived: '',
}

function dtoToItem(dto: TaskCenterItemDTO): TaskCenterItem {
  return {
    id: dto.id,
    title: dto.title,
    projectId: dto.projectId,
    projectTitle: dto.projectTitle,
    taskType: dto.taskType,
    maxScore: dto.maxScore,
    submissionCount: dto.submissionCount,
    totalStudents: dto.totalStudents,
    publishStatus: dto.publishStatus || 'draft',
    deadline: dto.deadline,
    stage: dto.stage,
    tier: dto.tier,
  }
}

async function loadCenter() {
  loading.value = true
  try {
    const res = await getTaskCenterApi()
    const data = res.data.data
    const items: TaskCenterItem[] = [
      ...data.toPublish.map(dtoToItem),
      ...data.inProgress.map(dtoToItem),
      ...data.dueSoon.map(dtoToItem),
      ...data.unsubmitted.map(dtoToItem),
      ...data.toClose.map(dtoToItem),
    ]
    // 去重（同一任务可能出现在多个桶中）
    const seen = new Set<string>()
    const unique: TaskCenterItem[] = []
    for (const it of items) {
      if (!seen.has(it.id)) {
        seen.add(it.id)
        unique.push(it)
      }
    }
    buckets.value = buildTaskCenterBuckets(unique, new Date())
  } catch {
    ElMessage.error('加载任务中心失败')
    buckets.value = emptyTaskCenterBuckets()
  } finally {
    loading.value = false
  }
}

function jumpToProject(projectId: string) {
  router.push(`/teacher/projects/${projectId}`)
}

function formatDeadline(deadline?: string): string {
  if (!deadline) return '未设置'
  const d = new Date(deadline)
  if (isNaN(d.getTime())) return deadline
  return d.toLocaleDateString()
}

onMounted(loadCenter)
</script>

<script lang="ts">
/**
 * Task 9 跨项目任务中心纯函数（供 task-center.test.ts 测试与组件复用）。
 *
 * 分类规则（与后端 get_task_center 对齐）：
 * - to_publish：publish_status 为 draft/scheduled
 * - in_progress：publish_status 为 published/in_progress
 * - due_soon：进行中且截止时间在 DUE_SOON_DAYS 天内
 * - unsubmitted：进行中且有未提交学生（submissionCount < totalStudents）
 * - to_close：publish_status 为 in_progress（待教师关闭）
 */

export const DUE_SOON_DAYS = 3

export type BucketName = 'to_publish' | 'in_progress' | 'due_soon' | 'unsubmitted' | 'to_close'

export interface TaskCenterItem {
  id: string
  title: string
  projectId: string
  projectTitle: string
  taskType: string
  maxScore: number
  submissionCount: number
  totalStudents: number
  publishStatus: string
  deadline?: string
  stage?: string
  tier?: string
}

export interface TaskCenterBuckets {
  to_publish: TaskCenterItem[]
  in_progress: TaskCenterItem[]
  due_soon: TaskCenterItem[]
  unsubmitted: TaskCenterItem[]
  to_close: TaskCenterItem[]
}

export function emptyTaskCenterBuckets(): TaskCenterBuckets {
  return {
    to_publish: [],
    in_progress: [],
    due_soon: [],
    unsubmitted: [],
    to_close: [],
  }
}

export function isDueSoon(
  deadline: string | undefined,
  now: Date,
  days: number = DUE_SOON_DAYS,
): boolean {
  if (!deadline) return false
  const d = new Date(deadline)
  if (isNaN(d.getTime())) return false
  const deltaMs = d.getTime() - now.getTime()
  if (deltaMs < 0) return false
  return deltaMs <= days * 24 * 60 * 60 * 1000
}

export function categorizeTask(item: TaskCenterItem, now: Date): BucketName[] {
  const cats: BucketName[] = []
  const ps = item.publishStatus
  if (ps === 'draft' || ps === 'scheduled') {
    cats.push('to_publish')
  } else if (ps === 'published' || ps === 'in_progress') {
    cats.push('in_progress')
    if (isDueSoon(item.deadline, now)) {
      cats.push('due_soon')
    }
    if (item.totalStudents > 0 && item.submissionCount < item.totalStudents) {
      cats.push('unsubmitted')
    }
    if (ps === 'in_progress') {
      cats.push('to_close')
    }
  }
  // closed / archived → 不归入任何待办桶
  return cats
}

export function buildTaskCenterBuckets(
  items: TaskCenterItem[],
  now: Date,
): TaskCenterBuckets {
  const buckets = emptyTaskCenterBuckets()
  for (const item of items) {
    const cats = categorizeTask(item, now)
    for (const cat of cats) {
      buckets[cat].push(item)
    }
  }
  return buckets
}
</script>

<template>
  <div class="page-container">
    <div class="flex-between" style="margin-bottom: 20px;">
      <h2 class="page-title" style="margin-bottom: 0;">任务中心</h2>
      <el-button @click="loadCenter" :loading="loading">刷新</el-button>
    </div>

    <el-card shadow="never" v-loading="loading">
      <template #header>
        <span style="font-weight: 600;">待发布（草稿 / 定时）</span>
        <el-tag style="margin-left: 8px;" size="small">{{ buckets.to_publish.length }}</el-tag>
      </template>
      <el-empty v-if="buckets.to_publish.length === 0" description="暂无待发布任务" :image-size="60" />
      <div v-else class="task-card-list">
        <div v-for="t in buckets.to_publish" :key="t.id" class="task-card">
          <div class="task-card-header">
            <span class="task-card-title">{{ t.title }}</span>
            <el-tag size="small" :type="(PUBLISH_STATUS_TYPES[t.publishStatus] as any)">
              {{ PUBLISH_STATUS_LABELS[t.publishStatus] || t.publishStatus }}
            </el-tag>
          </div>
          <div class="task-card-meta">
            <span>{{ t.projectTitle }}</span>
            <span>截止：{{ formatDeadline(t.deadline) }}</span>
          </div>
          <div class="task-card-actions">
            <el-button text type="primary" size="small" @click="jumpToProject(t.projectId)">前往项目</el-button>
          </div>
        </div>
      </div>
    </el-card>

    <el-card shadow="never" style="margin-top: 16px;" v-loading="loading">
      <template #header>
        <span style="font-weight: 600;">进行中</span>
        <el-tag style="margin-left: 8px;" size="small">{{ buckets.in_progress.length }}</el-tag>
      </template>
      <el-empty v-if="buckets.in_progress.length === 0" description="暂无进行中任务" :image-size="60" />
      <div v-else class="task-card-list">
        <div v-for="t in buckets.in_progress" :key="t.id" class="task-card">
          <div class="task-card-header">
            <span class="task-card-title">{{ t.title }}</span>
            <el-tag size="small" :type="(PUBLISH_STATUS_TYPES[t.publishStatus] as any)">
              {{ PUBLISH_STATUS_LABELS[t.publishStatus] || t.publishStatus }}
            </el-tag>
          </div>
          <div class="task-card-meta">
            <span>{{ t.projectTitle }}</span>
            <span>提交：{{ t.submissionCount }}/{{ t.totalStudents }}</span>
            <span>截止：{{ formatDeadline(t.deadline) }}</span>
          </div>
          <div class="task-card-actions">
            <el-button text type="primary" size="small" @click="jumpToProject(t.projectId)">前往项目</el-button>
          </div>
        </div>
      </div>
    </el-card>

    <el-card shadow="never" style="margin-top: 16px;" v-loading="loading">
      <template #header>
        <span style="font-weight: 600;">临期（{{ DUE_SOON_DAYS }} 天内截止）</span>
        <el-tag style="margin-left: 8px;" size="small" type="danger">{{ buckets.due_soon.length }}</el-tag>
      </template>
      <el-empty v-if="buckets.due_soon.length === 0" description="暂无临期任务" :image-size="60" />
      <div v-else class="task-card-list">
        <div v-for="t in buckets.due_soon" :key="t.id" class="task-card">
          <div class="task-card-header">
            <span class="task-card-title">{{ t.title }}</span>
            <el-tag size="small" type="danger">临期</el-tag>
          </div>
          <div class="task-card-meta">
            <span>{{ t.projectTitle }}</span>
            <span>截止：{{ formatDeadline(t.deadline) }}</span>
          </div>
          <div class="task-card-actions">
            <el-button text type="primary" size="small" @click="jumpToProject(t.projectId)">前往项目</el-button>
          </div>
        </div>
      </div>
    </el-card>

    <el-card shadow="never" style="margin-top: 16px;" v-loading="loading">
      <template #header>
        <span style="font-weight: 600;">未提交</span>
        <el-tag style="margin-left: 8px;" size="small" type="warning">{{ buckets.unsubmitted.length }}</el-tag>
      </template>
      <el-empty v-if="buckets.unsubmitted.length === 0" description="暂无未提交任务" :image-size="60" />
      <div v-else class="task-card-list">
        <div v-for="t in buckets.unsubmitted" :key="t.id" class="task-card">
          <div class="task-card-header">
            <span class="task-card-title">{{ t.title }}</span>
          </div>
          <div class="task-card-meta">
            <span>{{ t.projectTitle }}</span>
            <span>未提交：{{ t.totalStudents - t.submissionCount }}/{{ t.totalStudents }}</span>
          </div>
          <div class="task-card-actions">
            <el-button text type="primary" size="small" @click="jumpToProject(t.projectId)">前往项目</el-button>
          </div>
        </div>
      </div>
    </el-card>

    <el-card shadow="never" style="margin-top: 16px;" v-loading="loading">
      <template #header>
        <span style="font-weight: 600;">待关闭</span>
        <el-tag style="margin-left: 8px;" size="small">{{ buckets.to_close.length }}</el-tag>
      </template>
      <el-empty v-if="buckets.to_close.length === 0" description="暂无待关闭任务" :image-size="60" />
      <div v-else class="task-card-list">
        <div v-for="t in buckets.to_close" :key="t.id" class="task-card">
          <div class="task-card-header">
            <span class="task-card-title">{{ t.title }}</span>
            <el-tag size="small" type="success">进行中</el-tag>
          </div>
          <div class="task-card-meta">
            <span>{{ t.projectTitle }}</span>
            <span>提交：{{ t.submissionCount }}/{{ t.totalStudents }}</span>
          </div>
          <div class="task-card-actions">
            <el-button text type="primary" size="small" @click="jumpToProject(t.projectId)">前往项目</el-button>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.task-card-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.task-card {
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 12px 16px;
  background: #fafafa;
}
.task-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.task-card-title {
  font-weight: 600;
  font-size: 14px;
}
.task-card-meta {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: #909399;
  margin-bottom: 8px;
}
.task-card-actions {
  display: flex;
  gap: 8px;
}
</style>
