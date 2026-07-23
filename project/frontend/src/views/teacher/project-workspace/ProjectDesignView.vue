<script setup lang="ts">
/**
 * ProjectDesignView - 项目设计页（计划 3.5.2）。
 *
 * 包含：真实问题编辑器、学科贡献矩阵、学习目标-指标-证据链。
 * 自动保存真实问题（失焦 PATCH）；贡献与目标走显式新增/移除；
 * 保存状态机（saving/saved/error）展示在顶部；离开未保存时提示。
 * 项目进入 active/completed/archived 后只读（与后端 ensure_design_editable 一致）。
 */
import { computed, inject, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, onBeforeRouteLeave } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  addContributionApi,
  addEvidencePlanApi,
  addGoalApi,
  addIndicatorApi,
  getDesignSnapshotApi,
  patchProblemApi,
  removeContributionApi,
  removeEvidencePlanApi,
  removeGoalApi,
  removeIndicatorApi,
  upsertProblemApi,
} from '@/features/project-workspace/api'
import {
  canEditDesign,
  mapServerError,
} from '@/features/project-workspace/composables/useProjectWorkspace'
import type {
  EvidenceCollector,
  EvidencePlan,
  EvidenceType,
  GoalType,
  ProjectDesignSnapshot,
  ProjectProblem,
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
const loading = ref(false)
const savingProblem = ref(false)
const saveStatus = ref<'idle' | 'saving' | 'saved' | 'error'>('idle')
const lastSavedAt = ref<string | null>(null)

const editable = computed(() =>
  canEditDesign(project?.value?.status || 'draft'),
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
const problemLoaded = ref(false)

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
const supportContributions = computed(() =>
  snapshot.value?.contributions.filter((c) => c.role === 'support') || [],
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

function indicatorsByGoal(goalId: string) {
  return snapshot.value?.indicators.filter((i) => i.goalId === goalId) || []
}
function evidenceByIndicator(indicatorId: string) {
  return snapshot.value?.evidencePlans.filter((p) => p.indicatorId === indicatorId) || []
}

async function loadDesign() {
  loading.value = true
  try {
    const res = await getDesignSnapshotApi(projectId.value)
    snapshot.value = res.data.data
    syncProblemForm()
  } finally {
    loading.value = false
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
  problemLoaded.value = true
}

// ── 真实问题保存 ────────────────────────────────────────────────
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
  } catch (e) {
    saveStatus.value = 'error'
    const mapped = mapServerError(e)
    ElMessage.error(mapped.message)
  } finally {
    savingProblem.value = false
  }
}

// ── 贡献 CRUD ───────────────────────────────────────────────────
async function addContribution() {
  if (!editable.value) return
  if (!newContribution.value.subjectId) {
    ElMessage.warning('请选择学科')
    return
  }
  try {
    const res = await addContributionApi(projectId.value, { ...newContribution.value })
    snapshot.value?.contributions.push(res.data.data)
    newContribution.value = {
      subjectId: '',
      role: 'support',
      knowledge: '',
      thinking: '',
      inquiry: '',
    }
    ElMessage.success('已添加学科贡献')
  } catch (e) {
    const mapped = mapServerError(e)
    ElMessage.error(mapped.message)
  }
}

async function removeContribution(c: SubjectContribution) {
  if (!editable.value) return
  try {
    await ElMessageBox.confirm(
      `确定移除 ${subjectName(c.subjectId)} 的学科贡献？${c.removalImpact ? '影响：' + c.removalImpact : ''}`,
      '确认移除',
      { type: 'warning' },
    )
    await removeContributionApi(projectId.value, c.id)
    if (snapshot.value) {
      snapshot.value.contributions = snapshot.value.contributions.filter(
        (x) => x.id !== c.id,
      )
    }
    ElMessage.success('已移除')
  } catch (e) {
    if (e === 'cancel') return
    const mapped = mapServerError(e)
    ElMessage.error(mapped.message)
  }
}

// ── 目标 / 指标 / 证据 CRUD ─────────────────────────────────────
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
  } catch (e) {
    const mapped = mapServerError(e)
    ElMessage.error(mapped.message)
  }
}

async function removeGoal(goalId: string) {
  if (!editable.value) return
  try {
    await removeGoalApi(projectId.value, goalId)
    if (snapshot.value) {
      snapshot.value.goals = snapshot.value.goals.filter((g) => g.id !== goalId)
      const indicatorIds = snapshot.value.indicators
        .filter((i) => i.goalId === goalId)
        .map((i) => i.id)
      snapshot.value.indicators = snapshot.value.indicators.filter(
        (i) => i.goalId !== goalId,
      )
      snapshot.value.evidencePlans = snapshot.value.evidencePlans.filter(
        (p) => !indicatorIds.includes(p.indicatorId),
      )
    }
    ElMessage.success('已删除目标')
  } catch (e) {
    const mapped = mapServerError(e)
    ElMessage.error(mapped.message)
  }
}

function ensureIndicatorDraft(goalId: string) {
  if (!newIndicatorByGoal.value[goalId]) {
    newIndicatorByGoal.value[goalId] = { observableBehavior: '', levelRule: '' }
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
  } catch (e) {
    const mapped = mapServerError(e)
    ElMessage.error(mapped.message)
  }
}

async function removeIndicator(indicatorId: string) {
  if (!editable.value) return
  try {
    await removeIndicatorApi(projectId.value, indicatorId)
    if (snapshot.value) {
      snapshot.value.indicators = snapshot.value.indicators.filter(
        (i) => i.id !== indicatorId,
      )
      snapshot.value.evidencePlans = snapshot.value.evidencePlans.filter(
        (p) => p.indicatorId !== indicatorId,
      )
    }
    ElMessage.success('已删除指标')
  } catch (e) {
    const mapped = mapServerError(e)
    ElMessage.error(mapped.message)
  }
}

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
  } catch (e) {
    const mapped = mapServerError(e)
    ElMessage.error(mapped.message)
  }
}

async function removeEvidence(planId: string) {
  if (!editable.value) return
  try {
    await removeEvidencePlanApi(projectId.value, planId)
    if (snapshot.value) {
      snapshot.value.evidencePlans = snapshot.value.evidencePlans.filter(
        (p) => p.id !== planId,
      )
    }
    ElMessage.success('已删除证据计划')
  } catch (e) {
    const mapped = mapServerError(e)
    ElMessage.error(mapped.message)
  }
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

    <!-- 真实问题编辑器 -->
    <section class="panel">
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
            <el-form-item label="最终成果">
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

    <!-- 学科贡献矩阵 -->
    <section class="panel">
      <h3 class="panel-title">学科贡献矩阵</h3>
      <p class="panel-hint">只允许一个核心学科；至少一门支撑学科方可激活项目。</p>

      <table class="matrix-table" v-if="snapshot && snapshot.contributions.length > 0">
        <thead>
          <tr>
            <th style="width: 80px">角色</th>
            <th style="width: 120px">学科</th>
            <th>知识贡献</th>
            <th>思维方式</th>
            <th>探究方法</th>
            <th style="width: 80px">操作</th>
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
            <td>{{ c.knowledge || '—' }}</td>
            <td>{{ c.thinking || '—' }}</td>
            <td>{{ c.inquiry || '—' }}</td>
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

    <!-- 目标 - 指标 - 证据链 -->
    <section class="panel">
      <h3 class="panel-title">学习目标与证据链</h3>
      <p class="panel-hint">每个目标需拆解为可观察指标，每个指标需绑定证据计划。</p>

      <el-empty v-if="!snapshot || snapshot.goals.length === 0" description="尚未添加学习目标" :image-size="60" />

      <div v-else class="goal-list">
        <div v-for="g in snapshot.goals" :key="g.id" class="goal-card">
          <div class="goal-head">
            <el-tag size="small" type="info">{{ goalTypeLabel(g.goalType) }}</el-tag>
            <span class="goal-name">{{ g.name }}</span>
            <span class="goal-desc">{{ g.description || '' }}</span>
            <el-button
              text
              type="danger"
              size="small"
              :disabled="!editable"
              @click="removeGoal(g.id)"
            >
              删除目标
            </el-button>
          </div>

          <div class="indicator-list">
            <div v-for="i in indicatorsByGoal(g.id)" :key="i.id" class="indicator-item">
              <div class="indicator-head">
                <span class="indicator-behavior">{{ i.observableBehavior }}</span>
                <span v-if="i.levelRule" class="indicator-rule">{{ i.levelRule }}</span>
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
              <div class="evidence-list">
                <div
                  v-for="p in evidenceByIndicator(i.id)"
                  :key="p.id"
                  class="evidence-chip"
                >
                  <el-tag size="small">{{ stageLabel(p.stage) }}</el-tag>
                  <el-tag size="small" type="success">{{ evidenceTypeLabel(p.evidenceType) }}</el-tag>
                  <el-tag size="small" type="warning">{{ collectorLabel(p.collector) }}</el-tag>
                  <span v-if="p.description" class="evidence-desc">{{ p.description }}</span>
                  <el-button
                    text
                    type="danger"
                    size="small"
                    :disabled="!editable"
                    @click="removeEvidence(p.id)"
                  >
                    ×
                  </el-button>
                </div>
                <div class="evidence-add">
                  <el-button
                    text
                    size="small"
                    :disabled="!editable"
                    @click="ensureEvidenceDraft(i.id)"
                  >
                    + 证据计划
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
            </div>
            <div v-if="indicatorsByGoal(g.id).length === 0" class="empty-inline">尚无可观察指标</div>
          </div>

          <div class="indicator-add">
            <el-button
              text
              size="small"
              :disabled="!editable"
              @click="ensureIndicatorDraft(g.id)"
            >
              + 添加指标
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
  </div>
</template>

<style scoped>
.design {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 1080px;
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

.save-status.saving {
  color: #409eff;
}
.save-status.saved {
  color: #67c23a;
}
.save-status.error {
  color: #f56c6c;
}

.panel {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 16px 20px;
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
}

.matrix-table th {
  background: #fafbfc;
  color: #606266;
  font-weight: 500;
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

.goal-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.goal-card {
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 12px;
  background: #fafbfc;
}

.goal-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.goal-name {
  font-weight: 600;
  font-size: 14px;
  color: #303133;
}

.goal-desc {
  font-size: 12px;
  color: #909399;
  flex: 1;
}

.indicator-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.indicator-item {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 8px 10px;
}

.indicator-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.indicator-behavior {
  font-size: 13px;
  color: #303133;
  flex: 1;
}

.indicator-rule {
  font-size: 12px;
  color: #909399;
}

.evidence-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.evidence-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #606266;
}

.evidence-desc {
  color: #606266;
}

.evidence-add,
.indicator-add {
  margin-top: 4px;
}

.evidence-form,
.indicator-form {
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
</style>
