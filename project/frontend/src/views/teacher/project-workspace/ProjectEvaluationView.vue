<script setup lang="ts">
/**
 * ProjectEvaluationView - 评价与反馈阶段空壳（Task 4 / 计划 Step 4）。
 *
 * 业务实现归 Task 11。本空壳只负责：
 * - 从统一项目上下文 store 读取本阶段真实状态、阻断项、权限与真实计数（不重复请求项目详情）。
 * - 渲染正确的空态与只读态，不放入任何模拟评分、随机 AI 建议或假发布状态。
 * - 归档时全部内容只读。
 */
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useProjectContextStore } from '@/features/project-context/store'
import type { PhaseKey, PhaseStatus } from '@/features/project-context/types'

const PHASE: PhaseKey = 'evaluation'

const STATUS_LABELS: Record<PhaseStatus, string> = {
  not_started: '未开始',
  in_progress: '进行中',
  completed: '已完成',
  blocked: '已阻断',
}

const router = useRouter()
const store = useProjectContextStore()

const context = computed(() => store.currentContext)
const projectId = computed(() => context.value?.project.id ?? '')
const phase = computed(
  () => context.value?.phases.find((p) => p.phase === PHASE) ?? null,
)
const archived = computed(() => store.isArchived)
const canManage = computed(() => store.canManage)
const phaseBlockers = computed(
  () => (context.value?.blockers ?? []).filter((b) => b.phase === PHASE),
)
// 真实计数来自上下文，不伪造
const evaluationCount = computed(() => context.value?.counts.evaluations ?? 0)
const unpublishedCount = computed(
  () => context.value?.counts.unpublishedEvaluations ?? 0,
)

function gotoEvidence() {
  if (!projectId.value) return
  router.push({ name: 'ProjectEvidence', params: { id: projectId.value } })
}
</script>

<template>
  <section class="phase-shell" data-ui="phase-evaluation">
    <header class="phase-shell__head">
      <h2 class="phase-shell__title">评价与反馈</h2>
      <span
        v-if="phase"
        class="phase-shell__status"
        :data-status="phase.status"
      >{{ STATUS_LABELS[phase.status] }}</span>
    </header>

    <p class="phase-shell__desc">
      用量规评价、审阅 AI 建议、发布反馈；AI 建议仅作草稿，教师发布前学生不可见。发布后学生看到统一正式反馈。
    </p>

    <div v-if="archived" class="phase-shell__notice" role="status">
      项目已归档，本阶段只读。
    </div>

    <ul v-if="phaseBlockers.length" class="phase-shell__blockers" role="alert">
      <li v-for="b in phaseBlockers" :key="b.code">
        <span class="phase-shell__blocker-field">{{ b.field }}</span>
        <span class="phase-shell__blocker-msg">{{ b.message }}</span>
      </li>
    </ul>

    <div class="phase-shell__metrics">
      <div class="phase-shell__metric">
        <span class="phase-shell__metric-num">{{ evaluationCount }}</span>
        <span class="phase-shell__metric-label">评价记录</span>
      </div>
      <div class="phase-shell__metric">
        <span class="phase-shell__metric-num">{{ unpublishedCount }}</span>
        <span class="phase-shell__metric-label">未发布反馈</span>
      </div>
    </div>

    <div class="phase-shell__empty">
      <p class="phase-shell__empty-text">
        {{ evaluationCount === 0 ? '暂无评价记录。' : '评价工作台将在后续任务中实现。' }}
      </p>
      <p class="phase-shell__empty-hint">
        学生学习证据齐备后，可在此用量规评价、审阅 AI 建议并发布反馈。
      </p>
      <button
        v-if="canManage && !archived"
        type="button"
        class="phase-shell__link"
        @click="gotoEvidence"
      >前往学习证据</button>
    </div>
  </section>
</template>

<style scoped>
.phase-shell {
  display: flex;
  flex-direction: column;
  gap: var(--ui-space-3);
  max-width: var(--ui-content-max);
}
.phase-shell__head {
  display: flex;
  align-items: center;
  gap: var(--ui-space-3);
}
.phase-shell__title {
  margin: 0;
  font-size: var(--ui-font-size-lg);
  font-weight: 600;
  color: var(--ui-text-primary);
}
.phase-shell__status {
  font-size: var(--ui-font-size-xs);
  padding: 2px var(--ui-space-2);
  border-radius: var(--ui-radius-sm);
  border: 1px solid var(--ui-border);
  color: var(--ui-text-secondary);
}
.phase-shell__status[data-status='completed'] { color: var(--ui-success); border-color: var(--ui-success); }
.phase-shell__status[data-status='in_progress'] { color: var(--ui-primary); border-color: var(--ui-primary); }
.phase-shell__status[data-status='blocked'] { color: var(--ui-danger); border-color: var(--ui-danger); }
.phase-shell__desc {
  margin: 0;
  font-size: var(--ui-font-size-sm);
  color: var(--ui-text-secondary);
  line-height: 1.6;
}
.phase-shell__notice {
  padding: var(--ui-space-2) var(--ui-space-3);
  background: var(--ui-bg-subtle);
  border-radius: var(--ui-radius-md);
  font-size: var(--ui-font-size-sm);
  color: var(--ui-text-secondary);
}
.phase-shell__blockers {
  list-style: none;
  margin: 0;
  padding: var(--ui-space-2) var(--ui-space-3);
  background: #fdf3f3;
  border: 1px solid var(--ui-danger);
  border-radius: var(--ui-radius-md);
  display: flex;
  flex-direction: column;
  gap: var(--ui-space-1);
}
.phase-shell__blocker-field {
  color: var(--ui-text-muted);
  font-family: monospace;
  font-size: var(--ui-font-size-xs);
  margin-right: var(--ui-space-2);
}
.phase-shell__blocker-msg {
  color: var(--ui-danger);
  font-size: var(--ui-font-size-sm);
}
.phase-shell__metrics {
  display: flex;
  gap: var(--ui-space-6);
}
.phase-shell__metric {
  display: flex;
  flex-direction: column;
}
.phase-shell__metric-num {
  font-size: var(--ui-font-size-lg);
  font-weight: 600;
  color: var(--ui-text-primary);
}
.phase-shell__metric-label {
  font-size: var(--ui-font-size-xs);
  color: var(--ui-text-muted);
}
.phase-shell__empty {
  display: flex;
  flex-direction: column;
  gap: var(--ui-space-2);
  padding: var(--ui-space-8) var(--ui-space-4);
  background: var(--ui-bg-surface);
  border: 1px dashed var(--ui-border);
  border-radius: var(--ui-radius-md);
  align-items: center;
  text-align: center;
}
.phase-shell__empty-text {
  margin: 0;
  font-size: var(--ui-font-size-sm);
  color: var(--ui-text-secondary);
}
.phase-shell__empty-hint {
  margin: 0;
  font-size: var(--ui-font-size-xs);
  color: var(--ui-text-muted);
}
.phase-shell__link {
  appearance: none;
  background: transparent;
  border: none;
  color: var(--ui-primary);
  font-size: var(--ui-font-size-sm);
  cursor: pointer;
  padding: var(--ui-space-1) var(--ui-space-2);
  text-decoration: underline;
  min-height: 40px;
}
.phase-shell__link:hover { opacity: 0.85; }
</style>
