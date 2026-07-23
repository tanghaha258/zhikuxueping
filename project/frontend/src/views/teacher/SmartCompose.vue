<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { listSubjectsApi } from '@/api/subjects'
import {
  getClassLearningProfile,
  getKnowledgePointStats,
} from '@/api/learning_profile'
import { smartComposeApi } from '@/api/question_bank'
import type { KnowledgePointStat } from '@/api/learning_profile'
import * as echarts from 'echarts'

// ── 基础数据 ──
const subjects = ref<any[]>([])
const classes = ref<{ id: string; name: string }[]>([
  { id: 'c1', name: '七年级(1)班' },
  { id: 'c2', name: '七年级(2)班' },
  { id: 'c3', name: '八年级(1)班' },
  { id: 'c4', name: '八年级(2)班' },
  { id: 'c5', name: '九年级(1)班' },
])

// ── 配置表单 ──
const configForm = ref({
  classId: '',
  subject: '',
  knowledgePoints: [] as string[],
  strategy: 'learning_profile',
  totalScore: 100,
  duration: 90,
  bankRatio: 70,
})

const strategies = [
  { value: 'learning_profile', label: '学情驱动', desc: '根据班级薄弱知识点智能匹配' },
  { value: 'balanced', label: '均衡覆盖', desc: '各知识点均匀分布' },
  { value: 'challenge', label: '拔高挑战', desc: '侧重中高难度题目' },
]

const allKnowledgePoints = ref<string[]>([])
const selectedKnowledgePoints = ref<string[]>([])

// ── 学情分析结果 ──
const classMastery = ref(0)
const weakPoints = ref<KnowledgePointStat[]>([])
const strongPoints = ref<KnowledgePointStat[]>([])
const recommendStrategy = ref('learning_profile')
const analysisReady = ref(false)
const analyzing = ref(false)

// ── 组卷结果 ──
const composing = ref(false)
const composedPaper = ref<any>(null)
const showPreview = ref(false)

// ── 图表引用 ──
const analysisChartRef = ref<HTMLElement>()
let analysisChart: echarts.ECharts | null = null

// ── 统计卡片 ──
const analysisCards = computed(() => [
  { label: '班级掌握度', value: classMastery.value + '%', color: classMastery.value >= 70 ? '#67C23A' : '#E6A23C', icon: 'TrendCharts' },
  { label: '薄弱知识点', value: weakPoints.value.length, color: '#F56C6C', icon: 'WarningFilled' },
  { label: '优势知识点', value: strongPoints.value.length, color: '#67C23A', icon: 'StarFilled' },
  { label: '推荐策略', value: strategies.find(s => s.value === recommendStrategy.value)?.label || '—', color: '#409EFF', icon: 'MagicStick' },
])

// ── 所有可用知识点（模拟） ──
const mockKnowledgePoints: Record<string, string[]> = {
  math: ['有理数运算', '一元一次方程', '一元二次方程', '几何证明', '函数图像', '数据统计', '概率', '实数运算'],
  chinese: ['文言文阅读', '现代文阅读', '写作技巧', '修辞手法', '古诗词鉴赏', '名著阅读'],
  english: ['语法', '阅读理解', '听力', '写作', '词汇', '口语表达'],
  physics: ['力学', '光学', '电学', '热学', '声学', '运动学'],
  chemistry: ['酸碱盐', '化学方程式', '元素化合物', '实验操作', '氧化还原'],
  biology: ['细胞结构', '遗传与变异', '生态系统', '人体生理', '植物生理'],
}

async function loadSubjects() {
  try {
    const res = await listSubjectsApi()
    subjects.value = res.data?.data || []
  } catch { /* ignore */ }
}

// ── 学科变化 → 更新知识点列表 ──
watch(() => configForm.value.subject, (val) => {
  allKnowledgePoints.value = mockKnowledgePoints[val] || []
  selectedKnowledgePoints.value = []
  configForm.value.knowledgePoints = []
  analysisReady.value = false
  composedPaper.value = null
})

// ── 分析班级学情 ──
async function analyzeClass() {
  if (!configForm.value.classId) { ElMessage.warning('请选择班级'); return }
  if (!configForm.value.subject) { ElMessage.warning('请选择学科'); return }

  analyzing.value = true
  analysisReady.value = false

  try {
    const [profileRes, kpRes] = await Promise.allSettled([
      getClassLearningProfile(configForm.value.classId, configForm.value.subject),
      getKnowledgePointStats(configForm.value.classId, configForm.value.subject),
    ])

    let mastery = 72
    let kpStats: KnowledgePointStat[] = []

    if (kpRes.status === 'fulfilled' && kpRes.value.data?.data?.length) {
      kpStats = kpRes.value.data.data
    } else {
      // 使用模拟数据
      kpStats = generateMockKpStats()
    }

    if (profileRes.status === 'fulfilled' && profileRes.value.data?.data) {
      mastery = profileRes.value.data.data.masteryLevel
    }

    classMastery.value = mastery
    weakPoints.value = kpStats.filter(k => k.masteryRate < 60).sort((a, b) => a.masteryRate - b.masteryRate)
    strongPoints.value = kpStats.filter(k => k.masteryRate >= 80).sort((a, b) => b.masteryRate - a.masteryRate)

    // 推荐策略
    if (mastery < 50) {
      recommendStrategy.value = 'learning_profile'
    } else if (mastery < 75) {
      recommendStrategy.value = 'balanced'
    } else {
      recommendStrategy.value = 'challenge'
    }
    configForm.value.strategy = recommendStrategy.value

    analysisReady.value = true
    await nextTick()
    renderAnalysisChart(kpStats)
  } catch {
    // 降级到模拟数据
    classMastery.value = 68
    const mockKp = generateMockKpStats()
    weakPoints.value = mockKp.filter(k => k.masteryRate < 60)
    strongPoints.value = mockKp.filter(k => k.masteryRate >= 80)
    recommendStrategy.value = 'balanced'
    configForm.value.strategy = 'balanced'
    analysisReady.value = true
    await nextTick()
    renderAnalysisChart(mockKp)
  } finally {
    analyzing.value = false
  }
}

function generateMockKpStats(): KnowledgePointStat[] {
  const kps = allKnowledgePoints.value.length ? allKnowledgePoints.value : ['有理数', '方程', '几何', '函数', '统计']
  return kps.map((name, i) => ({
    name,
    masteryRate: Math.floor(30 + Math.random() * 60),
    studentCount: Math.floor(20 + Math.random() * 25),
    averageScore: +(2 + Math.random() * 7).toFixed(1),
    trend: (['up', 'down', 'stable'] as const)[i % 3],
  }))
}

function renderAnalysisChart(kpStats: KnowledgePointStat[]) {
  if (!analysisChartRef.value) return
  analysisChart = echarts.init(analysisChartRef.value)
  analysisChart.setOption({
    title: { text: '知识点掌握度概览', left: 'center', textStyle: { fontSize: 14, fontWeight: 600 } },
    tooltip: { trigger: 'axis' },
    grid: { left: 80, right: 20, top: 50, bottom: 40 },
    xAxis: {
      type: 'category',
      data: kpStats.map(k => k.name),
      axisLabel: { color: '#606266', fontSize: 11, rotate: 25 },
      axisLine: { lineStyle: { color: '#dcdfe6' } },
    },
    yAxis: {
      type: 'value',
      max: 100,
      axisLabel: { color: '#909399', formatter: '{value}%' },
      splitLine: { lineStyle: { color: '#ebeef5' } },
    },
    series: [{
      type: 'bar',
      barWidth: '45%',
      data: kpStats.map(k => ({
        value: k.masteryRate,
        itemStyle: {
          color: k.masteryRate >= 80
            ? '#67C23A'
            : k.masteryRate >= 60
              ? '#409EFF'
              : k.masteryRate >= 40
                ? '#E6A23C'
                : '#F56C6C',
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

// ── 智能组卷 ──
async function handleCompose() {
  if (!configForm.value.classId) { ElMessage.warning('请选择班级'); return }
  if (!configForm.value.subject) { ElMessage.warning('请选择学科'); return }
  if (!analysisReady.value) { ElMessage.warning('请先分析班级学情'); return }

  composing.value = true
  try {
    const res = await smartComposeApi({
      class_id: configForm.value.classId,
      subject: configForm.value.subject,
      knowledge_points: selectedKnowledgePoints.value.length ? selectedKnowledgePoints.value : undefined,
      strategy: configForm.value.strategy,
      total_score: configForm.value.totalScore,
      duration: configForm.value.duration,
      bank_ratio: configForm.value.bankRatio,
    })
    composedPaper.value = res.data?.data || generateMockPaper()
    showPreview.value = true
    ElMessage.success('组卷完成！')
  } catch {
    // 降级使用模拟试卷
    composedPaper.value = generateMockPaper()
    showPreview.value = true
    ElMessage.success('组卷完成（预览模式）')
  } finally {
    composing.value = false
  }
}

function generateMockPaper() {
  const kp = selectedKnowledgePoints.value.length ? selectedKnowledgePoints.value : allKnowledgePoints.value.slice(0, 4)
  return {
    title: `${configForm.value.strategy === 'challenge' ? '拔高' : configForm.value.strategy === 'balanced' ? '均衡' : '学情驱动'}测试卷`,
    totalScore: configForm.value.totalScore,
    duration: configForm.value.duration,
    questionCount: Math.floor(configForm.value.totalScore / 5),
    sections: [
      {
        name: '选择题',
        questions: kp.slice(0, 3).map((name, i) => ({
          id: `q${i + 1}`,
          content: `关于"${name}"的第${i + 1}题...`,
          score: 5,
          difficulty: configForm.value.strategy === 'challenge' ? 4 : 3,
          knowledgePoint: name,
        })),
      },
      {
        name: '填空题',
        questions: kp.slice(0, 2).map((name, i) => ({
          id: `q${i + 4}`,
          content: `"${name}"相关填空第${i + 1}题...`,
          score: 4,
          difficulty: configForm.value.strategy === 'challenge' ? 4 : 2,
          knowledgePoint: name,
        })),
      },
      {
        name: '解答题',
        questions: kp.slice(0, 2).map((name, i) => ({
          id: `q${i + 6}`,
          content: `"${name}"综合应用题第${i + 1}题...`,
          score: 12,
          difficulty: configForm.value.strategy === 'challenge' ? 5 : 3,
          knowledgePoint: name,
        })),
      },
    ],
  }
}

function handleResize() {
  analysisChart?.resize()
}

onMounted(async () => {
  await loadSubjects()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  analysisChart?.dispose()
})
</script>

<template>
  <div class="smart-compose">
    <!-- 页头 -->
    <div class="page-header">
      <div class="header-left">
        <h2>学情驱动智能组卷</h2>
        <el-tag type="primary" size="small" effect="plain">AI 智能</el-tag>
      </div>
    </div>

    <el-row :gutter="20">
      <!-- 左侧：配置面板 -->
      <el-col :xs="24" :md="10" :lg="8">
        <div class="content-card config-panel">
          <div class="section-header">
            <h3>组卷配置</h3>
            <el-tag size="small" effect="plain">配置项</el-tag>
          </div>

          <el-form :model="configForm" label-width="90px" label-position="top" size="default">
            <el-form-item label="选择班级">
              <el-select v-model="configForm.classId" placeholder="请选择班级" style="width:100%">
                <el-option v-for="cls in classes" :key="cls.id" :label="cls.name" :value="cls.id" />
              </el-select>
            </el-form-item>

            <el-form-item label="选择学科">
              <el-select v-model="configForm.subject" placeholder="请选择学科" style="width:100%">
                <el-option v-for="s in subjects" :key="s.code || s.id" :label="s.name" :value="s.code || s.name" />
              </el-select>
            </el-form-item>

            <el-form-item label="知试点范围">
              <el-select
                v-model="selectedKnowledgePoints"
                multiple
                collapse-tags
                collapse-tags-tooltip
                placeholder="留空则自动匹配"
                style="width:100%"
              >
                <el-option v-for="kp in allKnowledgePoints" :key="kp" :label="kp" :value="kp" />
              </el-select>
            </el-form-item>

            <el-form-item label="组卷策略">
              <el-radio-group v-model="configForm.strategy" class="strategy-group">
                <el-radio-button
                  v-for="s in strategies"
                  :key="s.value"
                  :value="s.value"
                >
                  {{ s.label }}
                </el-radio-button>
              </el-radio-group>
              <div class="strategy-desc">
                {{ strategies.find(s => s.value === configForm.strategy)?.desc }}
              </div>
            </el-form-item>

            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="总分">
                  <el-input-number v-model="configForm.totalScore" :min="50" :max="150" :step="10" style="width:100%" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="时长(分钟)">
                  <el-input-number v-model="configForm.duration" :min="30" :max="120" :step="10" style="width:100%" />
                </el-form-item>
              </el-col>
            </el-row>

            <el-form-item label="题库占比">
              <el-slider
                v-model="configForm.bankRatio"
                :min="30"
                :max="100"
                :step="5"
                show-input
                input-size="small"
              />
              <div class="slider-hint">题库题目占 {{ configForm.bankRatio }}%，AI 生成占 {{ 100 - configForm.bankRatio }}%</div>
            </el-form-item>
          </el-form>

          <div class="action-btns">
            <el-button type="primary" :loading="analyzing" @click="analyzeClass" style="width:100%">
              <el-icon><DataAnalysis /></el-icon>
              分析班级学情
            </el-button>
          </div>
        </div>
      </el-col>

      <!-- 右侧：学情分析 -->
      <el-col :xs="24" :md="14" :lg="16">
        <template v-if="analysisReady">
          <!-- 分析统计卡片 -->
          <div class="stat-cards">
            <div v-for="card in analysisCards" :key="card.label" class="stat-card">
              <div class="stat-icon" :style="{ background: card.color + '15', color: card.color }">
                <el-icon :size="24"><component :is="card.icon" /></el-icon>
              </div>
              <div class="stat-info">
                <span class="stat-value">{{ card.value }}</span>
                <span class="stat-label">{{ card.label }}</span>
              </div>
            </div>
          </div>

          <!-- 掌握度图表 -->
          <div class="content-card" style="margin-bottom:20px">
            <div ref="analysisChartRef" class="chart-container"></div>
          </div>

          <!-- 薄弱知识点高亮 -->
          <el-row :gutter="20" style="margin-bottom:20px">
            <el-col :span="12">
              <div class="content-card">
                <div class="section-header">
                  <h3>薄弱知识点</h3>
                  <el-tag type="danger" size="small" effect="plain">优先出题</el-tag>
                </div>
                <div class="tag-list" v-if="weakPoints.length">
                  <div v-for="wp in weakPoints" :key="wp.name" class="kp-item kp-weak">
                    <span class="kp-name">{{ wp.name }}</span>
                    <el-progress
                      :percentage="wp.masteryRate"
                      :color="'#F56C6C'"
                      :stroke-width="10"
                      :text-inside="true"
                      style="width:100px"
                    />
                  </div>
                </div>
                <el-empty v-else description="全部达标" :image-size="50" />
              </div>
            </el-col>
            <el-col :span="12">
              <div class="content-card">
                <div class="section-header">
                  <h3>推荐策略</h3>
                </div>
                <div class="recommend-card">
                  <div class="recommend-icon">
                    <el-icon :size="32" style="color:#409EFF"><MagicStick /></el-icon>
                  </div>
                  <div class="recommend-info">
                    <h4>{{ strategies.find(s => s.value === recommendStrategy)?.label }}</h4>
                    <p>{{ strategies.find(s => s.value === recommendStrategy)?.desc }}</p>
                    <el-tag type="primary" size="small" effect="plain">基于学情自动推荐</el-tag>
                  </div>
                </div>
              </div>
            </el-col>
          </el-row>

          <!-- 组卷按钮 -->
          <div class="content-card compose-action">
            <el-button
              type="primary"
              size="large"
              :loading="composing"
              @click="handleCompose"
              class="compose-btn"
            >
              <el-icon><MagicStick /></el-icon>
              智能组卷
            </el-button>
          </div>
        </template>

        <!-- 未分析时占位 -->
        <div v-else class="content-card empty-state">
          <el-empty description="请先选择班级和学科，然后点击「分析班级学情」">
            <el-icon :size="64" style="color:#dcdfe6"><DataAnalysis /></el-icon>
          </el-empty>
        </div>
      </el-col>
    </el-row>

    <!-- 试卷预览弹窗 -->
    <el-dialog
      v-model="showPreview"
      title="试卷预览"
      width="750px"
      top="5vh"
    >
      <div v-if="composedPaper" class="paper-preview">
        <div class="paper-header">
          <h3>{{ composedPaper.title }}</h3>
          <div class="paper-meta">
            <el-tag size="small">总分: {{ composedPaper.totalScore }}分</el-tag>
            <el-tag size="small" type="info">时长: {{ composedPaper.duration }}分钟</el-tag>
            <el-tag size="small" type="success">共 {{ composedPaper.questionCount }} 题</el-tag>
          </div>
        </div>

        <div v-for="(section, sIdx) in composedPaper.sections" :key="sIdx" class="paper-section">
          <h4 class="section-title">{{ sIdx + 1 }}. {{ section.name }}</h4>
          <div v-for="(q, qIdx) in section.questions" :key="q.id" class="question-item">
            <div class="question-header">
              <span class="question-num">{{ qIdx + 1 }}.</span>
              <span class="question-content">{{ q.content }}</span>
              <span class="question-score">({{ q.score }}分)</span>
            </div>
            <div class="question-tags">
              <el-tag size="small" effect="plain">{{ q.knowledgePoint }}</el-tag>
              <el-tag size="small" :type="q.difficulty >= 4 ? 'danger' : q.difficulty >= 3 ? 'warning' : 'success'" effect="plain">
                难度 {{ q.difficulty }}
              </el-tag>
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="showPreview = false">关闭</el-button>
        <el-button type="primary">导出试卷</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.smart-compose {
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
.content-card {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
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

/* 配置面板 */
.config-panel {
  position: sticky;
  top: 20px;
}
.strategy-group {
  width: 100%;
}
.strategy-desc {
  font-size: 12px;
  color: #909399;
  margin-top: 6px;
  line-height: 1.4;
}
.slider-hint {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
.action-btns {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #ebeef5;
}

/* 统计卡片 */
.stat-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}
.stat-card {
  background: #fff;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  display: flex;
  align-items: center;
  gap: 12px;
  transition: box-shadow 0.2s;
}
.stat-card:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
.stat-icon {
  width: 48px;
  height: 48px;
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
  font-size: 20px;
  font-weight: 700;
  color: #303133;
  line-height: 1;
}
.stat-label {
  font-size: 12px;
  color: #909399;
}

/* 图表 */
.chart-container {
  width: 100%;
  height: 300px;
}

/* 知识点列表 */
.tag-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.kp-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  border-radius: 6px;
  background: #f9fafc;
}
.kp-weak {
  border-left: 3px solid #F56C6C;
}
.kp-name {
  font-size: 13px;
  color: #303133;
  font-weight: 500;
  min-width: 80px;
}

/* 推荐策略卡片 */
.recommend-card {
  display: flex;
  gap: 16px;
  align-items: center;
  padding: 16px;
  background: linear-gradient(135deg, #f0f7ff 0%, #e8f4fd 100%);
  border-radius: 8px;
  border: 1px solid #d9ecff;
}
.recommend-icon {
  width: 56px;
  height: 56px;
  background: #fff;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(64,158,255,0.15);
}
.recommend-info h4 {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 4px;
  color: #303133;
}
.recommend-info p {
  font-size: 13px;
  color: #606266;
  margin: 0 0 6px;
  line-height: 1.4;
}

/* 组卷按钮 */
.compose-action {
  text-align: center;
  padding: 24px;
}
.compose-btn {
  min-width: 200px;
  height: 48px;
  font-size: 16px;
  border-radius: 8px;
}

/* 空状态 */
.empty-state {
  min-height: 400px;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 试卷预览 */
.paper-preview {
  max-height: 60vh;
  overflow-y: auto;
}
.paper-header {
  text-align: center;
  padding-bottom: 16px;
  border-bottom: 2px solid #303133;
  margin-bottom: 16px;
}
.paper-header h3 {
  font-size: 18px;
  font-weight: 700;
  margin: 0 0 8px;
  color: #303133;
}
.paper-meta {
  display: flex;
  justify-content: center;
  gap: 10px;
}
.paper-section {
  margin-bottom: 20px;
}
.section-title {
  font-size: 15px;
  font-weight: 600;
  margin: 0 0 10px;
  padding: 6px 0;
  border-bottom: 1px dashed #dcdfe6;
  color: #303133;
}
.question-item {
  padding: 10px 0;
  border-bottom: 1px solid #f5f7fa;
}
.question-header {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin-bottom: 6px;
}
.question-num {
  font-weight: 600;
  color: #303133;
  flex-shrink: 0;
}
.question-content {
  font-size: 13px;
  color: #606266;
  line-height: 1.5;
  flex: 1;
}
.question-score {
  font-size: 13px;
  color: #909399;
  flex-shrink: 0;
}
.question-tags {
  display: flex;
  gap: 6px;
  padding-left: 22px;
}

@media (max-width: 992px) {
  .stat-cards {
    grid-template-columns: repeat(2, 1fr);
  }
  .config-panel {
    position: static;
    margin-bottom: 20px;
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
