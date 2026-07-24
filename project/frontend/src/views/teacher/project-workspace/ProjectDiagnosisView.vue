<script setup lang="ts">
/**
 * ProjectDiagnosisView - 项目学情诊断阶段页面（Task 6）。
 *
 * 业务实现（替换 Task 4 空壳）：
 * - 从统一项目上下文 store 读取本阶段真实状态、阻断项与权限（不重复请求项目详情）。
 * - 从项目学情诊断 store 读取当前诊断、生成/确认状态与可观察错误。
 * - 数据来源与更新时间优先展示；其次展示掌握度、薄弱点、分层与教学建议。
 * - 无证据（insufficient_evidence）时只显示"导入前测/先发布任务"入口，绝不显示成功或伪画像。
 * - AI 失败（5xx/网络错误）必须转人工诊断：显示"转人工诊断"提示，不显示成功。
 * - 归档项目全部内容只读；非教师不可写。
 *
 * 工作区外壳（ProjectWorkspaceLayout）已加载上下文并处理 loading/forbidden/error。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useProjectContextStore } from '@/features/project-context/store'
import {
  canConfirmInsight,
  formatSourceCounts,
  useProjectDiagnosisStore,
} from '@/features/project-diagnosis/store'
import type { PhaseKey, PhaseStatus } from '@/features/project-context/types'
import type { ProjectLearningInsight } from '@/features/project-diagnosis/types'

const PHASE: PhaseKey = 'diagnosis'

const STATUS_LABELS: Record<PhaseStatus, string> = {
  not_started: '未开始',
  in_progress: '进行中',
  completed: '已完成',
  blocked: '已阻断',
}

const DIAGNOSIS_STATUS_LABELS: Record<string, string> = {
  draft: '草稿',
  insufficient_evidence: '证据不足',
  confirmed: '已确认',
  stale: '已失效',
}

const router = useRouter()
const ctxStore = useProjectContextStore()
const diagStore = useProjectDiagnosisStore()

const context = computed(() => ctxStore.currentContext)
const projectId = computed(() => context.value?.project.id ?? '')
const phase = computed(
  () => context.value?.phases.find((p) => p.phase === PHASE) ?? null,
)
const archived = computed(() => ctxStore.isArchived)
const canManage = computed(() => ctxStore.canManage)
const phaseBlockers = computed(
  () => (context.value?.blockers ?? []).filter((b) => b.phase === PHASE),
)

const insight = computed<ProjectLearningInsight | null>(
  () => diagStore.currentInsight,
)
const loading = computed(() => diagStore.loading)
const generating = computed(() => diagStore.generating)
const confirming = computed(() => diagStore.confirming)
const error = computed(() => diagStore.error)
const lastAction = computed(() => diagStore.lastAction)
const shouldFallbackToManual = computed(() => diagStore.shouldFallbackToManual)

const hasInsight = computed(() => diagStore.hasInsight)
const evidenceMissing = computed(() => diagStore.evidenceMissing)
const canConfirm = computed(() => canConfirmInsight(insight.value))
const sources = computed(() =>
  insight.value ? formatSourceCounts(insight.value.sourceCounts) : [],
)
const generatedAtLabel = computed(() => insight.value?.generatedAt ?? null)
const evidenceCutoffLabel = computed(
  () => insight.value?.evidenceCutoff ?? null,
)
const overallMasteryPct = computed(() => {
  const m = insight.value?.overallMastery
  return m === null || m === undefined ? null : Math.round(m * 100)
})

const writeable = computed(() => canManage.value && !archived.value)
const showError = computed(
  () => error.value !== null && lastAction.value !== null,
)
const showManualFallback = computed(
  () => shouldFallbackToManual.value && lastAction.value === 'generate',
)

// ── 加载诊断 ────────────────────────────────────────────────────
async function loadDiagnosis() {
  if (!projectId.value) return
  await diagStore.loadLatest(projectId.value)
}

onMounted(loadDiagnosis)

watch(projectId, (next, prev) => {
  if (next && next !== prev) {
    diagStore.clear()
    void loadDiagnosis()
  }
})

// ── 操作 ────────────────────────────────────────────────────────
async function handleGenerate() {
  if (!projectId.value || !writeable.value || generating.value) return
  try {
    await diagStore.generate(projectId.value)
  } catch {
    // 错误已映射到 store.error，UI 渲染错误条
  }
}

const confirmNote = ref<string>('')

async function handleConfirm() {
  if (!projectId.value || !writeable.value || confirming.value) return
  if (!insight.value) return
  try {
    await diagStore.confirm(insight.value.id, confirmNote.value || null)
    confirmNote.value = ''
  } catch {
    // 错误已映射到 store.error，UI 渲染错误条
  }
}

function gotoDesign() {
  if (!projectId.value) return
  router.push({ name: 'ProjectDesign', params: { id: projectId.value } })
}

function gotoPreparation() {
  if (!projectId.value) return
  router.push({ name: 'ProjectPreparation', params: { id: projectId.value } })
}

function gotoTaskChain() {
  if (!projectId.value) return
  router.push({ name: 'ProjectTaskChain', params: { id: projectId.value } })
}
</script>

<template>
  <section class="diagnosis" data-ui="phase-diagnosis">
    <header class="diagnosis__head">
      <h2 class="diagnosis__title">学情诊断</h2>
      <span
        v-if="phase"
        class="diagnosis__phase-status"
        :data-status="phase.status"
      >{{ STATUS_LABELS[phase.status] }}</span>
      <span
        v-if="insight"
        class="diagnosis__insight-status"
        :data-status="insight.status"
      >{{ DIAGNOSIS_STATUS_LABELS[insight.status] ?? insight.status }}</span>
    </header>

    <p class="diagnosis__desc">
      基于项目班级的前测、提交与已发布评价生成班级画像、薄弱点与分层建议；无学习证据时不生成确定结论。
    </p>

    <div v-if="archived" class="diagnosis__notice" role="status">
      项目已归档，本阶段只读。
    </div>

    <ul v-if="phaseBlockers.length" class="diagnosis__blockers" role="alert">
      <li v-for="b in phaseBlockers" :key="b.code">
        <span class="diagnosis__blocker-field">{{ b.field }}</span>
        <span class="diagnosis__blocker-msg">{{ b.message }}</span>
      </li>
    </ul>

    <!-- 可观察错误条：仅在写操作失败后显示，区分归档/无证据/权限/网络 -->
    <div
      v-if="showError"
      class="diagnosis__error"
      role="alert"
      :data-error-status="error?.status"
    >
      <span class="diagnosis__error-msg">{{ error?.message }}</span>
      <span v-if="error?.conflict" class="diagnosis__error-hint">
        （归档项目或无证据诊断不可执行此操作）
      </span>
    </div>

    <!-- AI 失败转人工诊断提示：不显示成功 -->
    <div
      v-if="showManualFallback"
      class="diagnosis__manual-fallback"
      role="alert"
      data-ui="manual-fallback"
    >
      <p class="diagnosis__manual-fallback-title">AI 诊断生成失败，请转人工诊断</p>
      <p class="diagnosis__manual-fallback-hint">
        可在确认诊断时填写人工诊断依据（teacher_note），系统不会显示成功。
      </p>
    </div>

    <!-- 加载态 -->
    <div v-if="loading && !hasInsight" class="diagnosis__loading" role="status">
      正在加载学情诊断…
    </div>

    <!--
      渲染优先级：
      1. 无诊断 → 空态（引导导入前测/先发布任务）
      2. 无证据（insufficient_evidence）→ 仅显示来源为 0 + 引导入口，不显示掌握/分层
      3. 有证据（draft/confirmed/stale）→ 先显示来源与时间，再显示掌握/薄弱点/分层/教学建议
    -->
    <template v-if="!loading || hasInsight">
      <!-- 1. 无诊断 -->
      <div
        v-if="!hasInsight"
        class="diagnosis__empty"
        data-ui="diagnosis-empty"
      >
        <p class="diagnosis__empty-text">本阶段暂无学情诊断。</p>
        <p class="diagnosis__empty-hint">
          请先导入前测或发布任务，生成基于真实证据的学情诊断。
        </p>
        <div class="diagnosis__empty-actions">
          <button
            v-if="writeable"
            type="button"
            class="diagnosis__link"
            @click="gotoPreparation"
          >前往导入前测</button>
          <button
            v-if="writeable"
            type="button"
            class="diagnosis__link"
            @click="gotoTaskChain"
          >先发布任务</button>
          <button
            v-if="writeable"
            type="button"
            class="diagnosis__link diagnosis__link--ghost"
            @click="gotoDesign"
          >前往跨学科设计</button>
        </div>
      </div>

      <!-- 2. 无证据诊断：不显示成功，仅显示来源为 0 + 引导入口 -->
      <div
        v-else-if="evidenceMissing"
        class="diagnosis__insufficient"
        data-ui="diagnosis-insufficient"
      >
        <div class="diagnosis__sources">
          <h3 class="diagnosis__section-title">数据来源</h3>
          <ul class="diagnosis__source-list">
            <li v-for="s in sources" :key="s.label">
              <span class="diagnosis__source-label">{{ s.label }}</span>
              <span class="diagnosis__source-count">{{ s.count }}</span>
            </li>
          </ul>
          <p v-if="generatedAtLabel" class="diagnosis__updated-at">
            最近更新：{{ generatedAtLabel }}
          </p>
        </div>
        <div class="diagnosis__empty">
          <p class="diagnosis__empty-text">
            项目暂无学习证据，无法生成确定结论。
          </p>
          <p class="diagnosis__empty-hint">
            请先导入前测或发布任务，待产生真实作答与评价后再生成诊断。
          </p>
          <div class="diagnosis__empty-actions">
            <button
              v-if="writeable"
              type="button"
              class="diagnosis__link"
              @click="gotoPreparation"
            >前往导入前测</button>
            <button
              v-if="writeable"
              type="button"
              class="diagnosis__link"
              @click="gotoTaskChain"
            >先发布任务</button>
          </div>
        </div>
      </div>

      <!-- 3. 有证据诊断：来源/时间 → 掌握度 → 薄弱点 → 分层 → 教学建议 -->
      <div
        v-else
        class="diagnosis__content"
        data-ui="diagnosis-content"
      >
        <!-- 3.1 数据来源与更新时间（优先展示） -->
        <section class="diagnosis__sources">
          <h3 class="diagnosis__section-title">数据来源</h3>
          <ul class="diagnosis__source-list">
            <li v-for="s in sources" :key="s.label">
              <span class="diagnosis__source-label">{{ s.label }}</span>
              <span class="diagnosis__source-count">{{ s.count }}</span>
            </li>
          </ul>
          <p v-if="generatedAtLabel" class="diagnosis__updated-at">
            最近生成：{{ generatedAtLabel }}
          </p>
          <p v-if="evidenceCutoffLabel" class="diagnosis__updated-at">
            证据截止：{{ evidenceCutoffLabel }}
          </p>
        </section>

        <!-- 3.2 整体掌握度 -->
        <section class="diagnosis__section">
          <h3 class="diagnosis__section-title">整体掌握度</h3>
          <p
            v-if="overallMasteryPct !== null"
            class="diagnosis__mastery"
            data-ui="overall-mastery"
          >
            {{ overallMasteryPct }}%
          </p>
          <p v-else class="diagnosis__mastery-empty">
            已采集证据，但尚未发布评价，暂无法计算掌握度。
          </p>
        </section>

        <!-- 3.3 学生分层 -->
        <section class="diagnosis__section">
          <h3 class="diagnosis__section-title">学生分层</h3>
          <ul v-if="insight?.segments.length" class="diagnosis__segments">
            <li
              v-for="seg in insight?.segments"
              :key="seg.name"
              class="diagnosis__segment"
              :data-segment="seg.name"
            >
              <span class="diagnosis__segment-name">{{ seg.name }}</span>
              <span class="diagnosis__segment-count">{{ seg.studentCount }} 人</span>
              <span
                v-if="seg.masteryRange"
                class="diagnosis__segment-range"
              >掌握度 {{ Math.round(seg.masteryRange[0] * 100) }}% - {{ Math.round(seg.masteryRange[1] * 100) }}%</span>
            </li>
          </ul>
          <p v-else class="diagnosis__mastery-empty">
            尚无已发布评价，分层建议将在评价发布后生成。
          </p>
        </section>

        <!-- 3.4 薄弱点 -->
        <section class="diagnosis__section">
          <h3 class="diagnosis__section-title">薄弱点</h3>
          <ul v-if="insight?.weakPoints.length" class="diagnosis__weak-points">
            <li
              v-for="wp in insight?.weakPoints"
              :key="wp.area"
              class="diagnosis__weak-point"
            >
              <span class="diagnosis__weak-area">{{ wp.area }}</span>
              <span class="diagnosis__weak-count">{{ wp.studentCount }} 人</span>
              <span
                v-if="wp.avgMastery !== null && wp.avgMastery !== undefined"
                class="diagnosis__weak-avg"
              >平均掌握度 {{ Math.round(wp.avgMastery * 100) }}%</span>
            </li>
          </ul>
          <p v-else class="diagnosis__mastery-empty">
            暂无明显薄弱点。
          </p>
        </section>

        <!-- 3.5 教学建议 -->
        <section class="diagnosis__section">
          <h3 class="diagnosis__section-title">教学建议</h3>
          <ul
            v-if="insight?.teachingSuggestions.length"
            class="diagnosis__suggestions"
          >
            <li
              v-for="(s, idx) in insight?.teachingSuggestions"
              :key="idx"
              class="diagnosis__suggestion"
            >{{ s }}</li>
          </ul>
          <p v-else class="diagnosis__mastery-empty">
            暂无教学建议。
          </p>
        </section>

        <!-- 3.6 教师确认区（仅 draft + 可写） -->
        <section
          v-if="canConfirm && writeable"
          class="diagnosis__confirm"
          data-ui="diagnosis-confirm"
        >
          <h3 class="diagnosis__section-title">确认诊断</h3>
          <p class="diagnosis__confirm-hint">
            确认后诊断将作为正式学情结论，可用于后续备课与评价设计。
            如有调整，可在备注中填写人工诊断依据。
          </p>
          <textarea
            v-model="confirmNote"
            class="diagnosis__confirm-note"
            placeholder="人工诊断依据（可选，AI 失败或教师复核时填写）"
            rows="3"
          ></textarea>
          <div class="diagnosis__confirm-actions">
            <button
              type="button"
              class="diagnosis__btn diagnosis__btn--primary"
              :disabled="confirming"
              @click="handleConfirm"
            >{{ confirming ? '确认中…' : '确认为正式学情结论' }}</button>
            <button
              type="button"
              class="diagnosis__btn diagnosis__btn--ghost"
              :disabled="generating"
              @click="handleGenerate"
            >{{ generating ? '重新生成中…' : '重新生成' }}</button>
          </div>
        </section>

        <!-- 已确认状态显示 -->
        <section
          v-else-if="insight?.status === 'confirmed'"
          class="diagnosis__confirmed"
          data-ui="diagnosis-confirmed"
        >
          <p class="diagnosis__confirmed-text">
            ✓ 诊断已确认为正式学情结论
          </p>
          <p v-if="insight.confirmedAt" class="diagnosis__confirmed-at">
            确认时间：{{ insight.confirmedAt }}
          </p>
          <p v-if="insight.teacherNote" class="diagnosis__confirmed-note">
            人工诊断依据：{{ insight.teacherNote }}
          </p>
        </section>
      </div>
    </template>
  </section>
</template>

<style scoped>
.diagnosis {
  display: flex;
  flex-direction: column;
  gap: var(--ui-space-3);
  max-width: var(--ui-content-max);
}
.diagnosis__head {
  display: flex;
  align-items: center;
  gap: var(--ui-space-3);
  flex-wrap: wrap;
}
.diagnosis__title {
  margin: 0;
  font-size: var(--ui-font-size-lg);
  font-weight: 600;
  color: var(--ui-text-primary);
}
.diagnosis__phase-status,
.diagnosis__insight-status {
  font-size: var(--ui-font-size-xs);
  padding: 2px var(--ui-space-2);
  border-radius: var(--ui-radius-sm);
  border: 1px solid var(--ui-border);
  color: var(--ui-text-secondary);
}
.diagnosis__phase-status[data-status='completed'] { color: var(--ui-success); border-color: var(--ui-success); }
.diagnosis__phase-status[data-status='in_progress'] { color: var(--ui-primary); border-color: var(--ui-primary); }
.diagnosis__phase-status[data-status='blocked'] { color: var(--ui-danger); border-color: var(--ui-danger); }
.diagnosis__insight-status[data-status='confirmed'] { color: var(--ui-success); border-color: var(--ui-success); }
.diagnosis__insight-status[data-status='draft'] { color: var(--ui-primary); border-color: var(--ui-primary); }
.diagnosis__insight-status[data-status='insufficient_evidence'] { color: var(--ui-text-muted); border-color: var(--ui-border); }
.diagnosis__insight-status[data-status='stale'] { color: var(--ui-warning); border-color: var(--ui-warning); }
.diagnosis__desc {
  margin: 0;
  font-size: var(--ui-font-size-sm);
  color: var(--ui-text-secondary);
  line-height: 1.6;
}
.diagnosis__notice {
  padding: var(--ui-space-2) var(--ui-space-3);
  background: var(--ui-bg-subtle);
  border-radius: var(--ui-radius-md);
  font-size: var(--ui-font-size-sm);
  color: var(--ui-text-secondary);
}
.diagnosis__blockers {
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
.diagnosis__blocker-field {
  color: var(--ui-text-muted);
  font-family: monospace;
  font-size: var(--ui-font-size-xs);
  margin-right: var(--ui-space-2);
}
.diagnosis__blocker-msg {
  color: var(--ui-danger);
  font-size: var(--ui-font-size-sm);
}
.diagnosis__error {
  padding: var(--ui-space-2) var(--ui-space-3);
  background: #fdf3f3;
  border: 1px solid var(--ui-danger);
  border-radius: var(--ui-radius-md);
  font-size: var(--ui-font-size-sm);
  color: var(--ui-danger);
}
.diagnosis__error-hint {
  color: var(--ui-text-muted);
  font-size: var(--ui-font-size-xs);
  margin-left: var(--ui-space-2);
}
.diagnosis__manual-fallback {
  padding: var(--ui-space-3);
  background: #fff8e6;
  border: 1px solid var(--ui-warning);
  border-radius: var(--ui-radius-md);
}
.diagnosis__manual-fallback-title {
  margin: 0 0 var(--ui-space-1) 0;
  font-size: var(--ui-font-size-sm);
  font-weight: 600;
  color: var(--ui-warning);
}
.diagnosis__manual-fallback-hint {
  margin: 0;
  font-size: var(--ui-font-size-xs);
  color: var(--ui-text-secondary);
}
.diagnosis__loading {
  padding: var(--ui-space-4);
  text-align: center;
  font-size: var(--ui-font-size-sm);
  color: var(--ui-text-secondary);
}
.diagnosis__empty {
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
.diagnosis__empty-text {
  margin: 0;
  font-size: var(--ui-font-size-sm);
  color: var(--ui-text-secondary);
}
.diagnosis__empty-hint {
  margin: 0;
  font-size: var(--ui-font-size-xs);
  color: var(--ui-text-muted);
}
.diagnosis__empty-actions {
  display: flex;
  gap: var(--ui-space-2);
  flex-wrap: wrap;
  justify-content: center;
  margin-top: var(--ui-space-2);
}
.diagnosis__insufficient {
  display: flex;
  flex-direction: column;
  gap: var(--ui-space-3);
}
.diagnosis__content {
  display: flex;
  flex-direction: column;
  gap: var(--ui-space-4);
}
.diagnosis__sources,
.diagnosis__section {
  display: flex;
  flex-direction: column;
  gap: var(--ui-space-2);
}
.diagnosis__section-title {
  margin: 0;
  font-size: var(--ui-font-size-sm);
  font-weight: 600;
  color: var(--ui-text-primary);
}
.diagnosis__source-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: var(--ui-space-2);
}
.diagnosis__source-list li {
  display: flex;
  flex-direction: column;
  padding: var(--ui-space-2) var(--ui-space-3);
  background: var(--ui-bg-surface);
  border: 1px solid var(--ui-border);
  border-radius: var(--ui-radius-sm);
}
.diagnosis__source-label {
  font-size: var(--ui-font-size-xs);
  color: var(--ui-text-muted);
}
.diagnosis__source-count {
  font-size: var(--ui-font-size-lg);
  font-weight: 600;
  color: var(--ui-text-primary);
}
.diagnosis__updated-at {
  margin: 0;
  font-size: var(--ui-font-size-xs);
  color: var(--ui-text-muted);
}
.diagnosis__mastery {
  margin: 0;
  font-size: var(--ui-font-size-xl);
  font-weight: 600;
  color: var(--ui-primary);
}
.diagnosis__mastery-empty {
  margin: 0;
  font-size: var(--ui-font-size-sm);
  color: var(--ui-text-secondary);
}
.diagnosis__segments,
.diagnosis__weak-points,
.diagnosis__suggestions {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--ui-space-2);
}
.diagnosis__segment,
.diagnosis__weak-point {
  display: grid;
  grid-template-columns: 1fr auto auto;
  gap: var(--ui-space-3);
  align-items: center;
  padding: var(--ui-space-2) var(--ui-space-3);
  background: var(--ui-bg-surface);
  border: 1px solid var(--ui-border);
  border-radius: var(--ui-radius-sm);
}
.diagnosis__segment-name,
.diagnosis__weak-area {
  font-size: var(--ui-font-size-sm);
  font-weight: 500;
  color: var(--ui-text-primary);
}
.diagnosis__segment-count,
.diagnosis__weak-count {
  font-size: var(--ui-font-size-sm);
  color: var(--ui-text-secondary);
}
.diagnosis__segment-range,
.diagnosis__weak-avg {
  font-size: var(--ui-font-size-xs);
  color: var(--ui-text-muted);
}
.diagnosis__suggestion {
  padding: var(--ui-space-2) var(--ui-space-3);
  background: var(--ui-bg-surface);
  border: 1px solid var(--ui-border);
  border-left: 3px solid var(--ui-primary);
  border-radius: var(--ui-radius-sm);
  font-size: var(--ui-font-size-sm);
  color: var(--ui-text-primary);
}
.diagnosis__confirm {
  padding: var(--ui-space-3);
  background: var(--ui-bg-subtle);
  border: 1px solid var(--ui-border);
  border-radius: var(--ui-radius-md);
  display: flex;
  flex-direction: column;
  gap: var(--ui-space-2);
}
.diagnosis__confirm-hint {
  margin: 0;
  font-size: var(--ui-font-size-xs);
  color: var(--ui-text-secondary);
}
.diagnosis__confirm-note {
  width: 100%;
  padding: var(--ui-space-2);
  border: 1px solid var(--ui-border);
  border-radius: var(--ui-radius-sm);
  font-size: var(--ui-font-size-sm);
  resize: vertical;
  font-family: inherit;
}
.diagnosis__confirm-actions {
  display: flex;
  gap: var(--ui-space-2);
  flex-wrap: wrap;
}
.diagnosis__btn {
  appearance: none;
  border: 1px solid transparent;
  border-radius: var(--ui-radius-sm);
  padding: var(--ui-space-2) var(--ui-space-3);
  font-size: var(--ui-font-size-sm);
  cursor: pointer;
  min-height: 40px;
}
.diagnosis__btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.diagnosis__btn--primary {
  background: var(--ui-primary);
  color: white;
}
.diagnosis__btn--primary:hover:not(:disabled) { opacity: 0.9; }
.diagnosis__btn--ghost {
  background: transparent;
  border-color: var(--ui-border);
  color: var(--ui-text-secondary);
}
.diagnosis__btn--ghost:hover:not(:disabled) { background: var(--ui-bg-subtle); }
.diagnosis__confirmed {
  padding: var(--ui-space-3);
  background: #f0f9eb;
  border: 1px solid var(--ui-success);
  border-radius: var(--ui-radius-md);
  display: flex;
  flex-direction: column;
  gap: var(--ui-space-1);
}
.diagnosis__confirmed-text {
  margin: 0;
  font-size: var(--ui-font-size-sm);
  font-weight: 600;
  color: var(--ui-success);
}
.diagnosis__confirmed-at,
.diagnosis__confirmed-note {
  margin: 0;
  font-size: var(--ui-font-size-xs);
  color: var(--ui-text-secondary);
}
.diagnosis__link {
  appearance: none;
  background: transparent;
  border: 1px solid var(--ui-primary);
  color: var(--ui-primary);
  font-size: var(--ui-font-size-sm);
  cursor: pointer;
  padding: var(--ui-space-1) var(--ui-space-3);
  border-radius: var(--ui-radius-sm);
  text-decoration: none;
  min-height: 36px;
  display: inline-flex;
  align-items: center;
}
.diagnosis__link:hover { background: var(--ui-bg-subtle); }
.diagnosis__link--ghost {
  border-color: var(--ui-border);
  color: var(--ui-text-secondary);
}
</style>
