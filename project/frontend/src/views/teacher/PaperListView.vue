<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listPapersApi, createPaperApi, deletePaperApi, setAnswerKeyApi, getAnswerKeyApi, distributePaperApi } from '@/api/papers'
import { listSchoolsApi, listClassesBySchoolApi } from '@/api/schools'
import type { Paper, PaperCreateForm, AnswerKeyQuestion, ClassItem } from '@/types'

const router = useRouter()
const papers = ref<Paper[]>([])
const loading = ref(false)

const createDialogVisible = ref(false)
const createForm = ref<PaperCreateForm>({ title: '', class_ids: [] })
const classes = ref<ClassItem[]>([])

const questionDialogVisible = ref(false)
const currentPaperId = ref('')
const questionForm = ref({
  total_score: 100,
  questions: [] as AnswerKeyQuestion[],
})
const questionLoading = ref(false)

async function fetchPapers() {
  loading.value = true
  try {
    const res = await listPapersApi({ limit: 100 })
    papers.value = res.data.data.items
  } finally {
    loading.value = false
  }
}

async function fetchClasses() {
  try {
    const schoolsRes = await listSchoolsApi()
    const schools = schoolsRes.data.data
    const all: ClassItem[] = []
    for (const s of schools) {
      const clsRes = await listClassesBySchoolApi(s.id)
      all.push(...clsRes.data.data)
    }
    classes.value = all
  } catch { /* ignore */ }
}

function openCreateDialog() {
  createForm.value = { title: '', class_ids: [] }
  fetchClasses()
  createDialogVisible.value = true
}

async function handleCreate() {
  if (!createForm.value.title) {
    ElMessage.warning('请输入试卷名称')
    return
  }
  try {
    await createPaperApi(createForm.value)
    ElMessage.success('创建成功')
    createDialogVisible.value = false
    fetchPapers()
  } catch {
    ElMessage.error('创建失败')
  }
}

function handleDelete(paper: Paper) {
  ElMessageBox.confirm(`确定删除试卷「${paper.title}」？`, '确认删除', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  }).then(async () => {
    try {
      await deletePaperApi(paper.id)
      ElMessage.success('已删除')
      fetchPapers()
    } catch {
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}

async function handleDistribute(paper: Paper) {
  try {
    const res = await distributePaperApi(paper.id)
    ElMessage.success(`已分发 ${res.data.data.distributed} 份答卷`)
    fetchPapers()
  } catch {
    ElMessage.error('分发失败')
  }
}

function openQuestionDialog(paper: Paper) {
  currentPaperId.value = paper.id
  questionForm.value = { total_score: 100, questions: [] }
  questionLoading.value = true
  questionDialogVisible.value = true
  getAnswerKeyApi(paper.id).then((res) => {
    const ak = res.data.data
    questionForm.value.total_score = ak.totalScore
    questionForm.value.questions = ak.questions.length > 0 ? ak.questions : [{ index: 0, type: 'essay', score: 100, answer: '', rubric: '' }]
  }).catch(() => {
    questionForm.value.questions = [{ index: 0, type: 'essay', score: 100, answer: '', rubric: '' }]
  }).finally(() => {
    questionLoading.value = false
  })
}

function addQuestion() {
  questionForm.value.questions.push({
    index: questionForm.value.questions.length,
    type: 'essay',
    score: 10,
    answer: '',
    rubric: '',
  })
}

function removeQuestion(idx: number) {
  questionForm.value.questions.splice(idx, 1)
  questionForm.value.questions.forEach((q, i) => { q.index = i })
}

async function saveQuestions() {
  if (!currentPaperId.value) return
  try {
    await setAnswerKeyApi(currentPaperId.value, {
      questions: questionForm.value.questions,
      total_score: questionForm.value.total_score,
    })
    ElMessage.success('题目设置成功')
    questionDialogVisible.value = false
  } catch {
    ElMessage.error('保存失败')
  }
}

function goToGrading(paper: Paper) {
  router.push(`/teacher/papers/${paper.id}/grading`)
}

const statusMap: Record<string, string> = {
  draft: '草稿',
  published: '已发布',
  grading: '批改中',
  done: '已完成',
}

onMounted(fetchPapers)
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <h2 class="page-title">试卷管理</h2>
      <el-button type="primary" @click="openCreateDialog">创建试卷</el-button>
    </div>

    <el-card shadow="never">
      <el-table :data="papers" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="title" label="试卷名称" min-width="200" />
        <el-table-column label="状态" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 'done' ? 'success' : row.status === 'grading' ? 'warning' : row.status === 'published' ? 'primary' : 'info'" size="small">
              {{ statusMap[row.status] || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="160">
          <template #default="{ row }">
            {{ row.createdAt ? new Date(row.createdAt).toLocaleString() : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="360" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openQuestionDialog(row)">设置题目</el-button>
            <el-button size="small" @click="handleDistribute(row)" :disabled="row.status !== 'draft'">分发</el-button>
            <el-button size="small" type="primary" @click="goToGrading(row)">批改</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="!loading && papers.length === 0" class="empty-state">
        <el-empty description="暂无试卷，点击上方按钮创建" />
      </div>
    </el-card>

    <!-- 创建试卷（含班级选择） -->
    <el-dialog v-model="createDialogVisible" title="创建试卷" width="480px">
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="试卷名称" required>
          <el-input v-model="createForm.title" placeholder="请输入试卷名称" />
        </el-form-item>
        <el-form-item label="目标班级">
          <el-select v-model="createForm.class_ids" multiple placeholder="选择班级（可选，也可后续设置）" style="width: 100%">
            <el-option v-for="c in classes" :key="c.id" :label="c.grade + c.name" :value="c.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- 设置题目（可滚动） -->
    <el-dialog v-model="questionDialogVisible" title="设置题目" width="620px" v-loading="questionLoading">
      <el-form :model="questionForm" label-width="100px">
        <el-form-item label="总分">
          <el-input-number v-model="questionForm.total_score" :min="1" :max="1000" />
        </el-form-item>
        <el-divider>题目列表</el-divider>
        <div class="question-scroll">
          <div v-for="(q, idx) in questionForm.questions" :key="idx" class="question-card">
            <div class="question-header">
              <strong>第 {{ idx + 1 }} 题</strong>
              <el-button size="small" type="danger" text @click="removeQuestion(idx)">移除</el-button>
            </div>
            <el-form-item label="类型">
              <el-select v-model="q.type">
                <el-option label="问答题" value="essay" />
                <el-option label="选择题" value="choice" />
                <el-option label="填空题" value="fill" />
              </el-select>
            </el-form-item>
            <el-form-item label="分值">
              <el-input-number v-model="q.score" :min="1" :max="1000" />
            </el-form-item>
            <el-form-item label="参考答案">
              <el-input v-model="q.answer" type="textarea" :rows="2" />
            </el-form-item>
            <el-form-item label="评分要点">
              <el-input v-model="q.rubric" type="textarea" :rows="2" />
            </el-form-item>
          </div>
        </div>
        <el-button type="primary" text @click="addQuestion">+ 添加题目</el-button>
      </el-form>
      <template #footer>
        <el-button @click="questionDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveQuestions">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.question-card {
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  padding: 12px;
  margin-bottom: 12px;
}
.question-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.question-scroll {
  max-height: 340px;
  overflow-y: auto;
  padding-right: 4px;
}
.question-scroll::-webkit-scrollbar {
  width: 4px;
}
.question-scroll::-webkit-scrollbar-thumb {
  background: #c0c4cc;
  border-radius: 2px;
}
</style>
