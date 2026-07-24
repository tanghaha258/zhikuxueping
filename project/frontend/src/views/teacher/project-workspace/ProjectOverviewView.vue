<script setup lang="ts">
/**
 * ProjectOverviewView - 项目总览（Task 5 重写）。
 *
 * 设计要点（计划 Task 5 Step 3 / 规格 §5.2）：
 * - 固定显示：阶段进度、唯一下一步、学生参与、未发布评价、AI待确认、阻断清单和真实时间线。
 * - 所有数字来自 project-context store 的 counts（真实计数），不伪造。
 * - 删除"后续Task实现"类页面文案；缺失项如实显示。
 * - 复用 shared UI 基座（MetricStrip、InlineAlert、StatusBadge），不重复造样式。
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useProjectContextStore } from '@/features/project-context/store'
import type {
  PhaseKey,
  ProjectWorkspacePhase,
  ProjectWorkspaceTimelineEvent,
} from '@/features/project-context/types'
import MetricStrip from '@/shared/ui/MetricStrip.vue'
import InlineAlert from '@/shared/ui/InlineAlert.vue'
import StatusBadge from '@/shared/ui/StatusBadge.vue'
import { formatDate } from '@/utils/format'

const route = useRoute()
const router = useRouter()
const store = useProjectContextStore()
const projectId = computed(() => route.params.id as string)

const timeline = ref<ProjectWorkspaceTimelineEvent[]>([])
const timelineLoading = ref(false)
const timelineError = ref<string>('')

// ── 阶段标签（与后端 PHASE_ORDER 单一来源一致）──────────────────
const PHASE_LABELS: Record<PhaseKey, string> = {
  diagnosis: '学情诊断',
  design: '跨学科设计',
  preparation: '备课与准备',
  implementation: '教学实施',
  evaluation: '评价与反馈',
  improvement: '改进与再评价',
  closure: '结项',
}

const PHASE_ROUTE: Record<PhaseKey, string> = {
  diagnosis: 'diagnosis',
  design: 'design',
  preparation: 'preparation',
  implementation: 'tasks',
  evaluation: 'evaluation',
  improvement: 'insights',
  closure: 'closure',
}

// ── 派生状态 ───────────────────────────────────────────────────
const context = computed(() => store.currentContext)
const phases = computed<ProjectWorkspacePhase[]>(() => context.value?.phases ?? [])
const blockers = computed(() => context.value?.blockers ?? [])
const warnings = computed(() => context.value?.warnings ?? [])
const counts = computed(() => context.value?.counts ?? null)
const nextAction = computed(() => context.value?.nextAction ?? null)
const archived = computed(() => store.isArchived)

const completionPct = computed(() => {
  const total = phases.value.length
  if (total === 0) return 0
  const done = phases.value.filter((p) => p.status === 'completed').length
  return Math.round((done / total) * 100)
})

type MetricTone = 'default' | 'primary' | 'success' | 'warning' | 'danger'

const metrics = computed(() => {
  const c = counts.value
  const unpublished = c?.unpublishedEvaluations ?? 0
  const pendingAi = c?.pendingAiReviews ?? 0
  return [
    { label: '学生', value: c?.students ?? 0 },
    { label: '任务', value: c?.tasks ?? 0 },
    { label: '已发布', value: c?.publishedTasks ?? 0 },
    { label: '提交', value: c?.submissions ?? 0 },
    {
      label: '未发布评价',
      value: unpublished,
      tone: (unpublished > 0 ? 'warning' : 'default') as MetricTone,
    },
    {
      label: 'AI 待确认',
      value: pendingAi,
      tone: (pendingAi > 0 ? 'warning' : 'default') as MetricTone,
    },
  ]
})

function gotoPhase(phase: PhaseKey) {
  if (archived.value) return
  router.push(`/teacher/projects/${projectId.value}/${PHASE_ROUTE[phase]}`)
}

function gotoNextAction() {
  const action = nextAction.value
  if (!action || !action.route || archived.value) return
  router.push(action.route)
}

async function loadTimeline() {
  if (!projectId.value) return
  timelineLoading.value = true
  timelineError.value = ''
  try {
    await store.loadTimeline(projectId.value)
    timeline.value = store.timeline
  } catch (e) {
    timelineError.value = (e as Error)?.message || '时间线加载失败'
  } finally {
    timelineLoading.value = false
  }
}

onMounted(loadTimeline)
</script>

<template>
  <div class="overview" data-ui="project-overview">
    <!-- 指标条：学生参与、任务、提交、未发布评价、AI待确认 -->
    <MetricStrip :metrics="metrics" />

    <!-- 完成度与下一步 -->
    <section class="overview-block" data-ui="overview-completion">
      <div class="block-head">
        <h3 class="block-title">项目完成度</h3>
        <span class="completion-text">{{ completionPct }}%</span>
      </div>
      <div class="completion-bar" role="progressbar" :aria-valuenow="completionPct" aria-valuemin="0" aria-valuemax="100">
        <div class="completion-bar__fill" :style="{ width: `${completionPct}%` }" />
      </div>
      <p class="block-hint">
        完成度 = 已完成阶段数 / 总阶段数；阻断项需在对应阶段解决后才能继续。
      </p>
    </section>

    <!-- 唯一下一步 -->
    <section v-if="nextAction && !archived" class="overview-block" data-ui="overview-next-action">
      <div class="block-head">
        <h3 class="block-title">下一步</h3>
      </div>
      <button
        v-if="nextAction.route"
        type="button"
        class="next-action-card ui-clickable"
        data-ui="next-action-button"
        @click="gotoNextAction"
      >
        <span class="next-action-label">{{ nextAction.label }}</span>
        <span v-if="nextAction.reason" class="next-action-reason">{{ nextAction.reason }}</span>
        <span class="next-action-arrow" aria-hidden="true">→</span>
      </button>
      <div v-else class="next-action-card next-action-card--readonly">
        <span class="next-action-label">{{ nextAction.label }}</span>
        <span v-if="nextAction.reason" class="next-action-reason">{{ nextAction.reason }}</span>
      </div>
    </section>

    <!-- 阶段进度 -->
    <section class="overview-block" data-ui="overview-phases">
      <div class="block-head">
        <h3 class="block-title">阶段进度</h3>
      </div>
      <div class="phase-list">
        <button
          v-for="p in phases"
          :key="p.phase"
          type="button"
          class="phase-row"
          :data-ui="`phase-${p.phase}`"
          :disabled="archived"
          @click="gotoPhase(p.phase)"
        >
          <span class="phase-label">{{ PHASE_LABELS[p.phase] ?? p.phase }}</span>
          <StatusBadge
            :status="p.status"
            :mapping="{
              not_started: { label: '未开始', tone: 'muted' },
              in_progress: { label: '进行中', tone: 'primary' },
              completed: { label: '已完成', tone: 'success' },
              blocked: { label: '阻断', tone: 'danger' },
            }"
          />
          <span v-if="p.completedAt" class="phase-time">{{ formatDate(p.completedAt, 'YYYY-MM-DD') }}</span>
        </button>
      </div>
    </section>

    <!-- 阻断与警告 -->
    <section
      v-if="blockers.length > 0 || warnings.length > 0"
      class="overview-block"
      data-ui="overview-issues"
    >
      <div class="block-head">
        <h3 class="block-title">阻断与警告</h3>
      </div>
      <div class="issue-list">
        <InlineAlert
          v-for="b in blockers"
          :key="'b-' + b.code"
          tone="blocker"
          :title="`${b.field}：${b.message}`"
          :description="b.phase ? `所属阶段：${PHASE_LABELS[b.phase] ?? b.phase}` : ''"
        />
        <InlineAlert
          v-for="w in warnings"
          :key="'w-' + w.code"
          tone="warning"
          :title="`${w.field}：${w.message}`"
          :description="w.phase ? `所属阶段：${PHASE_LABELS[w.phase] ?? w.phase}` : ''"
        />
      </div>
    </section>

    <!-- 真实时间线 -->
    <section class="overview-block" data-ui="overview-timeline">
      <div class="block-head">
        <h3 class="block-title">项目时间线</h3>
      </div>
      <p v-if="timelineLoading" class="block-hint">加载中…</p>
      <p v-else-if="timelineError" class="block-hint block-hint--error">{{ timelineError }}</p>
      <p v-else-if="timeline.length === 0" class="block-hint">暂无时间线事件</p>
      <ol v-else class="timeline-list">
        <li
          v-for="(evt, idx) in timeline"
          :key="idx"
          class="timeline-item"
          :data-ui="`timeline-${evt.type}`"
        >
          <span class="timeline-time">{{ formatDate(evt.timestamp, 'YYYY-MM-DD HH:mm') }}</span>
          <span class="timeline-label">{{ evt.label }}</span>
          <span v-if="evt.actor" class="timeline-actor">{{ evt.actor }}</span>
        </li>
      </ol>
    </section>
  </div>
</template>

<style scoped>
.overview {
  display: flex;
  flex-direction: column;
  gap: var(--ui-space-4, 16px);
  max-width: 1080px;
}

.overview-block {
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

.block-hint {
  margin: var(--ui-space-2, 8px) 0 0;
  font-size: var(--ui-font-size-xs, 12px);
  color: var(--ui-text-muted, #7b8794);
}

.block-hint--error {
  color: var(--ui-danger, #c53030);
}

/* ── 完成度条 ──────────────────────────────────────────────── */
.completion-text {
  font-size: var(--ui-font-size-lg, 18px);
  font-weight: 600;
  color: var(--ui-text-primary, #1f2933);
}

.completion-bar {
  width: 100%;
  height: 8px;
  background: var(--ui-bg-subtle, #f4f6f8);
  border-radius: var(--ui-radius-sm, 4px);
  overflow: hidden;
}

.completion-bar__fill {
  height: 100%;
  background: var(--ui-success, #38a169);
  transition: width 0.2s ease;
}

/* ── 下一步卡片 ────────────────────────────────────────────── */
.next-action-card {
  display: flex;
  align-items: center;
  gap: var(--ui-space-3, 12px);
  width: 100%;
  text-align: left;
  background: var(--ui-bg-subtle, #f8f9fb);
  border: 1px solid var(--ui-border-light, #e4e7eb);
  border-radius: var(--ui-radius-md, 6px);
  padding: var(--ui-space-3, 12px) var(--ui-space-4, 16px);
  cursor: pointer;
  font: inherit;
  color: var(--ui-text-primary, #1f2933);
}

.next-action-card:hover {
  border-color: var(--ui-primary, #2c6cf6);
}

.next-action-card--readonly {
  cursor: default;
}

.next-action-label {
  flex: 1 1 auto;
  font-size: var(--ui-font-size-sm, 14px);
  font-weight: 600;
}

.next-action-reason {
  font-size: var(--ui-font-size-xs, 12px);
  color: var(--ui-text-muted, #7b8794);
}

.next-action-arrow {
  color: var(--ui-primary, #2c6cf6);
  font-weight: 600;
}

/* ── 阶段列表 ──────────────────────────────────────────────── */
.phase-list {
  display: flex;
  flex-direction: column;
}

.phase-row {
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

.phase-row:last-child {
  border-bottom: none;
}

.phase-row:hover:not(:disabled) {
  background: var(--ui-bg-subtle, #f8f9fb);
}

.phase-row:disabled {
  cursor: not-allowed;
  opacity: 0.7;
}

.phase-label {
  flex: 1 1 auto;
  font-size: var(--ui-font-size-sm, 14px);
}

.phase-time {
  font-size: var(--ui-font-size-xs, 12px);
  color: var(--ui-text-muted, #7b8794);
  white-space: nowrap;
}

/* ── 阻断与警告 ────────────────────────────────────────────── */
.issue-list {
  display: flex;
  flex-direction: column;
  gap: var(--ui-space-2, 8px);
}

/* ── 时间线 ────────────────────────────────────────────────── */
.timeline-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}

.timeline-item {
  display: flex;
  align-items: center;
  gap: var(--ui-space-3, 12px);
  padding: var(--ui-space-2, 8px) 0;
  border-bottom: 1px solid var(--ui-border-light, #f0f2f5);
  font-size: var(--ui-font-size-sm, 14px);
}

.timeline-item:last-child {
  border-bottom: none;
}

.timeline-time {
  font-size: var(--ui-font-size-xs, 12px);
  color: var(--ui-text-muted, #7b8794);
  white-space: nowrap;
  min-width: 120px;
}

.timeline-label {
  flex: 1 1 auto;
  color: var(--ui-text-primary, #1f2933);
}

.timeline-actor {
  font-size: var(--ui-font-size-xs, 12px);
  color: var(--ui-text-muted, #7b8794);
}
</style>
