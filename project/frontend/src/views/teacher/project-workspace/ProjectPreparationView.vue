<script setup lang="ts">
/**
 * ProjectPreparationView - 备课与资源阶段空壳（Task 4 / 计划 Step 4）。
 *
 * 业务实现归 Task 8。本空壳只负责：
 * - 从统一项目上下文 store 读取本阶段真实状态、阻断项与权限（不重复请求项目详情）。
 * - 渲染正确的空态与只读态，不放入任何模拟教案、随机资源或假 AI 版本。
 * - 归档时全部内容只读。
 */
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useProjectContextStore } from '@/features/project-context/store'
import type { PhaseKey, PhaseStatus } from '@/features/project-context/types'

const PHASE: PhaseKey = 'preparation'

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

function gotoDesign() {
  if (!projectId.value) return
  router.push({ name: 'ProjectDesign', params: { id: projectId.value } })
}
</script>

<template>
  <section class="phase-shell" data-ui="phase-preparation">
    <header class="phase-shell__head">
      <h2 class="phase-shell__title">备课与资源</h2>
      <span
        v-if="phase"
        class="phase-shell__status"
        :data-status="phase.status"
      >{{ STATUS_LABELS[phase.status] }}</span>
    </header>

    <p class="phase-shell__desc">
      生成或编辑活动方案、资源包与分层任务链；AI 产出先进入待审核版本，教师采纳后写入项目备课与资源。
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

    <div class="phase-shell__empty">
      <p class="phase-shell__empty-text">本阶段暂无教案、资源或任务链。</p>
      <p class="phase-shell__empty-hint">
        完成跨学科设计后，可在此准备活动方案、分层资源与任务草稿。
      </p>
      <button
        v-if="canManage && !archived"
        type="button"
        class="phase-shell__link"
        @click="gotoDesign"
      >前往跨学科设计</button>
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
