<script setup lang="ts">
/**
 * ProjectDesignView - 跨学科设计页（计划 3.5.2 / Task 7）。
 *
 * 固定五段顺序：真实问题 → 学科贡献 → 学习目标 → 评价指标 → 证据计划。
 * 右侧栏仅展示紧凑完整度与问题清单（blockers/warnings），每个问题携带
 * fix_route 修复入口，点击后滚动到对应编辑区。不使用卡片嵌套。
 *
 * 原地编辑：已有贡献/目标/指标/证据计划通过 PATCH 局部更新，ID 保持不变，
 * 不删除重建。关联删除（目标被指标引用、指标被证据引用、移除核心学科）
 * 必须返回引用影响并要求显式确认（confirm=true）后才级联执行。
 */
import { computed, inject, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, onBeforeRouteLeave } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  addContributionApi,
  addEvidencePlanApi,
  addGoalApi,
  addIndicatorApi,
  getDesignSnapshotApi,
  patchContributionApi,
  patchEvidencePlanApi,
  patchGoalApi,
  patchIndicatorApi,
  patchProblemApi,
  removeContributionApi,
  removeEvidencePlanApi,
  removeGoalApi,
  removeIndicatorApi,
  upsertProblemApi,
  validateActivationApi,
} from '@/features/project-workspace/api'
import {
  anchorFromFixRoute,
  canEditDesign,
  formatCompletionSummary,
  mapServerError,
  parseDeletionImpact,
} from '@/features/project-workspace/composables/useProjectWorkspace'
import type {
  DeletionImpact,
  EvidenceCollector,
  EvidencePlan,
  EvidenceType,
  GoalType,
  ProjectDesignSnapshot,
  ProjectProblem,
  ProjectValidationResult,
  SubjectContribution,
  SubjectRole,
  TeachingStage,
} from '@/features/project-workspace/types'
import type { Project, SubjectItem } from '@/types'

type Ref<T> = import('vue').Ref<T>

const route = useRoute()
const projectId = computed(() => route.params.id as string)

const project = inject<Ref<Project | null>>('workspaceProject')
const subjects = inject<Ref<SubjectItem[]>>('workspaceSubjects')

const snapshot = ref<ProjectDesignSnapshot | null>(null)
const validation = ref<ProjectValidationResult | null>(null)
const loading = ref(false)
const savingProblem = ref(false)
const saveStatus = ref<'idle' | 'saving' | 'saved' | 'error'>('idle')
const lastSavedAt = ref<string | null>(null)
const activeAnchor = ref<string>('')

const editable = computed(() =>
  canEditDesign(project?.value?.status || 'draft'),
)

const completionSummary = computed(() =>
  formatCompletionSummary(validation.value),
)

// ── 真实问题表单 ────────────────────────────────────────────────
const problemForm = ref({
  context: '',
  object: '',
  audience: '',
  constraints: '',
  deliverable: '',
  usage: '',
})

// ── 新增贡献表单 ────────────────────────────────────────────────
const newContribution = ref({
  subjectId: '',
  role: 'support' as SubjectRole,
  knowledge: '',
  thinking: '',
  inquiry: '',
})

// ── 新增目标表单 ────────────────────────────────────────────────
const newGoal = ref({
  goalType: 'knowledge' as GoalType,
  name: '',
  description: '',
  scope: '',
})

// ── 新增指标表单（按目标）────────────────────────────────────────
const newIndicatorByGoal = ref<Record<string, { observableBehavior: string; levelRule: string }>>({})

// ── 新增证据计划表单（按指标）────────────────────────────────────
const newEvidenceByIndicator = ref<
  Record<string, { stage: TeachingStage; evidenceType: EvidenceType; collector: EvidenceCollector; description: string }>
>({})

const goalTypeOptions: Array<{ value: GoalType; label: string }> = [
  { value: 'knowledge', label: '知识' },
  { value: 'ability', label: '能力' },
  { value: 'transfer', label: '迁移' },
  { value: 'collaboration', label: '合作' },
  { value: 'practice', label: '实践' },
]
const stageOptions: Array<{ value: TeachingStage; label: string }> = [
  { value: 'pre_class', label: '课前' },
  { value: 'in_class', label: '课中' },
  { value: 'post_class', label: '课后' },
]
const evidenceTypeOptions: Array<{ value: EvidenceType; label: string }> = [
  { value: 'artifact', label: '作品' },
  { value: 'observation', label: '观察' },
  { value: 'test', label: '测试' },
  { value: 'reflection', label: '反思' },
  { value: 'process_log', label: '过程记录' },
]
const collectorOptions: Array<{ value: EvidenceCollector; label: string }> = [
  { value: 'teacher', label: '教师' },
  { value: 'student', label: '学生' },
  { value: 'peer', label: '同伴' },
  { value: 'system', label: '系统' },
]

const coreContribution = computed(() =>
  snapshot.value?.contributions.find((c) => c.role === 'core'),
)
const availableSubjectsForNew = computed(() => {
  const used = new Set(snapshot.value?.contributions.map((c) => c.subjectId) || [])
  return (subjects?.value || []).filter((s) => !used.has(s.id) && s.isActive)
})

function subjectName(id?: string | null) {
  return (id && subjects?.value?.find((s) => s.id === id)?.name) || id || '—'
}

function goalTypeLabel(t: GoalType) {
  return goalTypeOptions.find((o) => o.value === t)?.label || t
}
function stageLabel(s: TeachingStage) {
  return stageOptions.find((o) => o.value === s)?.label || s
}
function evidenceTypeLabel(t: EvidenceType) {
  return evidenceTypeOptions.find((o) => o.value === t)?.label || t
}
function collectorLabel(c: EvidenceCollector) {
  return collectorOptions.find((o) => o.value === c)?.label || c
}

function goalName(goalId: string) {
  return snapshot.value?.goals.find((g) => g.id === goalId)?.name || '—'
}
function indicatorBehavior(indicatorId: string) {
  return snapshot.value?.indicators.find((i) => i.id === indicatorId)?.observableBehavior || '—'
}

async function loadDesign() {
  loading.value = true
  try {
    const [snapRes, valRes] = await Promise.all([
      getDesignSnapshotApi(projectId.value),
      validateActivationApi(projectId.value).catch(() => null),
    ])
    snapshot.value = snapRes.data.data
    if (valRes) validation.value = valRes.data.data
    syncProblemForm()
  } finally {
    loading.value = false
  }
}

async function refreshValidation() {
  try {
    const res = await validateActivationApi(projectId.value)
    validation.value = res.data.data
  } catch {
    // 校验失败不阻塞编辑，右侧栏保留上次结果
  }
}

function syncProblemForm() {
  const p = snapshot.value?.problem
  if (p) {
    problemForm.value = {
      context: p.context || '',
      object: p.object || '',
      audience: p.audience || '',
      constraints: p.constraints || '',
      deliverable: p.deliverable || '',
      usage: p.usage || '',
    }
  }
}

// ── 真实问题保存（PUT 版本化首次写入，PATCH 原地更新）──────────
async function saveProblem() {
  if (!editable.value) return
  saveStatus.value = 'saving'
  savingProblem.value = true
  try {
    const hasExisting = !!snapshot.value?.problem
    const api = hasExisting ? patchProblemApi : upsertProblemApi
    const res = await api(projectId.value, { ...problemForm.value })
    if (snapshot.value) {
      snapshot.value.problem = res.data.data
    } else {
      snapshot.value = {
        problem: res.data.data,
        contributions: [],
        goals: [],
        indicators: [],
        evidencePlans: [],
      }
    }
    saveStatus.value = 'saved'
    lastSavedAt.value = new Date().toISOString()
    await refreshValidation()
  } catch (e) {
    saveStatus.value = 'error'
    const mapped = mapServerError(e)
    ElMessage.error(mapped.message)
  } finally {
    savingProblem.value = false
  }
}

// ── 贡献：原地编辑 + 新增 + 关联删除 ───────────────────────────
async function patchContributionField(c: SubjectContribution, field: 'knowledge' | 'thinking' | 'inquiry', value: string) {
  if (!editable.value) return
  try {
    const res = await patchContributionApi(projectId.value, c.id, { [field]: value })
    Object.assign(c, res.data.data)
    await refreshValidation()
  } catch (e) {
    const mapped = mapServerError(e)
    ElMessage.error(mapped.message)
  }
}

async function addContribution() {
  if (!editable.value) return
  if (!newContribution.value.subjectId) {
    ElMessage.warning('请选择学科')
    return
  }
  try {
    const res = await addContributionApi(projectId.value, { ...newContribution.value })
    snapshot.value?.contributions.push(res.data.data)
    newContribution.value = { subjectId: '', role: 'support', knowledge: '', thinking: '', inquiry: '' }
    ElMessage.success('已添加学科贡献')
    await refreshValidation()
  } catch (e) {
    const mapped = mapServerError(e)
    ElMessage.error(mapped.message)
  }
}

function describeContributionImpact(impact: DeletionImpact): string {
  if (impact.willClearCoreSubject) {
    return '该学科为核心学科，移除将清空项目核心学科设定。确认继续？'
  }
  return '确认移除该学科贡献？'
}

async function removeContribution(c: SubjectContribution) {
  if (!editable.value) return
  try {
    await removeContributionApi(projectId.value, c.id)
  } catch (err) {
    const impact = parseDeletionImpact(err)
    if (!impact) {
      const mapped = mapServerError(err)
      ElMessage.error(mapped.message)
      return
    }
    try {
      await ElMessageBox.confirm(describeContributionImpact(impact), '关联删除确认', {
        type: 'warning',
        confirmButtonText: '确认移除',
        cancelButtonText: '取消',
      })
    } catch {
      return
    }
    try {
      await removeContributionApi(projectId.value, c.id, true)
    } catch (e) {
      const mapped = mapServerError(e)
      ElMessage.error(mapped.message)
      return
    }
  }
  if (snapshot.value) {
    snapshot.value.contributions = snapshot.value.contributions.filter((x) => x.id !== c.id)
  }
  ElMessage.success('已移除')
  await refreshValidation()
}

// ── 学习目标：原地编辑 + 新增 + 关联删除 ───────────────────────
async function patchGoalField(g_id: string, field: 'name' | 'description', value: string) {
  if (!editable.value) return
  const g = snapshot.value?.goals.find((x) => x.id === g_id)
  if (!g) return
  try {
    const res = await patchGoalApi(projectId.value, g.id, { [field]: value })
    Object.assign(g, res.data.data)
    await refreshValidation()
  } catch (e) {
    const mapped = mapServerError(e)
    ElMessage.error(mapped.message)
  }
}

async function addGoal() {
  if (!editable.value) return
  if (!newGoal.value.name.trim()) {
    ElMessage.warning('请输入目标名称')
    return
  }
  try {
    const res = await addGoalApi(projectId.value, { ...newGoal.value })
    snapshot.value?.goals.push(res.data.data)
    newGoal.value = { goalType: 'knowledge', name: '', description: '', scope: '' }
    ElMessage.success('已添加目标')
    await refreshValidation()
  } catch (e) {
    const mapped = mapServerError(e)
    ElMessage.error(mapped.message)
  }
}

function describeGoalImpact(impact: DeletionImpact): string {
  const n = impact.referencedBy?.indicators ?? 0
  return `该目标仍被 ${n} 个指标引用，删除将级联清除关联指标及其证据计划。确认继续？`
}

async function removeGoal(goalId: string) {
  if (!editable.value) return
  try {
    await removeGoalApi(projectId.value, goalId)
  } catch (err) {
    const impact = parseDeletionImpact(err)
    if (!impact) {
      const mapped = mapServerError(err)
      ElMessage.error(mapped.message)
      return
    }
    try {
      await ElMessageBox.confirm(describeGoalImpact(impact), '关联删除确认', {
        type: 'warning',
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
      })
    } catch {
      return
    }
    try {
      await removeGoalApi(projectId.value, goalId, true)
    } catch (e) {
      const mapped = mapServerError(e)
      ElMessage.error(mapped.message)
      return
    }
  }
  if (snapshot.value) {
    const indicatorIds = new Set(
      snapshot.value.indicators.filter((i) => i.goalId === goalId).map((i) => i.id),
    )
    snapshot.value.goals = snapshot.value.goals.filter((g) => g.id !== goalId)
    snapshot.value.indicators = snapshot.value.indicators.filter((i) => i.goalId !== goalId)
    snapshot.value.evidencePlans = snapshot.value.evidencePlans.filter(
      (p) => !indicatorIds.has(p.indicatorId),
    )
  }
  ElMessage.success('已删除目标')
  await refreshValidation()
}

// ── 评价指标：原地编辑 + 新增 + 关联删除 ───────────────────────
function ensureIndicatorDraft(goalId: string) {
  if (!newIndicatorByGoal.value[goalId]) {
    newIndicatorByGoal.value[goalId] = { observableBehavior: '', levelRule: '' }
  }
}

async function patchIndicatorField(i_id: string, field: 'observableBehavior' | 'levelRule', value: string) {
  if (!editable.value) return
  const ind = snapshot.value?.indicators.find((x) => x.id === i_id)
  if (!ind) return
  try {
    const res = await patchIndicatorApi(projectId.value, ind.id, { [field]: value })
    Object.assign(ind, res.data.data)
    await refreshValidation()
  } catch (e) {
    const mapped = mapServerError(e)
    ElMessage.error(mapped.message)
  }
}

async function addIndicator(goalId: string) {
  if (!editable.value) return
  const draft = newIndicatorByGoal.value[goalId]
  if (!draft || !draft.observableBehavior.trim()) {
    ElMessage.warning('请输入可观察行为')
    return
  }
  try {
    const res = await addIndicatorApi(projectId.value, {
      goalId,
      observableBehavior: draft.observableBehavior,
      levelRule: draft.levelRule || null,
    })
    snapshot.value?.indicators.push(res.data.data)
    newIndicatorByGoal.value[goalId] = { observableBehavior: '', levelRule: '' }
    ElMessage.success('已添加指标')
    await refreshValidation()
  } catch (e) {
    const mapped = mapServerError(e)
    ElMessage.error(mapped.message)
  }
}

function describeIndicatorImpact(impact: DeletionImpact): string {
  const n = impact.referencedBy?.evidencePlans ?? 0
  return `该指标仍被 ${n} 个证据计划引用，删除将级联清除关联证据计划。确认继续？`
}

async function removeIndicator(indicatorId: string) {
  if (!editable.value) return
  try {
    await removeIndicatorApi(projectId.value, indicatorId)
  } catch (err) {
    const impact = parseDeletionImpact(err)
    if (!impact) {
      const mapped = mapServerError(err)
      ElMessage.error(mapped.message)
      return
    }
    try {
      await ElMessageBox.confirm(describeIndicatorImpact(impact), '关联删除确认', {
        type: 'warning',
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
      })
    } catch {
      return
    }
    try {
      await removeIndicatorApi(projectId.value, indicatorId, true)
    } catch (e) {
      const mapped = mapServerError(e)
      ElMessage.error(mapped.message)
      return
    }
  }
  if (snapshot.value) {
    snapshot.value.indicators = snapshot.value.indicators.filter((i) => i.id !== indicatorId)
    snapshot.value.evidencePlans = snapshot.value.evidencePlans.filter(
      (p) => p.indicatorId !== indicatorId,
    )
  }
  ElMessage.success('已删除指标')
  await refreshValidation()
}

// ── 证据计划：原地编辑 + 新增 + 删除 ───────────────────────────
function ensureEvidenceDraft(indicatorId: string) {
  if (!newEvidenceByIndicator.value[indicatorId]) {
    newEvidenceByIndicator.value[indicatorId] = {
      stage: 'pre_class',
      evidenceType: 'artifact',
      collector: 'teacher',
      description: '',
    }
  }
}

async function patchEvidenceField(p_id: string, field: 'description', value: string) {
  if (!editable.value) return
  const p = snapshot.value?.evidencePlans.find((x) => x.id === p_id)
  if (!p) return
  try {
    const res = await patchEvidencePlanApi(projectId.value, p.id, { [field]: value })
    Object.assign(p, res.data.data)
    await refreshValidation()
  } catch (e) {
    const mapped = mapServerError(e)
    ElMessage.error(mapped.message)
  }
}

async function patchEvidenceRequired(p_id: string, required: boolean) {
  if (!editable.value) return
  const p = snapshot.value?.evidencePlans.find((x) => x.id === p_id)
  if (!p) return
  try {
    const res = await patchEvidencePlanApi(projectId.value, p.id, { required })
    Object.assign(p, res.data.data)
    await refreshValidation()
  } catch (e) {
    const mapped = mapServerError(e)
    ElMessage.error(mapped.message)
  }
}

async function addEvidence(indicatorId: string) {
  if (!editable.value) return
  const draft = newEvidenceByIndicator.value[indicatorId]
  if (!draft) return
  try {
    const res = await addEvidencePlanApi(projectId.value, {
      indicatorId,
      stage: draft.stage,
      evidenceType: draft.evidenceType,
      collector: draft.collector,
      required: true,
      description: draft.description || null,
    })
    snapshot.value?.evidencePlans.push(res.data.data)
    newEvidenceByIndicator.value[indicatorId] = {
      stage: 'pre_class',
      evidenceType: 'artifact',
      collector: 'teacher',
      description: '',
    }
    ElMessage.success('已添加证据计划')
    await refreshValidation()
  } catch (e) {
    const mapped = mapServerError(e)
    ElMessage.error(mapped.message)
  }
}

async function removeEvidence(planId: string) {
  if (!editable.value) return
  try {
    await removeEvidencePlanApi(projectId.value, planId)
  } catch (e) {
    const mapped = mapServerError(e)
    ElMessage.error(mapped.message)
    return
  }
  if (snapshot.value) {
    snapshot.value.evidencePlans = snapshot.value.evidencePlans.filter((p) => p.id !== planId)
  }
  ElMessage.success('已删除证据计划')
  await refreshValidation()
}

// ── 修复路由：滚动到对应编辑区并高亮 ───────────────────────────
async function jumpToFixRoute(fixRoute?: string) {
  const anchor = anchorFromFixRoute(fixRoute)
  if (!anchor) return
  activeAnchor.value = anchor
  await nextTick()
  const el = document.getElementById(anchor)
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  setTimeout(() => {
    if (activeAnchor.value === anchor) activeAnchor.value = ''
  }, 2000)
}

// ── 离开保护 ────────────────────────────────────────────────────
onBeforeRouteLeave(async (_to, _from) => {
  if (saveStatus.value === 'saving') {
    try {
      await ElMessageBox.confirm('有内容正在保存，确定离开吗？', '离开提示', {
        type: 'warning',
      })
      return true
    } catch {
      return false
    }
  }
  return true
})

function beforeUnloadHandler(e: BeforeUnloadEvent) {
  if (saveStatus.value === 'saving') {
    e.preventDefault()
    e.returnValue = ''
  }
}

onMounted(() => {
  loadDesign()
  window.addEventListener('beforeunload', beforeUnloadHandler)
})

onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', beforeUnloadHandler)
})

const savedLabel = computed(() => {
  if (saveStatus.value === 'saving') return '保存中…'
  if (saveStatus.value === 'saved' && lastSavedAt.value)
    return `已保存 ${formatTime(lastSavedAt.value)}`
  if (saveStatus.value === 'error') return '保存失败'
  return ''
})

function formatTime(iso: string) {
  const d = new Date(iso)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}`
}
</script>

<template>
  <div class="design" v-loading="loading">
    <!-- 只读提示 -->
    <div v-if="!editable" class="readonly-bar">
      项目当前状态为「{{ project?.status }}」，设计内容只读
    </div>

    <!-- 保存状态 -->
    <div class="save-bar">
      <span class="save-status" :class="saveStatus">{{ savedLabel }}</span>
    </div>

    <div class="design-layout">
      <!-- 主区：五段固定顺序 -->
      <div class="design-main">
        <!-- 1. 真实问题 -->
        <section
          id="problem"
          class="panel"
          :class="{ 'panel-active': activeAnchor === 'problem' }"
        >
          <h3 class="panel-title">真实问题</h3>
          <el-form label-position="top" :disabled="!editable">
            <el-form-item label="情境描述" required>
              <el-input
                v-model="problemForm.context"
                type="textarea"
                :rows="3"
                placeholder="描述真实问题所处的情境"
                @blur="saveProblem"
              />
            </el-form-item>
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="问题对象">
                  <el-input v-model="problemForm.object" @blur="saveProblem" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="真实受众">
                  <el-input v-model="problemForm.audience" @blur="saveProblem" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="约束条件">
              <el-input
                v-model="problemForm.constraints"
                type="textarea"
                :rows="2"
                @blur="saveProblem"
              />
            </el-form-item>
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="最终成果" required>
                  <el-input v-model="problemForm.deliverable" @blur="saveProblem" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="成果用途">
                  <el-input v-model="problemForm.usage" @blur="saveProblem" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-button
              type="primary"
              :loading="savingProblem"
              :disabled="!editable"
              @click="saveProblem"
            >
              保存真实问题
            </el-button>
          </el-form>
        </section>

        <!-- 2. 学科贡献 -->
        <section
          id="contributions"
          class="panel"
          :class="{ 'panel-active': activeAnchor === 'contributions' }"
        >
          <h3 class="panel-title">学科贡献</h3>
          <p class="panel-hint">只允许一个核心学科；至少一门支撑学科方可激活项目。每个学科贡献说明可原地编辑。</p>

          <table class="matrix-table" v-if="snapshot && snapshot.contributions.length > 0">
            <thead>
              <tr>
                <th style="width: 64px">角色</th>
                <th style="width: 110px">学科</th>
                <th>知识贡献</th>
                <th>思维方式</th>
                <th>探究方法</th>
                <th style="width: 64px">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="c in snapshot.contributions" :key="c.id">
                <td>
                  <el-tag size="small" :type="c.role === 'core' ? 'primary' : 'info'">
                    {{ c.role === 'core' ? '核心' : '支撑' }}
                  </el-tag>
                </td>
                <td>{{ subjectName(c.subjectId) }}</td>
                <td>
                  <el-input
                    v-model="c.knowledge"
                    size="small"
                    :disabled="!editable"
                    placeholder="知识贡献"
                    @change="(v: string) => patchContributionField(c, 'knowledge', v)"
                  />
                </td>
                <td>
                  <el-input
                    v-model="c.thinking"
                    size="small"
                    :disabled="!editable"
                    placeholder="思维方式"
                    @change="(v: string) => patchContributionField(c, 'thinking', v)"
                  />
                </td>
                <td>
                  <el-input
                    v-model="c.inquiry"
                    size="small"
                    :disabled="!editable"
                    placeholder="探究方法"
                    @change="(v: string) => patchContributionField(c, 'inquiry', v)"
                  />
                </td>
                <td>
                  <el-button
                    text
                    type="danger"
                    size="small"
                    :disabled="!editable"
                    @click="removeContribution(c)"
                  >
                    移除
                  </el-button>
                </td>
              </tr>
            </tbody>
          </table>
          <el-empty v-else description="尚未配置学科贡献" :image-size="60" />

          <div v-if="editable" class="add-form">
            <h4 class="add-form-title">添加学科贡献</h4>
            <el-form label-position="top" size="small">
              <el-row :gutter="12">
                <el-col :span="6">
                  <el-form-item label="学科">
                    <el-select v-model="newContribution.subjectId" placeholder="选择学科">
                      <el-option
                        v-for="s in availableSubjectsForNew"
                        :key="s.id"
                        :label="s.name"
                        :value="s.id"
                      />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :span="6">
                  <el-form-item label="角色">
                    <el-radio-group v-model="newContribution.role">
                      <el-radio value="core">核心</el-radio>
                      <el-radio value="support">支撑</el-radio>
                    </el-radio-group>
                  </el-form-item>
                </el-col>
                <el-col :span="6">
                  <el-form-item label="知识贡献">
                    <el-input v-model="newContribution.knowledge" />
                  </el-form-item>
                </el-col>
                <el-col :span="6">
                  <el-form-item label="思维方式">
                    <el-input v-model="newContribution.thinking" />
                  </el-form-item>
                </el-col>
              </el-row>
              <el-row :gutter="12">
                <el-col :span="18">
                  <el-form-item label="探究方法">
                    <el-input v-model="newContribution.inquiry" />
                  </el-form-item>
                </el-col>
                <el-col :span="6">
                  <el-form-item label=" ">
                    <el-button type="primary" @click="addContribution">添加</el-button>
                  </el-form-item>
                </el-col>
              </el-row>
            </el-form>
            <div v-if="coreContribution" class="hint-success">核心学科已设定：{{ subjectName(coreContribution.subjectId) }}</div>
            <div v-else class="hint-warn">尚未设定核心学科</div>
          </div>
        </section>

        <!-- 3. 学习目标 -->
        <section
          id="goals"
          class="panel"
          :class="{ 'panel-active': activeAnchor === 'goals' }"
        >
          <h3 class="panel-title">学习目标</h3>
          <p class="panel-hint">每个目标需拆解为可观察指标。目标名称与描述可原地编辑。</p>

          <el-empty v-if="!snapshot || snapshot.goals.length === 0" description="尚未添加学习目标" :image-size="60" />

          <div v-else class="flat-list">
            <div v-for="g in snapshot.goals" :key="g.id" class="flat-row">
              <el-tag size="small" type="info">{{ goalTypeLabel(g.goalType) }}</el-tag>
              <el-input
                v-model="g.name"
                size="small"
                :disabled="!editable"
                class="grow"
                @change="(v: string) => patchGoalField(g.id, 'name', v)"
              />
              <el-input
                v-model="g.description"
                size="small"
                :disabled="!editable"
                placeholder="描述"
                class="grow"
                @change="(v: string) => patchGoalField(g.id, 'description', v)"
              />
              <el-button
                text
                type="danger"
                size="small"
                :disabled="!editable"
                @click="removeGoal(g.id)"
              >
                删除
              </el-button>
            </div>
          </div>

          <div v-if="editable" class="add-form">
            <h4 class="add-form-title">添加学习目标</h4>
            <el-form label-position="top" size="small">
              <el-row :gutter="12">
                <el-col :span="6">
                  <el-form-item label="类型">
                    <el-select v-model="newGoal.goalType">
                      <el-option v-for="o in goalTypeOptions" :key="o.value" :label="o.label" :value="o.value" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :span="10">
                  <el-form-item label="名称" required>
                    <el-input v-model="newGoal.name" />
                  </el-form-item>
                </el-col>
                <el-col :span="8">
                  <el-form-item label="范围">
                    <el-input v-model="newGoal.scope" />
                  </el-form-item>
                </el-col>
              </el-row>
              <el-form-item label="描述">
                <el-input v-model="newGoal.description" type="textarea" :rows="2" />
              </el-form-item>
              <el-button type="primary" @click="addGoal">添加目标</el-button>
            </el-form>
          </div>
        </section>

        <!-- 4. 评价指标 -->
        <section
          id="indicators"
          class="panel"
          :class="{ 'panel-active': activeAnchor === 'indicators' }"
        >
          <h3 class="panel-title">评价指标</h3>
          <p class="panel-hint">每个指标绑定一个学习目标，可观察行为与等级规则可原地编辑。</p>

          <el-empty v-if="!snapshot || snapshot.indicators.length === 0" description="尚无可观察指标" :image-size="60" />

          <div v-else class="flat-list">
            <div v-for="i in snapshot.indicators" :key="i.id" class="flat-row">
              <span class="ref-label">目标：{{ goalName(i.goalId) }}</span>
              <el-input
                v-model="i.observableBehavior"
                size="small"
                :disabled="!editable"
                class="grow"
                @change="(v: string) => patchIndicatorField(i.id, 'observableBehavior', v)"
              />
              <el-input
                v-model="i.levelRule"
                size="small"
                :disabled="!editable"
                placeholder="等级规则"
                class="grow"
                @change="(v: string) => patchIndicatorField(i.id, 'levelRule', v)"
              />
              <el-button
                text
                type="danger"
                size="small"
                :disabled="!editable"
                @click="removeIndicator(i.id)"
              >
                删除
              </el-button>
            </div>
          </div>

          <!-- 按目标新增指标 -->
          <div v-if="editable && snapshot && snapshot.goals.length > 0" class="add-form">
            <h4 class="add-form-title">添加指标</h4>
            <div v-for="g in snapshot.goals" :key="g.id" class="indicator-add">
              <el-button text size="small" @click="ensureIndicatorDraft(g.id)">
                + 为「{{ g.name }}」添加指标
              </el-button>
              <div v-if="newIndicatorByGoal[g.id]" class="indicator-form">
                <el-input
                  v-model="newIndicatorByGoal[g.id].observableBehavior"
                  size="small"
                  placeholder="可观察行为"
                  style="width: 280px"
                />
                <el-input
                  v-model="newIndicatorByGoal[g.id].levelRule"
                  size="small"
                  placeholder="等级规则（选填）"
                  style="width: 220px"
                />
                <el-button size="small" type="primary" @click="addIndicator(g.id)">添加</el-button>
              </div>
            </div>
          </div>
        </section>

        <!-- 5. 证据计划 -->
        <section
          id="evidence_plans"
          class="panel"
          :class="{ 'panel-active': activeAnchor === 'evidence_plans' }"
        >
          <h3 class="panel-title">证据计划</h3>
          <p class="panel-hint">每个证据计划绑定一个指标；描述与是否必须可原地编辑。</p>

          <el-empty v-if="!snapshot || snapshot.evidencePlans.length === 0" description="尚无证据计划" :image-size="60" />

          <div v-else class="flat-list">
            <div v-for="p in snapshot.evidencePlans" :key="p.id" class="flat-row">
              <span class="ref-label">指标：{{ indicatorBehavior(p.indicatorId) }}</span>
              <el-tag size="small">{{ stageLabel(p.stage) }}</el-tag>
              <el-tag size="small" type="success">{{ evidenceTypeLabel(p.evidenceType) }}</el-tag>
              <el-tag size="small" type="warning">{{ collectorLabel(p.collector) }}</el-tag>
              <el-input
                v-model="p.description"
                size="small"
                :disabled="!editable"
                placeholder="描述"
                class="grow"
                @change="(v: string) => patchEvidenceField(p.id, 'description', v)"
              />
              <el-switch
                :model-value="p.required"
                :disabled="!editable"
                active-text="必须"
                @change="(v: boolean) => patchEvidenceRequired(p.id, v)"
              />
              <el-button
                text
                type="danger"
                size="small"
                :disabled="!editable"
                @click="removeEvidence(p.id)"
              >
                删除
              </el-button>
            </div>
          </div>

          <!-- 按指标新增证据计划 -->
          <div v-if="editable && snapshot && snapshot.indicators.length > 0" class="add-form">
            <h4 class="add-form-title">添加证据计划</h4>
            <div v-for="i in snapshot.indicators" :key="i.id" class="indicator-add">
              <el-button text size="small" @click="ensureEvidenceDraft(i.id)">
                + 为「{{ i.observableBehavior }}」添加证据
              </el-button>
              <div v-if="newEvidenceByIndicator[i.id]" class="evidence-form">
                <el-select v-model="newEvidenceByIndicator[i.id].stage" size="small" style="width: 90px">
                  <el-option v-for="o in stageOptions" :key="o.value" :label="o.label" :value="o.value" />
                </el-select>
                <el-select v-model="newEvidenceByIndicator[i.id].evidenceType" size="small" style="width: 100px">
                  <el-option v-for="o in evidenceTypeOptions" :key="o.value" :label="o.label" :value="o.value" />
                </el-select>
                <el-select v-model="newEvidenceByIndicator[i.id].collector" size="small" style="width: 90px">
                  <el-option v-for="o in collectorOptions" :key="o.value" :label="o.label" :value="o.value" />
                </el-select>
                <el-input
                  v-model="newEvidenceByIndicator[i.id].description"
                  size="small"
                  placeholder="描述"
                  style="width: 180px"
                />
                <el-button size="small" type="primary" @click="addEvidence(i.id)">添加</el-button>
              </div>
            </div>
          </div>
        </section>
      </div>

      <!-- 右侧栏：紧凑完整度 + 问题清单（不嵌套卡片） -->
      <aside class="design-sidebar">
        <div class="sidebar-block">
          <div class="sidebar-title">设计完整度</div>
          <div class="completion">
            <span class="completion-pct" :class="{ 'is-ready': completionSummary.percent >= 100 }">
              {{ completionSummary.percent }}%
            </span>
            <span class="completion-meta">
              阻断 {{ completionSummary.blockerCount }} · 建议 {{ completionSummary.warningCount }}
            </span>
          </div>
          <div class="completion-bar">
            <div class="completion-bar-fill" :style="{ width: completionSummary.percent + '%' }" />
          </div>
        </div>

        <div class="sidebar-block">
          <div class="sidebar-title">问题清单</div>
          <div v-if="!validation || (validation.blockers.length === 0 && validation.warnings.length === 0)" class="empty-inline">
            暂无问题
          </div>
          <ul v-else class="issue-list">
            <li
              v-for="b in validation?.blockers"
              :key="'b-' + b.code + b.field"
              class="issue-item is-blocker"
            >
              <span class="issue-tag">阻断</span>
              <span class="issue-msg">{{ b.message }}</span>
              <el-button
                v-if="b.fixRoute"
                link
                type="primary"
                size="small"
                @click="jumpToFixRoute(b.fixRoute)"
              >
                去修复
              </el-button>
            </li>
            <li
              v-for="(w, idx) in validation?.warnings"
              :key="'w-' + idx"
              class="issue-item is-warning"
            >
              <span class="issue-tag warn">建议</span>
              <span class="issue-msg">{{ w.message }}</span>
              <el-button
                v-if="w.fixRoute"
                link
                type="primary"
                size="small"
                @click="jumpToFixRoute(w.fixRoute)"
              >
                去完善
              </el-button>
            </li>
          </ul>
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.design {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.readonly-bar {
  padding: 8px 12px;
  background: #fdf6ec;
  color: #e6a23c;
  font-size: 13px;
  border-radius: 4px;
  border: 1px solid #faecd8;
}

.save-bar {
  display: flex;
  justify-content: flex-end;
  font-size: 12px;
  color: #909399;
  min-height: 18px;
}

.save-status.saving { color: #409eff; }
.save-status.saved { color: #67c23a; }
.save-status.error { color: #f56c6c; }

.design-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 280px;
  gap: 16px;
  align-items: start;
}

@media (max-width: 1100px) {
  .design-layout {
    grid-template-columns: 1fr;
  }
}

.design-main {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}

.panel {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 16px 20px;
  scroll-margin-top: 72px;
  transition: box-shadow 0.2s;
}

.panel-active {
  box-shadow: 0 0 0 2px #2463a7;
}

.panel-title {
  margin: 0 0 12px;
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.panel-hint {
  margin: -4px 0 12px;
  font-size: 12px;
  color: #909399;
}

.matrix-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  margin-bottom: 12px;
}

.matrix-table th,
.matrix-table td {
  border: 1px solid #ebeef5;
  padding: 8px 10px;
  text-align: left;
  vertical-align: middle;
}

.matrix-table th {
  background: #fafbfc;
  color: #606266;
  font-weight: 500;
}

.flat-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.flat-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  background: #fafbfc;
}

.flat-row .grow {
  flex: 1;
  min-width: 0;
}

.ref-label {
  font-size: 12px;
  color: #7b8794;
  white-space: nowrap;
}

.add-form {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px dashed #ebeef5;
}

.add-form-title {
  margin: 0 0 10px;
  font-size: 13px;
  font-weight: 600;
  color: #606266;
}

.hint-success {
  margin-top: 6px;
  font-size: 12px;
  color: #67c23a;
}

.hint-warn {
  margin-top: 6px;
  font-size: 12px;
  color: #e6a23c;
}

.indicator-add,
.evidence-add {
  margin-top: 6px;
}

.indicator-form,
.evidence-form {
  display: flex;
  gap: 6px;
  align-items: center;
  margin-top: 6px;
  flex-wrap: wrap;
}

.empty-inline {
  font-size: 12px;
  color: #c0c4cc;
  padding: 4px 0;
}

/* 右侧栏：紧凑完整度 + 问题清单，单层不嵌套卡片 */
.design-sidebar {
  position: sticky;
  top: 72px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.sidebar-block {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 12px 14px;
}

.sidebar-title {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 8px;
}

.completion {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.completion-pct {
  font-size: 20px;
  font-weight: 600;
  color: #b43a3a;
}

.completion-pct.is-ready {
  color: #2f7d4a;
}

.completion-meta {
  font-size: 12px;
  color: #7b8794;
}

.completion-bar {
  margin-top: 8px;
  height: 6px;
  background: #f0f2f5;
  border-radius: 3px;
  overflow: hidden;
}

.completion-bar-fill {
  height: 100%;
  background: #2463a7;
  transition: width 0.3s;
}

.issue-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.issue-item {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 12px;
  line-height: 1.5;
  padding: 6px 8px;
  border-radius: 4px;
}

.issue-item.is-blocker {
  background: #fef0f0;
  border: 1px solid #fde2e2;
}

.issue-item.is-warning {
  background: #fdf6ec;
  border: 1px solid #faecd8;
}

.issue-tag {
  flex-shrink: 0;
  font-size: 11px;
  color: #fff;
  background: #b43a3a;
  border-radius: 2px;
  padding: 1px 5px;
}

.issue-tag.warn {
  background: #a86412;
}

.issue-msg {
  flex: 1;
  color: #303133;
  word-break: break-word;
}
</style>
