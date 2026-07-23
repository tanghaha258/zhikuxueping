<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listSubjectsApi } from '@/api/subjects'
import {
  listQuestionsApi, createQuestionApi, getQuestionApi,
  updateQuestionApi, deleteQuestionApi,
  aiGenerateQuestionsApi, batchImportQuestionsApi,
} from '@/api/question_bank'

const loading = ref(false)
const subjects = ref<any[]>([])
const questions = ref<any[]>([])
const total = ref(0)

const filterForm = ref({
  subject: '',
  grade: '',
  question_type: '',
  difficulty_min: 0,
  difficulty_max: 5,
  keyword: '',
  status: '',
  source: '',
})
const pagination = ref({ page: 1, pageSize: 20 })

const grades = ['7', '8', '9']
const questionTypes = [
  { value: 'choice', label: '选择题' },
  { value: 'fill', label: '填空题' },
  { value: 'essay', label: '简答题' },
  { value: 'judge', label: '判断题' },
  { value: 'material', label: '材料分析' },
]
const sources = [
  { value: 'manual', label: '手动录入' },
  { value: 'ai_generated', label: 'AI 生成' },
  { value: 'batch_import', label: '批量导入' },
]
const statusList = [
  { value: 'published', label: '已发布' },
  { value: 'draft', label: '草稿' },
  { value: 'archived', label: '已归档' },
]

const typeLabels: Record<string, string> = {
  choice: '选择题', fill: '填空题', essay: '简答题',
  judge: '判断题', reading: '阅读理解', cloze: '完形填空',
  writing: '写作', classical: '文言文', calculate: '计算题',
  proof: '证明题', experiment: '实验题', material: '材料分析',
}

const subjectMap = computed(() => {
  const map: Record<string, string> = {}
  for (const s of subjects.value) {
    const key = s.code || s.id
    map[key] = s.name
  }
  return map
})

const dialogVisible = ref(false)
const dialogTitle = ref('')
const isEdit = ref(false)
const editingId = ref('')
const form = ref({
  subject: '', grade: '', question_type: 'choice', difficulty: 3,
  content: '', options: '', answer: '', analysis: '', score: 5,
  knowledge_points: '[]',
})

const aiDialogVisible = ref(false)
const aiForm = ref({
  subject: '', grade: '', question_type: 'choice',
  knowledge_points: [] as string[], count: 5, difficulty: 3,
})
const aiLoading = ref(false)

const importDialogVisible = ref(false)
const importText = ref('')
const importLoading = ref(false)

async function loadSubjects() {
  try {
    const res = await listSubjectsApi()
    subjects.value = res.data?.data || []
  } catch { /* ignore */ }
}

async function loadQuestions() {
  loading.value = true
  try {
    const params: Record<string, any> = {
      skip: (pagination.value.page - 1) * pagination.value.pageSize,
      limit: pagination.value.pageSize,
    }
    if (filterForm.value.subject) params.subject = filterForm.value.subject
    if (filterForm.value.grade) params.grade = filterForm.value.grade
    if (filterForm.value.question_type) params.question_type = filterForm.value.question_type
    if (filterForm.value.difficulty_min > 0) params.difficulty_min = filterForm.value.difficulty_min
    if (filterForm.value.difficulty_max < 5) params.difficulty_max = filterForm.value.difficulty_max
    if (filterForm.value.keyword) params.keyword = filterForm.value.keyword
    if (filterForm.value.status) params.status = filterForm.value.status
    if (filterForm.value.source) params.source = filterForm.value.source
    const res = await listQuestionsApi(params)
    questions.value = res.data?.data?.items || []
    total.value = res.data?.data?.total || 0
  } catch { /* ignore */ } finally {
    loading.value = false
  }
}

function onSearch() {
  pagination.value.page = 1
  loadQuestions()
}

function onPageChange(page: number) {
  pagination.value.page = page
  loadQuestions()
}

function onPageSizeChange(size: number) {
  pagination.value.pageSize = size
  pagination.value.page = 1
  loadQuestions()
}

function resetFilter() {
  filterForm.value = { subject: '', grade: '', question_type: '', difficulty_min: 0, difficulty_max: 5, keyword: '', status: '', source: '' }
  onSearch()
}

function openCreate() {
  isEdit.value = false
  editingId.value = ''
  dialogTitle.value = '新增题目'
  form.value = { subject: '', grade: '', question_type: 'choice', difficulty: 3, content: '', options: '', answer: '', analysis: '', score: 5, knowledge_points: '[]' }
  dialogVisible.value = true
}

async function openEdit(id: string) {
  isEdit.value = true
  editingId.value = id
  dialogTitle.value = '编辑题目'
  try {
    const res = await getQuestionApi(id)
    const data = res.data?.data || {}
    form.value = {
      subject: data.subject || '',
      grade: data.grade || '',
      question_type: data.questionType || 'choice',
      difficulty: data.difficulty || 3,
      content: data.content || '',
      options: data.options || '',
      answer: data.answer || '',
      analysis: data.analysis || '',
      score: data.score || 5,
      knowledge_points: data.knowledgePoints || '[]',
    }
    dialogVisible.value = true
  } catch {
    ElMessage.error('加载题目详情失败')
  }
}

async function handleSave() {
  const payload = {
    subject: form.value.subject,
    grade: form.value.grade,
    question_type: form.value.question_type,
    difficulty: form.value.difficulty,
    content: form.value.content,
    options: form.value.options || null,
    answer: form.value.answer || null,
    analysis: form.value.analysis || null,
    score: form.value.score,
    knowledge_points: form.value.knowledge_points || '[]',
  }
  try {
    if (isEdit.value) {
      await updateQuestionApi(editingId.value, payload)
      ElMessage.success('更新成功')
    } else {
      await createQuestionApi(payload)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadQuestions()
  } catch {
    ElMessage.error('保存失败')
  }
}

async function handleDelete(id: string) {
  try {
    await ElMessageBox.confirm('确定删除此题目？', '确认', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
    await deleteQuestionApi(id)
    ElMessage.success('删除成功')
    loadQuestions()
  } catch { /* cancelled */ }
}

function openAiDialog() {
  aiForm.value = {
    subject: filterForm.value.subject || '',
    grade: filterForm.value.grade || '',
    question_type: filterForm.value.question_type || 'choice',
    knowledge_points: [],
    count: 5,
    difficulty: 3,
  }
  aiDialogVisible.value = true
}

async function handleAiGenerate() {
  if (!aiForm.value.subject) { ElMessage.warning('请选择学科'); return }
  if (!aiForm.value.grade) { ElMessage.warning('请选择年级'); return }
  aiLoading.value = true
  try {
    const res = await aiGenerateQuestionsApi({
      subject: aiForm.value.subject,
      grade: aiForm.value.grade,
      question_type: aiForm.value.question_type,
      knowledge_points: aiForm.value.knowledge_points,
      count: aiForm.value.count,
      difficulty: aiForm.value.difficulty,
    })
    ElMessage.success(res.data?.message || '生成成功')
    aiDialogVisible.value = false
    loadQuestions()
  } catch {
    ElMessage.error('AI 生成失败')
  } finally {
    aiLoading.value = false
  }
}

function openImportDialog() {
  importText.value = ''
  importDialogVisible.value = true
}

async function handleBatchImport() {
  if (!importText.value.trim()) { ElMessage.warning('请输入题目 JSON'); return }
  importLoading.value = true
  try {
    let questions: any[]
    try {
      questions = JSON.parse(importText.value.trim())
      if (!Array.isArray(questions)) throw new Error('必须是数组')
    } catch {
      ElMessage.error('JSON 格式无效，请确保是合法的 JSON 数组')
      return
    }
    const res = await batchImportQuestionsApi({ questions })
    const data = res.data?.data || {}
    ElMessage.success(`导入完成：成功 ${data.imported || 0} 题，失败 ${data.failed || 0} 题`)
    if (data.errors?.length > 0) {
      console.error('导入错误:', data.errors)
    }
    importDialogVisible.value = false
    loadQuestions()
  } catch {
    ElMessage.error('批量导入失败')
  } finally {
    importLoading.value = false
  }
}

function parseKp(kpStr: string): string {
  try {
    const kp = JSON.parse(kpStr)
    return Array.isArray(kp) ? kp.join(', ') : kpStr
  } catch { return kpStr }
}

onMounted(() => {
  loadSubjects()
  loadQuestions()
})
</script>

<template>
  <div class="question-bank">
    <div class="page-header">
      <h2>题库管理</h2>
      <div class="header-actions">
        <el-button type="primary" @click="openCreate()">新增题目</el-button>
        <el-button @click="openAiDialog()">AI 生成</el-button>
        <el-button @click="openImportDialog()">批量导入</el-button>
      </div>
    </div>

    <div class="filter-bar">
      <el-form :inline="true" size="small" label-width="auto">
        <el-form-item label="学科">
          <el-select v-model="filterForm.subject" placeholder="全部" clearable style="width:110px">
            <el-option v-for="s in subjects" :key="s.code || s.id" :label="s.name" :value="s.code || s.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="年级">
          <el-select v-model="filterForm.grade" placeholder="全部" clearable style="width:100px">
            <el-option v-for="g in grades" :key="g" :label="`${g}年级`" :value="g" />
          </el-select>
        </el-form-item>
        <el-form-item label="题型">
          <el-select v-model="filterForm.question_type" placeholder="全部" clearable style="width:110px">
            <el-option v-for="qt in questionTypes" :key="qt.value" :label="qt.label" :value="qt.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="难度">
          <el-space>
            <el-select v-model="filterForm.difficulty_min" placeholder="最低" style="width:80px">
              <el-option v-for="n in 5" :key="n" :label="`${n}星`" :value="n" />
            </el-select>
            <span>-</span>
            <el-select v-model="filterForm.difficulty_max" placeholder="最高" style="width:80px">
              <el-option v-for="n in 5" :key="n" :label="`${n}星`" :value="n" />
            </el-select>
          </el-space>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filterForm.status" placeholder="全部" clearable style="width:100px">
            <el-option v-for="st in statusList" :key="st.value" :label="st.label" :value="st.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="来源">
          <el-select v-model="filterForm.source" placeholder="全部" clearable style="width:110px">
            <el-option v-for="src in sources" :key="src.value" :label="src.label" :value="src.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="关键词">
          <el-input v-model="filterForm.keyword" placeholder="搜索题目内容" clearable style="width:180px" @keyup.enter="onSearch" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="onSearch">搜索</el-button>
          <el-button @click="resetFilter">重置</el-button>
        </el-form-item>
      </el-form>
    </div>

    <el-table :data="questions" v-loading="loading" stripe style="width:100%">
      <el-table-column type="index" label="#" width="50" />
      <el-table-column label="题目" min-width="280">
        <template #default="{ row }">
          <div class="q-preview" v-html="row.content?.substring(0, 120)"></div>
        </template>
      </el-table-column>
      <el-table-column label="学科" width="90">
        <template #default="{ row }">{{ subjectMap[row.subject] || row.subject }}</template>
      </el-table-column>
      <el-table-column label="年级" width="80">
        <template #default="{ row }">{{ row.grade }}年级</template>
      </el-table-column>
      <el-table-column label="题型" width="100">
        <template #default="{ row }">{{ typeLabels[row.questionType] || row.questionType }}</template>
      </el-table-column>
      <el-table-column label="难度" width="90">
        <template #default="{ row }">
          <el-rate :model-value="row.difficulty" disabled size="small" />
        </template>
      </el-table-column>
      <el-table-column label="分值" width="70" prop="score" />
      <el-table-column label="来源" width="100">
        <template #default="{ row }">
          <el-tag v-if="row.source === 'ai_generated'" size="small" type="warning">AI生成</el-tag>
          <el-tag v-else-if="row.source === 'batch_import'" size="small">批量导入</el-tag>
          <el-tag v-else size="small" type="info">手动</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag v-if="row.status === 'published'" size="small" type="success">已发布</el-tag>
          <el-tag v-else-if="row.status === 'draft'" size="small">草稿</el-tag>
          <el-tag v-else size="small" type="danger">归档</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button size="small" text type="primary" @click="openEdit(row.id)">编辑</el-button>
          <el-button size="small" text type="danger" @click="handleDelete(row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination-wrap">
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @current-change="onPageChange"
        @size-change="onPageSizeChange"
      />
    </div>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="700px" top="5vh">
      <el-form :model="form" label-width="80px" size="small">
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="学科">
              <el-select v-model="form.subject" filterable style="width:100%">
                <el-option v-for="s in subjects" :key="s.code || s.id" :label="s.name" :value="s.code || s.name" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="年级">
              <el-select v-model="form.grade" style="width:100%">
                <el-option v-for="g in grades" :key="g" :label="`${g}年级`" :value="g" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="题型">
              <el-select v-model="form.question_type" style="width:100%">
                <el-option v-for="qt in questionTypes" :key="qt.value" :label="qt.label" :value="qt.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="难度">
              <el-rate v-model="form.difficulty" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="分值">
              <el-input-number v-model="form.score" :min="0.5" :max="100" :step="0.5" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="题目">
          <el-input v-model="form.content" type="textarea" :rows="3" placeholder="支持 HTML 格式" />
        </el-form-item>
        <el-form-item label="选项" v-if="form.question_type === 'choice'">
          <el-input v-model="form.options" type="textarea" :rows="2" placeholder='[{"label":"A","content":"选项A"},{"label":"B","content":"选项B"}]' />
        </el-form-item>
        <el-form-item label="答案">
          <el-input v-model="form.answer" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="解析">
          <el-input v-model="form.analysis" type="textarea" :rows="2" placeholder="支持 HTML 格式" />
        </el-form-item>
        <el-form-item label="知识点">
          <el-input v-model="form.knowledge_points" placeholder='["知识点1","知识点2"]' />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="aiDialogVisible" title="AI 生成题目" width="500px">
      <el-form :model="aiForm" label-width="80px" size="small">
        <el-form-item label="学科">
          <el-select v-model="aiForm.subject" filterable style="width:100%">
            <el-option v-for="s in subjects" :key="s.code || s.id" :label="s.name" :value="s.code || s.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="年级">
          <el-select v-model="aiForm.grade" style="width:100%">
            <el-option v-for="g in grades" :key="g" :label="`${g}年级`" :value="g" />
          </el-select>
        </el-form-item>
        <el-form-item label="题型">
          <el-select v-model="aiForm.question_type" style="width:100%">
            <el-option v-for="qt in questionTypes" :key="qt.value" :label="qt.label" :value="qt.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="难度">
          <el-rate v-model="aiForm.difficulty" />
        </el-form-item>
        <el-form-item label="数量">
          <el-input-number v-model="aiForm.count" :min="1" :max="20" />
        </el-form-item>
        <el-form-item label="知识点">
          <el-input v-model="aiForm.knowledge_points" placeholder="逗号分隔，如：有理数,方程" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="aiDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="aiLoading" @click="handleAiGenerate">开始生成</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="importDialogVisible" title="批量导入题目" width="600px">
      <p style="color:#909399;font-size:13px;margin-bottom:8px">请输入 JSON 数组，每项包含 subject, grade, question_type, content 等字段：</p>
      <el-input v-model="importText" type="textarea" :rows="12" placeholder='[
  {
    "subject": "math",
    "grade": "7",
    "question_type": "choice",
    "content": "1+1=?",
    "options": "[{\"label\":\"A\",\"content\":\"1\"},{\"label\":\"B\",\"content\":\"2\"}]",
    "answer": "B",
    "difficulty": 1,
    "score": 5
  }
]' />
      <template #footer>
        <el-button @click="importDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="importLoading" @click="handleBatchImport">导入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.question-bank {
  padding: 20px;
  max-width: 1400px;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.page-header h2 {
  font-size: 20px;
  font-weight: 600;
  margin: 0;
}
.header-actions {
  display: flex;
  gap: 8px;
}
.filter-bar {
  background: #fff;
  border-radius: 8px;
  padding: 12px 16px;
  margin-bottom: 16px;
  box-shadow: 0 1px 4px rgba(0,0,0,.06);
}
.q-preview {
  font-size: 13px;
  line-height: 1.5;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
