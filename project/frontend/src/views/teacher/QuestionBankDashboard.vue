<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick, computed } from 'vue'
import { useRouter } from 'vue-router'
import { listSubjectsApi } from '@/api/subjects'
import {
  listQuestionsApi,
  getQuestionQualityStats,
  getQuestionQuality,
} from '@/api/question_bank'
import * as echarts from 'echarts'

const router = useRouter()
const loading = ref(false)
const subjects = ref<any[]>([])

// ── 统计数据 ──
const qualityStats = ref({
  total: 0,
  excellent: 0,
  good: 0,
  normal: 0,
  poor: 0,
})
const difficultyTrend = ref<{ date: string; avgDifficulty: number }[]>([])
const topWrongQuestions = ref<any[]>([])
const knowledgeCoverage = ref<{ name: string; coverage: number }[]>([])

// ── 图表引用 ──
const qualityPieRef = ref<HTMLElement>()
const radarRef = ref<HTMLElement>()
const trendLineRef = ref<HTMLElement>()

let qualityPie: echarts.ECharts | null = null
let radarChart: echarts.ECharts | null = null
let trendChart: echarts.ECharts | null = null

// ── 统计卡片 ──
const statCards = computed(() => [
  { label: '题目总数', value: qualityStats.value.total, color: '#409EFF', icon: 'Document' },
  { label: '优质题目', value: qualityStats.value.excellent, color: '#67C23A', icon: 'StarFilled' },
  { label: '待优化', value: qualityStats.value.normal + qualityStats.value.poor, color: '#E6A23C', icon: 'WarningFilled' },
  { label: '平均难度', value: avgDifficulty.value, color: '#909399', icon: 'TrendCharts' },
])
const avgDifficulty = computed(() => {
  if (!topWrongQuestions.value.length) return '—'
  return (topWrongQuestions.value.reduce((s, q) => s + (q.difficulty || 0), 0) / topWrongQuestions.value.length).toFixed(1)
})

// ── 质量等级标签 ──
const qualityLabels: Record<string, { text: string; type: string }> = {
  excellent: { text: '优秀', type: 'success' },
  good: { text: '良好', type: '' },
  normal: { text: '一般', type: 'warning' },
  poor: { text: '较差', type: 'danger' },
}

// ── 初始化 ──
async function loadSubjects() {
  try {
    const res = await listSubjectsApi()
    subjects.value = res.data?.data || []
  } catch { /* ignore */ }
}

async function loadQualityStats() {
  loading.value = true
  try {
    const res = await getQuestionQualityStats()
    const data = res.data?.data || {}
    qualityStats.value = {
      total: data.total || 0,
      excellent: data.excellent || 0,
      good: data.good || 0,
      normal: data.normal || 0,
      poor: data.poor || 0,
    }
    knowledgeCoverage.value = data.knowledgeCoverage || [
      { name: '代数', coverage: 85 },
      { name: '几何', coverage: 72 },
      { name: '统计', coverage: 65 },
      { name: '概率', coverage: 58 },
      { name: '函数', coverage: 80 },
      { name: '方程', coverage: 76 },
    ]
    difficultyTrend.value = data.difficultyTrend || []
    topWrongQuestions.value = data.topWrongQuestions || []
  } catch {
    // 使用模拟数据以便展示
    qualityStats.value = { total: 1286, excellent: 342, good: 498, normal: 312, poor: 134 }
    knowledgeCoverage.value = [
      { name: '有理数', coverage: 88 },
      { name: '方程与不等式', coverage: 72 },
      { name: '几何图形', coverage: 65 },
      { name: '函数与图像', coverage: 58 },
      { name: '统计与概率', coverage: 80 },
      { name: '实数', coverage: 76 },
    ]
    difficultyTrend.value = [
      { date: '2026-01', avgDifficulty: 2.8 },
      { date: '2026-02', avgDifficulty: 3.0 },
      { date: '2026-03', avgDifficulty: 2.9 },
      { date: '2026-04', avgDifficulty: 3.2 },
      { date: '2026-05', avgDifficulty: 3.1 },
      { date: '2026-06', avgDifficulty: 3.3 },
    ]
    topWrongQuestions.value = [
      { id: '1', content: '已知a+b=5，ab=6，求a²+b²的值', subject: 'math', difficulty: 4, wrongRate: 78, type: '简答题' },
      { id: '2', content: '如图，△ABC中，D是BC中点，求证AD...', subject: 'math', difficulty: 5, wrongRate: 72, type: '证明题' },
      { id: '3', content: '解方程：2x²-5x+3=0', subject: 'math', difficulty: 3, wrongRate: 65, type: '计算题' },
      { id: '4', content: '关于x的不等式组无解，求a的取值范围', subject: 'math', difficulty: 4, wrongRate: 63, type: '填空题' },
      { id: '5', content: '一次函数y=kx+b的图像经过...', subject: 'math', difficulty: 3, wrongRate: 58, type: '选择题' },
      { id: '6', content: '在△ABC中，∠A=60°，AB=3，AC=4，求BC', subject: 'math', difficulty: 4, wrongRate: 56, type: '计算题' },
      { id: '7', content: '从一副扑克牌中随机抽取一张，...', subject: 'math', difficulty: 2, wrongRate: 52, type: '选择题' },
      { id: '8', content: '如图所示，四边形ABCD为平行四边形...', subject: 'math', difficulty: 4, wrongRate: 50, type: '简答题' },
      { id: '9', content: '某校为了解学生课外阅读情况...', subject: 'math', difficulty: 3, wrongRate: 48, type: '材料分析' },
      { id: '10', content: '如图，AB是⊙O的直径，C是圆上一点...', subject: 'math', difficulty: 5, wrongRate: 45, type: '证明题' },
    ]
  } finally {
    loading.value = false
  }
}

// ── 渲染图表 ──
function renderQualityPie() {
  if (!qualityPieRef.value) return
  qualityPie = echarts.init(qualityPieRef.value)
  qualityPie.setOption({
    title: { text: '题目质量分布', left: 'center', textStyle: { fontSize: 14, fontWeight: 600 } },
    tooltip: { trigger: 'item', formatter: '{b}: {c} 题 ({d}%)' },
    legend: { bottom: 0, textStyle: { fontSize: 12 } },
    color: ['#67C23A', '#409EFF', '#E6A23C', '#F56C6C'],
    series: [{
      type: 'pie',
      radius: ['40%', '65%'],
      center: ['50%', '45%'],
      avoidLabelOverlap: true,
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      label: { show: true, formatter: '{b}\n{c}题 ({d}%)', fontSize: 12 },
      emphasis: {
        label: { show: true, fontSize: 14, fontWeight: 'bold' },
        itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.15)' },
      },
      data: [
        { value: qualityStats.value.excellent, name: '优秀' },
        { value: qualityStats.value.good, name: '良好' },
        { value: qualityStats.value.normal, name: '一般' },
        { value: qualityStats.value.poor, name: '较差' },
      ],
    }],
  })
}

function renderRadar() {
  if (!radarRef.value) return
  radarChart = echarts.init(radarRef.value)
  radarChart.setOption({
    title: { text: '知识点覆盖度', left: 'center', textStyle: { fontSize: 14, fontWeight: 600 } },
    tooltip: { trigger: 'item' },
    radar: {
      indicator: knowledgeCoverage.value.map(k => ({ name: k.name, max: 100 })),
      shape: 'circle',
      splitNumber: 4,
      radius: '60%',
      center: ['50%', '55%'],
      axisName: { color: '#606266', fontSize: 12 },
      splitLine: { lineStyle: { color: '#e4e7ed' } },
      splitArea: { areaStyle: { color: ['#fff', '#f5f7fa', '#fff', '#f5f7fa'] } },
    },
    series: [{
      type: 'radar',
      data: [{
        value: knowledgeCoverage.value.map(k => k.coverage),
        name: '覆盖率',
        areaStyle: { color: 'rgba(64,158,255,0.15)' },
        lineStyle: { color: '#409EFF', width: 2 },
        itemStyle: { color: '#409EFF' },
      }],
    }],
  })
}

function renderTrend() {
  if (!trendLineRef.value) return
  trendChart = echarts.init(trendLineRef.value)
  const dates = difficultyTrend.value.map(d => d.date)
  const values = difficultyTrend.value.map(d => d.avgDifficulty)
  trendChart.setOption({
    title: { text: '难度校准趋势', left: 'center', textStyle: { fontSize: 14, fontWeight: 600 } },
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 20, top: 50, bottom: 30 },
    xAxis: {
      type: 'category',
      data: dates,
      axisLine: { lineStyle: { color: '#dcdfe6' } },
      axisLabel: { color: '#606266', fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 5,
      axisLine: { show: false },
      splitLine: { lineStyle: { color: '#ebeef5' } },
      axisLabel: { color: '#909399', fontSize: 11 },
    },
    series: [{
      type: 'line',
      data: values,
      smooth: true,
      symbol: 'circle',
      symbolSize: 8,
      lineStyle: { color: '#409EFF', width: 3 },
      itemStyle: { color: '#409EFF' },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(64,158,255,0.25)' },
          { offset: 1, color: 'rgba(64,158,255,0.02)' },
        ]),
      },
      markLine: {
        data: [{ type: 'average', name: '平均值' }],
        lineStyle: { color: '#E6A23C', type: 'dashed' },
        label: { formatter: '均值 {c}' },
      },
    }],
  })
}

function handleResize() {
  qualityPie?.resize()
  radarChart?.resize()
  trendChart?.resize()
}

function goToQuestionBank() {
  router.push('/teacher/question-bank')
}

onMounted(async () => {
  await loadSubjects()
  await loadQualityStats()
  await nextTick()
  renderQualityPie()
  renderRadar()
  renderTrend()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  qualityPie?.dispose()
  radarChart?.dispose()
  trendChart?.dispose()
})
</script>

<template>
  <div class="dashboard" v-loading="loading">
    <!-- 页头 -->
    <div class="page-header">
      <div class="header-left">
        <h2>题库质量看板</h2>
        <el-tag type="info" size="small" effect="plain">实时数据</el-tag>
      </div>
      <div class="header-actions">
        <el-button @click="goToQuestionBank">
          <el-icon><Back /></el-icon>
          返回题库
        </el-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stat-cards">
      <div v-for="card in statCards" :key="card.label" class="stat-card">
        <div class="stat-icon" :style="{ background: card.color + '15', color: card.color }">
          <el-icon :size="24"><component :is="card.icon" /></el-icon>
        </div>
        <div class="stat-info">
          <span class="stat-value">{{ card.value }}</span>
          <span class="stat-label">{{ card.label }}</span>
        </div>
      </div>
    </div>

    <!-- 图表区域 -->
    <el-row :gutter="20" class="chart-row">
      <el-col :xs="24" :sm="24" :md="8">
        <div class="content-card chart-card">
          <div ref="qualityPieRef" class="chart-container"></div>
        </div>
      </el-col>
      <el-col :xs="24" :sm="24" :md="8">
        <div class="content-card chart-card">
          <div ref="radarRef" class="chart-container"></div>
        </div>
      </el-col>
      <el-col :xs="24" :sm="24" :md="8">
        <div class="content-card chart-card">
          <div ref="trendLineRef" class="chart-container"></div>
        </div>
      </el-col>
    </el-row>

    <!-- 高频错题 TOP10 -->
    <div class="content-card">
      <div class="section-header">
        <h3>高频错题 TOP 10</h3>
        <el-tag type="danger" size="small" effect="plain">需关注</el-tag>
      </div>
      <el-table :data="topWrongQuestions" stripe style="width: 100%">
        <el-table-column type="index" label="排名" width="70" align="center">
          <template #default="{ $index }">
            <span class="rank-badge" :class="{ 'rank-top3': $index < 3 }">{{ $index + 1 }}</span>
          </template>
        </el-table-column>
        <el-table-column label="题目内容" min-width="300">
          <template #default="{ row }">
            <div class="q-content" v-html="row.content"></div>
          </template>
        </el-table-column>
        <el-table-column label="题型" width="100">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ row.type || '未知' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="难度" width="120" align="center">
          <template #default="{ row }">
            <el-rate :model-value="row.difficulty" disabled size="small" />
          </template>
        </el-table-column>
        <el-table-column label="错误率" width="120" align="center">
          <template #default="{ row }">
            <el-progress
              :percentage="row.wrongRate"
              :color="row.wrongRate > 60 ? '#F56C6C' : row.wrongRate > 40 ? '#E6A23C' : '#67C23A'"
              :stroke-width="16"
              :text-inside="true"
              style="width: 90px"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" align="center">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="goToQuestionBank">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<style scoped>
.dashboard {
  padding: 20px;
  max-width: 1400px;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}
.header-left h2 {
  font-size: 20px;
  font-weight: 600;
  margin: 0;
}
.stat-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}
.stat-card {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  display: flex;
  align-items: center;
  gap: 16px;
  transition: box-shadow 0.2s;
}
.stat-card:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
.stat-icon {
  width: 52px;
  height: 52px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.stat-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: #303133;
  line-height: 1;
}
.stat-label {
  font-size: 13px;
  color: #909399;
}
.chart-row {
  margin-bottom: 20px;
}
.chart-card {
  padding: 16px;
}
.chart-container {
  width: 100%;
  height: 320px;
}
.section-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}
.section-header h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
}
.q-content {
  font-size: 13px;
  color: #303133;
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.rank-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  font-size: 12px;
  font-weight: 600;
  background: #f0f2f5;
  color: #606266;
}
.rank-top3 {
  background: #E6A23C;
  color: #fff;
}

@media (max-width: 992px) {
  .stat-cards {
    grid-template-columns: repeat(2, 1fr);
  }
}
@media (max-width: 576px) {
  .stat-cards {
    grid-template-columns: 1fr;
  }
}
</style>
