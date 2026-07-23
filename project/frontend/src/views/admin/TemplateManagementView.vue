<script setup lang="ts">
import { ref, reactive, onMounted, watch, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search, Refresh } from '@element-plus/icons-vue'
import { listTemplatesApi, createTemplateApi, updateTemplateApi, syncTemplateApi } from '@/api/paper_generator'
import type { PaperTemplate, SectionItem } from '@/types'

const loading = ref(false)
const templates = ref<PaperTemplate[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const subjectFilter = ref('')
const gradeFilter = ref('')

const dialogVisible = ref(false)
const dialogTitle = ref('新增模板')
const isEditing = ref(false)
const editingId = ref('')
const formLoading = ref(false)

const form = reactive({
  name: '',
  subject: '',
  grade: '',
  exam_type: 'quiz',
  sections: [] as SectionItem[],
})

const subjectCodeToName: Record<string, string> = {
  chinese: '语文', math: '数学', english: '英语',
  physics: '物理', chemistry: '化学', biology: '生物',
  history: '历史', geography: '地理', morality: '道德与法治',
  art: '美术', music: '音乐', pe: '体育与健康', it: '信息技术', labor: '劳动',
}

const gradeCodeToName: Record<string, string> = {
  '7': '七年级', '8': '八年级', '9': '九年级',
}

function displaySubject(v: string): string {
  return subjectCodeToName[v] || v
}

function displayGrade(v: string): string {
  return gradeCodeToName[v] || v
}

function normalizeSubject(v: string): string {
  return subjectCodeToName[v] || v
}

function normalizeGrade(v: string): string {
  return gradeCodeToName[v] || v
}

const subjectOptions = [
  { value: '', label: '全部科目' },
  ...Object.entries(subjectCodeToName).map(([k, v]) => ({ value: k, label: v })),
]

const gradeOptions = [
  { value: '', label: '全部年级' },
  ...Object.entries(gradeCodeToName).map(([k, v]) => ({ value: k, label: v })),
]

const examTypeOptions = [
  { value: 'quiz', label: '单元测验' },
  { value: 'midterm', label: '期中考试' },
  { value: 'final', label: '期末考试' },
]

const examTypeLabels: Record<string, string> = {
  quiz: '单元测验',
  midterm: '期中考试',
  final: '期末考试',
}

const sectionTypeOptions = [
  { value: '单选题', label: '单选题' },
  { value: '多选题', label: '多选题' },
  { value: '判断题', label: '判断题' },
  { value: '填空题', label: '填空题' },
  { value: '简答题', label: '简答题' },
  { value: '解答题', label: '解答题' },
  { value: '作文题', label: '作文题' },
  { value: '实验题', label: '实验题' },
  { value: '综合题', label: '综合题' },
]

const totalScore = computed(() => {
  return form.sections.reduce((sum, s) => sum + s.count * s.score_per, 0)
})

async function loadTemplates() {
  loading.value = true
  try {
    const params: Record<string, unknown> = {
      skip: (page.value - 1) * pageSize.value,
      limit: pageSize.value,
    }
    if (subjectFilter.value) params.subject = subjectFilter.value
    if (gradeFilter.value) params.grade = gradeFilter.value
    const res = await listTemplatesApi(params as any)
    const d = res.data.data
    templates.value = (d.items || []).map((item: any) => ({
      ...item,
      sections: typeof item.sections === 'string' ? JSON.parse(item.sections) : item.sections || [],
    }))
    total.value = d.total || 0
  } catch {
    templates.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

onMounted(() => { loadTemplates() })

watch([subjectFilter, gradeFilter], () => {
  page.value = 1
  loadTemplates()
})

function onPageChange(p: number) {
  page.value = p
  loadTemplates()
}

function resetFilters() {
  subjectFilter.value = ''
  gradeFilter.value = ''
}

function getDefaultSections(examType: string): SectionItem[] {
  const id = () => Math.random().toString(36).substring(2, 10)
  if (examType === 'quiz') {
    return [
      { id: id(), label: '选择题', type: '单选题', count: 10, score_per: 2, total: 20 },
      { id: id(), label: '填空题', type: '填空题', count: 5, score_per: 2, total: 10 },
      { id: id(), label: '简答题', type: '简答题', count: 2, score_per: 5, total: 10 },
    ]
  }
  if (examType === 'midterm') {
    return [
      { id: id(), label: '选择题', type: '单选题', count: 15, score_per: 3, total: 45 },
      { id: id(), label: '填空题', type: '填空题', count: 5, score_per: 4, total: 20 },
      { id: id(), label: '解答题', type: '解答题', count: 5, score_per: 7, total: 35 },
    ]
  }
  return [
    { id: id(), label: '选择题', type: '单选题', count: 20, score_per: 2, total: 40 },
    { id: id(), label: '填空题', type: '填空题', count: 8, score_per: 3, total: 24 },
    { id: id(), label: '解答题', type: '解答题', count: 6, score_per: 6, total: 36 },
  ]
}

function openCreate() {
  isEditing.value = false
  dialogTitle.value = '新增模板'
  editingId.value = ''
  form.name = ''
  form.subject = subjectFilter.value || 'math'
  form.grade = gradeFilter.value || '7'
  form.exam_type = 'quiz'
  form.sections = getDefaultSections('quiz')
  dialogVisible.value = true
}

function openEdit(row: PaperTemplate) {
  isEditing.value = true
  dialogTitle.value = '编辑模板'
  editingId.value = row.id
  form.name = row.name
  form.subject = row.subject
  form.grade = row.grade
  form.exam_type = row.examType
  form.sections = row.sections.map((s) => ({ ...s }))
  dialogVisible.value = true
}

function onExamTypeChange() {
  if (!isEditing.value) form.sections = getDefaultSections(form.exam_type)
}

function addSection() {
  form.sections.push({
    id: Math.random().toString(36).substring(2, 10),
    label: '',
    type: '单选题',
    count: 1,
    score_per: 1,
    total: 1,
  })
}

function removeSection(index: number) {
  form.sections.splice(index, 1)
}

function updateSectionTotal(index: number) {
  const s = form.sections[index]
  s.total = s.count * s.score_per
}

async function handleSave() {
  if (!form.name || !form.subject || !form.grade) {
    ElMessage.warning('请填写模板名称、科目和年级')
    return
  }
  if (form.sections.length === 0) {
    ElMessage.warning('请至少添加一个题型')
    return
  }
  for (const s of form.sections) {
    if (!s.label) { ElMessage.warning('请填写所有题型的名称'); return }
  }
  formLoading.value = true
  try {
    const payload = {
      name: form.name,
      subject: form.subject,
      grade: form.grade,
      exam_type: form.exam_type,
      total_score: totalScore.value,
      sections: JSON.stringify(form.sections),
    }
    if (isEditing.value) {
      await updateTemplateApi(editingId.value, payload)
      ElMessage.success('模板更新成功')
    } else {
      await createTemplateApi(payload)
      ElMessage.success('模板创建成功')
    }
    dialogVisible.value = false
    loadTemplates()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.message || '操作失败')
  } finally {
    formLoading.value = false
  }
}

async function handleSync(row: PaperTemplate) {
  try {
    await ElMessageBox.confirm(`确认同步模板「${row.name}」到所有教师？`, '提示')
  } catch { return }
  try {
    await syncTemplateApi(row.id)
    ElMessage.success('同步成功')
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.message || '同步失败')
  }
}

function sectionsSummary(sections: SectionItem[]): string {
  if (!sections || sections.length === 0) return '未配置'
  return sections.map((s) => `${s.label}${s.count}题`).join('、')
}
</script>

<template>
  <div class="page-container">
    <div class="action-bar">
      <h2 class="page-title" style="margin-bottom: 0;">模板管理</h2>
      <el-button type="primary" :icon="Plus" @click="openCreate">新增模板</el-button>
    </div>

    <el-card shadow="never">
      <div class="search-bar">
        <el-select v-model="subjectFilter" placeholder="科目筛选" style="width: 140px" clearable>
          <el-option v-for="opt in subjectOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
        </el-select>
        <el-select v-model="gradeFilter" placeholder="年级筛选" style="width: 140px" clearable>
          <el-option v-for="opt in gradeOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
        </el-select>
        <el-button :icon="Refresh" @click="resetFilters">重置</el-button>
      </div>

      <el-table :data="templates" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="name" label="模板名称" min-width="180" show-overflow-tooltip />
        <el-table-column label="科目" width="100">
          <template #default="{ row }">{{ displaySubject(row.subject) }}</template>
        </el-table-column>
        <el-table-column label="年级" width="100">
          <template #default="{ row }">{{ displayGrade(row.grade) }}</template>
        </el-table-column>
        <el-table-column prop="examType" label="考试类型" width="110">
          <template #default="{ row }">
            <el-tag size="small">{{ examTypeLabels[row.examType] || row.examType }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="totalScore" label="总分" width="70" align="center" />
        <el-table-column label="题型配置" min-width="280" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="section-summary">{{ sectionsSummary(row.sections) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="isActive" label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.isActive ? 'success' : 'info'" size="small">
              {{ row.isActive ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button text type="success" size="small" @click="handleSync(row)">同步</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @current-change="onPageChange"
        />
      </div>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="760px" :close-on-click-modal="false">
      <el-form :model="form" label-position="top">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="模板名称">
              <el-input v-model="form.name" placeholder="例如：七年级数学单元测验" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="科目">
              <el-select v-model="form.subject" style="width: 100%">
                <el-option v-for="opt in subjectOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="年级">
              <el-select v-model="form.grade" style="width: 100%">
                <el-option v-for="opt in gradeOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="考试类型">
              <el-select v-model="form.exam_type" style="width: 100%" @change="onExamTypeChange">
                <el-option v-for="opt in examTypeOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="总分（自动计算）">
              <el-input :model-value="totalScore" disabled />
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider content-position="left">题型配置</el-divider>

        <div class="section-editor">
          <div class="section-header">
            <span style="flex: 0 0 140px;">题型名称</span>
            <span style="flex: 0 0 120px;">题目类型</span>
            <span style="flex: 0 0 80px; text-align: center;">题数</span>
            <span style="flex: 0 0 100px; text-align: center;">每题分值</span>
            <span style="flex: 0 0 80px; text-align: center;">小计</span>
            <span style="width: 40px;"></span>
          </div>
          <div v-for="(section, index) in form.sections" :key="section.id" class="section-row">
            <el-input v-model="section.label" placeholder="如：选择题" size="small" style="flex: 0 0 130px" />
            <el-select v-model="section.type" size="small" style="flex: 0 0 110px">
              <el-option v-for="opt in sectionTypeOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
            </el-select>
            <el-input-number
              v-model="section.count"
              :min="0"
              :max="99"
              size="small"
              style="flex: 0 0 80px"
              @change="updateSectionTotal(index)"
            />
            <el-input-number
              v-model="section.score_per"
              :min="0"
              :max="999"
              :step="0.5"
              size="small"
              style="flex: 0 0 100px"
              @change="updateSectionTotal(index)"
            />
            <span class="section-total">{{ section.count * section.score_per }}</span>
            <el-button text type="danger" size="small" @click="removeSection(index)">删除</el-button>
          </div>
          <el-button class="add-section-btn" text type="primary" :icon="Plus" @click="addSection">
            添加题型
          </el-button>
        </div>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="formLoading" @click="handleSave">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.search-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.section-summary {
  font-size: 13px;
  color: #606266;
}

.section-editor {
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  padding: 16px;
  background: #fafafa;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 4px 8px;
  font-size: 13px;
  font-weight: 600;
  color: #606266;
  border-bottom: 1px solid #e4e7ed;
  margin-bottom: 8px;
}

.section-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.section-total {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 60px;
  font-size: 14px;
  font-weight: 600;
  color: #409EFF;
}

.add-section-btn {
  margin-top: 8px;
}
</style>
