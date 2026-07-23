<script setup lang="ts">
/**
 * ProjectInsightsView - 项目学情视图（计划 Task 7 / 验收 3.7）。
 *
 * 展示与操作：
 * - 目标 / 知识点 / 指标达成聚合（ECharts 柱状图）
 * - 班级共性薄弱点
 * - 三阶段（设计/实施/评价）达成变化
 * - 改进建议列表：每项引用正式证据，支持采用/修改/拒绝（原因留痕）、转改进任务
 * - 二次评价：创建 + 前后对比
 *
 * 数据来源：
 * - GET /learning-profile/projects/:id/aggregations
 * - GET /improvements/suggestions?project_id=
 * - 评价记录（作为建议/二次评价引用的正式证据）：GET /evaluation-plans/records
 */
import { computed, inject, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as echarts from 'echarts/core'
import { BarChart, LineChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { ECharts } from 'echarts/core'
import type { Ref } from 'vue'
import type { Project } from '@/types'
import {
  adoptSuggestionApi,
  convertSuggestionToTaskApi,
  createSecondEvaluationApi,
  createSuggestionApi,
  getProjectAggregationsApi,
  getSecondEvaluationComparisonApi,
  listSuggestionsApi,
  modifySuggestionApi,
  rejectSuggestionApi,
} from '@/features/learning-improvement/api'
import type {
  ImprovementSuggestion,
  ProjectLearningAggregations,
  SecondEvaluationComparison,
} from '@/features/learning-improvement/types'
import {
  SUGGESTION_PRIORITY_LABELS,
  SUGGESTION_PRIORITY_TYPES,
  SUGGESTION_STATUS_LABELS,
  SUGGESTION_STATUS_TYPES,
} from '@/features/learning-improvement/types'
import { listRecordsApi } from '@/features/evaluation-plan/api'
import type { EvaluationRecord } from '@/features/evaluation-plan/types'

echarts.use([
  BarChart,
  LineChart,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
  CanvasRenderer,
])

const route = useRoute()
const projectId = computed(() => route.params.id as string)
const project = inject<Ref<Project | null>>('workspaceProject')

// ── 数据 ─────────────────────────────────────────────────────
const loading = ref(false)
const errorMsg = ref('')
const aggregations = ref<ProjectLearningAggregations | null>(null)
const suggestions = ref<ImprovementSuggestion[]>([])
const evaluationRecords = ref<EvaluationRecord[]>([])

// ── 图表 ─────────────────────────────────────────────────────
const goalsChartEl = ref<HTMLDivElement | null>(null)
const knowledgeChartEl = ref<HTMLDivElement | null>(null)
const stageChartEl = ref<HTMLDivElement | null>(null)
let goalsChart: ECharts | null = null
let knowledgeChart: ECharts | null = null
let stageChart: ECharts | null = null

/** 将 0-1 或 0-100 的比率归一化为 0-100 百分比 */
function toPct(v: number | null | undefined): number {
  if (v === null || v === undefined || Number.isNaN(v)) return 0
  return v <= 1 ? v * 100 : v
}

function renderGoalsChart() {
  if (!goalsChartEl.value) return
  if (!goalsChart) goalsChart = echarts.init(goalsChartEl.value)
  const goals = aggregations.value?.goals || []
  goalsChart.setOption({
    title: { text: '学习目标达成分布', left: 'center', textStyle: { fontSize: 13 } },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: any) => {
        const p = Array.isArray(params) ? params[0] : params
        return `${p.name}<br/>达成率：${p.value}%`
      },
    },
    grid: { left: 40, right: 24, top: 50, bottom: 40 },
    xAxis: {
      type: 'category',
      data: goals.map((g) => g.goalName || g.goalId.slice(0, 8)),
      axisLabel: { fontSize: 11, interval: 0, rotate: goals.length > 4 ? 30 : 0 },
    },
    yAxis: { type: 'value', max: 100, axisLabel: { formatter: '{value}%' } },
    series: [
      {
        type: 'bar',
        data: goals.map((g) => Number(toPct(g.achievementRate).toFixed(1))),
        itemStyle: { color: '#409EFF' },
        barMaxWidth: 40,
        label: { show: true, position: 'top', formatter: '{c}%', fontSize: 11 },
      },
    ],
  })
}

function renderKnowledgeChart() {
  if (!knowledgeChartEl.value) return
  if (!knowledgeChart) knowledgeChart = echarts.init(knowledgeChartEl.value)
  const kps = (aggregations.value?.knowledgePoints || []).slice()
  // 按掌握率升序，便于一眼识别薄弱
  kps.sort((a, b) => a.masteryRate - b.masteryRate)
  knowledgeChart.setOption({
    title: { text: '知识点掌握分布（升序）', left: 'center', textStyle: { fontSize: 13 } },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: any) => {
        const p = Array.isArray(params) ? params[0] : params
        return `${p.name}<br/>掌握率：${p.value}%`
      },
    },
    grid: { left: 40, right: 24, top: 50, bottom: 40 },
    xAxis: {
      type: 'category',
      data: kps.map((k) => k.name),
      axisLabel: { fontSize: 11, interval: 0, rotate: kps.length > 4 ? 30 : 0 },
    },
    yAxis: { type: 'value', max: 100, axisLabel: { formatter: '{value}%' } },
    series: [
      {
        type: 'bar',
        data: kps.map((k) => {
          const pct = toPct(k.masteryRate)
          return {
            value: Number(pct.toFixed(1)),
            itemStyle: { color: pct < 60 ? '#F56C6C' : pct < 80 ? '#E6A23C' : '#67C23A' },
          }
        }),
        barMaxWidth: 40,
        label: { show: true, position: 'top', formatter: '{c}%', fontSize: 11 },
      },
    ],
  })
}

function renderStageChart() {
  if (!stageChartEl.value) return
  if (!stageChart) stageChart = echarts.init(stageChartEl.value)
  const stages = aggregations.value?.stages || []
  stageChart.setOption({
    title: { text: '三阶段达成变化', left: 'center', textStyle: { fontSize: 13 } },
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const p = Array.isArray(params) ? params[0] : params
        return `${p.name}<br/>达成率：${p.value}%`
      },
    },
    grid: { left: 40, right: 24, top: 50, bottom: 40 },
    xAxis: {
      type: 'category',
      data: stages.map((s) => s.label || s.stage),
      axisLabel: { fontSize: 12 },
    },
    yAxis: { type: 'value', max: 100, axisLabel: { formatter: '{value}%' } },
    series: [
      {
        type: 'line',
        data: stages.map((s) => Number(toPct(s.achievementRate).toFixed(1))),
        smooth: true,
        symbol: 'circle',
        symbolSize: 8,
        lineStyle: { color: '#409EFF', width: 2 },
        itemStyle: { color: '#409EFF' },
        label: { show: true, position: 'top', formatter: '{c}%', fontSize: 11 },
        areaStyle: { color: 'rgba(64,158,255,0.08)' },
      },
    ],
  })
}

function renderAllCharts() {
  renderGoalsChart()
  renderKnowledgeChart()
  renderStageChart()
}

function handleResize() {
  goalsChart?.resize()
  knowledgeChart?.resize()
  stageChart?.resize()
}

// ── 计算属性 ─────────────────────────────────────────────────
const weakPoints = computed(() => aggregations.value?.weakPoints || [])
const indicators = computed(() => aggregations.value?.indicators || [])
const pendingSuggestions = computed(
  () => suggestions.value.filter((s) => s.status === 'pending').length,
)

// ── 加载 ─────────────────────────────────────────────────────
async function loadAll() {
  loading.value = true
  errorMsg.value = ''
  try {
    const [aggRes, sugRes, recRes] = await Promise.all([
      getProjectAggregationsApi(projectId.value),
      listSuggestionsApi(projectId.value),
      listRecordsApi({ project_id: projectId.value }).catch(() => null),
    ])
    aggregations.value = aggRes.data.data
    suggestions.value = sugRes.data.data.items || []
    if (recRes) evaluationRecords.value = recRes.data.data || []
    await nextTick()
    renderAllCharts()
  } catch (err: unknown) {
    errorMsg.value = err instanceof Error ? err.message : '加载学情数据失败'
  } finally {
    loading.value = false
  }
}

async function reloadSuggestions() {
  try {
    const res = await listSuggestionsApi(projectId.value)
    suggestions.value = res.data.data.items || []
  } catch {
    // 错误由拦截器提示
  }
}

// ── 创建建议对话框 ───────────────────────────────────────────
const createDialogVisible = ref(false)
const createForm = ref({
  evidenceRecordId: '' as string,
  title: '',
  content: '',
  category: '',
  priority: 'medium' as 'high' | 'medium' | 'low',
  evidenceSummary: '',
})

function evidenceLabel(rec: EvaluationRecord): string {
  const score = rec.totalScore !== null && rec.totalScore !== undefined
    ? ` · ${rec.totalScore}分`
    : ''
  const t = rec.createdAt ? rec.createdAt.slice(0, 10) : ''
  return `证据#${rec.id.slice(0, 8)}${score}${t ? ' · ' + t : ''}`
}

function openCreateDialog() {
  createForm.value = {
    evidenceRecordId: '',
    title: '',
    content: '',
    category: '',
    priority: 'medium',
    evidenceSummary: '',
  }
  createDialogVisible.value = true
}

function onEvidenceChange(id: string) {
  const rec = evaluationRecords.value.find((r) => r.id === id)
  if (rec && !createForm.value.evidenceSummary) {
    createForm.value.evidenceSummary = rec.comment || ''
  }
}

async function submitCreate() {
  if (!createForm.value.evidenceRecordId) {
    ElMessage.warning('请选择引用的正式证据')
    return
  }
  if (!createForm.value.title.trim()) {
    ElMessage.warning('请填写建议标题')
    return
  }
  try {
    await createSuggestionApi({
      projectId: projectId.value,
      evidenceRecordId: createForm.value.evidenceRecordId,
      title: createForm.value.title.trim(),
      content: createForm.value.content.trim(),
      category: createForm.value.category || null,
      priority: createForm.value.priority,
      evidenceSummary: createForm.value.evidenceSummary || null,
    })
    ElMessage.success('已创建改进建议')
    createDialogVisible.value = false
    await reloadSuggestions()
  } catch {
    // 错误由拦截器提示
  }
}

// ── 采用 / 修改 / 拒绝（原因留痕） ──────────────────────────
const actionDialogVisible = ref(false)
const actionMode = ref<'adopt' | 'modify' | 'reject'>('adopt')
const actionTarget = ref<ImprovementSuggestion | null>(null)
const actionForm = ref({ reason: '', modifications: '' })

const actionDialogTitle = computed(() => {
  const map = { adopt: '采用建议', modify: '修改建议', reject: '拒绝建议' } as const
  return map[actionMode.value]
})

function openActionDialog(mode: 'adopt' | 'modify' | 'reject', s: ImprovementSuggestion) {
  actionMode.value = mode
  actionTarget.value = s
  actionForm.value = { reason: '', modifications: '' }
  actionDialogVisible.value = true
}

async function submitAction() {
  if (!actionTarget.value) return
  if (!actionForm.value.reason.trim()) {
    ElMessage.warning('请填写原因（留痕）')
    return
  }
  if (actionMode.value === 'modify' && !actionForm.value.modifications.trim()) {
    ElMessage.warning('请填写修改说明')
    return
  }
  const id = actionTarget.value.id
  try {
    if (actionMode.value === 'adopt') {
      await adoptSuggestionApi(id, { reason: actionForm.value.reason.trim() })
    } else if (actionMode.value === 'modify') {
      await modifySuggestionApi(id, {
        reason: actionForm.value.reason.trim(),
        modifications: actionForm.value.modifications.trim(),
      })
    } else {
      await rejectSuggestionApi(id, { reason: actionForm.value.reason.trim() })
    }
    ElMessage.success('已处理')
    actionDialogVisible.value = false
    await reloadSuggestions()
  } catch {
    // 错误由拦截器提示
  }
}

// ── 转改进任务 ───────────────────────────────────────────────
async function handleConvertToTask(s: ImprovementSuggestion) {
  try {
    await ElMessageBox.confirm(
      `将建议「${s.title}」转换为改进任务？`,
      '转改进任务',
      { type: 'warning' },
    )
  } catch {
    return
  }
  try {
    const res = await convertSuggestionToTaskApi(s.id)
    const taskId = res.data.data.taskId
    ElMessage.success(`已转换为改进任务（#${taskId.slice(0, 8)}）`)
    await reloadSuggestions()
  } catch {
    // 错误由拦截器提示
  }
}

// ── 二次评价 + 前后对比 ──────────────────────────────────────
const secondEvalDialogVisible = ref(false)
const secondEvalForm = ref({
  firstEvaluationId: '' as string,
  score: null as number | null,
  comment: '',
})
const comparison = ref<SecondEvaluationComparison | null>(null)
const comparisonLoading = ref(false)

function openSecondEvalDialog() {
  secondEvalForm.value = { firstEvaluationId: '', score: null, comment: '' }
  comparison.value = null
  secondEvalDialogVisible.value = true
}

async function submitSecondEval() {
  if (!secondEvalForm.value.firstEvaluationId) {
    ElMessage.warning('请选择首次评价记录')
    return
  }
  try {
    const res = await createSecondEvaluationApi({
      firstEvaluationId: secondEvalForm.value.firstEvaluationId,
      score: secondEvalForm.value.score,
      comment: secondEvalForm.value.comment || null,
    })
    const secondId = res.data.data.id
    ElMessage.success('已创建二次评价')
    await loadComparison(secondId)
  } catch {
    // 错误由拦截器提示
  }
}

async function loadComparison(secondEvaluationId: string) {
  comparisonLoading.value = true
  try {
    const res = await getSecondEvaluationComparisonApi(secondEvaluationId)
    comparison.value = res.data.data
  } catch {
    // 错误由拦截器提示
  } finally {
    comparisonLoading.value = false
  }
}

function fmtScore(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—'
  return String(v)
}

function fmtDelta(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—'
  const sign = v > 0 ? '+' : ''
  return `${sign}${Number(v).toFixed(1)}`
}

// ── 生命周期 ─────────────────────────────────────────────────
onMounted(loadAll)

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  goalsChart?.dispose()
  knowledgeChart?.dispose()
  stageChart?.dispose()
  goalsChart = null
  knowledgeChart = null
  stageChart = null
})

watch(
  () => aggregations.value,
  () => nextTick(() => renderAllCharts()),
)

window.addEventListener('resize', handleResize)
</script>

<template>
  <div class="insights-view" v-loading="loading">
    <el-alert
      v-if="errorMsg"
      :title="errorMsg"
      type="error"
      :closable="true"
      show-icon
      style="margin-bottom: 16px"
    />

    <!-- 达成聚合：目标 + 知识点 -->
    <section class="card-section">
      <div class="section-header">
        <h3 class="section-title">目标 / 知识点达成分布</h3>
        <span class="section-hint">数据来源：项目学情聚合（真实评价数据）</span>
      </div>
      <div class="chart-grid">
        <div ref="goalsChartEl" class="chart-box" />
        <div ref="knowledgeChartEl" class="chart-box" />
      </div>
    </section>

    <!-- 指标达成 -->
    <section v-if="indicators.length > 0" class="card-section">
      <div class="section-header">
        <h3 class="section-title">评价指标达成</h3>
      </div>
      <el-table :data="indicators" stripe size="small">
        <el-table-column label="可观察行为" min-width="220">
          <template #default="{ row }">
            {{ row.observableBehavior || row.indicatorId.slice(0, 8) }}
          </template>
        </el-table-column>
        <el-table-column label="达成率" width="180">
          <template #default="{ row }">
            <el-progress
              :percentage="toPct(row.achievementRate)"
              :stroke-width="12"
              :color="toPct(row.achievementRate) < 60 ? '#F56C6C' : '#409EFF'"
            />
          </template>
        </el-table-column>
      </el-table>
    </section>

    <!-- 班级共性薄弱点 -->
    <section class="card-section">
      <div class="section-header">
        <h3 class="section-title">班级共性薄弱点</h3>
      </div>
      <div v-if="weakPoints.length > 0" class="weak-points">
        <el-tag
          v-for="(wp, i) in weakPoints"
          :key="i"
          type="danger"
          size="large"
          class="weak-tag"
        >
          {{ wp }}
        </el-tag>
      </div>
      <el-empty v-else description="暂无共性薄弱点" :image-size="60" />
    </section>

    <!-- 三阶段变化 -->
    <section class="card-section">
      <div class="section-header">
        <h3 class="section-title">三阶段达成变化</h3>
      </div>
      <div ref="stageChartEl" class="chart-box single" />
    </section>

    <!-- 改进建议列表 -->
    <section class="card-section">
      <div class="section-header">
        <h3 class="section-title">
          改进建议（{{ suggestions.length }}）<span class="muted">· 待处理 {{ pendingSuggestions }}</span>
        </h3>
        <el-button type="primary" size="small" @click="openCreateDialog">
          新增建议
        </el-button>
      </div>
      <el-empty v-if="suggestions.length === 0" description="暂无改进建议" :image-size="60" />
      <div v-else class="suggestion-list">
        <div v-for="s in suggestions" :key="s.id" class="suggestion-item">
          <div class="suggestion-head">
            <span class="suggestion-title">{{ s.title }}</span>
            <el-tag
              size="small"
              :type="(SUGGESTION_STATUS_TYPES[s.status] as any) || 'info'"
            >
              {{ SUGGESTION_STATUS_LABELS[s.status] || s.status }}
            </el-tag>
            <el-tag
              v-if="s.priority"
              size="small"
              :type="(SUGGESTION_PRIORITY_TYPES[s.priority] as any) || 'info'"
            >
              {{ SUGGESTION_PRIORITY_LABELS[s.priority] || s.priority }}优先级
            </el-tag>
            <el-tag v-if="s.category" size="small" type="info">{{ s.category }}</el-tag>
          </div>
          <p class="suggestion-content">{{ s.content }}</p>
          <!-- 引用证据（每项必须引用） -->
          <div class="evidence-ref">
            <el-icon><Link /></el-icon>
            <span class="evidence-label">引用证据：</span>
            <span class="evidence-id">#{{ (s.evidenceRecordId || '').slice(0, 8) }}</span>
            <span v-if="s.evidenceSummary" class="evidence-summary">
              {{ s.evidenceSummary }}
            </span>
            <span v-if="s.evidenceRef" class="evidence-src">{{ s.evidenceRef }}</span>
          </div>
          <!-- 留痕信息 -->
          <div v-if="s.reason || s.modifications || s.convertedTaskId" class="trace">
            <span v-if="s.reason" class="trace-item">原因留痕：{{ s.reason }}</span>
            <span v-if="s.modifications" class="trace-item">修改说明：{{ s.modifications }}</span>
            <span v-if="s.convertedTaskId" class="trace-item trace-task">
              已转任务 #{{ s.convertedTaskId.slice(0, 8) }}
            </span>
          </div>
          <!-- 操作（仅 pending 可操作） -->
          <div v-if="s.status === 'pending'" class="suggestion-actions">
            <el-button size="small" type="success" @click="openActionDialog('adopt', s)">采用</el-button>
            <el-button size="small" type="primary" @click="openActionDialog('modify', s)">修改</el-button>
            <el-button size="small" @click="openActionDialog('reject', s)">拒绝</el-button>
            <el-button size="small" type="warning" @click="handleConvertToTask(s)">转改进任务</el-button>
          </div>
        </div>
      </div>
    </section>

    <!-- 二次评价 + 前后对比 -->
    <section class="card-section">
      <div class="section-header">
        <h3 class="section-title">二次评价 · 前后对比</h3>
        <el-button type="primary" size="small" @click="openSecondEvalDialog">
          创建二次评价
        </el-button>
      </div>
      <el-empty
        v-if="!comparison"
        description="创建二次评价后展示前后对比"
        :image-size="60"
      />
      <div v-else v-loading="comparisonLoading" class="comparison">
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="阶段">首次评价</el-descriptions-item>
          <el-descriptions-item label="得分">{{ fmtScore(comparison.first?.score) }}</el-descriptions-item>
          <el-descriptions-item label="评语">{{ comparison.first?.comment || '—' }}</el-descriptions-item>
          <el-descriptions-item label="阶段">二次评价</el-descriptions-item>
          <el-descriptions-item label="得分">{{ fmtScore(comparison.second?.score) }}</el-descriptions-item>
          <el-descriptions-item label="评语">{{ comparison.second?.comment || '—' }}</el-descriptions-item>
          <el-descriptions-item label="变化">
            <span :class="['delta', (comparison.delta ?? 0) >= 0 ? 'up' : 'down']">
              {{ fmtDelta(comparison.delta) }}
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="改进率">
            {{ comparison.improvementRate !== null && comparison.improvementRate !== undefined
              ? toPct(comparison.improvementRate).toFixed(1) + '%' : '—' }}
          </el-descriptions-item>
          <el-descriptions-item label="二次评价时间">
            {{ comparison.second?.evaluatedAt
              ? comparison.second.evaluatedAt.slice(0, 19).replace('T', ' ') : '—' }}
          </el-descriptions-item>
        </el-descriptions>
      </div>
    </section>

    <!-- 创建建议对话框 -->
    <el-dialog v-model="createDialogVisible" title="新增改进建议" width="560px">
      <el-form :model="createForm" label-width="100px" size="default">
        <el-form-item label="引用证据" required>
          <el-select
            v-model="createForm.evidenceRecordId"
            placeholder="选择正式评价证据"
            filterable
            style="width: 100%"
            @change="onEvidenceChange"
          >
            <el-option
              v-for="rec in evaluationRecords"
              :key="rec.id"
              :label="evidenceLabel(rec)"
              :value="rec.id"
            />
          </el-select>
          <div class="form-hint">每条建议必须引用一条正式学习证据，作为提出依据</div>
        </el-form-item>
        <el-form-item label="建议标题" required>
          <el-input v-model="createForm.title" placeholder="简述改进建议" />
        </el-form-item>
        <el-form-item label="建议内容">
          <el-input v-model="createForm.content" type="textarea" :rows="3" placeholder="详细描述建议内容" />
        </el-form-item>
        <el-form-item label="类别">
          <el-input v-model="createForm.category" placeholder="如：共性薄弱 / 目标未达成 / 分层支持" />
        </el-form-item>
        <el-form-item label="优先级">
          <el-radio-group v-model="createForm.priority">
            <el-radio value="high">高</el-radio>
            <el-radio value="medium">中</el-radio>
            <el-radio value="low">低</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="证据摘要">
          <el-input v-model="createForm.evidenceSummary" type="textarea" :rows="2" placeholder="可补充证据摘要" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- 采用/修改/拒绝 对话框 -->
    <el-dialog v-model="actionDialogVisible" :title="actionDialogTitle" width="480px">
      <el-form :model="actionForm" label-width="80px" size="default">
        <el-form-item label="原因" required>
          <el-input v-model="actionForm.reason" type="textarea" :rows="3" placeholder="说明原因（留痕）" />
        </el-form-item>
        <el-form-item v-if="actionMode === 'modify'" label="修改说明" required>
          <el-input v-model="actionForm.modifications" type="textarea" :rows="3" placeholder="说明具体修改内容" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="actionDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitAction">确定</el-button>
      </template>
    </el-dialog>

    <!-- 创建二次评价对话框 -->
    <el-dialog v-model="secondEvalDialogVisible" title="创建二次评价" width="500px">
      <el-form :model="secondEvalForm" label-width="100px" size="default">
        <el-form-item label="首次评价" required>
          <el-select
            v-model="secondEvalForm.firstEvaluationId"
            placeholder="选择首次评价记录"
            filterable
            style="width: 100%"
          >
            <el-option
              v-for="rec in evaluationRecords"
              :key="rec.id"
              :label="evidenceLabel(rec)"
              :value="rec.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="二次得分">
          <el-input-number v-model="secondEvalForm.score" :min="0" :max="100" :step="1" />
        </el-form-item>
        <el-form-item label="评语">
          <el-input v-model="secondEvalForm.comment" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="secondEvalDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitSecondEval">创建并对比</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.insights-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.card-section {
  background: #fff;
  border-radius: 8px;
  padding: 16px 20px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  flex-wrap: wrap;
  gap: 8px;
}

.section-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.section-hint {
  font-size: 12px;
  color: #909399;
}

.muted {
  color: #909399;
  font-weight: 400;
  font-size: 13px;
}

.chart-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.chart-box {
  width: 100%;
  height: 280px;
}

.chart-box.single {
  height: 260px;
}

.weak-points {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.weak-tag {
  font-size: 13px;
}

/* 建议列表 */
.suggestion-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.suggestion-item {
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 12px 14px;
  background: #fafbfc;
}

.suggestion-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}

.suggestion-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.suggestion-content {
  margin: 0 0 8px;
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
  white-space: pre-wrap;
}

.evidence-ref {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #909399;
  background: #f4f6f8;
  padding: 6px 10px;
  border-radius: 4px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.evidence-label {
  color: #606266;
}

.evidence-id {
  font-weight: 600;
  color: #409eff;
}

.evidence-summary {
  color: #606266;
}

.evidence-src {
  color: #c0c4cc;
}

.trace {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 12px;
  color: #909399;
  margin-bottom: 8px;
}

.trace-task {
  color: #67c23a;
}

.suggestion-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

/* 对比 */
.comparison {
  margin-top: 4px;
}

.delta.up {
  color: #67c23a;
  font-weight: 600;
}

.delta.down {
  color: #f56c6c;
  font-weight: 600;
}

.form-hint {
  font-size: 12px;
  color: #909399;
  line-height: 1.4;
  margin-top: 4px;
}

@media (max-width: 1024px) {
  .chart-grid {
    grid-template-columns: 1fr;
  }
}
</style>
