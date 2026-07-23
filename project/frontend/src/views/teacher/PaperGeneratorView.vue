<script setup lang="ts">
import { ref, onMounted, computed, watch, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listSubjectsApi } from '@/api/subjects'
import { listTemplatesApi, generatePaperApi, getGeneratedPaperApi, updateGeneratedPaperApi, finalizePaperApi, exportPaperApi, deleteGeneratedPaperApi, listKnowledgePointsApi, formatPaperApi, updateFormattedPaperApi } from '@/api/paper_generator'
import type { SubjectItem, SectionItem } from '@/types'
import draggable from 'vuedraggable'
import SectionGroup from '@/components/paper/SectionGroup.vue'
import PaperFormatPreview from '@/components/paper/PaperFormatPreview.vue'
import StreamingProgress from '@/components/paper/StreamingProgress.vue'

const activeStep = ref(0)
const loading = ref(false)
const subjects = ref<SubjectItem[]>([])
const templates = ref<any[]>([])
const knowledgePoints = ref<any[]>([])

const form = ref({
  title: '',
  subject: '',
  grade: '',
  template_id: undefined as string | undefined,
  difficulty: 'medium',
  knowledgePointInput: '',
  knowledge_points: [] as string[],
})

const generatedPaper = ref<any>(null)
const currentPaperId = ref('')
const editQuestions = ref<any[]>([])
const editTotalScore = ref(100)
const editDuration = ref(90)
const sectionList = ref<any[]>([])

// NEW: section config state
const examType = ref('quiz')
const sections = ref<SectionItem[]>([])
const generating = ref(false)
const elapsedSeconds = ref(0)
const retryAttempt = ref(0)
let timerHandle: number | null = null

const formatDialogVisible = ref(false)
const formattedHtml = ref('')
const formatLoading = ref(false)
const templateTypes = [
  { value: 'quiz', label: '周测（A4）' },
  { value: 'midterm', label: '期中考试（A3）' },
  { value: 'final', label: '期末考试（A3）' },
]

const streamingRef = ref<InstanceType<typeof StreamingProgress> | null>(null)
const showStreaming = ref(false)

const sectionTotalScore = computed(() => sections.value.reduce((s, sec) => s + (sec.total || 0), 0))

const questionTypes = [
  { value: 'choice', label: '选择题' },
  { value: 'fill', label: '填空题' },
  { value: 'essay', label: '简答题/解答题' },
  { value: 'reading', label: '阅读理解' },
  { value: 'listening', label: '听力题' },
  { value: 'cloze', label: '完形填空' },
  { value: 'writing', label: '写作/作文' },
  { value: 'judge', label: '判断题' },
  { value: 'classical', label: '文言文阅读' },
  { value: 'calculate', label: '计算题' },
  { value: 'proof', label: '证明题' },
  { value: 'experiment', label: '实验题' },
  { value: 'material', label: '材料分析题' },
]

const grades = ['7', '8', '9']
const difficulties = [
  { value: 'easy', label: '简单' },
  { value: 'medium', label: '中等' },
  { value: 'hard', label: '困难' },
]
const examTypes = [
  { value: 'general', label: '通用' },
  { value: 'quiz', label: '周测' },
  { value: 'midterm', label: '期中考试' },
  { value: 'final', label: '期末考试' },
]

const filteredByExamType = computed(() => {
  const map: Record<string, any[]> = {}
  const sub = form.value.subject
  const grade = form.value.grade
  for (const t of templates.value) {
    const tSub = t.subject || t.subjectCode
    const tGrade = t.grade
    if (sub && tSub !== sub) continue
    if (grade && tGrade !== grade) continue
    const key = t.examType || t.exam_type || 'general'
    if (!map[key]) map[key] = []
    map[key].push(t)
  }
  return map
})

const filteredKnowledgePoints = computed(() => {
  const sub = form.value.subject
  const grade = form.value.grade
  if (!sub || !grade) return []
  return knowledgePoints.value.filter(
    (kp: any) => kp.subject === sub && kp.grade === grade
  )
})

onMounted(async () => {
  try {
    const [subRes, tplRes] = await Promise.all([
      listSubjectsApi(),
      listTemplatesApi({ limit: 200 }),
    ])
    subjects.value = subRes.data?.data || []
    templates.value = tplRes.data?.data?.items || []
  } catch { /* ignore */ }
})

watch([() => form.value.subject, () => form.value.grade], async ([sub, grade]) => {
  if (sub && grade) {
    try {
      const res = await listKnowledgePointsApi({ subject: sub, grade })
      knowledgePoints.value = res.data?.data || []
    } catch { /* ignore */ }
  } else {
    knowledgePoints.value = []
  }
})

function addKnowledgePoint() {
  const v = form.value.knowledgePointInput.trim()
  if (v && !form.value.knowledge_points.includes(v)) {
    form.value.knowledge_points.push(v)
  }
  form.value.knowledgePointInput = ''
}

function removeKnowledgePoint(idx: number) {
  form.value.knowledge_points.splice(idx, 1)
}

function selectTemplate(tid: string | undefined) {
  form.value.template_id = tid
  if (tid) {
    const tpl = templates.value.find(t => t.id === tid)
    if (tpl && tpl.sections) {
      try {
        const parsed = JSON.parse(tpl.sections)
        parsed.forEach((sec: SectionItem) => calcSectionTotal(sec))
        sections.value = parsed
      } catch { sections.value = [] }
    } else { sections.value = [] }
  } else { sections.value = [] }
}

function addSection() {
  sections.value.push({
    id: `sec_${sections.value.length + 1}`,
    label: '',
    type: 'choice',
    instruction: '',
    count: 1,
    score_per: 1,
    total: 1,
  })
}

function removeSection(idx: number) {
  sections.value.splice(idx, 1)
}

function calcSectionTotal(sec: SectionItem) {
  sec.total = sec.count * sec.score_per
}

function startTimer() {
  elapsedSeconds.value = 0
  timerHandle = window.setInterval(() => { elapsedSeconds.value++ }, 1000)
}

function stopTimer() {
  if (timerHandle !== null) { clearInterval(timerHandle); timerHandle = null }
}

function removeQuestion(idx: number) {
  editQuestions.value.splice(idx, 1)
  handleEditSave()
}

const typeAliases: Record<string, string[]> = {
  choice: ['choice', '单选', '选择题', 'single'],
  fill: ['fill', '填空', '填空题', 'blank'],
  essay: ['essay', 'solve', '简答', '解答', '简答题', '解答题', '问答'],
  reading: ['reading', 'read', 'comprehension', '阅读理解', '阅读', '理解'],
  writing: ['writing', 'write', 'composition', '作文', '写作', '书面表达'],
  judge: ['judge', '判断', '判断题', 'truefalse'],
  cloze: ['cloze', '完形', '完形填空', 'cloze test'],
  classical: ['classical', '文言文', '文言文阅读', '古文'],
  calculate: ['calculate', '计算', '计算题', 'calc'],
  proof: ['proof', '证明', '证明题'],
  experiment: ['experiment', '实验', '实验题', 'exp'],
  material: ['material', '材料', '材料分析', '材料题'],
}

function matchType(aiType: string, secType: string): boolean {
  if (!aiType || !secType) return false
  if (aiType === secType) return true
  const aliases = typeAliases[secType]
  if (!aliases) return false
  return aliases.includes(aiType.toLowerCase())
}

function buildSectionList() {
  const qs = editQuestions.value
  const secs = sections.value
  if (!secs || secs.length === 0) {
    sectionList.value = []
    return
  }
  const used = new Set<number>()
  const result = secs.map(sec => {
    const count = sec.count || 0
    const secType = sec.type || ''
    const questions: any[] = []
    for (let i = 0; i < qs.length && questions.length < count; i++) {
      if (used.has(i)) continue
      if (matchType(qs[i].type, secType)) {
        questions.push(qs[i])
        used.add(i)
      }
    }
    return { ...sec, questions }
  })
  sectionList.value = result
}

function handleUpdateQuestion(sectionId: string, idx: number, question: any) {
  const sec = sectionList.value.find(s => s.id === sectionId)
  if (sec && sec.questions[idx]) {
    sec.questions[idx] = question
  }
}

function handleDeleteQuestion(sectionId: string, idx: number) {
  const sec = sectionList.value.find(s => s.id === sectionId)
  if (sec) {
    sec.questions.splice(idx, 1)
  }
}

function getSectionStartIndex(sectionId: string) {
  let idx = 0
  for (const sec of sectionList.value) {
    if (sec.id === sectionId) break
    idx += sec.questions.length
  }
  return idx
}

async function handleGenerate() {
  if (!form.value.subject) {
    ElMessage.warning('请选择学科')
    return
  }
  if (!form.value.grade) {
    ElMessage.warning('请选择年级')
    return
  }
  generating.value = true
  loading.value = true
  startTimer()
  try {
    const subjectName = subjects.value.find(s => s.code === form.value.subject)?.name || form.value.subject
    const res = await generatePaperApi({
      title: form.value.title || undefined,
      subject: subjectName,
      grade: form.value.grade,
      template_id: form.value.template_id,
      difficulty: form.value.difficulty,
      knowledge_points: form.value.knowledge_points.length > 0 ? form.value.knowledge_points : undefined,
      sections: sections.value.length > 0 ? JSON.stringify(sections.value) : undefined,
      exam_type: examType.value,
    })
    stopTimer()
    currentPaperId.value = res.data.data.id
    generatedPaper.value = res.data.data
    const qs = JSON.parse(res.data.data.questions || '[]')
    editQuestions.value = qs.map((q: any, i: number) => ({
      ...q,
      _editIdx: i,
    }))
    editTotalScore.value = res.data.data.total_score
    editDuration.value = res.data.data.duration
    if (res.data.data.warning) {
      ElMessage.warning(res.data.data.warning)
    }
    activeStep.value = 2
    ElMessage.success('生成成功')
    buildSectionList()
  } catch {
    stopTimer()
    ElMessage.error('生成失败')
  } finally {
    generating.value = false
    loading.value = false
  }
}

function handleGenerateStream() {
  if (!form.value.subject) { ElMessage.warning('请选择学科'); return }
  if (!form.value.grade) { ElMessage.warning('请选择年级'); return }
  showStreaming.value = true
  const subjectName = subjects.value.find(s => s.code === form.value.subject)?.name || form.value.subject
  nextTick(() => {
    streamingRef.value?.startStream('http://localhost:2358/api/v1/paper-generator/generate-stream', {
      subject: subjectName,
      grade: form.value.grade,
      difficulty: form.value.difficulty,
      knowledge_points: form.value.knowledge_points.length > 0 ? form.value.knowledge_points : undefined,
      sections: sections.value.length > 0 ? JSON.stringify(sections.value) : undefined,
      exam_type: examType.value,
    })
  })
}

function handleStreamComplete(data: any, questionsData: any[]) {
  showStreaming.value = false
  const subjectName = subjects.value.find(s => s.code === form.value.subject)?.name || form.value.subject
  const title = data?.title || form.value.title || `${form.value.grade}年级${subjectName}测试卷`
  editQuestions.value = (questionsData || []).map((q: any, i: number) => ({ ...q, _editIdx: i }))
  editTotalScore.value = data?.total_score || 100
  editDuration.value = data?.duration || 90
  generatedPaper.value = { title, questions: JSON.stringify(questionsData || []), total_score: editTotalScore.value, duration: editDuration.value, subject: form.value.subject }
  currentPaperId.value = data?.id || ''
  activeStep.value = 2
  ElMessage.success(`生成完成，共 ${questionsData?.length || 0} 题`)
  buildSectionList()
}

function handleStreamError(msg: string) {
  ElMessage.error(msg || 'AI 出卷失败')
}

async function handleEditSave() {
  loading.value = true
  try {
    let flatQuestions: any[]
    if (sectionList.value.length > 0) {
      flatQuestions = sectionList.value.flatMap((sec: any) => sec.questions)
      editQuestions.value = flatQuestions
    } else {
      flatQuestions = editQuestions.value
    }
    await updateGeneratedPaperApi(currentPaperId.value, {
      questions: JSON.stringify(flatQuestions.map(({ _editIdx, _sectionId, ...q }: any) => q)),
      total_score: editTotalScore.value,
      duration: editDuration.value,
    })
    ElMessage.success('已保存')
  } catch {
    ElMessage.error('保存失败')
  } finally {
    loading.value = false
  }
}

async function handleFinalize() {
  try {
    const res = await finalizePaperApi(currentPaperId.value)
    generatedPaper.value = res.data.data
    activeStep.value = 3
    ElMessage.success('已定稿')
  } catch {
    ElMessage.error('定稿失败')
  }
}

async function handleFormatPaper(type: string) {
  formatLoading.value = true
  try {
    const sub = generatedPaper.value?.subject || form.value.subject
    const res = await formatPaperApi(currentPaperId.value, {
      template_type: type,
      subject: sub,
    })
    formattedHtml.value = res.data?.data?.formattedHtml || res.data?.data?.formatted_html || ''
    if (formattedHtml.value) {
      formatDialogVisible.value = true
      ElMessage.success('试卷转换成功')
    } else {
      ElMessage.warning('转换成功但未返回排版内容')
    }
  } catch {
    ElMessage.error('试卷转换失败')
  } finally {
    formatLoading.value = false
  }
}

async function handleSaveFormatted(html: string) {
  await updateFormattedPaperApi(currentPaperId.value, { formatted_html: html })
  formattedHtml.value = html
}

function handleExportPdf() {
  window.print()
}

async function handleExport(format: string) {
  try {
    if (format === 'html') {
      const res = await exportPaperApi(currentPaperId.value, 'html')
      const w = window.open()
      if (w) {
        w.document.write(res.data as any)
        w.document.close()
      }
    } else {
      ElMessage.info('Word/PDF 导出开发中')
    }
  } catch {
    ElMessage.error('导出失败')
  }
}

async function handleDelete() {
  ElMessageBox.confirm('确定删除此试卷？', '确认', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  }).then(async () => {
    try {
      await deleteGeneratedPaperApi(currentPaperId.value)
      ElMessage.success('已删除')
      activeStep.value = 0
      generatedPaper.value = null
      currentPaperId.value = ''
    } catch {
      ElMessage.error('删除失败')
    }
  })
}

const totalScore = computed(() => {
  if (sectionList.value.length > 0) {
    return sectionList.value.reduce(
      (s, sec) => s + sec.questions.reduce(
        (s2: number, q: any) => s2 + (parseFloat(q.score) || 0), 0
      ), 0
    )
  }
  return editQuestions.value.reduce((s: number, q: any) => s + (parseFloat(q.score) || 0), 0)
})
</script>

<template>
  <div class="paper-generator">
    <h2>AI 出卷</h2>

    <!-- Steps: 1=Config, 2=Preview, 3=Done -->
    <div class="steps">
      <div :class="['step', { active: activeStep === 0, done: activeStep > 0 }]">
        <div class="step-num">1</div>
        <div>配置参数</div>
      </div>
      <div class="step-line" :class="{ done: activeStep > 0 }" />
      <div :class="['step', { active: activeStep === 1 }, { done: activeStep > 1 }]">
        <div class="step-num">2</div>
        <div>AI 生成</div>
      </div>
      <div class="step-line" :class="{ done: activeStep > 1 }" />
      <div :class="['step', { active: activeStep === 2 }, { done: activeStep > 2 }]">
        <div class="step-num">3</div>
        <div>预览 & 编辑</div>
      </div>
      <div class="step-line" :class="{ done: activeStep > 2 }" />
      <div :class="['step', { active: activeStep === 3 }, { done: activeStep > 3 }]">
        <div class="step-num">4</div>
        <div>定稿 & 导出</div>
      </div>
    </div>

    <!-- Step 1: Config -->
    <div v-if="activeStep === 0" class="step-panel">
      <h3 style="margin-bottom:16px;font-size:15px;color:#303133">参数配置</h3>
      <el-form label-width="100px">
        <el-form-item label="试卷标题">
          <el-input v-model="form.title" placeholder="如不填将自动生成" style="width:300px" />
        </el-form-item>
        <el-form-item label="学科">
          <el-select v-model="form.subject" placeholder="请选择" filterable style="width:200px">
            <el-option v-for="s in subjects" :key="s.code || s.id" :label="s.name" :value="s.code || s.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="年级">
          <el-select v-model="form.grade" placeholder="请选择" style="width:200px">
            <el-option v-for="g in grades" :key="g" :label="`${g}年级`" :value="g" />
          </el-select>
        </el-form-item>
        <el-form-item label="难度">
          <el-radio-group v-model="form.difficulty">
            <el-radio v-for="d in difficulties" :key="d.value" :value="d.value">
              {{ d.label }}
            </el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="试卷模板">
          <div v-if="!form.subject || !form.grade" style="color:#909399;font-size:13px">
            请先选择学科和年级以加载匹配的模板
          </div>
          <div v-else class="template-list">
            <div v-for="(items, et) in filteredByExamType" :key="et" style="margin-bottom:12px">
              <div style="font-size:13px;color:#606266;margin-bottom:6px;font-weight:600">
                {{ examTypes.find(e => e.value === et)?.label || et }}
              </div>
              <div v-if="items.length === 0" style="font-size:12px;color:#c0c4cc">暂无此类型模板</div>
              <div v-else style="display:flex;flex-wrap:wrap;gap:4px">
                <el-tag v-for="t in items" :key="t.id"
                  :type="form.template_id === t.id ? 'primary' : 'info'"
                  style="cursor:pointer"
                  @click="selectTemplate(t.id)"
                >
                  {{ t.name }}
                </el-tag>
              </div>
            </div>
            <el-tag :type="!form.template_id ? 'primary' : 'info'"
              style="cursor:pointer;margin-top:4px"
              @click="selectTemplate(undefined)"
            >不使用模板</el-tag>
          </div>
        </el-form-item>
        <el-form-item label="知识点">
          <template v-if="form.subject && form.grade">
            <div style="margin-bottom:8px">
              <el-checkbox-group v-model="form.knowledge_points" class="kp-checkbox-group">
                <el-checkbox v-for="kp in filteredKnowledgePoints" :key="kp.name" :value="kp.name" :label="kp.name" />
              </el-checkbox-group>
            </div>
            <div style="display:flex;gap:8px;align-items:center">
              <el-input v-model="form.knowledgePointInput" placeholder="自定义知识点" style="width:200px" size="small"
                @keyup.enter="addKnowledgePoint" />
              <el-button size="small" @click="addKnowledgePoint">添加</el-button>
            </div>
            <div v-if="form.knowledge_points.length > 0" style="margin-top:6px;display:flex;flex-wrap:wrap;gap:4px">
              <el-tag v-for="(kp, i) in form.knowledge_points" :key="i" size="small" closable @close="removeKnowledgePoint(i)">
                {{ kp }}
              </el-tag>
            </div>
          </template>
          <div v-else style="color:#909399;font-size:13px">
            请先选择学科和年级以加载知识点
          </div>
        </el-form-item>
      </el-form>

      <el-divider />

      <h3 style="margin-bottom:16px;font-size:15px;color:#303133">题型配置</h3>
      <el-form label-width="100px">
        <el-form-item label="考试类型">
          <el-select v-model="examType" style="width:200px">
            <el-option v-for="et in examTypes" :key="et.value" :label="et.label" :value="et.value" />
          </el-select>
        </el-form-item>

        <el-form-item label="题型分布">
          <div v-if="sections.length === 0" style="color:#909399;font-size:13px;padding:8px 0">
            选择模板后将自动加载题型配置，或手动添加题型
          </div>
          <div v-for="(sec, idx) in sections" :key="idx" class="section-row">
            <div class="section-header">
              <span class="section-num">题型 {{ idx + 1 }}</span>
              <el-button text type="danger" size="small" @click="removeSection(idx)">移除</el-button>
            </div>
            <div class="section-fields">
              <el-select v-model="sec.type" style="width:110px" size="small" @change="sec.label = questionTypes.find(q => q.value === sec.type)?.label || sec.label">
                <el-option v-for="qt in questionTypes" :key="qt.value" :label="qt.label" :value="qt.value" />
              </el-select>
              <el-input v-model="sec.label" placeholder="显示名称" size="small" style="width:120px" />
              <div class="field-group">
                <span class="field-label">题数:</span>
                <el-input-number v-model="sec.count" :min="0" :max="100" size="small" style="width:90px" @change="calcSectionTotal(sec)" />
              </div>
              <div class="field-group">
                <span class="field-label">每题:</span>
                <el-input-number v-model="sec.score_per" :min="0.5" :max="100" :step="0.5" size="small" style="width:90px" @change="calcSectionTotal(sec)" />
              </div>
              <span class="section-subtotal">小计: {{ sec.total }}分</span>
            </div>
          </div>
          <el-button text type="primary" size="small" @click="addSection" style="margin-top:8px">+ 添加题型</el-button>
          <div v-if="sections.length > 0" style="margin-top:8px;font-size:13px;color:#606266">
            题型总分合计：<strong>{{ sectionTotalScore }}</strong> 分
          </div>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" size="large" :loading="loading" @click="handleGenerateStream()">
            🚀 AI 开始出卷（流式）
          </el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- Step 2: Generating overlay -->
    <div v-if="generating" class="loading-overlay">
      <div class="loading-card">
        <div class="loading-spinner" />
        <h3 style="margin-top:16px">AI 正在出卷...</h3>
        <div style="margin:20px 0;width:260px">
          <el-progress :percentage="Math.min(Math.floor(elapsedSeconds / 60 * 100), 95)" :stroke-width="8" />
        </div>
        <p style="color:#909399;margin:8px 0">已用时 {{ elapsedSeconds }} 秒</p>
      </div>
    </div>

    <!-- Step 3: Preview & Edit -->
    <div v-if="activeStep === 2 && generatedPaper" class="step-panel">
      <div class="edit-header">
        <el-input v-model="generatedPaper.title" style="width:400px" @change="handleEditSave" />
        <span style="margin-left:16px;color:#909399">总分: {{ totalScore }}</span>
        <span style="margin-left:16px;color:#909399">
          时长:
          <el-input-number v-model="editDuration" :min="10" :max="240" size="small" style="width:90px" @change="handleEditSave" />
          分钟
        </span>
      </div>

      <draggable
        v-if="sectionList.length > 0"
        :list="sectionList"
        item-key="id"
        handle=".section-drag-handle"
        ghost-class="ghost"
        style="margin-bottom:16px"
      >
        <template #item="{ element }">
          <SectionGroup
            :section="element"
            :start-index="getSectionStartIndex(element.id)"
            @update-question="handleUpdateQuestion"
            @delete-question="handleDeleteQuestion"
          />
        </template>
      </draggable>

      <!-- Fallback: flat list when no sections configured -->
      <div v-else class="question-list">
        <div v-for="(q, i) in editQuestions" :key="q._editIdx" class="question-card">
          <div class="q-header">
            <span class="q-num">{{ i + 1 }}.</span>
            <el-select v-model="q.type" size="small" style="width:90px;margin:0 8px" @change="handleEditSave">
              <el-option label="选择题" value="choice" />
              <el-option label="填空题" value="fill" />
              <el-option label="简答题" value="essay" />
            </el-select>
            <span style="color:#909399">分值:</span>
            <el-input-number v-model="q.score" :min="1" :max="50" size="small" style="width:80px;margin:0 8px" @change="handleEditSave" />
            <el-button size="small" text @click="removeQuestion(i)">删除</el-button>
          </div>
          <div class="q-content">
            <el-input v-model="q.content" type="textarea" :rows="2" placeholder="题目内容" @change="handleEditSave" />
          </div>
          <div v-if="q.type === 'choice'" class="q-options">
            <div v-for="(opt, oi) in q.options" :key="oi" class="option-row">
              <el-tag size="small" :type="q.answer === opt ? 'success' : 'info'" style="width:30px;text-align:center">
                {{ String.fromCharCode(65 + oi) }}
              </el-tag>
              <el-input v-model="q.options[oi]" size="small" style="width:200px;margin:0 8px" @change="handleEditSave" />
              <el-radio v-model="q.answer" :value="opt" size="small" @change="handleEditSave">正确答案</el-radio>
            </div>
          </div>
          <div class="q-answer">
            <div style="display:flex;gap:8px;align-items:center">
              <span style="color:#909399;font-size:12px">答案:</span>
              <el-input v-model="q.answer" size="small" style="width:200px" @change="handleEditSave" />
              <span style="color:#909399;font-size:12px">解析:</span>
              <el-input v-model="q.analysis" size="small" style="width:300px" @change="handleEditSave" />
            </div>
          </div>
        </div>
      </div>

      <div style="margin-top:16px;border-top:1px solid #ebeef5;padding-top:16px">
        <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:12px">
          <el-button type="primary" @click="handleFinalize">定稿</el-button>
          <el-button @click="handleEditSave">保存修改</el-button>
          <el-button @click="activeStep = 0">返回修改参数</el-button>
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
          <span style="font-size:13px;color:#909399;margin-right:4px">试卷转换：</span>
          <el-button :loading="formatLoading" size="small" @click="handleFormatPaper('quiz')">周测 A4</el-button>
          <el-button :loading="formatLoading" size="small" @click="handleFormatPaper('midterm')">期中 A3</el-button>
          <el-button :loading="formatLoading" size="small" @click="handleFormatPaper('final')">期末 A3</el-button>
          <el-tag v-if="formattedHtml" type="success" size="small" style="margin-left:8px">已转换</el-tag>
        </div>
      </div>
    </div>

    <!-- Step 4: Done -->
    <div v-if="activeStep === 3" class="step-panel" style="text-align:center;padding:60px">
      <el-result icon="success" title="试卷已定稿">
        <template #extra>
          <div style="display:flex;gap:12px;justify-content:center;flex-wrap:wrap">
            <el-button type="primary" @click="handleExport('html')">预览 HTML</el-button>
            <el-button @click="handleExport('word')">导出 Word</el-button>
            <el-button @click="handleExport('pdf')">导出 PDF</el-button>
            <el-button @click="handleDelete">删除试卷</el-button>
          </div>
        </template>
      </el-result>
      <div v-if="formattedHtml" style="margin-top:24px">
        <h3 style="margin-bottom:16px;font-size:15px;color:#303133;text-align:left">专业排版预览</h3>
        <PaperFormatPreview
          :formatted-html="formattedHtml"
          @save="handleSaveFormatted"
          @export-pdf="handleExportPdf"
        />
      </div>
    </div>

    <!-- Format Preview Dialog (Step 3 转换后弹出) -->
    <el-dialog
      v-model="formatDialogVisible"
      title="试卷排版预览"
      width="90%"
      top="3vh"
      destroy-on-close
    >
      <PaperFormatPreview
        v-if="formattedHtml"
        :formatted-html="formattedHtml"
        @save="handleSaveFormatted"
        @export-pdf="handleExportPdf"
      />
      <template #footer>
        <div style="display:flex;gap:12px;justify-content:flex-end">
          <el-button @click="formatDialogVisible = false">关闭</el-button>
          <el-button type="primary" @click="formatDialogVisible = false; handleFinalize()">定稿</el-button>
        </div>
      </template>
    </el-dialog>

    <!-- Streaming Progress Dialog -->
    <StreamingProgress
      ref="streamingRef"
      v-if="showStreaming"
      @complete="handleStreamComplete"
      @error="handleStreamError"
      @retry="handleGenerateStream"
      @cancel="showStreaming = false"
    />
  </div>
</template>

<style scoped>
.paper-generator {
  max-width: 900px;
  margin: 0 auto;
}
h2 {
  margin-bottom: 24px;
  font-size: 20px;
  font-weight: 600;
}
.steps {
  display: flex;
  align-items: center;
  margin-bottom: 32px;
}
.step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: #909399;
}
.step.active { color: #409eff; font-weight: 600; }
.step.done { color: #67c23a; }
.step-num {
  width: 32px; height: 32px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  background: #e4e7ed; color: #fff; font-weight: 600;
}
.step.active .step-num { background: #409eff; }
.step.done .step-num { background: #67c23a; }
.step-line {
  flex: 1; height: 2px; background: #e4e7ed; margin: 0 12px; margin-bottom: 24px;
}
.step-line.done { background: #67c23a; }
.step-panel {
  background: #fff;
  border-radius: 8px;
  padding: 24px;
  box-shadow: 0 1px 4px rgba(0,0,0,.08);
}
.template-list {
  display: flex;
  flex-wrap: wrap;
}
.edit-header {
  display: flex;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid #ebeef5;
}
.question-card {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 12px;
}
.q-header {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
}
.q-num {
  font-weight: 600;
  font-size: 15px;
}
.q-content {
  margin-bottom: 8px;
}
.q-options {
  margin: 8px 0;
}
.option-row {
  display: flex;
  align-items: center;
  margin-bottom: 4px;
}
.q-answer {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed #e4e7ed;
}
.question-list {
  max-height: 600px;
  overflow-y: auto;
}
.kp-checkbox-group {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.kp-checkbox-group :deep(.el-checkbox) {
  margin-right: 0;
  margin-bottom: 4px;
}
.section-row {
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  padding: 12px;
  margin-bottom: 10px;
}
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.section-num {
  font-weight: 600;
  font-size: 13px;
}
.section-fields {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.field-group {
  display: flex;
  align-items: center;
  gap: 4px;
}
.field-label {
  font-size: 12px;
  color: #909399;
  white-space: nowrap;
}
.section-subtotal {
  font-size: 13px;
  font-weight: 600;
  color: #409eff;
}
.loading-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(255,255,255,0.88);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}
.loading-card {
  background: #fff;
  border-radius: 16px;
  padding: 40px 60px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.12);
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.loading-spinner {
  width: 48px;
  height: 48px;
  border: 4px solid #e4e7ed;
  border-top-color: #409eff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
.ghost { opacity: 0.4; }
</style>
