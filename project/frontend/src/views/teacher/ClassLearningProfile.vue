<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { listSubjectsApi } from '@/api/subjects'
import {
  getClassLearningProfile,
  getClassStudentList,
  getKnowledgePointStats,
  generateClassReport,
} from '@/api/learning_profile'
import type {
  ClassLearningProfile as CLP,
  ClassStudentSummary,
  KnowledgePointStat,
} from '@/api/learning_profile'
import * as echarts from 'echarts'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const subjects = ref<any[]>([])
const selectedSubject = ref('')
const classId = computed(() => route.params.id as string)

// ── 数据 ──
const profile = ref<CLP | null>(null)
const students = ref<ClassStudentSummary[]>([])
const knowledgeStats = ref<KnowledgePointStat[]>([])

// ── 图表引用 ──
const barChartRef = ref<HTMLElement>()
const pieChartRef = ref<HTMLElement>()
let barChart: echarts.ECharts | null = null
let pieChart: echarts.ECharts | null = null

// ── 统计卡片 ──
const statCards = computed(() => {
  const p = profile.value
  if (!p) return []
  return [
    { label: '学生总数', value: p.totalStudents, color: '#409EFF', icon: 'User' },
    { label: '整体掌握度', value: p.masteryLevel + '%', color: p.masteryLevel >= 70 ? '#67C23A' : '#E6A23C', icon: 'TrendCharts' },
    { label: '平均分', value: p.averageScore.toFixed(1), color: '#909399', icon: 'DataLine' },
    { label: '优势知识点', value: p.strongPoints.length, color: '#67C23A', icon: 'StarFilled' },
  ]
})

// ── 掌握度分布标签颜色 ──
function masteryTagType(level: number): string {
  if (level >= 80) return 'success'
  if (level >= 60) return ''
  if (level >= 40) return 'warning'
  return 'danger'
}

function masteryTagText(level: number): string {
  if (level >= 80) return '优秀'
  if (level >= 60) return '良好'
  if (level >= 40) return '一般'
  return '薄弱'
}

function priorityTagType(p: string): string {
  if (p === 'high') return 'danger'
  if (p === 'medium') return 'warning'
  return 'info'
}

function priorityText(p: string): string {
  if (p === 'high') return '高优先'
  if (p === 'medium') return '中优先'
  return '低优先'
}

// ── 加载数据 ──
async function loadSubjects() {
  try {
    const res = await listSubjectsApi()
    subjects.value = res.data?.data || []
  } catch { /* ignore */ }
}

async function loadProfile() {
  loading.value = true
  try {
    const [profileRes, studentRes, knowledgeRes] = await Promise.allSettled([
      getClassLearningProfile(classId.value, selectedSubject.value),
      getClassStudentList(classId.value, selectedSubject.value),
      getKnowledgePointStats(classId.value, selectedSubject.value),
    ])

    if (profileRes.status === 'fulfilled') {
      profile.value = profileRes.value.data?.data || null
    }
    if (studentRes.status === 'fulfilled') {
      students.value = studentRes.value.data?.data || []
    }
    if (knowledgeRes.status === 'fulfilled') {
      knowledgeStats.value = knowledgeRes.value.data?.data || []
    }

    // 如果数据为空则使用模拟数据
    if (!profile.value) {
      useMockData()
    }
  } catch {
    useMockData()
  } finally {
    loading.value = false
    await nextTick()
    renderCharts()
  }
}

function useMockData() {
  profile.value = {
    classId: classId.value,
    className: '七年级(1)班',
    subject: selectedSubject.value || 'math',
    totalStudents: 45,
    averageScore: 76.5,
    masteryLevel: 72,
    masteryDistribution: { excellent: 12, good: 18, normal: 10, weak: 5 },
    strongPoints: ['有理数运算', '一元一次方程', '图形认识'],
    weakPoints: ['一元二次方程', '几何证明', '函数图像'],
    teachingSuggestions: [
      { category: '教学策略', title: '加强几何证明训练', content: '班级在几何证明题上得分率较低，建议增加辅助线构造的专项训练，每周安排2次几何专题练习。', priority: 'high' },
      { category: '分层教学', title: '函数概念分层讲解', content: '部分学生对函数概念理解不深，建议用生活实例引入，由浅入深分层讲解。', priority: 'medium' },
      { category: '作业设计', title: '设计阶梯式作业', content: '为不同层次学生设计A/B/C三档作业，确保每人都在最近发展区内练习。', priority: 'medium' },
      { category: '课堂活动', title: '增加小组合作探究', content: '薄弱知识点可通过小组讨论、同伴互教的方式强化，提升参与度和理解深度。', priority: 'low' },
    ],
    knowledgePointStats: [
      { name: '有理数运算', masteryRate: 88, studentCount: 42, averageScore: 8.5, trend: 'up' },
      { name: '一元一次方程', masteryRate: 82, studentCount: 40, averageScore: 8.2, trend: 'up' },
      { name: '图形认识', masteryRate: 78, studentCount: 38, averageScore: 7.8, trend: 'stable' },
      { name: '数据统计', masteryRate: 75, studentCount: 37, averageScore: 7.5, trend: 'up' },
      { name: '一元二次方程', masteryRate: 55, studentCount: 30, averageScore: 5.8, trend: 'down' },
      { name: '几何证明', masteryRate: 48, studentCount: 27, averageScore: 5.2, trend: 'down' },
      { name: '函数图像', masteryRate: 42, studentCount: 24, averageScore: 4.8, trend: 'stable' },
    ],
  }
  knowledgeStats.value = profile.value.knowledgePointStats
  students.value = [
    { studentId: 's1', studentName: '张明', averageScore: 92, rank: 1, masteryLevel: 92, strongPoints: ['有理数运算', '方程'], weakPoints: [], trend: 'up' },
    { studentId: 's2', studentName: '李华', averageScore: 88, rank: 2, masteryLevel: 88, strongPoints: ['图形认识'], weakPoints: ['几何证明'], trend: 'up' },
    { studentId: 's3', studentName: '王芳', averageScore: 85, rank: 3, masteryLevel: 85, strongPoints: ['一元一次方程'], weakPoints: [], trend: 'stable' },
    { studentId: 's4', studentName: '赵强', averageScore: 78, rank: 8, masteryLevel: 78, strongPoints: ['数据统计'], weakPoints: ['一元二次方程', '函数图像'], trend: 'down' },
    { studentId: 's5', studentName: '刘洋', averageScore: 72, rank: 12, masteryLevel: 72, strongPoints: [], weakPoints: ['几何证明', '函数图像'], trend: 'stable' },
    { studentId: 's6', studentName: '陈静', averageScore: 68, rank: 15, masteryLevel: 68, strongPoints: ['有理数运算'], weakPoints: ['几何证明'], trend: 'up' },
    { studentId: 's7', studentName: '周杰', averageScore: 55, rank: 25, masteryLevel: 55, strongPoints: [], weakPoints: ['一元二次方程', '几何证明', '函数图像'], trend: 'down' },
    { studentId: 's8', studentName: '吴娜', averageScore: 48, rank: 32, masteryLevel: 48, strongPoints: [], weakPoints: ['一元一次方程', '几何证明', '函数图像', '数据统计'], trend: 'down' },
  ]
}

// ── 图表渲染 ──
function renderBarChart() {
  if (!barChartRef.value || !knowledgeStats.value.length) return
  barChart = echarts.init(barChartRef.value)
  barChart.setOption({
    title: { text: '知识点掌握度', left: 'center', textStyle: { fontSize: 14, fontWeight: 600 } },
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const d = params[0]
        return `${d.name}<br/>掌握率: <b>${d.value}%</b>`
      },
    },
    legend: { show: false },
    grid: { left: 60, right: 20, top: 50, bottom: 40 },
    xAxis: {
      type: 'category',
      data: knowledgeStats.value.map(k => k.name),
      axisLabel: { color: '#606266', fontSize: 11, rotate: 20 },
      axisLine: { lineStyle: { color: '#dcdfe6' } },
    },
    yAxis: {
      type: 'value',
      max: 100,
      axisLabel: { color: '#909399', fontSize: 11, formatter: '{value}%' },
      splitLine: { lineStyle: { color: '#ebeef5' } },
    },
    series: [{
      type: 'bar',
      barWidth: '50%',
      data: knowledgeStats.value.map(k => ({
        value: k.masteryRate,
        itemStyle: {
          color: k.masteryRate >= 70
            ? new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: '#67C23A' }, { offset: 1, color: '#85ce61' }])
            : k.masteryRate >= 50
              ? new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: '#E6A23C' }, { offset: 1, color: '#ebb563' }])
              : new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: '#F56C6C' }, { offset: 1, color: '#f78989' }]),
          borderRadius: [4, 4, 0, 0],
        },
      })),
      label: {
        show: true,
        position: 'top',
        formatter: '{c}%',
        fontSize: 11,
        color: '#606266',
      },
    }],
  })
}

function renderPieChart() {
  if (!pieChartRef.value || !profile.value) return
  pieChart = echarts.init(pieChartRef.value)
  const dist = profile.value.masteryDistribution
  pieChart.setOption({
    title: { text: '学生掌握度分布', left: 'center', textStyle: { fontSize: 14, fontWeight: 600 } },
    tooltip: { trigger: 'item', formatter: '{b}: {c}人 ({d}%)' },
    legend: { bottom: 0, textStyle: { fontSize: 12 } },
    color: ['#67C23A', '#409EFF', '#E6A23C', '#F56C6C'],
    series: [{
      type: 'pie',
      radius: ['38%', '62%'],
      center: ['50%', '45%'],
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      label: { show: true, formatter: '{b}\n{c}人', fontSize: 12 },
      emphasis: {
        label: { show: true, fontSize: 14, fontWeight: 'bold' },
        itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.15)' },
      },
      data: [
        { value: dist.excellent, name: '优秀(≥80)' },
        { value: dist.good, name: '良好(60-79)' },
        { value: dist.normal, name: '一般(40-59)' },
        { value: dist.weak, name: '薄弱(<40)' },
      ],
    }],
  })
}

function renderCharts() {
  renderBarChart()
  renderPieChart()
}

function handleResize() {
  barChart?.resize()
  pieChart?.resize()
}

function onSubjectChange() {
  loadProfile()
}

async function handleGenerateReport() {
  try {
    await generateClassReport(classId.value, selectedSubject.value)
    ElMessage.success('学情报告生成成功')
  } catch {
    ElMessage.error('报告生成失败')
  }
}

function goToStudent(studentId: string) {
  router.push(`/teacher/students/${studentId}/learning-profile`)
}

onMounted(async () => {
  await loadSubjects()
  if (subjects.value.length && !selectedSubject.value) {
    selectedSubject.value = subjects.value[0].code || subjects.value[0].name || 'math'
  }
  await loadProfile()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  barChart?.dispose()
  pieChart?.dispose()
})
</script>

<template>
  <div class="learning-profile" v-loading="loading">
    <!-- 页头 -->
    <div class="page-header">
      <div class="header-left">
        <el-button text @click="router.back()">
          <el-icon><ArrowLeft /></el-icon>返回
        </el-button>
        <h2>班级学情分析</h2>
      </div>
      <div class="header-actions">
        <el-select v-model="selectedSubject" placeholder="选择学科" style="width:140px" @change="onSubjectChange">
          <el-option v-for="s in subjects" :key="s.code || s.id" :label="s.name" :value="s.code || s.name" />
        </el-select>
        <el-button type="primary" @click="handleGenerateReport">生成学情报告</el-button>
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
      <el-col :xs="24" :md="14">
        <div class="content-card chart-card">
          <div ref="barChartRef" class="chart-container"></div>
        </div>
      </el-col>
      <el-col :xs="24" :md="10">
        <div class="content-card chart-card">
          <div ref="pieChartRef" class="chart-container"></div>
        </div>
      </el-col>
    </el-row>

    <!-- 知识点掌握度详情 -->
    <el-row :gutter="20">
      <!-- 薄弱知识点 -->
      <el-col :xs="24" :md="12">
        <div class="content-card">
          <div class="section-header">
            <h3>薄弱知识点</h3>
            <el-tag type="danger" size="small" effect="plain">需重点关注</el-tag>
          </div>
          <div class="tag-list" v-if="profile?.weakPoints?.length">
            <el-tag
              v-for="wp in profile.weakPoints"
              :key="wp"
              type="danger"
              effect="dark"
              size="large"
              class="weak-tag"
            >
              <el-icon><WarningFilled /></el-icon>
              {{ wp }}
            </el-tag>
          </div>
          <el-empty v-else description="暂无薄弱知识点" :image-size="60" />
        </div>
      </el-col>

      <!-- 优势知识点 -->
      <el-col :xs="24" :md="12">
        <div class="content-card">
          <div class="section-header">
            <h3>优势知识点</h3>
            <el-tag type="success" size="small" effect="plain">继续保持</el-tag>
          </div>
          <div class="tag-list" v-if="profile?.strongPoints?.length">
            <el-tag
              v-for="sp in profile.strongPoints"
              :key="sp"
              type="success"
              effect="dark"
              size="large"
              class="strong-tag"
            >
              <el-icon><CircleCheckFilled /></el-icon>
              {{ sp }}
            </el-tag>
          </div>
          <el-empty v-else description="暂无优势知识点" :image-size="60" />
        </div>
      </el-col>
    </el-row>

    <!-- 教学建议 -->
    <div class="content-card" style="margin-top:20px">
      <div class="section-header">
        <h3>教学建议</h3>
        <el-tag size="small" effect="plain">AI 生成</el-tag>
      </div>
      <div class="suggestion-grid" v-if="profile?.teachingSuggestions?.length">
        <div v-for="(sug, idx) in profile.teachingSuggestions" :key="idx" class="suggestion-card">
          <div class="suggestion-header">
            <el-tag :type="priorityTagType(sug.priority)" size="small" effect="plain">{{ priorityText(sug.priority) }}</el-tag>
            <span class="suggestion-category">{{ sug.category }}</span>
          </div>
          <h4 class="suggestion-title">{{ sug.title }}</h4>
          <p class="suggestion-content">{{ sug.content }}</p>
        </div>
      </div>
      <el-empty v-else description="暂无教学建议" />
    </div>

    <!-- 学生个人学情表格 -->
    <div class="content-card" style="margin-top:20px">
      <div class="section-header">
        <h3>学生个人学情</h3>
        <el-tag type="info" size="small" effect="plain">共 {{ students.length }} 人</el-tag>
      </div>
      <el-table :data="students" stripe style="width:100%">
        <el-table-column type="index" label="#" width="50" />
        <el-table-column label="姓名" width="100" prop="studentName" />
        <el-table-column label="掌握度" width="120" align="center">
          <template #default="{ row }">
            <el-progress
              :percentage="row.masteryLevel"
              :color="row.masteryLevel >= 70 ? '#67C23A' : row.masteryLevel >= 50 ? '#E6A23C' : '#F56C6C'"
              :stroke-width="14"
              :text-inside="true"
              style="width:90px"
            />
          </template>
        </el-table-column>
        <el-table-column label="评级" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="masteryTagType(row.masteryLevel)" size="small" effect="plain">
              {{ masteryTagText(row.masteryLevel) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="优势知识点" min-width="160">
          <template #default="{ row }">
            <el-tag v-for="sp in (row.strongPoints || []).slice(0, 2)" :key="sp" size="small" type="success" effect="plain" style="margin-right:4px">
              {{ sp }}
            </el-tag>
            <span v-if="!(row.strongPoints || []).length" class="text-muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="薄弱知识点" min-width="180">
          <template #default="{ row }">
            <el-tag v-for="wp in (row.weakPoints || []).slice(0, 3)" :key="wp" size="small" type="danger" effect="plain" style="margin-right:4px">
              {{ wp }}
            </el-tag>
            <span v-if="!(row.weakPoints || []).length" class="text-muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="趋势" width="80" align="center">
          <template #default="{ row }">
            <el-icon v-if="row.trend === 'up'" style="color:#67C23A"><Top /></el-icon>
            <el-icon v-else-if="row.trend === 'down'" style="color:#F56C6C"><Bottom /></el-icon>
            <el-icon v-else style="color:#909399"><Minus /></el-icon>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right" align="center">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="goToStudent(row.studentId)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<style scoped>
.learning-profile {
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
.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
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
.content-card {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
.chart-row {
  margin-bottom: 20px;
}
.chart-card {
  padding: 16px;
}
.chart-container {
  width: 100%;
  height: 340px;
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
.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.weak-tag,
.strong-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
  padding: 8px 16px;
}
.suggestion-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}
.suggestion-card {
  background: #f9fafc;
  border-radius: 8px;
  padding: 16px;
  border: 1px solid #ebeef5;
  transition: box-shadow 0.2s;
}
.suggestion-card:hover {
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}
.suggestion-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.suggestion-category {
  font-size: 12px;
  color: #909399;
}
.suggestion-title {
  font-size: 14px;
  font-weight: 600;
  margin: 0 0 6px;
  color: #303133;
}
.suggestion-content {
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
  margin: 0;
}
.text-muted {
  color: #c0c4cc;
  font-size: 13px;
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
  .page-header {
    flex-direction: column;
    gap: 12px;
    align-items: flex-start;
  }
}
</style>
