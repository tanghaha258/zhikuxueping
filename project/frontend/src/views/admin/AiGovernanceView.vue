<script setup lang="ts">
/**
 * AiGovernanceView - AI 任务治理看板（Task 8 / 验收 3.8.2）。
 *
 * 复用 features/ai-content 的 listAiJobsApi / getAiJobApi 聚合：
 * - 任务统计（总数 / 成功 / 失败 / 采用率 / 阻断数）
 * - 任务状态分布（ECharts 饼图）
 * - 场景分布（ECharts 柱状图）
 * - 质量问题分布（按规则 / 严重度，ECharts 柱状图）
 * - Provider 健康（按 Provider 聚合成功率/失败率）
 *
 * 默认仅展示真实数据；dataOrigin=real 不可切换。
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { BarChart, PieChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { ECharts } from 'echarts/core'
import { getAiJobApi, listAiJobsApi } from '@/features/ai-content/api'
import type {
  AiJob,
  AiJobDetail,
  QualityIssue,
} from '@/features/ai-content/types'
import {
  JOB_STATUS_LABELS,
  RULE_CODE_LABELS,
  SCENE_OPTIONS,
  SEVERITY_LABELS,
} from '@/features/ai-content/types'

echarts.use([
  BarChart,
  PieChart,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
  CanvasRenderer,
])

const loading = ref(false)
const errorMsg = ref('')
const jobs = ref<AiJob[]>([])
const details = ref<AiJobDetail[]>([])
const dataOrigin = ref<'real'>('real')

// ── 图表 ─────────────────────────────────────────────────────
const statusChartEl = ref<HTMLDivElement | null>(null)
const sceneChartEl = ref<HTMLDivElement | null>(null)
const issueChartEl = ref<HTMLDivElement | null>(null)
let statusChart: ECharts | null = null
let sceneChart: ECharts | null = null
let issueChart: ECharts | null = null

// ── 聚合统计 ─────────────────────────────────────────────────
const total = computed(() => jobs.value.length)
const succeededCount = computed(
  () => jobs.value.filter((j) => j.status === 'succeeded' || j.status === 'adopted').length,
)
const failedCount = computed(() => jobs.value.filter((j) => j.status === 'failed').length)
const adoptedCount = computed(() => jobs.value.filter((j) => j.status === 'adopted').length)
const rejectedCount = computed(() => jobs.value.filter((j) => j.status === 'rejected').length)

const adoptionRate = computed(() => {
  const denom = adoptedCount.value + rejectedCount.value
  if (denom === 0) return 0
  return Math.round((adoptedCount.value / denom) * 1000) / 10
})

const openBlockers = computed(() =>
  details.value.reduce((sum, d) => sum + (d.openBlockers || 0), 0),
)

const allIssues = computed<QualityIssue[]>(() =>
  details.value.flatMap((d) => d.issues || []),
)

const sceneLabelMap = computed(() => {
  const m: Record<string, string> = {}
  for (const o of SCENE_OPTIONS) m[o.value] = o.label
  return m
})

const statusStats = computed(() => {
  const m: Record<string, number> = {}
  for (const j of jobs.value) m[j.status] = (m[j.status] || 0) + 1
  return m
})

const sceneStats = computed(() => {
  const m: Record<string, number> = {}
  for (const j of jobs.value) m[j.scene] = (m[j.scene] || 0) + 1
  return m
})

const issueRuleStats = computed(() => {
  const m: Record<string, number> = {}
  for (const i of allIssues.value) m[i.ruleCode] = (m[i.ruleCode] || 0) + 1
  return m
})

interface ProviderHealth {
  provider: string
  total: number
  success: number
  failed: number
  failureRate: number
}

const providerHealth = computed<ProviderHealth[]>(() => {
  const m: Record<string, { total: number; success: number; failed: number }> = {}
  for (const j of jobs.value) {
    const key = j.providerId || j.providerModel || '未指定'
    if (!m[key]) m[key] = { total: 0, success: 0, failed: 0 }
    m[key].total += 1
    if (j.status === 'succeeded' || j.status === 'adopted' || j.status === 'reviewed') {
      m[key].success += 1
    } else if (j.status === 'failed') {
      m[key].failed += 1
    }
  }
  return Object.entries(m).map(([provider, v]) => ({
    provider,
    total: v.total,
    success: v.success,
    failed: v.failed,
    failureRate: v.total === 0 ? 0 : Math.round((v.failed / v.total) * 1000) / 10,
  }))
})

// ── 渲染图表 ─────────────────────────────────────────────────
function renderStatusChart() {
  if (!statusChartEl.value) return
  if (!statusChart) statusChart = echarts.init(statusChartEl.value)
  const data = Object.entries(statusStats.value).map(([k, v]) => ({
    name: JOB_STATUS_LABELS[k] || k,
    value: v,
  }))
  statusChart.setOption({
    title: { text: '任务状态分布', left: 'center', textStyle: { fontSize: 13 } },
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0, type: 'scroll' },
    series: [
      {
        type: 'pie',
        radius: ['38%', '62%'],
        center: ['50%', '46%'],
        data,
        label: { fontSize: 11 },
        itemStyle: { borderColor: '#fff', borderWidth: 2 },
      },
    ],
  })
}

function renderSceneChart() {
  if (!sceneChartEl.value) return
  if (!sceneChart) sceneChart = echarts.init(sceneChartEl.value)
  const entries = Object.entries(sceneStats.value)
  sceneChart.setOption({
    title: { text: '场景分布', left: 'center', textStyle: { fontSize: 13 } },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 40, right: 24, top: 50, bottom: 30 },
    xAxis: {
      type: 'category',
      data: entries.map(([k]) => sceneLabelMap.value[k] || k),
      axisLabel: { fontSize: 11 },
    },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      {
        type: 'bar',
        data: entries.map(([, v]) => v),
        itemStyle: { color: '#409EFF' },
        barMaxWidth: 36,
        label: { show: true, position: 'top', fontSize: 11 },
      },
    ],
  })
}

function renderIssueChart() {
  if (!issueChartEl.value) return
  if (!issueChart) issueChart = echarts.init(issueChartEl.value)
  const entries = Object.entries(issueRuleStats.value).sort((a, b) => b[1] - a[1])
  issueChart.setOption({
    title: { text: '质量问题规则分布', left: 'center', textStyle: { fontSize: 13 } },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 40, right: 24, top: 50, bottom: 60 },
    xAxis: {
      type: 'category',
      data: entries.map(([k]) => RULE_CODE_LABELS[k] || k),
      axisLabel: { fontSize: 10, interval: 0, rotate: 30 },
    },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      {
        type: 'bar',
        data: entries.map(([, v]) => v),
        itemStyle: { color: '#E6A23C' },
        barMaxWidth: 36,
        label: { show: true, position: 'top', fontSize: 11 },
      },
    ],
  })
}

function renderAllCharts() {
  renderStatusChart()
  renderSceneChart()
  renderIssueChart()
}

function handleResize() {
  statusChart?.resize()
  sceneChart?.resize()
  issueChart?.resize()
}

// ── 加载 ─────────────────────────────────────────────────────
async function loadAll() {
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await listAiJobsApi()
    jobs.value = res.data.data.items || []
    // 拉取每个任务的详情以聚合质量问题（allSettled 容错）
    const results = await Promise.allSettled(
      jobs.value.map((j) => getAiJobApi(j.id)),
    )
    const fetched: AiJobDetail[] = []
    for (const r of results) {
      if (r.status === 'fulfilled') {
        fetched.push(r.value.data.data)
      }
    }
    details.value = fetched
    await nextTick()
    renderAllCharts()
  } catch (err: unknown) {
    errorMsg.value = err instanceof Error ? err.message : '加载 AI 治理数据失败'
  } finally {
    loading.value = false
  }
}

function severityLabel(s: string): string {
  return SEVERITY_LABELS[s] || s
}

function ruleLabel(c: string): string {
  return RULE_CODE_LABELS[c] || c
}

function statusLabel(s: string): string {
  return JOB_STATUS_LABELS[s] || s
}

function fmtPct(v: number): string {
  return `${v.toFixed(1)}%`
}

// ── 生命周期 ─────────────────────────────────────────────────
onMounted(loadAll)

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  statusChart?.dispose()
  sceneChart?.dispose()
  issueChart?.dispose()
  statusChart = null
  sceneChart = null
  issueChart = null
})

watch(
  [jobs, details],
  () => nextTick(() => renderAllCharts()),
  { deep: true },
)

window.addEventListener('resize', handleResize)
</script>

<template>
  <div class="page-container" v-loading="loading">
    <div class="page-head">
      <h2 class="page-title">AI 任务治理看板</h2>
      <el-tag size="small" type="success">数据口径：仅真实数据（{{ dataOrigin }}）</el-tag>
    </div>

    <el-alert
      v-if="errorMsg"
      :title="errorMsg"
      type="error"
      :closable="true"
      show-icon
      style="margin-bottom: 16px"
    />

    <!-- 统计卡片 -->
    <div class="stat-cards">
      <el-card shadow="hover" class="stat-card">
        <p class="stat-value">{{ total }}</p>
        <p class="stat-title">AI 任务总数</p>
      </el-card>
      <el-card shadow="hover" class="stat-card">
        <p class="stat-value success">{{ succeededCount }}</p>
        <p class="stat-title">成功（含采用）</p>
      </el-card>
      <el-card shadow="hover" class="stat-card">
        <p class="stat-value danger">{{ failedCount }}</p>
        <p class="stat-title">失败</p>
      </el-card>
      <el-card shadow="hover" class="stat-card">
        <p class="stat-value primary">{{ fmtPct(adoptionRate) }}</p>
        <p class="stat-title">采用率（采用/已决）</p>
      </el-card>
      <el-card shadow="hover" class="stat-card">
        <p class="stat-value danger">{{ openBlockers }}</p>
        <p class="stat-title">未处理阻断问题</p>
      </el-card>
    </div>

    <!-- 图表区 -->
    <div class="chart-grid">
      <el-card shadow="never">
        <div ref="statusChartEl" class="chart-box" />
      </el-card>
      <el-card shadow="never">
        <div ref="sceneChartEl" class="chart-box" />
      </el-card>
    </div>

    <el-card shadow="never" style="margin-top: 16px">
      <div ref="issueChartEl" class="chart-box wide" />
      <el-empty
        v-if="allIssues.length === 0"
        description="暂无质量问题"
        :image-size="60"
        style="margin-top: -260px; pointer-events: none"
      />
    </el-card>

    <!-- Provider 健康 -->
    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <span class="card-title">Provider 健康</span>
      </template>
      <el-table :data="providerHealth" stripe size="small" empty-text="暂无 Provider 数据">
        <el-table-column prop="provider" label="Provider" min-width="160" />
        <el-table-column prop="total" label="任务数" width="100" align="right" />
        <el-table-column prop="success" label="成功" width="100" align="right" />
        <el-table-column prop="failed" label="失败" width="100" align="right" />
        <el-table-column label="失败率" width="220">
          <template #default="{ row }">
            <el-progress
              :percentage="row.failureRate"
              :stroke-width="12"
              :color="row.failureRate > 20 ? '#F56C6C' : row.failureRate > 5 ? '#E6A23C' : '#67C23A'"
            />
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 近期质量问题 -->
    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <span class="card-title">质量问题明细（{{ allIssues.length }}）</span>
      </template>
      <el-table
        :data="allIssues.slice(0, 50)"
        stripe
        size="small"
        empty-text="暂无质量问题"
        max-height="360"
      >
        <el-table-column label="严重度" width="100">
          <template #default="{ row }">
            <el-tag
              size="small"
              :type="(row.severity === 'blocker' ? 'danger' : row.severity === 'warning' ? 'warning' : 'info') as any"
            >
              {{ severityLabel(row.severity) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="规则" min-width="140">
          <template #default="{ row }">{{ ruleLabel(row.ruleCode) }}</template>
        </el-table-column>
        <el-table-column prop="message" label="说明" min-width="240" show-overflow-tooltip />
        <el-table-column prop="objectRef" label="对象引用" min-width="160" show-overflow-tooltip />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="(row.status === 'open' ? 'danger' : 'success') as any">
              {{ row.status === 'open' ? '待处理' : row.status === 'resolved' ? '已处理' : row.status }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.page-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.page-title {
  margin: 0;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
}

.stat-cards {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.stat-card {
  border-radius: 8px;
  text-align: center;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #303133;
  margin: 0;
}

.stat-value.success {
  color: #67c23a;
}

.stat-value.danger {
  color: #f56c6c;
}

.stat-value.primary {
  color: #409eff;
}

.stat-title {
  font-size: 13px;
  color: #909399;
  margin: 4px 0 0;
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

.chart-box.wide {
  height: 300px;
}

@media (max-width: 1024px) {
  .stat-cards {
    grid-template-columns: repeat(2, 1fr);
  }
  .chart-grid {
    grid-template-columns: 1fr;
  }
}
</style>
