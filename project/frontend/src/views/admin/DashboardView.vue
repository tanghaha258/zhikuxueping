<script setup lang="ts">
/**
 * AdminDashboard - 管理后台概览（Task 8：用 ECharts 替换 CSS 柱状图占位）。
 *
 * 阶段验收（计划 3.8.1 / 8.5）：
 * - 默认仅统计真实数据；data_origin_filter 标识当前数据口径。
 * - 对外指标展示公式、周期、样本量、来源和责任人。
 * - 图表使用真实接口（dashboard/stats）而非 CSS 占位。
 */
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { getDashboardStatsApi } from '@/api/dashboard'
import type { DashboardStats, DashboardMetricOverviewItem } from '@/types'
import * as echarts from 'echarts/core'
import { BarChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { ECharts } from 'echarts/core'

echarts.use([
  BarChart,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
  CanvasRenderer,
])

const stats = ref([
  { title: '教师总数', value: 0, icon: 'User', color: '#409EFF' },
  { title: '学生总数', value: 0, icon: 'UserFilled', color: '#67C23A' },
  { title: '项目总数', value: 0, icon: 'FolderOpened', color: '#E6A23C' },
  { title: '活跃用户（本周）', value: 0, icon: 'TrendCharts', color: '#F56C6C' },
])

const dailyStats = ref<DashboardStats['dailyStats']>([])
const recentActivities = ref<DashboardStats['recentActivities']>([])
const metricOverview = ref<DashboardMetricOverviewItem[]>([])
const dataOriginFilter = ref<string>('real')
const updatedAt = ref<string>('')
const metricCount = ref<number>(0)
const loading = ref(false)
const errorMsg = ref('')

const chartContainer = ref<HTMLDivElement | null>(null)
let chart: ECharts | null = null

function renderChart() {
  if (!chartContainer.value) return
  if (!chart) {
    chart = echarts.init(chartContainer.value)
  }
  const categories = dailyStats.value.map((d) => d.date.slice(5))
  const activeUsers = dailyStats.value.map((d) => d.activeUsers)
  const newTasks = dailyStats.value.map((d) => d.newTasks)
  chart.setOption({
    title: { text: '平台数据概览（近 7 天）', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: ['活跃用户', '新增任务'], top: 30 },
    grid: { left: 40, right: 24, top: 70, bottom: 30 },
    xAxis: {
      type: 'category',
      data: categories,
      axisLabel: { fontSize: 11 },
    },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      {
        name: '活跃用户',
        type: 'bar',
        data: activeUsers,
        itemStyle: { color: '#409EFF' },
        barGap: '10%',
      },
      {
        name: '新增任务',
        type: 'bar',
        data: newTasks,
        itemStyle: { color: '#67C23A' },
      },
    ],
  })
}

function handleResize() {
  chart?.resize()
}

onMounted(async () => {
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await getDashboardStatsApi()
    const data = res.data.data
    stats.value[0].value = data.teacherCount
    stats.value[1].value = data.studentCount
    stats.value[2].value = data.projectCount
    stats.value[3].value = data.weeklyActiveUsers
    dailyStats.value = data.dailyStats
    recentActivities.value = data.recentActivities
    metricOverview.value = data.metricOverview ?? []
    metricCount.value = data.metricCount ?? metricOverview.value.length
    dataOriginFilter.value = data.dataOriginFilter ?? 'real'
    updatedAt.value = data.updatedAt ?? ''
    await nextTick()
    renderChart()
  } catch (err: unknown) {
    errorMsg.value =
      err instanceof Error ? err.message : '加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
  chart = null
})

watch(dailyStats, () => {
  nextTick(() => renderChart())
})
</script>

<template>
  <div class="page-container">
    <div class="dashboard-header">
      <h2 class="page-title">系统概览</h2>
      <div class="dashboard-meta">
        <el-tag size="small" type="success">
          数据口径：{{ dataOriginFilter === 'real' ? '仅真实数据' : dataOriginFilter }}
        </el-tag>
        <el-tag v-if="updatedAt" size="small" type="info">
          更新时间：{{ updatedAt.slice(0, 19).replace('T', ' ') }}
        </el-tag>
      </div>
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
      <el-card
        v-for="stat in stats"
        :key="stat.title"
        shadow="hover"
        class="stat-card"
      >
        <div class="stat-card-inner">
          <div>
            <p class="stat-value">{{ stat.value.toLocaleString() }}</p>
            <p class="stat-title">{{ stat.title }}</p>
          </div>
          <el-icon :size="36" :color="stat.color">
            <component :is="stat.icon" />
          </el-icon>
        </div>
      </el-card>
    </div>

    <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 20px;">
      <!-- ECharts 图表（替换原 CSS 柱状图占位） -->
      <el-card shadow="never" v-loading="loading">
        <template #header>
          <span class="card-title">平台数据概览（近 7 天）</span>
        </template>
        <div ref="chartContainer" class="chart-container" />
      </el-card>

      <!-- 最近活动 -->
      <el-card shadow="never">
        <template #header>
          <span class="card-title">最近活动</span>
        </template>

        <div v-for="(act, idx) in recentActivities" :key="idx" class="activity-item">
          <div class="activity-dot" />
          <div class="activity-content">
            <p class="activity-text">
              <strong>{{ act.user }}</strong> {{ act.action }}
            </p>
            <p class="activity-time">{{ act.time }}</p>
          </div>
        </div>
        <el-empty v-if="recentActivities.length === 0" description="暂无活动" />
      </el-card>
    </div>

    <!-- 运营指标概览（阶段验收：公式/周期/样本量/来源/责任人） -->
    <el-card shadow="never" style="margin-top: 20px">
      <template #header>
        <div class="metric-header">
          <span class="card-title">运营指标概览（{{ metricCount }}）</span>
          <span class="metric-hint">
            阶段验收：每项指标可查看公式、周期、样本量、来源与责任人
          </span>
        </div>
      </template>
      <el-table
        :data="metricOverview"
        v-loading="loading"
        empty-text="暂无运营指标"
        stripe
      >
        <el-table-column prop="name" label="指标名称" min-width="160" />
        <el-table-column prop="code" label="代码" min-width="160" />
        <el-table-column prop="formula" label="公式" min-width="240" show-overflow-tooltip />
        <el-table-column prop="period" label="周期" width="90" />
        <el-table-column prop="sampleSize" label="样本量" width="90" align="right" />
        <el-table-column prop="sourceTable" label="来源表" min-width="160" show-overflow-tooltip />
        <el-table-column prop="sourceOwner" label="数据来源责任方" min-width="140" show-overflow-tooltip />
        <el-table-column prop="responsiblePerson" label="责任人" min-width="120" show-overflow-tooltip />
        <el-table-column label="当前值" width="110" align="right">
          <template #default="{ row }">
            <span v-if="row.value !== null && row.value !== undefined">
              {{ row.value }}
            </span>
            <span v-else class="metric-empty">未采集</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.dashboard-meta {
  display: flex;
  gap: 8px;
}

.page-title {
  margin: 0;
}

.stat-card {
  border-radius: 8px;
}

.stat-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.stat-card-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.stat-value {
  font-size: 30px;
  font-weight: 700;
  color: #303133;
  margin: 0;
}

.stat-title {
  font-size: 14px;
  color: #909399;
  margin: 4px 0 0;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
}

.chart-container {
  width: 100%;
  height: 320px;
}

.metric-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.metric-hint {
  font-size: 12px;
  color: #909399;
}

.metric-empty {
  color: #c0c4cc;
  font-style: italic;
}

/* 活动列表 */
.activity-item {
  display: flex;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid #f0f0f0;
}

.activity-item:last-child {
  border-bottom: none;
}

.activity-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #409eff;
  margin-top: 6px;
  flex-shrink: 0;
}

.activity-content {
  flex: 1;
}

.activity-text {
  font-size: 14px;
  color: #303133;
  margin: 0;
  line-height: 1.5;
}

.activity-time {
  font-size: 12px;
  color: #909399;
  margin: 4px 0 0;
}

@media (max-width: 1024px) {
  .stat-cards {
    grid-template-columns: repeat(2, 1fr);
  }
  div[style*='grid-template-columns: 2fr 1fr'] {
    grid-template-columns: 1fr !important;
  }
}
</style>
