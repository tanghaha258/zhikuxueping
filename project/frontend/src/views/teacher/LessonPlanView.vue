<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { MagicStick, RefreshRight, Download, Edit, DocumentCopy, Link } from '@element-plus/icons-vue'
import { listSubjectsApi } from '@/api/subjects'
import { listProjectsApi } from '@/api/projects'
import { generateLessonPlanApi, mockGenerateLessonPlan, listLessonPlansApi, createLessonPlanApi, updateLessonPlanApi, deleteLessonPlanApi } from '@/api/ai'
import { linkContextApi, listContextLinksByArtifactApi } from '@/features/tool-context/api'
import { validateToolContext, type ProjectPhase, type ToolContext } from '@/features/tool-context/types'
import type { SubjectItem, Project } from '@/types'
import type { SavedLessonPlan } from '@/api/ai'

const form = ref({
  subject: '',
  grade: '',
  topic: '',
  duration: 45,
  objectives: '',
  additional: '',
})

// ── Task 8：工具上下文（独立 / 关联项目）─────────────────────────
// 独立工具页默认 independent；教师可选择加入项目（project 模式）。
// 项目模式保存教案时自动建立一条 lesson_plan 引用；AI 产出先进入待审核版本。
const context = ref<ToolContext>({ mode: 'independent' })
const projects = ref<Project[]>([])
const linkingPlan = ref(false)
/** 当前教案已关联的项目引用列表（独立模式或未关联时为空）。 */
const planLinks = ref<{ id: string; projectId: string; phase: string | null }[]>([])

const isProjectMode = computed(() => context.value.mode === 'project')
const contextValidation = computed(() => validateToolContext(context.value))
/** 项目模式且合同有效时才允许保存并关联。 */
const canLinkProject = computed(
  () => isProjectMode.value && contextValidation.value.valid,
)

function switchMode(mode: 'independent' | 'project') {
  if (mode === 'independent') {
    context.value = { mode: 'independent' }
  } else {
    context.value = { mode: 'project', projectId: '', phase: 'preparation' }
  }
}

function onProjectChange(projectId: string) {
  if (context.value.mode === 'project') {
    context.value = { ...context.value, projectId }
  }
}

function onPhaseChange(phase: ProjectPhase) {
  if (context.value.mode === 'project') {
    context.value = { ...context.value, phase }
  }
}

async function loadProjects() {
  try {
    const res = await listProjectsApi({ limit: 200 })
    projects.value = res.data.data.items
  } catch {
    projects.value = []
  }
}

/** 加载当前教案已关联的项目引用。 */
async function loadPlanLinks(planId: string | null) {
  if (!planId) {
    planLinks.value = []
    return
  }
  try {
    const links = await listContextLinksByArtifactApi('lesson_plan', planId)
    planLinks.value = links.map((l) => ({
      id: l.id,
      projectId: l.projectId,
      phase: l.phase,
    }))
  } catch {
    planLinks.value = []
  }
}

/** 保存教案后，若为项目模式则建立一条 lesson_plan 引用。 */
async function linkPlanToProject(planId: string) {
  if (!canLinkProject.value) return
  linkingPlan.value = true
  try {
    await linkContextApi('lesson_plan', planId, context.value)
    ElMessage.success('教案已关联到项目备课')
    await loadPlanLinks(planId)
  } catch {
    // 关联失败不影响教案已保存的事实；教师可稍后在项目备课页重试
    ElMessage.warning('教案已保存，但关联项目失败，可稍后重试')
  } finally {
    linkingPlan.value = false
  }
}

const subjectOptions = ref<{ value: string; label: string }[]>([])
const gradeOptions = [
  { value: '七年级', label: '七年级' },
  { value: '八年级', label: '八年级' },
  { value: '九年级', label: '九年级' },
]

const generating = ref(false)
const generatedPlan = ref<{ content: string; title: string } | null>(null)
const subjectsLoading = ref(true)
const apiUnavailable = ref(false)
const editing = ref(false)
const savedPlans = ref<SavedLessonPlan[]>([])
const showHistory = ref(false)
const currentPlanId = ref<string | null>(null)
const editableContent = ref('')

/** 加载学科列表 */
async function loadSubjects() {
  subjectsLoading.value = true
  try {
    const res = await listSubjectsApi()
    const items: SubjectItem[] = res.data?.data ?? []
    subjectOptions.value = items
      .filter((s) => s.isActive)
      .map((s) => ({ value: s.id, label: s.name }))
  } catch {
    ElMessage.warning('学科列表加载失败，请稍后重试')
    subjectOptions.value = []
  } finally {
    subjectsLoading.value = false
  }
}

/** 使用模拟数据生成 */
function doMockGenerate() {
  const result = mockGenerateLessonPlan({
    subject: form.value.subject
      ? subjectOptions.value.find((s) => s.value === form.value.subject)?.label || form.value.subject
      : '',
    grade: form.value.grade,
    topic: form.value.topic,
    duration: form.value.duration,
    objectives: form.value.objectives,
    additional: form.value.additional,
  })
  generatedPlan.value = result
}

/** 调用 AI 备课 API */
async function generatePlan() {
  if (!form.value.topic.trim()) {
    ElMessage.warning('请输入教学主题')
    return
  }
  if (!form.value.subject) {
    ElMessage.warning('请选择学科')
    return
  }
  if (!form.value.grade) {
    ElMessage.warning('请选择年级')
    return
  }

  generating.value = true
  apiUnavailable.value = false

  try {
    const res = await generateLessonPlanApi({
      subject: form.value.subject,
      grade: form.value.grade,
      topic: form.value.topic,
      duration: form.value.duration,
      objectives: form.value.objectives,
      additional: form.value.additional,
    })
    generatedPlan.value = res.data?.data ?? null
    if (!generatedPlan.value) {
      throw new Error('返回数据为空')
    }
  } catch (err: any) {
    const status = err?.response?.status
    if (status === 404 || status === 500 || status === 501 || status === 502) {
      apiUnavailable.value = true
      ElMessage.error('AI 备课服务暂不可用，可尝试使用模拟数据')
    } else {
      ElMessage.error(err?.response?.data?.message || err?.message || '生成教案失败')
    }
  } finally {
    generating.value = false
  }
}

/** 使用模拟数据（后备方案） */
function useMockFallback() {
  generating.value = true
  apiUnavailable.value = false
  setTimeout(() => {
    doMockGenerate()
    generating.value = false
    ElMessage.success('已使用本地模拟数据生成教案')
  }, 600)
}

/** 重新生成 */
function regenerate() {
  generatedPlan.value = null
  generatePlan()
}

/** 导出教案文本 */
function exportPlan() {
  if (!generatedPlan.value) return
  const blob = new Blob([generatedPlan.value.content], { type: 'text/html;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${generatedPlan.value.title}.html`
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success('教案导出成功')
}

/** 获取学科名称 */
function getSubjectLabel(value: string): string {
  return subjectOptions.value.find((s) => s.value === value)?.label || value
}

/** Markdown/HTML 简单预处理：将 ## 标题等转为 HTML，然后直接用 v-html */
function renderContent(html: string): string {
  if (!html) return ''
  return html
}

/** 下载 Word 文档（前端 HTML → .doc 格式） */
function exportWord() {
  if (!generatedPlan.value) return
  const { content, title } = generatedPlan.value
  const fullHtml = `<!DOCTYPE html>
<html xmlns:o="urn:schemas-microsoft-com:office:office"
      xmlns:w="urn:schemas-microsoft-com:office:word"
      xmlns="http://www.w3.org/TR/REC-html40">
<head><meta charset="utf-8"><title>${title}</title></head>
<body>${content}</body>
</html>`
  const blob = new Blob(['\ufeff' + fullHtml], {
    type: 'application/msword',
  })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${title}.doc`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
  ElMessage.success('Word 教案下载成功')
}

/** 切换编辑/预览模式 */
async function toggleEdit() {
  if (!editing && generatedPlan.value) {
    editableContent.value = generatedPlan.value.content
  }
  editing.value = !editing.value
}

/** 保存教案 */
async function savePlan() {
  if (!generatedPlan.value) return
  // 项目模式合同未通过时阻止保存并提示
  if (isProjectMode.value && !contextValidation.value.valid) {
    ElMessage.warning(contextValidation.value.error || '请完成项目上下文选择')
    return
  }
  try {
    if (currentPlanId.value) {
      await updateLessonPlanApi(currentPlanId.value, {
        title: generatedPlan.value.title,
        content: generatedPlan.value.content,
      })
      ElMessage.success('教案已更新')
    } else {
      const res = await createLessonPlanApi({
        title: generatedPlan.value.title,
        content: generatedPlan.value.content,
        subject: getSubjectLabel(form.value.subject),
        grade: form.value.grade,
        topic: form.value.topic,
        duration: form.value.duration,
      })
      currentPlanId.value = res.data.data.id
      ElMessage.success('教案已保存')
      // Task 8：项目模式保存后建立一条 lesson_plan 引用
      await linkPlanToProject(res.data.data.id)
    }
  } catch { /* error handled */ }
}

/** 加载历史教案列表 */
async function loadHistory() {
  try {
    const res = await listLessonPlansApi()
    savedPlans.value = res.data.data
    showHistory.value = true
  } catch { ElMessage.error('加载历史教案失败') }
}

/** 加载指定教案 */
async function loadPlan(plan: SavedLessonPlan) {
  generatedPlan.value = { title: plan.title, content: plan.content }
  currentPlanId.value = plan.id
  showHistory.value = false
  editing.value = false
  ElMessage.success('已加载教案')
  // Task 8：加载该教案已关联的项目引用
  await loadPlanLinks(plan.id)
}

/** 删除教案 */
async function deletePlan(id: string) {
  try {
    await deleteLessonPlanApi(id)
    savedPlans.value = savedPlans.value.filter((p) => p.id !== id)
    if (currentPlanId.value === id) currentPlanId.value = null
    ElMessage.success('已删除')
  } catch { /* error */ }
}

/** PPT 生成占位 */
function pptPlaceholder() {
  ElMessage.info('PPT 生成功能开发中，敬请期待')
}

onMounted(() => {
  loadSubjects()
  loadProjects()
})
</script>

<template>
  <div class="page-container">
    <h2 class="page-title">智能备课</h2>
    <p class="page-subtitle">
      输入教学主题，AI 辅助生成跨学科教案
    </p>

    <!-- Task 8：工具上下文选择条。独立模式不关联项目；项目模式锁定到指定阶段。 -->
    <div class="context-bar" data-ui="lesson-context-bar">
      <el-radio-group :model-value="context.mode" @change="switchMode">
        <el-radio-button value="independent">独立教案</el-radio-button>
        <el-radio-button value="project">关联项目</el-radio-button>
      </el-radio-group>
      <template v-if="isProjectMode">
        <el-select
          :model-value="(context as any).projectId"
          placeholder="选择项目"
          style="width: 220px"
          @change="onProjectChange"
        >
          <el-option v-for="p in projects" :key="p.id" :label="p.title" :value="p.id" />
        </el-select>
        <el-select
          :model-value="(context as any).phase"
          placeholder="项目阶段"
          style="width: 140px"
          @change="onPhaseChange"
        >
          <el-option label="诊断" value="diagnosis" />
          <el-option label="设计" value="design" />
          <el-option label="备课" value="preparation" />
          <el-option label="实施" value="implementation" />
          <el-option label="评价" value="evaluation" />
          <el-option label="改进" value="improvement" />
          <el-option label="结项" value="closure" />
        </el-select>
        <span v-if="!contextValidation.valid" class="context-bar__error">
          {{ contextValidation.error }}
        </span>
      </template>
      <span v-else class="context-bar__hint">独立教案不关联项目，可稍后加入项目</span>
    </div>

    <div v-if="planLinks.length" class="plan-links" data-ui="lesson-plan-links">
      <span class="plan-links__label">已关联项目：</span>
      <el-tag
        v-for="lk in planLinks"
        :key="lk.id"
        size="small"
        type="info"
        class="plan-links__tag"
      >{{ lk.projectId }}（{{ lk.phase || '未指定阶段' }}）</el-tag>
    </div>

    <div class="ai-review-hint">
      AI 生成的教案保存后进入待审核版本，教师确认后方可用于项目备课。
    </div>

    <div class="layout-grid">
      <!-- 备课表单 -->
      <el-card shadow="never" class="form-card">
        <template #header>
          <span class="card-title">备课信息</span>
        </template>

        <el-form :model="form" label-position="top">
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="学科">
                <el-select
                  v-model="form.subject"
                  placeholder="请选择学科"
                  style="width: 100%"
                  :loading="subjectsLoading"
                  filterable
                >
                  <el-option
                    v-for="opt in subjectOptions"
                    :key="opt.value"
                    :label="opt.label"
                    :value="opt.value"
                  />
                  <template v-if="!subjectsLoading && subjectOptions.length === 0">
                    <el-option disabled label="暂无学科数据，请先联系管理员配置" value="" />
                  </template>
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="年级">
                <el-select v-model="form.grade" placeholder="请选择年级" style="width: 100%">
                  <el-option
                    v-for="opt in gradeOptions"
                    :key="opt.value"
                    :label="opt.label"
                    :value="opt.value"
                  />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>

          <el-form-item label="教学主题">
            <el-input
              v-model="form.topic"
              placeholder="请输入教学主题，如：光合作用、二次函数..."
            />
          </el-form-item>

          <el-form-item label="课时（分钟）">
            <el-input-number v-model="form.duration" :min="15" :max="90" :step="15" />
          </el-form-item>

          <el-form-item label="教学目标说明（选填）">
            <el-input
              v-model="form.objectives"
              type="textarea"
              :rows="3"
              placeholder="描述您希望达成的教学目标..."
            />
          </el-form-item>

          <el-form-item label="额外要求（选填）">
            <el-input
              v-model="form.additional"
              type="textarea"
              :rows="2"
              placeholder="如：融入思政元素、跨学科结合..."
            />
          </el-form-item>

          <el-form-item>
            <el-button
              type="primary"
              size="large"
              :icon="MagicStick"
              :loading="generating"
              style="width: 100%"
              @click="generatePlan"
            >
              {{ generating ? 'AI 生成中...' : 'AI 生成教案' }}
            </el-button>
          </el-form-item>

          <el-form-item v-if="apiUnavailable">
            <el-button
              size="small"
              type="warning"
              plain
              style="width: 100%"
              :icon="RefreshRight"
              @click="useMockFallback"
            >
              使用模拟数据生成（后备方案）
            </el-button>
          </el-form-item>
        </el-form>
      </el-card>

      <!-- 教案展示区 -->
      <el-card shadow="never" class="result-card">
        <template #header>
          <div class="flex-between">
            <span class="card-title">
              {{ generatedPlan ? generatedPlan.title : '生成的教案' }}
            </span>
            <div v-if="generatedPlan" class="header-actions">
              <el-button size="small" :icon="Edit" @click="toggleEdit" v-if="generatedPlan">
                {{ editing ? '预览' : '编辑' }}
              </el-button>
              <el-button size="small" @click="savePlan" :disabled="!generatedPlan" v-if="editing">
                保存
              </el-button>
              <el-button size="small" @click="loadHistory">历史教案</el-button>
              <el-button size="small" @click="pptPlaceholder">生成 PPT</el-button>
              <el-button size="small" :icon="RefreshRight" @click="regenerate">
                重新生成
              </el-button>
              <el-button size="small" :icon="DocumentCopy" @click="exportPlan">
                导出 HTML
              </el-button>
              <el-button size="small" :icon="Download" type="primary" plain @click="exportWord">
                下载 Word
              </el-button>
            </div>
          </div>
        </template>

        <!-- 空状态 -->
        <div v-if="!generatedPlan && !generating" class="empty-state">
          <el-empty description='请在左侧填写备课信息，点击"AI 生成教案"开始' />
        </div>

        <!-- 生成中骨架屏 -->
        <div v-if="generating && !generatedPlan" class="skeleton-wrap">
          <el-skeleton :rows="1" animated />
          <div style="margin: 16px 0;">
            <el-skeleton :rows="3" animated />
          </div>
          <el-skeleton :rows="5" animated />
          <div style="margin: 16px 0;">
            <el-skeleton :rows="4" animated />
          </div>
          <el-skeleton :rows="6" animated />
        </div>

        <!-- 教案内容 -->
        <div v-if="generatedPlan && !generating">
          <div v-if="editing" class="plan-content">
            <el-input v-model="editableContent" type="textarea" :rows="20" />
          </div>
          <div v-else class="plan-content">
            <div v-html="renderContent(generatedPlan.content)" class="lp-render" />
          </div>
        </div>

        <!-- 底部操作栏 -->
        <div v-if="generatedPlan" class="result-footer">
          <el-divider />
          <div class="flex-between">
            <span class="footer-tip">内容由 AI 生成，仅供参考，请教师根据实际情况调整</span>
            <el-button size="small" type="primary" :icon="Edit" @click="regenerate">
              重新生成
            </el-button>
          </div>
        </div>
      </el-card>
    </div>

    <el-dialog v-model="showHistory" title="历史教案" width="600px">
      <div v-if="savedPlans.length === 0">
        <el-empty description="暂无保存的教案" />
      </div>
      <el-table v-else :data="savedPlans" stripe style="width: 100%">
        <el-table-column prop="title" label="标题" min-width="160" />
        <el-table-column prop="subject" label="学科" width="80" />
        <el-table-column prop="grade" label="年级" width="80" />
        <el-table-column prop="topic" label="主题" width="120" />
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="loadPlan(row)">加载</el-button>
            <el-button size="small" type="danger" link @click="deletePlan(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-container {
  padding: 8px;
}

.page-title {
  font-size: 22px;
  font-weight: 700;
  color: #303133;
  margin: 0 0 4px;
}

.page-subtitle {
  color: #909399;
  margin: 0 0 20px;
  font-size: 14px;
}

.context-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 10px 14px;
  margin-bottom: 12px;
  background: #f5f7fa;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
}

.context-bar__error {
  color: #f56c6c;
  font-size: 12px;
}

.context-bar__hint {
  color: #909399;
  font-size: 12px;
}

.plan-links {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.plan-links__label {
  font-size: 12px;
  color: #606266;
}

.plan-links__tag {
  margin-right: 4px;
}

.ai-review-hint {
  margin-bottom: 16px;
  padding: 8px 12px;
  background: #fdf6ec;
  border: 1px solid #f5dab1;
  border-radius: 4px;
  color: #b88230;
  font-size: 12px;
  line-height: 1.5;
}

.layout-grid {
  display: grid;
  grid-template-columns: 380px 1fr;
  gap: 20px;
  align-items: start;
}

@media (max-width: 1200px) {
  .layout-grid {
    grid-template-columns: 340px 1fr;
  }
}

@media (max-width: 960px) {
  .layout-grid {
    grid-template-columns: 1fr;
  }
}

.form-card {
  border-radius: 8px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
}

.result-card {
  border-radius: 8px;
}

.flex-between {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.empty-state {
  padding: 60px 0;
}

.skeleton-wrap {
  padding: 16px 0;
}

.plan-content {
  min-height: 200px;
}

.lp-render {
  font-size: 14px;
  line-height: 1.8;
  color: #303133;
}

.plan-content :deep(h1) {
  font-size: 22px;
  color: #303133;
  border-bottom: 2px solid #409eff;
  padding-bottom: 8px;
  margin-bottom: 16px;
  font-weight: 700;
}

.plan-content :deep(h2) {
  font-size: 18px;
  color: #409eff;
  margin: 20px 0 10px;
  padding-left: 10px;
  border-left: 3px solid #409eff;
  font-weight: 600;
}

.plan-content :deep(h3) {
  font-size: 15px;
  color: #606266;
  margin: 12px 0 6px;
  font-weight: 600;
}

.plan-content :deep(ul),
.plan-content :deep(ol) {
  padding-left: 22px;
  margin: 6px 0;
}

.plan-content :deep(li) {
  margin: 4px 0;
}

.plan-content :deep(p) {
  margin: 8px 0;
}

.result-footer {
  margin-top: 8px;
}

.result-footer :deep(.el-divider) {
  margin: 12px 0;
}

.footer-tip {
  font-size: 12px;
  color: #c0c4cc;
}
</style>
