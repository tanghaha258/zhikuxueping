<script setup lang="ts">
/**
 * ProjectAiContentView - AI 内容治理视图（计划 Task 5 / 验收标准 3.5.6）。
 *
 * 左栏：AI 任务列表（按场景/状态过滤）。
 * 右栏：选中任务的详情：
 *   - 输入摘要（项目/学情/学科贡献/资源/任务/目标）+ 模型 + 提示版本 + 时长
 *   - 输出版本列表：版本号、内容预览、结构校验、采用状态、局部重生成
 *   - 质量审查：阻断/警告/建议三级，处理或不予处理
 *   - 教师审核、采用/部分采用/退回
 *
 * 验收要点：
 *   - AI 失败不丢输入（失败任务仍展示 inputSummary）
 *   - 阻断问题未处理不能标记正式版本（adopt 按钮禁用 + 提示）
 *   - 任何生成内容未经教师审核不能发布（未 reviewed 时 adopt 禁用）
 *   - 所有 AI 内容均有输入摘要、模型、提示版本、原始输出、校验结果、教师决定和最终版本
 */
import { computed, inject, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { Ref } from 'vue'
import {
  adoptAiJobApi,
  createAiJobApi,
  getAiJobApi,
  listAiJobsApi,
  regenerateAiJobApi,
  resolveQualityIssueApi,
  retryAiJobApi,
  reviewAiJobApi,
} from '@/features/ai-content/api'
import {
  ADOPTION_STATUS_LABELS,
  ADOPTION_STATUS_TYPES,
  ISSUE_STATUS_LABELS,
  ISSUE_STATUS_TYPES,
  JOB_STATUS_LABELS,
  JOB_STATUS_TYPES,
  OUTPUT_TYPE_OPTIONS,
  RULE_CODE_LABELS,
  SCHEMA_STATUS_LABELS,
  SCHEMA_STATUS_TYPES,
  SCENE_OPTIONS,
  SEVERITY_LABELS,
  SEVERITY_TYPES,
} from '@/features/ai-content/types'
import type {
  AiJob,
  AiJobDetail,
  AiJobScene,
  AiOutputVersion,
  QualityIssue,
} from '@/features/ai-content/types'
import type { Project } from '@/types'

const route = useRoute()
const projectId = computed(() => route.params.id as string)
const project = inject<Ref<Project | null>>('workspaceProject')

// ── 列表 ─────────────────────────────────────────────────────
const jobs = ref<AiJob[]>([])
const listLoading = ref(false)
const filterScene = ref<string>('')
const filterStatus = ref<string>('')

async function loadJobs() {
  listLoading.value = true
  try {
    const res = await listAiJobsApi({
      projectId: projectId.value,
      scene: filterScene.value || undefined,
      status: filterStatus.value || undefined,
    })
    jobs.value = res.data.data.items
    // 保留当前选中，否则选第一条
    if (selectedJobId.value) {
      const stillExists = jobs.value.some((j) => j.id === selectedJobId.value)
      if (!stillExists) selectedJobId.value = jobs.value[0]?.id || ''
    } else {
      selectedJobId.value = jobs.value[0]?.id || ''
    }
  } catch {
    ElMessage.error('加载 AI 任务列表失败')
  } finally {
    listLoading.value = false
  }
}

const selectedJobId = ref<string>('')
const detail = ref<AiJobDetail | null>(null)
const detailLoading = ref(false)

async function loadDetail(jobId: string) {
  if (!jobId) {
    detail.value = null
    return
  }
  detailLoading.value = true
  try {
    const res = await getAiJobApi(jobId)
    detail.value = res.data.data
  } catch {
    ElMessage.error('加载任务详情失败')
    detail.value = null
  } finally {
    detailLoading.value = false
  }
}

watch(selectedJobId, (v) => {
  if (v) loadDetail(v)
})

function selectJob(job: AiJob) {
  selectedJobId.value = job.id
}

// ── 新建任务对话框 ───────────────────────────────────────────
const createDialogVisible = ref(false)
const createForm = ref({
  scene: 'lesson_plan' as AiJobScene,
  outputType: '教案',
  taskId: '',
  submissionId: '',
})

function openCreateDialog() {
  createForm.value = {
    scene: 'lesson_plan',
    outputType: '教案',
    taskId: '',
    submissionId: '',
  }
  createDialogVisible.value = true
}

const creating = ref(false)

async function submitCreate() {
  if (!projectId.value) return
  creating.value = true
  try {
    const res = await createAiJobApi({
      projectId: projectId.value,
      scene: createForm.value.scene,
      outputType: createForm.value.outputType,
      taskId: createForm.value.taskId || null,
      submissionId: createForm.value.submissionId || null,
    })
    ElMessage.success('AI 任务已创建')
    createDialogVisible.value = false
    await loadJobs()
    selectedJobId.value = res.data.data.id
  } catch {
    // 错误由拦截器提示
  } finally {
    creating.value = false
  }
}

// ── 重试失败任务 ─────────────────────────────────────────────
async function handleRetry() {
  if (!detail.value) return
  try {
    await retryAiJobApi(detail.value.job.id)
    ElMessage.success('已重新执行')
    await loadDetail(detail.value.job.id)
    await loadJobs()
  } catch {
    // 错误由拦截器提示
  }
}

// ── 教师审核 ─────────────────────────────────────────────────
const reviewDialogVisible = ref(false)
const reviewNote = ref('')

function openReviewDialog() {
  reviewNote.value = ''
  reviewDialogVisible.value = true
}

async function submitReview() {
  if (!detail.value) return
  try {
    await reviewAiJobApi(detail.value.job.id, { note: reviewNote.value || undefined })
    ElMessage.success('已标记为已审核')
    reviewDialogVisible.value = false
    await loadDetail(detail.value.job.id)
    await loadJobs()
  } catch {
    // 错误由拦截器提示
  }
}

// ── 采用/退回 ────────────────────────────────────────────────
const adoptDialogVisible = ref(false)
const adoptForm = ref({
  versionId: '',
  adoptionStatus: 'adopted' as 'adopted' | 'partially_adopted' | 'rejected',
  note: '',
})

function openAdoptDialog(version: AiOutputVersion) {
  adoptForm.value = {
    versionId: version.id,
    adoptionStatus: 'adopted',
    note: '',
  }
  adoptDialogVisible.value = true
}

const canAdopt = computed(() => {
  if (!detail.value) return false
  // 未经教师审核不能发布
  if (detail.value.job.status !== 'reviewed') return false
  // 阻断问题未处理不能标记正式版本
  if (detail.value.openBlockers > 0) return false
  return true
})

async function submitAdopt() {
  if (!detail.value) return
  try {
    await adoptAiJobApi(detail.value.job.id, {
      versionId: adoptForm.value.versionId,
      adoptionStatus: adoptForm.value.adoptionStatus,
      note: adoptForm.value.note || undefined,
    })
    ElMessage.success('已记录采用决定')
    adoptDialogVisible.value = false
    await loadDetail(detail.value.job.id)
    await loadJobs()
  } catch {
    // 错误由拦截器提示
  }
}

// ── 局部重生成 ───────────────────────────────────────────────
const regenDialogVisible = ref(false)
const regenForm = ref({ note: '', baseVersionId: '' })

function openRegenDialog(version?: AiOutputVersion) {
  regenForm.value = {
    note: '',
    baseVersionId: version?.id || '',
  }
  regenDialogVisible.value = true
}

async function submitRegen() {
  if (!detail.value) return
  try {
    await regenerateAiJobApi(detail.value.job.id, {
      note: regenForm.value.note || undefined,
      baseVersionId: regenForm.value.baseVersionId || undefined,
    })
    ElMessage.success('已创建新版本')
    regenDialogVisible.value = false
    await loadDetail(detail.value.job.id)
    await loadJobs()
  } catch {
    // 错误由拦截器提示
  }
}

// ── 质量问题处理 ─────────────────────────────────────────────
const resolveDialogVisible = ref(false)
const resolveForm = ref({ issueId: '', resolution: '', status: 'resolved' as 'resolved' | 'wontfix' })

function openResolveDialog(issue: QualityIssue) {
  resolveForm.value = {
    issueId: issue.id,
    resolution: '',
    status: 'resolved',
  }
  resolveDialogVisible.value = true
}

async function submitResolve() {
  if (!resolveForm.value.resolution.trim()) {
    ElMessage.warning('请填写处理说明')
    return
  }
  try {
    await resolveQualityIssueApi(resolveForm.value.issueId, {
      resolution: resolveForm.value.resolution,
      status: resolveForm.value.status,
    })
    ElMessage.success('已处理质量问题')
    resolveDialogVisible.value = false
    if (detail.value) await loadDetail(detail.value.job.id)
    await loadJobs()
  } catch {
    // 错误由拦截器提示
  }
}

// ── 版本对比 ─────────────────────────────────────────────────
const compareIds = ref<string[]>([])
const compareDialogVisible = ref(false)

function toggleCompare(versionId: string) {
  const idx = compareIds.value.indexOf(versionId)
  if (idx >= 0) {
    compareIds.value.splice(idx, 1)
  } else if (compareIds.value.length < 2) {
    compareIds.value.push(versionId)
  } else {
    compareIds.value = [compareIds.value[1], versionId]
  }
}

function openCompare() {
  if (compareIds.value.length !== 2) {
    ElMessage.warning('请选择两个版本进行对比')
    return
  }
  compareDialogVisible.value = true
}

const compareVersions = computed(() => {
  if (!detail.value || compareIds.value.length !== 2) return []
  return compareIds.value
    .map((id) => detail.value!.versions.find((v) => v.id === id))
    .filter(Boolean) as AiOutputVersion[]
})

// ── 辅助 ─────────────────────────────────────────────────────
const currentJob = computed(() => detail.value?.job)
const versions = computed(() => detail.value?.versions || [])
const issues = computed(() => detail.value?.issues || [])
const openBlockers = computed(() => detail.value?.openBlockers ?? 0)

const inputSummaryPairs = computed<{ key: string; value: unknown }[]>(() => {
  const s = currentJob.value?.inputSummary
  if (!s || typeof s !== 'object') return []
  return Object.entries(s).map(([key, value]) => ({ key, value }))
})

function formatValue(v: unknown): string {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean') return String(v)
  try {
    return JSON.stringify(v, null, 2)
  } catch {
    return String(v)
  }
}

function fmtTime(s?: string | null): string {
  if (!s) return '—'
  try {
    return new Date(s).toLocaleString()
  } catch {
    return s
  }
}

const isFailed = computed(() => currentJob.value?.status === 'failed')
const isReviewed = computed(() => currentJob.value?.status === 'reviewed')

onMounted(loadJobs)
</script>

<template>
  <div class="ai-content-view">
    <!-- 顶部说明与新建 -->
    <section class="card-section toolbar">
      <div class="toolbar-info">
        <h3 class="section-title">AI 内容治理</h3>
        <p class="section-desc">
          输入由项目结构化上下文自动聚合；任务失败不丢输入；阻断问题未处理不能标记正式版本；任何内容未经教师审核不能发布。
        </p>
      </div>
      <div class="toolbar-actions">
        <el-button type="primary" size="small" @click="openCreateDialog">
          发起 AI 任务
        </el-button>
      </div>
    </section>

    <div class="split-layout">
      <!-- 左栏：任务列表 -->
      <aside class="left-pane">
        <div class="filter-bar">
          <el-select
            v-model="filterScene"
            placeholder="场景"
            clearable
            size="small"
            style="width: 110px"
            @change="loadJobs"
          >
            <el-option
              v-for="o in SCENE_OPTIONS"
              :key="o.value"
              :label="o.label"
              :value="o.value"
            />
          </el-select>
          <el-select
            v-model="filterStatus"
            placeholder="状态"
            clearable
            size="small"
            style="width: 110px"
            @change="loadJobs"
          >
            <el-option
              v-for="(label, key) in JOB_STATUS_LABELS"
              :key="key"
              :label="label"
              :value="key"
            />
          </el-select>
        </div>

        <div v-loading="listLoading" class="job-list">
          <el-empty
            v-if="jobs.length === 0 && !listLoading"
            description="暂无 AI 任务"
            :image-size="60"
          />
          <div
            v-for="j in jobs"
            :key="j.id"
            class="job-item"
            :class="{ active: j.id === selectedJobId }"
            @click="selectJob(j)"
          >
            <div class="job-item-head">
              <el-tag
                size="small"
                :type="(JOB_STATUS_TYPES[j.status] as any) || 'info'"
              >
                {{ JOB_STATUS_LABELS[j.status] || j.status }}
              </el-tag>
              <span class="job-output">{{ j.outputType }}</span>
            </div>
            <div class="job-item-meta">
              <span>{{ j.scene }}</span>
              <span v-if="j.providerModel">· {{ j.providerModel }}</span>
            </div>
            <div class="job-item-time">{{ fmtTime(j.createdAt) }}</div>
          </div>
        </div>
      </aside>

      <!-- 右栏：任务详情 -->
      <section class="right-pane" v-loading="detailLoading">
        <el-empty
          v-if="!detail && !detailLoading"
          description="请选择左侧任务查看详情"
          :image-size="80"
        />

        <template v-else-if="detail">
          <!-- 任务概要 + 输入摘要 -->
          <section class="card-section">
            <div class="section-header">
              <h3 class="section-title">任务概要</h3>
              <div class="section-actions">
                <el-button
                  v-if="isFailed"
                  size="small"
                  type="warning"
                  @click="handleRetry"
                >
                  重试
                </el-button>
                <el-button
                  v-if="!isReviewed && currentJob?.status === 'succeeded'"
                  size="small"
                  type="primary"
                  @click="openReviewDialog"
                >
                  标记已审核
                </el-button>
              </div>
            </div>
            <div class="summary-grid">
              <div class="summary-item">
                <span class="summary-label">场景</span>
                <span class="summary-value">{{ currentJob?.scene }}</span>
              </div>
              <div class="summary-item">
                <span class="summary-label">输出类型</span>
                <span class="summary-value">{{ currentJob?.outputType }}</span>
              </div>
              <div class="summary-item">
                <span class="summary-label">状态</span>
                <el-tag
                  size="small"
                  :type="(JOB_STATUS_TYPES[currentJob?.status || ''] as any) || 'info'"
                >
                  {{ JOB_STATUS_LABELS[currentJob?.status || ''] || currentJob?.status }}
                </el-tag>
              </div>
              <div class="summary-item">
                <span class="summary-label">模型</span>
                <span class="summary-value">{{ currentJob?.providerModel || '—' }}</span>
              </div>
              <div class="summary-item">
                <span class="summary-label">提示版本</span>
                <span class="summary-value">{{ currentJob?.promptVersion || '—' }}</span>
              </div>
              <div class="summary-item">
                <span class="summary-label">耗时(ms)</span>
                <span class="summary-value">{{ currentJob?.durationMs ?? '—' }}</span>
              </div>
              <div class="summary-item" v-if="currentJob?.errorCode">
                <span class="summary-label">错误码</span>
                <span class="summary-value error">{{ currentJob.errorCode }}</span>
              </div>
              <div class="summary-item" v-if="currentJob?.errorMessage">
                <span class="summary-label">错误信息</span>
                <span class="summary-value error">{{ currentJob.errorMessage }}</span>
              </div>
            </div>
          </section>

          <!-- 结构化输入预览 -->
          <section class="card-section">
            <div class="section-header">
              <h3 class="section-title">结构化输入预览</h3>
              <span class="section-hint">AI 失败不丢输入</span>
            </div>
            <el-empty
              v-if="inputSummaryPairs.length === 0"
              description="无输入摘要"
              :image-size="60"
            />
            <div v-else class="input-summary">
              <div v-for="p in inputSummaryPairs" :key="p.key" class="input-row">
                <div class="input-key">{{ p.key }}</div>
                <pre class="input-value">{{ formatValue(p.value) }}</pre>
              </div>
            </div>
          </section>

          <!-- 输出版本 -->
          <section class="card-section">
            <div class="section-header">
              <h3 class="section-title">输出版本（{{ versions.length }}）</h3>
              <div class="section-actions">
                <el-button
                  size="small"
                  :disabled="compareIds.length !== 2"
                  @click="openCompare"
                >
                  对比所选版本
                </el-button>
                <el-button
                  v-if="currentJob?.status === 'succeeded' || currentJob?.status === 'reviewed'"
                  size="small"
                  type="primary"
                  @click="openRegenDialog()"
                >
                  局部重生成
                </el-button>
              </div>
            </div>
            <el-empty
              v-if="versions.length === 0"
              description="暂无输出版本"
              :image-size="60"
            />
            <div v-else class="version-list">
              <div
                v-for="v in versions"
                :key="v.id"
                class="version-item"
                :class="{ selected: compareIds.includes(v.id) }"
              >
                <div class="version-head">
                  <el-checkbox
                    :model-value="compareIds.includes(v.id)"
                    @change="toggleCompare(v.id)"
                  />
                  <span class="version-no">v{{ v.version }}</span>
                  <el-tag
                    size="small"
                    :type="(SCHEMA_STATUS_TYPES[v.schemaStatus] as any) || 'info'"
                  >
                    {{ SCHEMA_STATUS_LABELS[v.schemaStatus] || v.schemaStatus }}
                  </el-tag>
                  <el-tag
                    size="small"
                    :type="(ADOPTION_STATUS_TYPES[v.adoptionStatus] as any) || 'info'"
                  >
                    {{ ADOPTION_STATUS_LABELS[v.adoptionStatus] || v.adoptionStatus }}
                  </el-tag>
                  <el-tag v-if="v.isFinal" size="small" type="success">正式版本</el-tag>
                  <span class="version-time">{{ fmtTime(v.createdAt) }}</span>
                  <div class="version-actions">
                    <el-button
                      text
                      size="small"
                      @click="openRegenDialog(v)"
                    >
                      基于此重生成
                    </el-button>
                    <el-button
                      text
                      size="small"
                      type="primary"
                      :disabled="!canAdopt"
                      @click="openAdoptDialog(v)"
                    >
                      采用/退回
                    </el-button>
                  </div>
                </div>
                <div v-if="v.schemaErrors && v.schemaErrors.length > 0" class="schema-errors">
                  <span class="error-label">结构错误：</span>
                  <code>{{ JSON.stringify(v.schemaErrors) }}</code>
                </div>
                <div v-if="v.teacherNote" class="teacher-note">
                  教师备注：{{ v.teacherNote }}
                </div>
                <pre class="version-content">{{ v.content || '（无内容）' }}</pre>
              </div>
            </div>
            <div v-if="!isReviewed && currentJob?.status === 'succeeded'" class="block-tip">
              未经教师审核的内容不能发布，请先标记已审核。
            </div>
            <div v-if="openBlockers > 0" class="block-tip danger">
              仍有 {{ openBlockers }} 个阻断问题未处理，不能标记正式版本。
            </div>
          </section>

          <!-- 质量审查 -->
          <section class="card-section">
            <div class="section-header">
              <h3 class="section-title">质量审查（{{ issues.length }}）</h3>
              <span class="section-hint">阻断 / 警告 / 建议 三级</span>
            </div>
            <el-empty
              v-if="issues.length === 0"
              description="无质量问题"
              :image-size="60"
            />
            <el-table v-else :data="issues" stripe size="small">
              <el-table-column label="级别" width="90">
                <template #default="{ row }">
                  <el-tag
                    size="small"
                    :type="(SEVERITY_TYPES[row.severity] as any) || 'info'"
                  >
                    {{ SEVERITY_LABELS[row.severity] || row.severity }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="规则" width="140">
                <template #default="{ row }">
                  {{ RULE_CODE_LABELS[row.ruleCode] || row.ruleCode }}
                </template>
              </el-table-column>
              <el-table-column prop="objectRef" label="对象" width="140" show-overflow-tooltip />
              <el-table-column prop="message" label="说明" min-width="220" show-overflow-tooltip />
              <el-table-column label="状态" width="100">
                <template #default="{ row }">
                  <el-tag
                    size="small"
                    :type="(ISSUE_STATUS_TYPES[row.status] as any) || 'info'"
                  >
                    {{ ISSUE_STATUS_LABELS[row.status] || row.status }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="处理" width="100" fixed="right">
                <template #default="{ row }">
                  <el-button
                    v-if="row.status === 'open'"
                    text
                    size="small"
                    type="primary"
                    @click="openResolveDialog(row)"
                  >
                    处理
                  </el-button>
                  <span v-else class="text-muted">{{ row.resolution || '—' }}</span>
                </template>
              </el-table-column>
            </el-table>
          </section>
        </template>
      </section>
    </div>

    <!-- 新建任务对话框 -->
    <el-dialog v-model="createDialogVisible" title="发起 AI 内容任务" width="520px">
      <el-form :model="createForm" label-width="100px" size="default">
        <el-form-item label="所属项目">
          <el-input :model-value="project?.title || projectId" disabled />
        </el-form-item>
        <el-form-item label="场景">
          <el-select v-model="createForm.scene">
            <el-option
              v-for="o in SCENE_OPTIONS"
              :key="o.value"
              :label="o.label"
              :value="o.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="输出类型">
          <el-select v-model="createForm.outputType">
            <el-option
              v-for="o in OUTPUT_TYPE_OPTIONS"
              :key="o.value"
              :label="o.label"
              :value="o.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-if="createForm.scene === 'grading'" label="任务 ID">
          <el-input v-model="createForm.taskId" placeholder="grading 场景关联任务" />
        </el-form-item>
        <el-form-item v-if="createForm.scene === 'grading'" label="提交 ID">
          <el-input v-model="createForm.submissionId" placeholder="grading 场景关联提交" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- 审核对话框 -->
    <el-dialog v-model="reviewDialogVisible" title="标记已审核" width="480px">
      <el-form label-width="80px">
        <el-form-item label="审核备注">
          <el-input v-model="reviewNote" type="textarea" :rows="3" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reviewDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitReview">确认</el-button>
      </template>
    </el-dialog>

    <!-- 采用/退回对话框 -->
    <el-dialog v-model="adoptDialogVisible" title="采用/退回输出版本" width="480px">
      <el-form :model="adoptForm" label-width="100px">
        <el-form-item label="采用状态">
          <el-radio-group v-model="adoptForm.adoptionStatus">
            <el-radio value="adopted">采用</el-radio>
            <el-radio value="partially_adopted">部分采用</el-radio>
            <el-radio value="rejected">退回</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="adoptForm.note" type="textarea" :rows="3" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="adoptDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitAdopt">确认</el-button>
      </template>
    </el-dialog>

    <!-- 重生成对话框 -->
    <el-dialog v-model="regenDialogVisible" title="局部重生成" width="480px">
      <el-form :model="regenForm" label-width="100px">
        <el-form-item label="基于版本">
          <el-input
            :model-value="regenForm.baseVersionId || '最新版本'"
            disabled
          />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="regenForm.note" type="textarea" :rows="3" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="regenDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitRegen">确认</el-button>
      </template>
    </el-dialog>

    <!-- 质量问题处理对话框 -->
    <el-dialog v-model="resolveDialogVisible" title="处理质量问题" width="480px">
      <el-form :model="resolveForm" label-width="100px">
        <el-form-item label="处理结果">
          <el-radio-group v-model="resolveForm.status">
            <el-radio value="resolved">已处理</el-radio>
            <el-radio value="wontfix">不予处理</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="处理说明">
          <el-input v-model="resolveForm.resolution" type="textarea" :rows="3" placeholder="必填" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resolveDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitResolve">确认</el-button>
      </template>
    </el-dialog>

    <!-- 版本对比对话框 -->
    <el-dialog v-model="compareDialogVisible" title="版本对比" width="900px">
      <div v-if="compareVersions.length === 2" class="compare-grid">
        <div v-for="v in compareVersions" :key="v.id" class="compare-col">
          <div class="compare-head">
            <span>v{{ v.version }}</span>
            <el-tag size="small" :type="(ADOPTION_STATUS_TYPES[v.adoptionStatus] as any) || 'info'">
              {{ ADOPTION_STATUS_LABELS[v.adoptionStatus] || v.adoptionStatus }}
            </el-tag>
          </div>
          <pre class="compare-content">{{ v.content || '（无内容）' }}</pre>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.ai-content-view {
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

.toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.section-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.section-desc {
  margin: 4px 0 0;
  font-size: 12px;
  color: #909399;
}

.toolbar-actions {
  flex-shrink: 0;
}

.split-layout {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 16px;
  min-height: 480px;
}

.left-pane {
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.filter-bar {
  display: flex;
  gap: 8px;
  padding: 12px;
  border-bottom: 1px solid #f0f2f5;
}

.job-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.job-item {
  padding: 10px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
}

.job-item:hover {
  background: #f5f7fa;
}

.job-item.active {
  background: #ecf5ff;
}

.job-item-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.job-output {
  font-size: 13px;
  font-weight: 500;
  color: #303133;
}

.job-item-meta {
  margin-top: 4px;
  font-size: 12px;
  color: #909399;
}

.job-item-time {
  margin-top: 2px;
  font-size: 11px;
  color: #c0c4cc;
}

.right-pane {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.section-actions {
  display: flex;
  gap: 8px;
}

.section-hint {
  font-size: 12px;
  color: #909399;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.summary-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.summary-label {
  font-size: 12px;
  color: #909399;
}

.summary-value {
  font-size: 13px;
  color: #303133;
  word-break: break-all;
}

.summary-value.error {
  color: #f56c6c;
}

.input-summary {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.input-row {
  display: grid;
  grid-template-columns: 140px 1fr;
  gap: 12px;
  align-items: flex-start;
}

.input-key {
  font-size: 13px;
  font-weight: 500;
  color: #606266;
}

.input-value {
  margin: 0;
  font-size: 12px;
  color: #303133;
  background: #f7f8fa;
  padding: 6px 8px;
  border-radius: 4px;
  max-height: 200px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

.version-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.version-item {
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 12px;
}

.version-item.selected {
  border-color: #409eff;
  background: #ecf5ff;
}

.version-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.version-no {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}

.version-time {
  margin-left: auto;
  font-size: 11px;
  color: #c0c4cc;
}

.version-actions {
  display: flex;
  gap: 4px;
}

.schema-errors {
  margin-top: 8px;
  font-size: 12px;
  color: #f56c6c;
}

.error-label {
  font-weight: 500;
}

.schema-errors code {
  font-size: 11px;
}

.teacher-note {
  margin-top: 8px;
  font-size: 12px;
  color: #606266;
}

.version-content {
  margin: 8px 0 0;
  font-size: 12px;
  color: #303133;
  background: #f7f8fa;
  padding: 8px;
  border-radius: 4px;
  max-height: 240px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

.block-tip {
  margin-top: 12px;
  padding: 8px 12px;
  background: #fdf6ec;
  color: #e6a23c;
  font-size: 12px;
  border-radius: 4px;
}

.block-tip.danger {
  background: #fef0f0;
  color: #f56c6c;
}

.text-muted {
  color: #c0c4cc;
  font-size: 12px;
}

.compare-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.compare-col {
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 8px;
}

.compare-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
  font-size: 13px;
  font-weight: 600;
}

.compare-content {
  margin: 0;
  font-size: 12px;
  color: #303133;
  background: #f7f8fa;
  padding: 8px;
  border-radius: 4px;
  max-height: 420px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
