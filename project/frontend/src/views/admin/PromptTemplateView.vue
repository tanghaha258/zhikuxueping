<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listPromptTemplatesApi,
  createPromptTemplateApi,
  updatePromptTemplateApi,
  deletePromptTemplateApi,
} from '@/api/prompt_template'
import type { PromptTemplate } from '@/api/prompt_template'

const templates = ref<PromptTemplate[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('新增提示词模板')
const editingId = ref<string | null>(null)

const subjects = ['语文', '数学', '英语', '物理', '化学', '历史', '地理', '生物', '道德与法治']
const examTypes = [
  { label: '周测', value: 'quiz' },
  { label: '期中考试', value: 'midterm' },
  { label: '期末考试', value: 'final' },
]

const filterSubject = ref('')
const filterExamType = ref('')

const form = ref({
  name: '',
  subject: '语文',
  examType: 'quiz',
  template: '',
  description: '',
  isActive: true,
})

const VARIABLES_HELP = [
  { var: '{subject}', desc: '学科名称，如「语文」' },
  { var: '{grade}', desc: '年级，如「七年级」' },
  { var: '{difficulty}', desc: '难度：简单/中等/困难' },
  { var: '{exam_label}', desc: '考试类型名称，如「周测」「期中考试」' },
  { var: '{kp_str}', desc: '教师选择的知识点，顿号分隔' },
  { var: '{section_block}', desc: '题型结构配置（自动生成）' },
  { var: '{total_score}', desc: '试卷总分' },
]

const DEFAULT_TEMPLATE = `你是一位资深初中{subject}学科教师，现在需要为{grade}年级学生出一份{subject}学科的{exam_label}（{difficulty}难度）。

【最高优先级-绝对禁止】
你只能出{subject}学科的题目！绝对不能出任何其他学科的题目！

{section_block}知识点范围：{kp_str}

请严格按以下JSON格式输出，不要包含任何其他内容：
{{
  "title": "试卷标题（必须包含{subject}）",
  "questions": [
    {{"index": 1, "type": "choice", "score": 5, "content": "{subject}学科选择题内容", "options": ["A. 选项内容", "B. 选项内容", "C. 选项内容", "D. 选项内容"], "answer": "A", "analysis": "解析"}},
    {{"index": 2, "type": "fill", "score": 5, "content": "{subject}学科填空题内容____", "answer": "答案", "analysis": "解析"}},
    {{"index": 3, "type": "essay", "score": 10, "content": "{subject}学科简答题内容", "answer": "参考答案", "analysis": "解析"}}
  ],
  "total_score": {total_score},
  "duration": 90
}}

要求：
1. 所有题目必须与{subject}学科直接相关
2. 严格按照上述题型和题数出题，不得增减
3. 各题目不得重复或高度相似
4. 选择题必须包含 4 个选项(A/B/C/D)及正确答案
5. 所有内容用中文`

async function fetchTemplates() {
  loading.value = true
  try {
    const params: Record<string, unknown> = {}
    if (filterSubject.value) params.subject = filterSubject.value
    if (filterExamType.value) params.examType = filterExamType.value
    const res = await listPromptTemplatesApi(params as any)
    templates.value = res.data.data
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  dialogTitle.value = '新增提示词模板'
  form.value = {
    name: '',
    subject: '语文',
    examType: 'quiz',
    template: DEFAULT_TEMPLATE,
    description: '',
    isActive: true,
  }
  dialogVisible.value = true
}

function openEdit(row: PromptTemplate) {
  editingId.value = row.id
  dialogTitle.value = '编辑提示词模板'
  form.value = {
    name: row.name,
    subject: row.subject,
    examType: row.examType,
    template: row.template,
    description: row.description || '',
    isActive: row.isActive,
  }
  dialogVisible.value = true
}

async function handleSave() {
  if (!form.value.name || !form.value.template) {
    ElMessage.warning('请填写模板名称和模板内容')
    return
  }
  try {
    const payload = {
      name: form.value.name,
      subject: form.value.subject,
      examType: form.value.examType,
      template: form.value.template,
      description: form.value.description || undefined,
      isActive: form.value.isActive,
    }
    if (editingId.value) {
      await updatePromptTemplateApi(editingId.value, payload)
      ElMessage.success('更新成功')
    } else {
      await createPromptTemplateApi(payload)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchTemplates()
  } catch { /* handled by interceptor */ }
}

async function handleDelete(row: PromptTemplate) {
  try {
    await ElMessageBox.confirm(`确定要删除模板「${row.name}」吗？`, '确认删除', { type: 'warning' })
    await deletePromptTemplateApi(row.id)
    ElMessage.success('删除成功')
    fetchTemplates()
  } catch { /* cancelled or error */ }
}

async function toggleActive(row: PromptTemplate) {
  try {
    await updatePromptTemplateApi(row.id, { isActive: !row.isActive })
    ElMessage.success(row.isActive ? '已禁用' : '已启用')
    fetchTemplates()
  } catch { /* handled */ }
}

function insertVariable(v: string) {
  form.value.template += v
}

const filteredTemplates = computed(() => {
  return templates.value
})

const examTypeLabel = (val: string) => examTypes.find(e => e.value === val)?.label || val

onMounted(fetchTemplates)
</script>

<template>
  <div class="page-container">
    <div class="flex-between" style="margin-bottom: 20px;">
      <h2 class="page-title" style="margin-bottom: 0;">提示词模板管理</h2>
      <el-button type="primary" @click="openCreate">新增模板</el-button>
    </div>

    <el-card shadow="never">
      <div class="filter-bar" style="margin-bottom: 16px; display: flex; gap: 12px; align-items: center;">
        <el-select v-model="filterSubject" placeholder="按学科筛选" clearable style="width: 140px;" @change="fetchTemplates">
          <el-option v-for="s in subjects" :key="s" :label="s" :value="s" />
        </el-select>
        <el-select v-model="filterExamType" placeholder="按考试类型筛选" clearable style="width: 140px;" @change="fetchTemplates">
          <el-option v-for="et in examTypes" :key="et.value" :label="et.label" :value="et.value" />
        </el-select>
        <el-text type="info" size="small">共 {{ filteredTemplates.length }} 条模板</el-text>
      </div>

      <el-table :data="filteredTemplates" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="name" label="模板名称" min-width="160" />
        <el-table-column prop="subject" label="学科" width="100" />
        <el-table-column label="考试类型" width="110">
          <template #default="{ row }">{{ examTypeLabel(row.examType) }}</template>
        </el-table-column>
        <el-table-column prop="description" label="说明" min-width="200" show-overflow-tooltip />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.isActive ? 'success' : 'info'" size="small">
              {{ row.isActive ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" width="170">
          <template #default="{ row }">{{ row.updatedAt ? new Date(row.updatedAt).toLocaleString('zh-CN') : '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" :type="row.isActive ? 'warning' : 'success'" plain @click="toggleActive(row)">
              {{ row.isActive ? '禁用' : '启用' }}
            </el-button>
            <el-button text type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button text type="danger" size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loading && filteredTemplates.length === 0" description="暂无提示词模板，请点击上方按钮新增" />
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="780px" :close-on-click-modal="false" top="5vh">
      <el-form label-width="90px" label-position="left">
        <el-form-item label="模板名称">
          <el-input v-model="form.name" placeholder="如：语文周测标准模板" maxlength="100" />
        </el-form-item>
        <el-form-item label="适用学科">
          <el-select v-model="form.subject" style="width: 100%;">
            <el-option v-for="s in subjects" :key="s" :label="s" :value="s" />
          </el-select>
        </el-form-item>
        <el-form-item label="考试类型">
          <el-select v-model="form.examType" style="width: 100%;">
            <el-option v-for="et in examTypes" :key="et.value" :label="et.label" :value="et.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="模板说明">
          <el-input v-model="form.description" placeholder="简要描述此模板的适用场景（可选）" maxlength="200" />
        </el-form-item>
        <el-form-item label="启用状态">
          <el-switch v-model="form.isActive" active-text="启用" inactive-text="禁用" />
        </el-form-item>
        <el-form-item label="模板内容">
          <div class="template-editor">
            <div class="var-toolbar">
              <el-text type="info" size="small" style="margin-right: 8px;">可用变量：</el-text>
              <el-tag
                v-for="v in VARIABLES_HELP"
                :key="v.var"
                size="small"
                class="var-tag"
                :title="v.desc"
                @click="insertVariable(v.var)"
              >{{ v.var }}</el-tag>
            </div>
            <el-input
              v-model="form.template"
              type="textarea"
              :autosize="{ minRows: 12, maxRows: 24 }"
              placeholder="输入提示词模板，使用 {变量名} 占位"
              style="font-family: 'Courier New', monospace; font-size: 13px;"
            />
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-container {
  padding: 20px;
}
.page-title {
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}
.flex-between {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.template-editor {
  width: 100%;
}
.var-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
  margin-bottom: 8px;
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 6px;
}
.var-tag {
  cursor: pointer;
  transition: all 0.2s;
}
.var-tag:hover {
  background: #409EFF;
  color: #fff;
  border-color: #409EFF;
}
</style>
