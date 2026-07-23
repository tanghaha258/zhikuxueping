<script setup lang="ts">
/**
 * ProjectEvaluationPlanView - 评价计划页（计划 Task 4.6 / 验收标准 4）。
 *
 * 展示与编辑项目评价计划：
 * - 量规版本管理：新建版本、发布（含完整性校验）、归档。
 * - 量规维度 CRUD：发布后只读，需新建版本。
 * - 完整性校验：AI 默认权重为零、目标可观察、等级描述、缺失证据。
 * - 证据列表与新增。
 * - 设计上下文：目标、指标、证据计划。
 *
 * 项目进入 active 后量规只读，但评价记录管理仍可用。
 */
import { computed, inject, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { Ref } from 'vue'
import {
  addArtifactApi,
  addCriterionApi,
  archiveRubricApi,
  createRubricApi,
  deleteCriterionApi,
  getPlanSnapshotApi,
  publishRubricApi,
  updateCriterionApi,
} from '@/features/evaluation-plan/api'
import type {
  EvaluationPlanSnapshot,
  EvidenceArtifact,
  RubricCriterion,
  RubricLevel,
} from '@/features/evaluation-plan/types'
import { canEditDesign } from '@/features/project-workspace/composables/useProjectWorkspace'
import { useUserStore } from '@/stores/user'
import type { Project } from '@/types'

const route = useRoute()
const userStore = useUserStore()
const projectId = computed(() => route.params.id as string)
const project = inject<Ref<Project | null>>('workspaceProject')

const editable = computed(() =>
  canEditDesign(project?.value?.status || 'draft'),
)

const rubricEditable = computed(() => {
  const snap = snapshot.value
  return editable.value && snap?.rubric?.status === 'draft'
})

// ── 常量 ─────────────────────────────────────────────────────
const RUBRIC_STATUS_LABELS: Record<string, string> = {
  draft: '草稿',
  published: '已发布',
  archived: '已归档',
}
const RUBRIC_STATUS_TYPES: Record<string, string> = {
  draft: 'info',
  published: 'success',
  archived: 'info',
}
const SOURCE_TYPE_LABELS: Record<string, string> = {
  submission: '学生提交',
  observation: '教师观察',
  test: '测试',
  reflection: '反思',
  process_log: '过程记录',
}

// ── 数据 ─────────────────────────────────────────────────────
const snapshot = ref<EvaluationPlanSnapshot | null>(null)
const loading = ref(false)

async function loadSnapshot() {
  loading.value = true
  try {
    const res = await getPlanSnapshotApi(projectId.value)
    snapshot.value = res.data.data
  } catch {
    ElMessage.error('加载评价计划失败')
  } finally {
    loading.value = false
  }
}

const rubric = computed(() => snapshot.value?.rubric || null)
const criteria = computed(() => snapshot.value?.criteria || [])
const goals = computed(() => snapshot.value?.goals || [])
const indicators = computed(() => snapshot.value?.indicators || [])
const evidencePlans = computed(() => snapshot.value?.evidencePlans || [])
const artifacts = computed(() => snapshot.value?.evidenceArtifacts || [])
const validation = computed(() => snapshot.value?.validation || null)

// ── 新建量规版本 ────────────────────────────────────────────
async function handleCreateRubric() {
  if (!userStore.userInfo?.id) return
  try {
    await ElMessageBox.confirm(
      '新建量规版本将使当前版本变为非当前。继续？',
      '新建量规版本',
      { type: 'warning' },
    )
  } catch {
    return
  }
  try {
    await createRubricApi({
      projectId: projectId.value,
      createdBy: userStore.userInfo.id,
    })
    ElMessage.success('已新建量规版本')
    await loadSnapshot()
  } catch {
    // 错误由拦截器提示
  }
}

// ── 发布量规 ────────────────────────────────────────────────
async function handlePublishRubric() {
  if (!rubric.value) return
  try {
    const res = await publishRubricApi(rubric.value.id)
    const result = res.data.data
    if (result.blockers.length > 0) {
      ElMessage.warning(`发布被阻断：${result.blockers.join('；')}`)
    } else {
      ElMessage.success('量规已发布')
    }
    await loadSnapshot()
  } catch {
    // 错误由拦截器提示
  }
}

// ── 归档量规 ────────────────────────────────────────────────
async function handleArchiveRubric() {
  if (!rubric.value) return
  try {
    await ElMessageBox.confirm('归档后该量规不可用于新评价。继续？', '归档量规', {
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await archiveRubricApi(rubric.value.id)
    ElMessage.success('量规已归档')
    await loadSnapshot()
  } catch {
    // 错误由拦截器提示
  }
}

// ── 维度对话框 ──────────────────────────────────────────────
const criterionDialogVisible = ref(false)
const criterionDialogMode = ref<'create' | 'edit'>('create')
const criterionForm = ref({
  id: '',
  dimension: '',
  weight: 0.5,
  aiWeight: 0,
  indicatorId: '' as string,
  levels: [] as RubricLevel[],
})

function openCreateCriterion() {
  criterionDialogMode.value = 'create'
  criterionForm.value = {
    id: '', dimension: '', weight: 0.5, aiWeight: 0,
    indicatorId: '', levels: [],
  }
  criterionDialogVisible.value = true
}

function openEditCriterion(c: RubricCriterion) {
  criterionDialogMode.value = 'edit'
  criterionForm.value = {
    id: c.id,
    dimension: c.dimension,
    weight: c.weight,
    aiWeight: c.aiWeight,
    indicatorId: c.indicatorId || '',
    levels: [...(c.levels || [])],
  }
  criterionDialogVisible.value = true
}

function addLevel() {
  criterionForm.value.levels.push({ level: '', score: 0, description: '' })
}

function removeLevel(idx: number) {
  criterionForm.value.levels.splice(idx, 1)
}

async function submitCriterion() {
  if (!rubric.value) return
  if (!criterionForm.value.dimension.trim()) {
    ElMessage.warning('维度名称不能为空')
    return
  }
  const payload = {
    rubricId: rubric.value.id,
    indicatorId: criterionForm.value.indicatorId || null,
    dimension: criterionForm.value.dimension,
    weight: criterionForm.value.weight,
    aiWeight: criterionForm.value.aiWeight,
    levels: criterionForm.value.levels,
  }
  try {
    if (criterionDialogMode.value === 'create') {
      await addCriterionApi(payload)
      ElMessage.success('已添加维度')
    } else {
      await updateCriterionApi(criterionForm.value.id, {
        indicatorId: payload.indicatorId,
        dimension: payload.dimension,
        weight: payload.weight,
        aiWeight: payload.aiWeight,
        levels: payload.levels,
      })
      ElMessage.success('已更新维度')
    }
    criterionDialogVisible.value = false
    await loadSnapshot()
  } catch {
    // 错误由拦截器提示
  }
}

async function handleDeleteCriterion(c: RubricCriterion) {
  try {
    await ElMessageBox.confirm(`确认删除维度「${c.dimension}」？`, '删除维度', {
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await deleteCriterionApi(c.id)
    ElMessage.success('已删除维度')
    await loadSnapshot()
  } catch {
    // 错误由拦截器提示
  }
}

// ── 证据对话框 ──────────────────────────────────────────────
const artifactDialogVisible = ref(false)
const artifactForm = ref({
  indicatorId: '',
  sourceType: 'observation',
  contentRef: '',
  planId: '',
})

function openAddArtifact() {
  artifactForm.value = {
    indicatorId: '', sourceType: 'observation', contentRef: '', planId: '',
  }
  artifactDialogVisible.value = true
}

async function submitArtifact() {
  if (!userStore.userInfo?.id) return
  if (!artifactForm.value.indicatorId) {
    ElMessage.warning('请选择关联指标')
    return
  }
  if (!artifactForm.value.contentRef.trim()) {
    ElMessage.warning('内容引用不能为空')
    return
  }
  try {
    await addArtifactApi({
      projectId: projectId.value,
      indicatorId: artifactForm.value.indicatorId,
      sourceType: artifactForm.value.sourceType,
      contentRef: artifactForm.value.contentRef,
      collectedBy: userStore.userInfo.id,
      planId: artifactForm.value.planId || null,
    })
    ElMessage.success('已添加证据')
    artifactDialogVisible.value = false
    await loadSnapshot()
  } catch {
    // 错误由拦截器提示
  }
}

// ── 辅助 ─────────────────────────────────────────────────────
function indicatorName(id: string): string {
  const ind = indicators.value.find((i) => (i as Record<string, unknown>).id === id)
  return (ind as Record<string, unknown>)?.observableBehavior as string || id.slice(0, 8)
}

function goalName(id: string): string {
  const g = goals.value.find((g) => (g as Record<string, unknown>).id === id)
  return (g as Record<string, unknown>)?.name as string || id.slice(0, 8)
}

onMounted(loadSnapshot)
</script>

<template>
  <div class="evaluation-plan-view" v-loading="loading">
    <!-- 量规区 -->
    <section class="card-section">
      <div class="section-header">
        <h3 class="section-title">量规</h3>
        <div class="section-actions">
          <el-button
            v-if="rubricEditable"
            type="primary"
            size="small"
            @click="openCreateCriterion"
          >
            新增维度
          </el-button>
          <el-button
            v-if="editable && rubric?.status === 'draft'"
            type="success"
            size="small"
            @click="handlePublishRubric"
          >
            发布量规
          </el-button>
          <el-button
            v-if="rubric?.status === 'published'"
            size="small"
            @click="handleArchiveRubric"
          >
            归档
          </el-button>
          <el-button
            v-if="editable"
            size="small"
            @click="handleCreateRubric"
          >
            新建版本
          </el-button>
        </div>
      </div>

      <div v-if="rubric" class="rubric-info">
        <el-tag :type="(RUBRIC_STATUS_TYPES[rubric.status] as any) || 'info'" size="small">
          {{ RUBRIC_STATUS_LABELS[rubric.status] || rubric.status }}
        </el-tag>
        <span class="rubric-version">版本 v{{ rubric.version }}</span>
        <span v-if="rubric.isCurrent" class="rubric-current">当前版本</span>
      </div>
      <el-empty v-else description="尚无量规，请新建版本" :image-size="60" />
    </section>

    <!-- 完整性校验区 -->
    <section v-if="validation" class="card-section">
      <div class="section-header">
        <h3 class="section-title">完整性校验</h3>
        <el-tag :type="validation.ready ? 'success' : 'danger'" size="small">
          {{ validation.ready ? '可发布' : '存在阻断' }}
        </el-tag>
      </div>
      <div v-if="validation.blockers.length > 0" class="validation-block">
        <div class="validation-label validation-blockers">阻断问题</div>
        <ul class="validation-list">
          <li v-for="(b, i) in validation.blockers" :key="i">{{ b }}</li>
        </ul>
      </div>
      <div v-if="validation.warnings.length > 0" class="validation-block">
        <div class="validation-label validation-warnings">警告</div>
        <ul class="validation-list">
          <li v-for="(w, i) in validation.warnings" :key="i">{{ w }}</li>
        </ul>
      </div>
      <div v-if="validation.blockers.length === 0 && validation.warnings.length === 0"
           class="validation-ok">
        评价计划完整性检查通过
      </div>
    </section>

    <!-- 维度列表 -->
    <section v-if="criteria.length > 0" class="card-section">
      <div class="section-header">
        <h3 class="section-title">量规维度</h3>
      </div>
      <el-table :data="criteria" stripe size="small">
        <el-table-column prop="dimension" label="维度" min-width="120" />
        <el-table-column label="权重" width="80">
          <template #default="{ row }">
            {{ (row.weight * 100).toFixed(0) }}%
          </template>
        </el-table-column>
        <el-table-column label="AI 权重" width="90">
          <template #default="{ row }">
            <span :class="{ 'ai-weight-nonzero': row.aiWeight > 0 }">
              {{ (row.aiWeight * 100).toFixed(0) }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column label="关联指标" min-width="100">
          <template #default="{ row }">
            {{ row.indicatorId ? indicatorName(row.indicatorId) : '—' }}
          </template>
        </el-table-column>
        <el-table-column label="等级描述" min-width="200">
          <template #default="{ row }">
            <div v-if="row.levels && row.levels.length > 0" class="levels-list">
              <span v-for="(lv, i) in row.levels" :key="i" class="level-tag">
                {{ lv.level }}({{ lv.score }}): {{ lv.description }}
              </span>
            </div>
            <span v-else class="text-muted">无等级</span>
          </template>
        </el-table-column>
        <el-table-column v-if="rubricEditable" label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button text size="small" @click="openEditCriterion(row)">编辑</el-button>
            <el-button text size="small" type="danger" @click="handleDeleteCriterion(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <!-- 设计上下文 -->
    <section v-if="goals.length > 0 || indicators.length > 0" class="card-section">
      <div class="section-header">
        <h3 class="section-title">设计上下文</h3>
      </div>
      <div class="design-context">
        <div class="context-block">
          <div class="context-label">学习目标（{{ goals.length }}）</div>
          <div class="context-items">
            <el-tag v-for="g in goals" :key="(g as any).id" size="small" class="context-tag">
              {{ (g as any).name }}
            </el-tag>
          </div>
        </div>
        <div class="context-block">
          <div class="context-label">评价指标（{{ indicators.length }}）</div>
          <div class="context-items">
            <el-tag v-for="i in indicators" :key="(i as any).id" size="small" type="info" class="context-tag">
              {{ (i as any).observableBehavior }}
            </el-tag>
          </div>
        </div>
        <div class="context-block">
          <div class="context-label">证据计划（{{ evidencePlans.length }}）</div>
          <div class="context-items">
            <el-tag v-for="p in evidencePlans" :key="(p as any).id" size="small" type="warning" class="context-tag">
              {{ (p as any).description || (p as any).evidenceType }}
            </el-tag>
          </div>
        </div>
      </div>
    </section>

    <!-- 证据列表 -->
    <section class="card-section">
      <div class="section-header">
        <h3 class="section-title">正式学习证据（{{ artifacts.length }}）</h3>
        <el-button
          v-if="editable"
          type="primary"
          size="small"
          @click="openAddArtifact"
        >
          新增证据
        </el-button>
      </div>
      <el-empty v-if="artifacts.length === 0" description="暂无证据" :image-size="60" />
      <el-table v-else :data="artifacts" stripe size="small">
        <el-table-column label="来源" width="100">
          <template #default="{ row }">
            {{ SOURCE_TYPE_LABELS[row.sourceType] || row.sourceType }}
          </template>
        </el-table-column>
        <el-table-column label="关联指标" min-width="100">
          <template #default="{ row }">
            {{ indicatorName(row.indicatorId) }}
          </template>
        </el-table-column>
        <el-table-column prop="contentRef" label="内容引用" min-width="200" show-overflow-tooltip />
        <el-table-column prop="collectedBy" label="采集者" width="100" />
        <el-table-column label="采集时间" width="160">
          <template #default="{ row }">
            {{ row.collectedAt ? new Date(row.collectedAt).toLocaleString() : '—' }}
          </template>
        </el-table-column>
      </el-table>
    </section>

    <!-- 维度对话框 -->
    <el-dialog
      v-model="criterionDialogVisible"
      :title="criterionDialogMode === 'create' ? '新增维度' : '编辑维度'"
      width="640px"
    >
      <el-form :model="criterionForm" label-width="100px" size="default">
        <el-form-item label="维度名称">
          <el-input v-model="criterionForm.dimension" placeholder="如：论证逻辑" />
        </el-form-item>
        <el-form-item label="教师权重">
          <el-input-number v-model="criterionForm.weight" :min="0" :max="1" :step="0.1" />
          <span class="form-hint">所有维度权重之和应为 1</span>
        </el-form-item>
        <el-form-item label="AI 权重">
          <el-input-number v-model="criterionForm.aiWeight" :min="0" :max="1" :step="0.1" />
          <span class="form-hint">AI 默认权重为零</span>
        </el-form-item>
        <el-form-item label="关联指标">
          <el-select v-model="criterionForm.indicatorId" clearable placeholder="可选">
            <el-option
              v-for="i in indicators"
              :key="(i as any).id"
              :label="(i as any).observableBehavior"
              :value="(i as any).id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="等级描述">
          <div class="levels-editor">
            <div v-for="(lv, idx) in criterionForm.levels" :key="idx" class="level-row">
              <el-input v-model="lv.level" placeholder="等级名" style="width: 100px" />
              <el-input-number v-model="lv.score" :min="0" :max="100" :step="1" style="width: 120px" />
              <el-input v-model="lv.description" placeholder="可观察描述" style="flex: 1" />
              <el-button text type="danger" @click="removeLevel(idx)">删除</el-button>
            </div>
            <el-button size="small" @click="addLevel">添加等级</el-button>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="criterionDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitCriterion">确定</el-button>
      </template>
    </el-dialog>

    <!-- 证据对话框 -->
    <el-dialog v-model="artifactDialogVisible" title="新增证据" width="500px">
      <el-form :model="artifactForm" label-width="100px" size="default">
        <el-form-item label="关联指标">
          <el-select v-model="artifactForm.indicatorId" placeholder="选择指标">
            <el-option
              v-for="i in indicators"
              :key="(i as any).id"
              :label="(i as any).observableBehavior"
              :value="(i as any).id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="证据来源">
          <el-select v-model="artifactForm.sourceType">
            <el-option label="教师观察" value="observation" />
            <el-option label="学生提交" value="submission" />
            <el-option label="测试" value="test" />
            <el-option label="反思" value="reflection" />
            <el-option label="过程记录" value="process_log" />
          </el-select>
        </el-form-item>
        <el-form-item label="内容引用">
          <el-input
            v-model="artifactForm.contentRef"
            type="textarea"
            :rows="3"
            placeholder="URL/文本摘要/附件路径"
          />
        </el-form-item>
        <el-form-item label="证据计划">
          <el-select v-model="artifactForm.planId" clearable placeholder="可选">
            <el-option
              v-for="p in evidencePlans"
              :key="(p as any).id"
              :label="(p as any).description || (p as any).evidenceType"
              :value="(p as any).id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="artifactDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitArtifact">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.evaluation-plan-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.card-section {
  background: #fff;
  border-radius: 8px;
  padding: 16px 20px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.section-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.section-actions {
  display: flex;
  gap: 8px;
}

.rubric-info {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
  color: #606266;
}

.rubric-version {
  font-weight: 500;
}

.rubric-current {
  color: #67c23a;
  font-weight: 500;
}

.ai-weight-nonzero {
  color: #f56c6c;
  font-weight: 600;
}

.validation-block {
  margin-bottom: 10px;
}

.validation-label {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 4px;
}

.validation-blockers {
  color: #f56c6c;
}

.validation-warnings {
  color: #e6a23c;
}

.validation-list {
  margin: 0;
  padding-left: 20px;
  font-size: 13px;
  color: #606266;
  line-height: 1.8;
}

.validation-ok {
  color: #67c23a;
  font-size: 13px;
}

.levels-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.level-tag {
  font-size: 12px;
  color: #606266;
}

.text-muted {
  color: #c0c4cc;
  font-size: 12px;
}

.design-context {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.context-block {
  font-size: 13px;
}

.context-label {
  font-weight: 500;
  color: #606266;
  margin-bottom: 4px;
}

.context-items {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.context-tag {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.levels-editor {
  width: 100%;
}

.level-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.form-hint {
  margin-left: 8px;
  font-size: 12px;
  color: #909399;
}
</style>
