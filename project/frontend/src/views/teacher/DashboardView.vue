<script lang="ts">
/**
 * 教师工作台类型与纯函数（Task 5）。
 *
 * 纯函数（partitionWorkbench / computeWorkbenchMetrics / itemLabelOf）
 * 单独导出，便于在不挂载组件的情况下单元测试。
 * 字段命名使用 camelCase，与前端拦截器转换后的响应一致。
 */

/** 工作台待办条目（各分区共用结构；按需携带附加字段）。 */
export interface WorkbenchItem {
  id: string
  projectId: string
  projectTitle?: string
  route: string
  title?: string
  taskTitle?: string
  message?: string
  scene?: string
  status?: string
  publishStatus?: string
  reviewStatus?: string
  submittedAt?: string | null
  confirmedAt?: string | null
  deadline?: string | null
  daysLeft?: number | null
  createdAt?: string | null
  studentId?: string
  /** 计算后的展示标签，由 partitionWorkbench 填充。 */
  label?: string
}

/** 活跃项目摘要。 */
export interface WorkbenchActiveProject {
  id: string
  title: string
  status: string
  currentPhase?: string | null
  currentPhaseLabel?: string | null
  completion?: number
  route: string
}

export interface TeacherWorkbenchData {
  activeProjects: WorkbenchActiveProject[]
  tasksToPublish: WorkbenchItem[]
  submissionsToReview: WorkbenchItem[]
  feedbackToPublish: WorkbenchItem[]
  aiToReview: WorkbenchItem[]
  deadlines: WorkbenchItem[]
  learningAlerts: WorkbenchItem[]
}

export interface WorkbenchSection {
  key: string
  title: string
  emptyHint: string
  items: WorkbenchItem[]
}

/** 各分区的展示标签计算；不伪造内容，缺失时回退到项目名或占位。 */
export function itemLabelOf(key: keyof TeacherWorkbenchData, item: WorkbenchItem): string {
  switch (key) {
    case 'tasksToPublish':
      return item.title ?? '未命名任务'
    case 'submissionsToReview':
      return item.taskTitle ?? '待复核提交'
    case 'feedbackToPublish':
      return item.projectTitle ? `${item.projectTitle} · 评价待发布` : '评价待发布'
    case 'aiToReview':
      return item.scene ? `${item.scene} · AI 待确认` : 'AI 任务待确认'
    case 'deadlines':
      return item.title ?? '临近截止任务'
    case 'learningAlerts':
      return item.message ?? '学习预警'
    default:
      return item.title ?? item.projectTitle ?? '—'
  }
}

/** 将工作台数据映射为紧凑待办分区列表；空数据时各分区 items 为空，不伪造。 */
export function partitionWorkbench(data: TeacherWorkbenchData): WorkbenchSection[] {
  const sections: Array<{
    key: keyof TeacherWorkbenchData
    title: string
    emptyHint: string
  }> = [
    { key: 'tasksToPublish', title: '待发布任务', emptyHint: '暂无草稿任务待发布' },
    { key: 'submissionsToReview', title: '待复核提交', emptyHint: '暂无待复核提交' },
    { key: 'feedbackToPublish', title: '待发布评价', emptyHint: '暂无待发布评价' },
    { key: 'aiToReview', title: 'AI 待确认', emptyHint: '暂无 AI 待确认' },
    { key: 'deadlines', title: '临近截止', emptyHint: '近 7 天无截止任务' },
    { key: 'learningAlerts', title: '学习预警', emptyHint: '暂无学习预警' },
  ]
  return sections.map((s) => {
    const raw = (data[s.key] as unknown as WorkbenchItem[]) ?? []
    return {
      key: s.key,
      title: s.title,
      emptyHint: s.emptyHint,
      items: raw.map((it) => ({ ...it, label: itemLabelOf(s.key, it) })),
    }
  })
}

export interface WorkbenchMetric {
  label: string
  value: number
  hint?: string
}

/** 计算工作台指标条数字；全部来自真实计数，不伪造。 */
export function computeWorkbenchMetrics(data: TeacherWorkbenchData): WorkbenchMetric[] {
  return [
    { label: '活跃项目', value: data.activeProjects.length },
    { label: '待发布任务', value: data.tasksToPublish.length },
    { label: '待复核提交', value: data.submissionsToReview.length },
    { label: '待发布评价', value: data.feedbackToPublish.length },
    { label: 'AI 待确认', value: data.aiToReview.length },
    { label: '临近截止', value: data.deadlines.length },
    { label: '学习预警', value: data.learningAlerts.length },
  ]
}

/** 空工作台数据，用于初始化与测试夹具。 */
export function emptyWorkbenchData(): TeacherWorkbenchData {
  return {
    activeProjects: [],
    tasksToPublish: [],
    submissionsToReview: [],
    feedbackToPublish: [],
    aiToReview: [],
    deadlines: [],
    learningAlerts: [],
  }
}
</script>

<script setup lang="ts">
/**
 * 教师工作台页面（Task 5 重写）。
 *
 * 设计要点（计划 Task 5 Step 2 / 规格 §5.1）：
 * - 紧凑待办分区，不显示静态待办；每项操作直接进入所属项目和阶段。
 * - 所有数据来自 /dashboard/teacher-workbench 真实接口；失败显示错误与重试。
 * - 复用 shared UI 基座（PageHeader、AsyncState、MetricStrip），不重复造样式。
 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import http from '@/api'
import { useUserStore } from '@/stores/user'
import PageHeader from '@/shared/ui/PageHeader.vue'
import AsyncState from '@/shared/ui/AsyncState.vue'
import MetricStrip from '@/shared/ui/MetricStrip.vue'
import type { ApiResponse } from '@/types'

const router = useRouter()
const userStore = useUserStore()

const data = ref<TeacherWorkbenchData | null>(null)
const loading = ref(false)
const errorMsg = ref<string>('')

const sections = computed<WorkbenchSection[]>(() =>
  data.value ? partitionWorkbench(data.value) : [],
)
const metrics = computed<WorkbenchMetric[]>(() =>
  data.value ? computeWorkbenchMetrics(data.value) : [],
)
const activeProjects = computed(() => data.value?.activeProjects ?? [])

const asyncState = computed<'loading' | 'ready' | 'empty' | 'error' | 'forbidden'>(() => {
  if (loading.value && !data.value) return 'loading'
  if (errorMsg.value && !data.value) return 'error'
  if (!data.value) return 'loading'
  return 'ready'
})

async function load() {
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await http.get<ApiResponse<TeacherWorkbenchData>>(
      '/dashboard/teacher-workbench',
    )
    data.value = res.data.data
  } catch (e) {
    errorMsg.value = (e as Error)?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

function goto(route: string | undefined) {
  if (!route) return
  router.push(route)
}

onMounted(load)
</script>

<template>
  <div class="teacher-workbench" data-ui="teacher-workbench">
    <PageHeader
      :title="`欢迎回来，${userStore.displayName}老师`"
      subtitle="以下是您可管理范围的真实待办与活跃项目"
    />

    <AsyncState :state="asyncState" :message="errorMsg" @retry="load">
      <div class="workbench-body">
        <MetricStrip :metrics="metrics" />

        <!-- 活跃项目 -->
        <section class="workbench-block" data-ui="active-projects">
          <div class="block-head">
            <h3 class="block-title">活跃项目</h3>
            <span class="block-count">{{ activeProjects.length }}</span>
          </div>
          <div v-if="activeProjects.length === 0" class="block-empty">
            暂无活跃项目
          </div>
          <button
            v-for="p in activeProjects"
            :key="p.id"
            type="button"
            class="workbench-row"
            data-ui="active-project-item"
            @click="goto(p.route)"
          >
            <span class="row-title">{{ p.title }}</span>
            <span v-if="p.currentPhaseLabel" class="row-meta">{{ p.currentPhaseLabel }}</span>
            <span class="row-completion">{{ Math.round((p.completion ?? 0) * 100) }}%</span>
          </button>
        </section>

        <!-- 紧凑待办分区 -->
        <section
          v-for="section in sections"
          :key="section.key"
          class="workbench-block"
          :data-ui="`section-${section.key}`"
        >
          <div class="block-head">
            <h3 class="block-title">{{ section.title }}</h3>
            <span class="block-count">{{ section.items.length }}</span>
          </div>
          <div v-if="section.items.length === 0" class="block-empty">
            {{ section.emptyHint }}
          </div>
          <button
            v-for="item in section.items"
            :key="item.id"
            type="button"
            class="workbench-row"
            :data-ui="`item-${section.key}`"
            @click="goto(item.route)"
          >
            <span class="row-title">{{ item.label }}</span>
            <span v-if="item.projectTitle" class="row-meta">{{ item.projectTitle }}</span>
            <span v-if="item.daysLeft !== undefined && item.daysLeft !== null" class="row-deadline">
              {{ item.daysLeft }} 天后截止
            </span>
          </button>
        </section>
      </div>
    </AsyncState>
  </div>
</template>

<style scoped>
.teacher-workbench {
  display: flex;
  flex-direction: column;
  gap: var(--ui-space-4, 16px);
  padding: var(--ui-space-4, 16px) var(--ui-space-6, 24px);
  max-width: 1080px;
}

.workbench-body {
  display: flex;
  flex-direction: column;
  gap: var(--ui-space-4, 16px);
}

.workbench-block {
  background: var(--ui-bg-surface, #fff);
  border: 1px solid var(--ui-border-light, #e4e7eb);
  border-radius: var(--ui-radius-md, 6px);
  padding: var(--ui-space-3, 12px) var(--ui-space-4, 16px);
}

.block-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--ui-space-2, 8px);
}

.block-title {
  margin: 0;
  font-size: var(--ui-font-size-sm, 14px);
  font-weight: 600;
  color: var(--ui-text-primary, #1f2933);
}

.block-count {
  font-size: var(--ui-font-size-xs, 12px);
  color: var(--ui-text-muted, #7b8794);
  padding: 2px var(--ui-space-2, 8px);
  background: var(--ui-bg-subtle, #f4f6f8);
  border-radius: var(--ui-radius-sm, 4px);
}

.block-empty {
  font-size: var(--ui-font-size-sm, 14px);
  color: var(--ui-text-muted, #7b8794);
  padding: var(--ui-space-2, 8px) 0;
}

.workbench-row {
  display: flex;
  align-items: center;
  gap: var(--ui-space-3, 12px);
  width: 100%;
  text-align: left;
  background: transparent;
  border: none;
  border-bottom: 1px solid var(--ui-border-light, #f0f2f5);
  padding: var(--ui-space-2, 8px) 0;
  cursor: pointer;
  font: inherit;
  color: var(--ui-text-primary, #1f2933);
}

.workbench-row:last-child {
  border-bottom: none;
}

.workbench-row:hover {
  background: var(--ui-bg-subtle, #f8f9fb);
}

.row-title {
  flex: 1 1 auto;
  font-size: var(--ui-font-size-sm, 14px);
  min-width: 0;
}

.row-meta {
  font-size: var(--ui-font-size-xs, 12px);
  color: var(--ui-text-muted, #7b8794);
  white-space: nowrap;
}

.row-completion {
  font-size: var(--ui-font-size-xs, 12px);
  font-weight: 600;
  color: var(--ui-primary, #2c6cf6);
}

.row-deadline {
  font-size: var(--ui-font-size-xs, 12px);
  color: var(--ui-warning, #d97706);
  white-space: nowrap;
}
</style>
