<script setup lang="ts">
/**
 * ProjectCreateWizard - 五步项目创建向导（计划 3.4）。
 *
 * 步骤：基本信息 → 真实问题 → 学科贡献 → 目标与证据 → 确认创建。
 * 草稿自动保存到 localStorage('new')，刷新不丢失；离开提示未保存变化；
 * 创建失败保留全部输入并定位到具体步骤与字段（mapServerError）。
 *
 * 仅基本信息中的名称为后端必填，其余字段缺失不阻断草稿前进；
 * 核心学科/支撑学科缺失在确认步骤提示，但允许创建草稿项目（计划 3.4）。
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter, onBeforeRouteLeave } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createProjectApi } from '@/api/projects'
import { listSubjectsApi } from '@/api/subjects'
import { listClassesBySchoolApi } from '@/api/schools'
import { useUserStore } from '@/stores/user'
import {
  WIZARD_STEPS,
  emptyDraft,
  loadDraft,
  saveDraft,
  clearDraft,
  validateStep,
  mapServerError,
} from '@/features/project-workspace/composables/useProjectWorkspace'
import type { ProjectWizardDraft, GoalType } from '@/features/project-workspace/types'
import {
  addContributionApi,
  addGoalApi,
  addIndicatorApi,
  addEvidencePlanApi,
  upsertProblemApi,
} from '@/features/project-workspace/api'
import type { SubjectItem, ClassItem } from '@/types'

const router = useRouter()
const userStore = useUserStore()

const draft = ref<ProjectWizardDraft>(emptyDraft())
const subjects = ref<SubjectItem[]>([])
const classes = ref<ClassItem[]>([])
const currentStep = ref(0)
const creating = ref(false)
const stepErrors = ref<Array<{ field: string; message: string }>>([])
const stepWarnings = ref<Array<{ field: string; message: string }>>([])
const lastSavedAt = ref<string | null>(null)

const DRAFT_ID = 'new'

const goalTypeOptions: Array<{ value: GoalType; label: string }> = [
  { value: 'knowledge', label: '知识' },
  { value: 'ability', label: '能力' },
  { value: 'transfer', label: '迁移' },
  { value: 'collaboration', label: '合作' },
  { value: 'practice', label: '实践' },
]

const gradeOptions = [
  { value: '', label: '请选择' },
  { value: '七年级', label: '七年级' },
  { value: '八年级', label: '八年级' },
  { value: '九年级', label: '九年级' },
]

const availableSupportSubjects = computed(() =>
  subjects.value.filter(
    (s) => s.isActive && s.id !== draft.value.coreSubjectId,
  ),
)

const displayName = computed(() => userStore.userInfo?.displayName || '当前教师')

function subjectName(id: string) {
  return subjects.value.find((s) => s.id === id)?.name || id
}

function className(id: string) {
  return classes.value.find((c) => c.id === id)?.name || id
}

// ── 草稿恢复与自动保存 ──────────────────────────────────────────
function restoreDraft() {
  const saved = loadDraft(DRAFT_ID)
  if (saved) {
    draft.value = saved
    currentStep.value = saved.step || 0
    ElMessage.info('已恢复上次未完成的创建草稿')
  }
}

let saveTimer: ReturnType<typeof setTimeout> | null = null
function scheduleSave() {
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(() => {
    draft.value.step = currentStep.value
    saveDraft(DRAFT_ID, draft.value)
    lastSavedAt.value = draft.value.savedAt || new Date().toISOString()
  }, 800)
}

watch(
  draft,
  () => scheduleSave(),
  { deep: true },
)

watch(currentStep, () => {
  draft.value.step = currentStep.value
  saveDraft(DRAFT_ID, draft.value)
})

// ── 步骤导航 ────────────────────────────────────────────────────
function gotoStep(idx: number) {
  if (idx < 0 || idx >= WIZARD_STEPS.length) return
  // 前进需校验当前步骤的硬错误
  if (idx > currentStep.value) {
    const r = validateStep(currentStep.value, draft.value)
    if (!r.valid) {
      stepErrors.value = r.errors
      stepWarnings.value = r.warnings
      ElMessage.error(r.errors[0].message)
      return
    }
  }
  currentStep.value = idx
  stepErrors.value = []
  stepWarnings.value = validateStep(idx, draft.value).warnings
}

function nextStep() {
  gotoStep(currentStep.value + 1)
}

function prevStep() {
  gotoStep(currentStep.value - 1)
}

// ── 学科贡献辅助 ────────────────────────────────────────────────
function setCoreSubject(id: string) {
  // 切换核心学科时，从支撑列表移除该学科
  draft.value.coreSubjectId = id
  draft.value.supportSubjectIds = draft.value.supportSubjectIds.filter(
    (s) => s !== id,
  )
  if (!draft.value.contributionNotes[id]) {
    draft.value.contributionNotes[id] = { knowledge: '', thinking: '', inquiry: '' }
  }
}

function toggleSupport(id: string) {
  const idx = draft.value.supportSubjectIds.indexOf(id)
  if (idx >= 0) {
    draft.value.supportSubjectIds.splice(idx, 1)
  } else {
    draft.value.supportSubjectIds.push(id)
    if (!draft.value.contributionNotes[id]) {
      draft.value.contributionNotes[id] = { knowledge: '', thinking: '', inquiry: '' }
    }
  }
}

// ── 目标编辑 ────────────────────────────────────────────────────
function addGoal() {
  draft.value.goals.push({
    goalType: 'knowledge',
    name: '',
    description: '',
    scope: '',
  })
}
function removeGoal(idx: number) {
  draft.value.goals.splice(idx, 1)
}

// ── 创建项目 ────────────────────────────────────────────────────
async function createProject() {
  // 确认步骤汇总校验
  const r = validateStep(4, draft.value)
  if (!r.valid) {
    stepErrors.value = r.errors
    ElMessage.error(r.errors[0].message)
    return
  }

  creating.value = true
  let projectId: string | null = null
  try {
    // 1. 创建项目主体（仅后端支持的字段）
    const createRes = await createProjectApi({
      title: draft.value.title,
      description: draft.value.description || undefined,
      grade: draft.value.grade || undefined,
      start_date: draft.value.startDate || undefined,
      end_date: draft.value.endDate || undefined,
      cover_image_url: draft.value.coverImageUrl || undefined,
      subject_ids: [
        draft.value.coreSubjectId,
        ...draft.value.supportSubjectIds,
      ].filter(Boolean),
      class_ids: draft.value.classIds,
    })
    projectId = createRes.data.data.id

    // 2. 保存真实问题（若填写）
    if (draft.value.problemContext.trim()) {
      await upsertProblemApi(projectId, {
        context: draft.value.problemContext,
        object: draft.value.problemObject || null,
        audience: draft.value.problemAudience || null,
        constraints: draft.value.problemConstraints || null,
        deliverable: draft.value.problemDeliverable || null,
        usage: draft.value.problemUsage || null,
      })
    }

    // 3. 保存学科贡献
    if (draft.value.coreSubjectId) {
      const notes = draft.value.contributionNotes[draft.value.coreSubjectId]
      await addContributionApi(projectId, {
        subjectId: draft.value.coreSubjectId,
        role: 'core',
        knowledge: notes?.knowledge || null,
        thinking: notes?.thinking || null,
        inquiry: notes?.inquiry || null,
      })
    }
    for (const sid of draft.value.supportSubjectIds) {
      const notes = draft.value.contributionNotes[sid]
      await addContributionApi(projectId, {
        subjectId: sid,
        role: 'support',
        knowledge: notes?.knowledge || null,
        thinking: notes?.thinking || null,
        inquiry: notes?.inquiry || null,
      })
    }

    // 4. 保存目标（指标与证据计划在向导中不强制，留待设计页完善）
    for (const g of draft.value.goals) {
      if (g.name.trim()) {
        await addGoalApi(projectId, {
          goalType: g.goalType,
          name: g.name,
          description: g.description || null,
          scope: g.scope || null,
        })
      }
    }

    // 5. 清除草稿，跳转工作区
    clearDraft(DRAFT_ID)
    ElMessage.success('项目已创建')
    router.push({
      name: 'ProjectOverview',
      params: { id: projectId },
    })
  } catch (e) {
    const mapped = mapServerError(e)
    if (mapped.step !== null) {
      currentStep.value = mapped.step
    }
    stepErrors.value = mapped.field
      ? [{ field: mapped.field, message: mapped.message }]
      : []
    ElMessage.error(mapped.message)
    // 创建失败保留全部输入（草稿仍在 localStorage）
  } finally {
    creating.value = false
  }
}

// ── 离开保护 ────────────────────────────────────────────────────
function isDirty() {
  return (
    draft.value.title.trim() !== '' ||
    draft.value.problemContext.trim() !== '' ||
    draft.value.coreSubjectId !== '' ||
    draft.value.goals.length > 0
  )
}

onBeforeRouteLeave(async (to) => {
  // 创建成功后跳转不走提示
  if (to.name === 'ProjectOverview' && !creating.value === false) {
    return true
  }
  if (!isDirty()) return true
  try {
    await ElMessageBox.confirm(
      '离开将丢失未保存的草稿（已自动保存的字段可在下次恢复），确定离开吗？',
      '离开提示',
      { type: 'warning' },
    )
    return true
  } catch {
    return false
  }
})

function beforeUnloadHandler(e: BeforeUnloadEvent) {
  if (isDirty()) {
    e.preventDefault()
    e.returnValue = ''
  }
}

// ── 元数据加载 ──────────────────────────────────────────────────
async function loadMeta() {
  const schoolId = userStore.userInfo?.schoolId
  const [subjRes, clsRes] = await Promise.all([
    listSubjectsApi(),
    schoolId
      ? listClassesBySchoolApi(schoolId)
      : Promise.resolve({ data: { data: [] as ClassItem[] } }),
  ])
  subjects.value = subjRes.data.data
  classes.value = (clsRes.data.data as ClassItem[]) || []
}

const savedLabel = computed(() => {
  if (!lastSavedAt.value) return ''
  const d = new Date(lastSavedAt.value)
  return `已自动保存 ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}`
})

onMounted(() => {
  restoreDraft()
  loadMeta()
  window.addEventListener('beforeunload', beforeUnloadHandler)
})

onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', beforeUnloadHandler)
})
</script>

<template>
  <div class="wizard">
    <div class="wizard-header">
      <el-link :underline="false" href="#/teacher/projects" class="back-link">
        <el-icon><ArrowLeft /></el-icon> 返回项目列表
      </el-link>
      <h2 class="wizard-title">创建跨学科项目</h2>
      <span class="save-hint">{{ savedLabel }}</span>
    </div>

    <!-- 步骤指示器 -->
    <div class="steps">
      <div
        v-for="step in WIZARD_STEPS"
        :key="step.index"
        class="step-item"
        :class="{
          active: currentStep === step.index,
          done: currentStep > step.index,
        }"
        @click="gotoStep(step.index)"
      >
        <div class="step-index">{{ step.index + 1 }}</div>
        <div class="step-info">
          <div class="step-title">{{ step.title }}</div>
          <div class="step-desc">{{ step.description }}</div>
        </div>
      </div>
    </div>

    <!-- 步骤内容 -->
    <div class="step-content">
      <!-- 步骤 1：基本信息 -->
      <div v-show="currentStep === 0" class="step-pane">
        <h3 class="pane-title">基本信息</h3>
        <el-form label-position="top">
          <el-form-item label="项目名称" required>
            <el-input v-model="draft.title" placeholder="请输入项目名称" />
            <div v-if="stepErrors.find(e => e.field === 'title')" class="field-error">
              {{ stepErrors.find(e => e.field === 'title')!.message }}
            </div>
          </el-form-item>
          <el-row :gutter="16">
            <el-col :span="8">
              <el-form-item label="年级">
                <el-select v-model="draft.grade" placeholder="请选择">
                  <el-option v-for="g in gradeOptions" :key="g.value" :label="g.label" :value="g.value" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="10">
              <el-form-item label="参与班级">
                <el-select v-model="draft.classIds" multiple placeholder="选择班级" style="width: 100%">
                  <el-option v-for="c in classes" :key="c.id" :label="c.name" :value="c.id" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="课时（规划）">
                <el-input-number v-model="draft.lessonHours" :min="1" :max="200" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="16">
            <el-col :span="8">
              <el-form-item label="负责人">
                <el-input :model-value="displayName" disabled />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="开始日期">
                <el-date-picker v-model="draft.startDate" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="结束日期">
                <el-date-picker v-model="draft.endDate" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item label="项目描述">
            <el-input v-model="draft.description" type="textarea" :rows="3" />
          </el-form-item>
          <p class="field-hint">协作人与审核人字段为规划信息，暂存于本地草稿，将在后续阶段同步到服务端。</p>
        </el-form>
      </div>

      <!-- 步骤 2：真实问题 -->
      <div v-show="currentStep === 1" class="step-pane">
        <h3 class="pane-title">真实问题</h3>
        <el-form label-position="top">
          <el-form-item label="情境描述" required>
            <el-input v-model="draft.problemContext" type="textarea" :rows="4" placeholder="描述真实问题所处的情境" />
          </el-form-item>
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="问题对象">
                <el-input v-model="draft.problemObject" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="真实受众">
                <el-input v-model="draft.problemAudience" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item label="约束条件">
            <el-input v-model="draft.problemConstraints" type="textarea" :rows="2" />
          </el-form-item>
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="最终成果">
                <el-input v-model="draft.problemDeliverable" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="成果用途">
                <el-input v-model="draft.problemUsage" />
              </el-form-item>
            </el-col>
          </el-row>
        </el-form>
      </div>

      <!-- 步骤 3：学科贡献 -->
      <div v-show="currentStep === 2" class="step-pane">
        <h3 class="pane-title">学科贡献</h3>
        <p class="field-hint">选择唯一核心学科与至少一门支撑学科。核心学科不与支撑学科重复。</p>

        <div class="subject-block">
          <h4 class="block-title">核心学科（唯一）</h4>
          <el-select v-model="draft.coreSubjectId" placeholder="选择核心学科" @change="setCoreSubject">
            <el-option v-for="s in subjects" :key="s.id" :label="s.name" :value="s.id" :disabled="!s.isActive" />
          </el-select>
          <template v-if="draft.coreSubjectId">
            <el-row :gutter="12" class="contrib-notes">
              <el-col :span="8">
                <el-input v-model="draft.contributionNotes[draft.coreSubjectId].knowledge" placeholder="知识贡献" />
              </el-col>
              <el-col :span="8">
                <el-input v-model="draft.contributionNotes[draft.coreSubjectId].thinking" placeholder="思维方式" />
              </el-col>
              <el-col :span="8">
                <el-input v-model="draft.contributionNotes[draft.coreSubjectId].inquiry" placeholder="探究方法" />
              </el-col>
            </el-row>
          </template>
        </div>

        <div class="subject-block">
          <h4 class="block-title">支撑学科（至少一门）</h4>
          <el-checkbox-group v-model="draft.supportSubjectIds">
            <el-checkbox
              v-for="s in availableSupportSubjects"
              :key="s.id"
              :value="s.id"
              :label="s.name"
              @change="toggleSupport(s.id)"
            >
              {{ s.name }}
            </el-checkbox>
          </el-checkbox-group>
          <div v-if="stepErrors.find(e => e.field === 'supportSubjectIds')" class="field-error">
            {{ stepErrors.find(e => e.field === 'supportSubjectIds')!.message }}
          </div>
          <template v-for="sid in draft.supportSubjectIds" :key="sid">
            <el-row :gutter="12" class="contrib-notes">
              <el-col :span="2"><span class="sub-label">{{ subjectName(sid) }}</span></el-col>
              <el-col :span="7">
                <el-input v-model="draft.contributionNotes[sid].knowledge" placeholder="知识贡献" />
              </el-col>
              <el-col :span="7">
                <el-input v-model="draft.contributionNotes[sid].thinking" placeholder="思维方式" />
              </el-col>
              <el-col :span="8">
                <el-input v-model="draft.contributionNotes[sid].inquiry" placeholder="探究方法" />
              </el-col>
            </el-row>
          </template>
        </div>
      </div>

      <!-- 步骤 4：目标与证据 -->
      <div v-show="currentStep === 3" class="step-pane">
        <h3 class="pane-title">目标与证据</h3>
        <p class="field-hint">向导阶段仅记录目标概要；指标与证据计划可在项目设计页继续完善。</p>
        <div v-for="(g, idx) in draft.goals" :key="idx" class="goal-row">
          <el-row :gutter="12">
            <el-col :span="6">
              <el-select v-model="g.goalType">
                <el-option v-for="o in goalTypeOptions" :key="o.value" :label="o.label" :value="o.value" />
              </el-select>
            </el-col>
            <el-col :span="10">
              <el-input v-model="g.name" placeholder="目标名称" />
            </el-col>
            <el-col :span="6">
              <el-input v-model="g.scope" placeholder="范围" />
            </el-col>
            <el-col :span="2">
              <el-button text type="danger" @click="removeGoal(idx)">删除</el-button>
            </el-col>
          </el-row>
          <el-input v-model="g.description" placeholder="描述（选填）" class="goal-desc-input" />
        </div>
        <el-button @click="addGoal">+ 添加目标</el-button>
      </div>

      <!-- 步骤 5：确认创建 -->
      <div v-show="currentStep === 4" class="step-pane">
        <h3 class="pane-title">确认创建</h3>

        <div class="confirm-section">
          <h4 class="block-title">基本信息</h4>
          <div class="kv"><span class="k">名称</span><span class="v">{{ draft.title || '—' }}</span></div>
          <div class="kv"><span class="k">年级</span><span class="v">{{ draft.grade || '—' }}</span></div>
          <div class="kv"><span class="k">班级</span><span class="v">{{ draft.classIds.map(className).join('、') || '—' }}</span></div>
          <div class="kv"><span class="k">课时</span><span class="v">{{ draft.lessonHours || '—' }}</span></div>
        </div>

        <div class="confirm-section">
          <h4 class="block-title">真实问题</h4>
          <div class="kv"><span class="k">情境</span><span class="v">{{ draft.problemContext || '—' }}</span></div>
          <div class="kv"><span class="k">成果</span><span class="v">{{ draft.problemDeliverable || '—' }}</span></div>
        </div>

        <div class="confirm-section">
          <h4 class="block-title">学科贡献</h4>
          <div class="kv"><span class="k">核心</span><span class="v">{{ draft.coreSubjectId ? subjectName(draft.coreSubjectId) : '未指定' }}</span></div>
          <div class="kv"><span class="k">支撑</span><span class="v">{{ draft.supportSubjectIds.map(subjectName).join('、') || '未指定' }}</span></div>
        </div>

        <div class="confirm-section">
          <h4 class="block-title">目标</h4>
          <div v-if="draft.goals.length === 0" class="empty">无目标</div>
          <ul v-else class="goal-summary">
            <li v-for="(g, idx) in draft.goals" :key="idx">
              {{ goalTypeOptions.find(o => o.value === g.goalType)?.label }} · {{ g.name || '未命名' }}
            </li>
          </ul>
        </div>

        <!-- 缺失与警告 -->
        <div v-if="stepWarnings.length > 0" class="warning-block">
          <h4 class="block-title">建议处理项</h4>
          <ul>
            <li v-for="(w, i) in stepWarnings" :key="i">{{ w.message }}</li>
          </ul>
        </div>
        <div v-if="stepErrors.length > 0" class="error-block">
          <h4 class="block-title">阻断项</h4>
          <ul>
            <li v-for="(e, i) in stepErrors" :key="i">{{ e.message }}</li>
          </ul>
        </div>

        <p class="create-hint">
          创建后将生成草稿项目；正式激活需在工作区补齐所有阻断项并通过完整性校验。
        </p>
      </div>
    </div>

    <!-- 底部导航 -->
    <div class="wizard-footer">
      <el-button :disabled="currentStep === 0" @click="prevStep">上一步</el-button>
      <el-button v-if="currentStep < WIZARD_STEPS.length - 1" type="primary" @click="nextStep">
        下一步
      </el-button>
      <el-button
        v-else
        type="primary"
        :loading="creating"
        @click="createProject"
      >
        创建项目
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.wizard {
  max-width: 960px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 8px 0 32px;
}

.wizard-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.back-link {
  font-size: 13px;
  color: #909399;
}

.wizard-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #303133;
  flex: 1;
}

.save-hint {
  font-size: 12px;
  color: #909399;
}

.steps {
  display: flex;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 12px;
  gap: 4px;
}

.step-item {
  flex: 1;
  display: flex;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.15s;
}

.step-item:hover {
  background: #f7f8fa;
}

.step-item.active {
  background: #f0f1f3;
}

.step-index {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #e6e8eb;
  color: #909399;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}

.step-item.active .step-index {
  background: #303133;
  color: #fff;
}

.step-item.done .step-index {
  background: #67c23a;
  color: #fff;
}

.step-title {
  font-size: 13px;
  font-weight: 500;
  color: #303133;
}

.step-item.active .step-title {
  font-weight: 600;
}

.step-desc {
  font-size: 11px;
  color: #909399;
  margin-top: 2px;
}

.step-content {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 24px;
  min-height: 320px;
}

.pane-title {
  margin: 0 0 16px;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.field-hint {
  font-size: 12px;
  color: #909399;
  margin: -8px 0 16px;
}

.field-error {
  font-size: 12px;
  color: #f56c6c;
  margin-top: 4px;
}

.subject-block {
  margin-bottom: 20px;
}

.block-title {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: #606266;
}

.contrib-notes {
  margin-top: 8px;
}

.sub-label {
  font-size: 13px;
  color: #606266;
  line-height: 32px;
}

.goal-row {
  margin-bottom: 12px;
  padding: 12px;
  background: #fafbfc;
  border-radius: 4px;
}

.goal-desc-input {
  margin-top: 8px;
}

.confirm-section {
  margin-bottom: 20px;
  padding: 12px;
  background: #fafbfc;
  border-radius: 4px;
}

.kv {
  display: grid;
  grid-template-columns: 80px 1fr;
  gap: 8px;
  padding: 3px 0;
  font-size: 13px;
}

.kv .k {
  color: #909399;
}

.kv .v {
  color: #303133;
  word-break: break-word;
}

.empty {
  font-size: 13px;
  color: #c0c4cc;
}

.goal-summary {
  margin: 0;
  padding-left: 20px;
  font-size: 13px;
  color: #606266;
}

.warning-block {
  margin-bottom: 16px;
  padding: 12px;
  background: #fdf6ec;
  border-radius: 4px;
  font-size: 13px;
  color: #e6a23c;
}

.warning-block ul {
  margin: 6px 0 0;
  padding-left: 20px;
}

.error-block {
  margin-bottom: 16px;
  padding: 12px;
  background: #fef0f0;
  border-radius: 4px;
  font-size: 13px;
  color: #f56c6c;
}

.error-block ul {
  margin: 6px 0 0;
  padding-left: 20px;
}

.create-hint {
  font-size: 12px;
  color: #909399;
  margin-top: 16px;
}

.wizard-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 0;
}
</style>
