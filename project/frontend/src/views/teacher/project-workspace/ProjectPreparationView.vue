<script setup lang="ts">
/**
 * ProjectPreparationView - 项目备课与资源阶段（Task 8）。
 *
 * 项目备课页进入后上下文锁定为 project 模式（projectId 来自统一项目上下文 store，
 * phase=preparation，不可切换）。本页只读展示项目备课阶段的工具上下文引用：
 * - 列出 lesson_plan / resource 等资产的项目引用（不复制资产本体）。
 * - 提供入口跳转到独立教案/资源页创建资产后关联回项目。
 * - AI 产出先进入待审核版本，教师确认后写入项目备课。
 * - 归档时全部内容只读。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useProjectContextStore } from '@/features/project-context/store'
import { listContextLinksByProjectApi } from '@/features/tool-context/api'
import type { ContextLink } from '@/features/tool-context/types'
import type { PhaseKey, PhaseStatus } from '@/features/project-context/types'

const PHASE: PhaseKey = 'preparation'

const STATUS_LABELS: Record<PhaseStatus, string> = {
  not_started: '未开始',
  in_progress: '进行中',
  completed: '已完成',
  blocked: '已阻断',
}

const ARTIFACT_LABELS: Record<string, string> = {
  lesson_plan: '教案',
  resource: '资源',
  paper: '试卷',
  ai_output: 'AI 产出',
  question_bank: '题库',
}

const router = useRouter()
const store = useProjectContextStore()

const context = computed(() => store.currentContext)
const projectId = computed(() => context.value?.project.id ?? '')
const projectName = computed(() => context.value?.project.title ?? '')
const phase = computed(
  () => context.value?.phases.find((p) => p.phase === PHASE) ?? null,
)
const archived = computed(() => store.isArchived)
const canManage = computed(() => store.canManage)
const phaseBlockers = computed(
  () => (context.value?.blockers ?? []).filter((b) => b.phase === PHASE),
)

// ── Task 8：项目备课阶段上下文引用（锁定 project 模式）──────────
const links = ref<ContextLink[]>([])
const loadingLinks = ref(false)
const lessonPlanLinks = computed(() =>
  links.value.filter((l) => l.artifactType === 'lesson_plan'),
)
const resourceLinks = computed(() =>
  links.value.filter((l) => l.artifactType === 'resource'),
)
const otherLinks = computed(() =>
  links.value.filter(
    (l) => l.artifactType !== 'lesson_plan' && l.artifactType !== 'resource',
  ),
)

async function loadLinks() {
  if (!projectId.value) return
  loadingLinks.value = true
  try {
    links.value = await listContextLinksByProjectApi(projectId.value)
  } catch {
    links.value = []
  } finally {
    loadingLinks.value = false
  }
}

function gotoDesign() {
  if (!projectId.value) return
  router.push({ name: 'ProjectDesign', params: { id: projectId.value } })
}

function gotoLessonPlan() {
  router.push({ name: 'LessonPlan' })
}

function gotoResources() {
  router.push({ name: 'Resources' })
}

onMounted(() => {
  loadLinks()
})

watch(projectId, (next, prev) => {
  if (next && next !== prev) loadLinks()
})
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

    <!-- Task 8：上下文锁定提示。项目备课页进入后上下文固定为当前项目 + preparation 阶段。 -->
    <div class="context-lock" data-ui="preparation-context-lock">
      <span class="context-lock__label">当前上下文（已锁定）：</span>
      <span class="context-lock__value">{{ projectName || '未选择项目' }}</span>
      <span class="context-lock__sep">·</span>
      <span class="context-lock__value">备课阶段</span>
    </div>

    <div v-if="archived" class="phase-shell__notice" role="status">
      项目已归档，本阶段只读。
    </div>

    <ul v-if="phaseBlockers.length" class="phase-shell__blockers" role="alert">
      <li v-for="b in phaseBlockers" :key="b.code">
        <span class="phase-shell__blocker-field">{{ b.field }}</span>
        <span class="phase-shell__blocker-msg">{{ b.message }}</span>
      </li>
    </ul>

    <!-- 项目备课阶段引用列表（真实数据，非模拟） -->
    <div class="links-section" v-if="!loadingLinks">
      <div class="links-group">
        <h3 class="links-group__title">教案（{{ lessonPlanLinks.length }}）</h3>
        <ul v-if="lessonPlanLinks.length" class="links-list">
          <li v-for="l in lessonPlanLinks" :key="l.id" class="links-list__item">
            <span class="links-list__id">{{ l.artifactId }}</span>
            <span class="links-list__placement">{{ l.placement }}</span>
          </li>
        </ul>
        <p v-else class="links-list__empty">暂无教案关联，可前往独立教案页生成并关联。</p>
      </div>

      <div class="links-group">
        <h3 class="links-group__title">资源（{{ resourceLinks.length }}）</h3>
        <ul v-if="resourceLinks.length" class="links-list">
          <li v-for="l in resourceLinks" :key="l.id" class="links-list__item">
            <span class="links-list__id">{{ l.artifactId }}</span>
            <span class="links-list__placement">{{ l.placement }}</span>
          </li>
        </ul>
        <p v-else class="links-list__empty">暂无资源关联，可前往独立资源页上传并关联。</p>
      </div>

      <div v-if="otherLinks.length" class="links-group">
        <h3 class="links-group__title">其他（{{ otherLinks.length }}）</h3>
        <ul class="links-list">
          <li v-for="l in otherLinks" :key="l.id" class="links-list__item">
            <span class="links-list__type">{{ ARTIFACT_LABELS[l.artifactType] || l.artifactType }}</span>
            <span class="links-list__id">{{ l.artifactId }}</span>
            <span class="links-list__placement">{{ l.placement }}</span>
          </li>
        </ul>
      </div>
    </div>

    <div v-else class="phase-shell__empty">
      <p class="phase-shell__empty-text">正在加载备课引用…</p>
    </div>

    <div class="ai-review-hint">
      AI 生成的教案与资源先进入待审核版本，教师确认后方可正式用于项目备课。
    </div>

    <div class="phase-shell__empty" v-if="canManage && !archived">
      <p class="phase-shell__empty-text">需要新增备课资产？</p>
      <div class="phase-shell__actions">
        <button type="button" class="phase-shell__link" @click="gotoLessonPlan">前往独立教案</button>
        <button type="button" class="phase-shell__link" @click="gotoResources">前往资源中心</button>
        <button type="button" class="phase-shell__link" @click="gotoDesign">前往跨学科设计</button>
      </div>
      <p class="phase-shell__empty-hint">
        在独立工具页创建资产后，选择关联到本项目，引用会出现在上方列表。
      </p>
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
.context-lock {
  display: flex;
  align-items: center;
  gap: var(--ui-space-2);
  padding: var(--ui-space-2) var(--ui-space-3);
  background: var(--ui-bg-subtle);
  border: 1px solid var(--ui-border-light);
  border-radius: var(--ui-radius-md);
  font-size: var(--ui-font-size-sm);
}
.context-lock__label {
  color: var(--ui-text-muted);
}
.context-lock__value {
  color: var(--ui-text-primary);
  font-weight: 500;
}
.context-lock__sep {
  color: var(--ui-text-muted);
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
.links-section {
  display: flex;
  flex-direction: column;
  gap: var(--ui-space-4);
}
.links-group__title {
  margin: 0 0 var(--ui-space-2);
  font-size: var(--ui-font-size-sm);
  font-weight: 600;
  color: var(--ui-text-primary);
}
.links-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--ui-space-1);
}
.links-list__item {
  display: flex;
  align-items: center;
  gap: var(--ui-space-3);
  padding: var(--ui-space-2) var(--ui-space-3);
  background: var(--ui-bg-surface);
  border: 1px solid var(--ui-border-light);
  border-radius: var(--ui-radius-sm);
  font-size: var(--ui-font-size-sm);
}
.links-list__type {
  color: var(--ui-text-muted);
  font-size: var(--ui-font-size-xs);
  min-width: 48px;
}
.links-list__id {
  color: var(--ui-text-primary);
  font-family: monospace;
  font-size: var(--ui-font-size-xs);
}
.links-list__placement {
  color: var(--ui-text-secondary);
  font-size: var(--ui-font-size-xs);
  margin-left: auto;
}
.links-list__empty {
  margin: 0;
  padding: var(--ui-space-3);
  font-size: var(--ui-font-size-xs);
  color: var(--ui-text-muted);
}
.ai-review-hint {
  padding: var(--ui-space-2) var(--ui-space-3);
  background: #fdf6ec;
  border: 1px solid #f5dab1;
  border-radius: var(--ui-radius-md);
  color: #b88230;
  font-size: var(--ui-font-size-xs);
  line-height: 1.5;
}
.phase-shell__empty {
  display: flex;
  flex-direction: column;
  gap: var(--ui-space-2);
  padding: var(--ui-space-6) var(--ui-space-4);
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
.phase-shell__actions {
  display: flex;
  gap: var(--ui-space-3);
  flex-wrap: wrap;
  justify-content: center;
}
.phase-shell__link {
  appearance: none;
  background: transparent;
  border: 1px solid var(--ui-primary);
  color: var(--ui-primary);
  font-size: var(--ui-font-size-sm);
  cursor: pointer;
  padding: var(--ui-space-1) var(--ui-space-3);
  border-radius: var(--ui-radius-sm);
  min-height: 36px;
}
.phase-shell__link:hover { opacity: 0.85; }
</style>
