<script setup lang="ts">
/**
 * ProjectClosureView - 项目结项视图（计划 3.5.9 / Task 9）。
 *
 * 功能区块：
 *   1. 闭环完整性检查：展示 blockers（未发布反馈、未处理阻断问题），存在时禁用"完成"。
 *   2. 项目数据摘要：学生数、任务数、评价数、订正率、证据完整率、改进效果。
 *   3. 教师反思草案编辑器：textarea + 字数统计 + 自动保存防抖。
 *   4. 案例归档与脱敏预览：switch 切换脱敏视图，展示学生姓名→编号、联系方式隐藏。
 *   5. 操作按钮（按项目状态）：
 *      - active：完成项目（blockers 存在时禁用）
 *      - completed：归档
 *      - archived：重新开放（弹 reason 对话框）+ 所有编辑控件只读
 *
 * 验收：存在未发布反馈或未处理阻断问题时给出明确提示；归档后只读；
 *       重新开放必须授权并记录原因。
 *
 * 注意：本视图调用的结项接口为约定路径，后端增量实现；缺失项如实显示"未采集/—"，
 *       不以零值伪装已完成。
 */
import { computed, inject, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { Ref } from 'vue'
import http from '@/api'
import type { ApiResponse, Project } from '@/types'
import { formatDate } from '@/utils/format'

const route = useRoute()
const projectId = computed(() => route.params.id as string)
const project = inject<Ref<Project | null>>('workspaceProject')
const reloadProject = inject<() => Promise<void>>('workspaceReload')

// ── 项目状态 ──────────────────────────────────────────────────
const projectStatus = computed(() => project?.value?.status || 'draft')
const isActive = computed(() => projectStatus.value === 'active')
const isCompleted = computed(() => projectStatus.value === 'completed')
const isArchived = computed(() => projectStatus.value === 'archived')
// 归档后所有编辑控件只读
const isReadOnly = computed(() => isArchived.value)

// ── 1. 闭环完整性检查 ─────────────────────────────────────────
interface ClosureBlocker {
  code: string
  field?: string
  message: string
  severity?: 'blocker' | 'warning'
}
interface ClosureCheck {
  blockers: ClosureBlocker[]
  warnings?: ClosureBlocker[]
}

const closureCheck = ref<ClosureCheck | null>(null)
const checkLoading = ref(false)
const checkError = ref<string | null>(null)

const blockers = computed(() => closureCheck.value?.blockers ?? [])
const warnings = computed(() => closureCheck.value?.warnings ?? [])
const hasBlockers = computed(() => blockers.value.length > 0)

async function loadClosureCheck() {
  if (!projectId.value) return
  checkLoading.value = true
  checkError.value = null
  try {
    const res = await http.get<ApiResponse<ClosureCheck>>(
      `/projects/${projectId.value}/closure-check`,
    )
    closureCheck.value = res.data.data
  } catch (e) {
    checkError.value = (e as Error).message || '闭环检查加载失败'
    closureCheck.value = null
  } finally {
    checkLoading.value = false
  }
}

// ── 2. 项目数据摘要 ───────────────────────────────────────────
interface ClosureSummary {
  studentCount?: number
  taskCount?: number
  evaluationCount?: number
  correctionRate?: number | null // 0-1
  evidenceCompletenessRate?: number | null // 0-1
  improvementEffect?: string | null
}

const summary = ref<ClosureSummary | null>(null)
const summaryLoading = ref(false)
const summaryError = ref<string | null>(null)

function fmtRate(rate: number | null | undefined): string {
  if (rate === null || rate === undefined) return '—'
  // 兼容 0-1 与 0-100 两种返回
  const pct = rate > 1 ? rate : rate * 100
  return `${Math.round(pct)}%`
}

function fmtCount(n: number | undefined): string {
  if (n === undefined || n === null) return '—'
  return String(n)
}

async function loadSummary() {
  if (!projectId.value) return
  summaryLoading.value = true
  summaryError.value = null
  try {
    const res = await http.get<ApiResponse<ClosureSummary>>(
      `/projects/${projectId.value}/closure-summary`,
    )
    summary.value = res.data.data
  } catch (e) {
    summaryError.value = (e as Error).message || '数据摘要加载失败'
    summary.value = null
  } finally {
    summaryLoading.value = false
  }
}

// ── 3. 教师反思草案 ───────────────────────────────────────────
const REFLECTION_MIN = 200
const REFLECTION_MAX = 1000

const reflectionText = ref('')
const reflectionConfirmed = ref(false) // 人工确认标记
const reflectionSaving = ref(false)
const reflectionSavedAt = ref<string | null>(null)
const reflectionError = ref<string | null>(null)
let saveTimer: ReturnType<typeof setTimeout> | null = null

const reflectionLen = computed(() => reflectionText.value.length)
const reflectionLenTip = computed(() => {
  if (reflectionLen.value < REFLECTION_MIN) {
    return `建议不少于 ${REFLECTION_MIN} 字（当前 ${reflectionLen.value} 字）`
  }
  if (reflectionLen.value > REFLECTION_MAX) {
    return `建议不超过 ${REFLECTION_MAX} 字（当前 ${reflectionLen.value} 字）`
  }
  return `${reflectionLen.value} 字`
})
const reflectionOutOfRange = computed(
  () =>
    reflectionLen.value > 0 &&
    (reflectionLen.value < REFLECTION_MIN || reflectionLen.value > REFLECTION_MAX),
)

async function saveReflection(text: string) {
  if (!projectId.value || isReadOnly.value) return
  reflectionSaving.value = true
  reflectionError.value = null
  try {
    await http.put<ApiResponse<{ savedAt: string }>>(
      `/projects/${projectId.value}/teacher-reflection`,
      {
        reflection: text,
        confirmed: reflectionConfirmed.value,
      },
    )
    reflectionSavedAt.value = new Date().toISOString()
  } catch (e) {
    reflectionError.value = (e as Error).message || '反思保存失败'
  } finally {
    reflectionSaving.value = false
  }
}

// 自动保存防抖
watch(reflectionText, () => {
  if (isReadOnly.value) return
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(() => {
    saveReflection(reflectionText.value)
  }, 1500)
})

function manualSaveReflection() {
  if (saveTimer) clearTimeout(saveTimer)
  saveReflection(reflectionText.value)
}

async function toggleConfirm() {
  if (isReadOnly.value) return
  reflectionConfirmed.value = !reflectionConfirmed.value
  // 切换确认状态立即保存
  if (saveTimer) clearTimeout(saveTimer)
  await saveReflection(reflectionText.value)
}

// ── 4. 案例归档与脱敏预览 ─────────────────────────────────────
interface AnonymizedStudent {
  original: string
  anonymized: string // 编号，如 S01
}
interface AnonymizedContact {
  field: string
  original: string
  anonymized: string // 通常为 *** 隐藏
}
interface CaseAttachment {
  name: string
  url?: string
  size?: number
}
interface CaseAnonymization {
  title?: string
  description?: string
  students?: AnonymizedStudent[]
  contacts?: AnonymizedContact[]
  attachments?: CaseAttachment[]
  caseNarrative?: string
}

const anonymizePreview = ref(false)
const anonymizedCase = ref<CaseAnonymization | null>(null)
const caseLoading = ref(false)
const caseError = ref<string | null>(null)
const caseLoaded = ref(false)

async function loadCaseAnonymization() {
  if (!projectId.value) return
  caseLoading.value = true
  caseError.value = null
  try {
    const res = await http.get<ApiResponse<CaseAnonymization>>(
      `/projects/${projectId.value}/case-anonymization`,
    )
    anonymizedCase.value = res.data.data
    caseLoaded.value = true
  } catch (e) {
    caseError.value = (e as Error).message || '脱敏预览加载失败'
    anonymizedCase.value = null
  } finally {
    caseLoading.value = false
  }
}

async function handleAnonymizeSwitch(val: boolean | string | number) {
  if (val === true && !caseLoaded.value) {
    await loadCaseAnonymization()
  }
}

// ── 5. 操作按钮：完成 / 归档 / 重新开放 ───────────────────────
const actionLoading = ref(false)

async function handleClose() {
  if (hasBlockers.value) {
    ElMessage.warning('存在阻断问题，无法完成项目')
    return
  }
  try {
    await ElMessageBox.confirm(
      '确认完成此项目？完成后将进入"已完成"状态，可继续归档。',
      '完成项目',
      { type: 'warning', confirmButtonText: '确认完成', cancelButtonText: '取消' },
    )
  } catch {
    return // 用户取消
  }
  actionLoading.value = true
  try {
    await http.post<ApiResponse<Project>>(`/projects/${projectId.value}/close`)
    ElMessage.success('项目已完成')
    await loadClosureCheck()
    if (reloadProject) await reloadProject()
  } catch {
    // 错误由拦截器提示
  } finally {
    actionLoading.value = false
  }
}

async function handleArchive() {
  try {
    await ElMessageBox.confirm(
      '确认归档此项目？归档后项目将变为只读，如需修改须重新开放并记录原因。',
      '归档项目',
      { type: 'warning', confirmButtonText: '确认归档', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  actionLoading.value = true
  try {
    await http.post<ApiResponse<Project>>(`/projects/${projectId.value}/archive`)
    ElMessage.success('项目已归档')
    if (reloadProject) await reloadProject()
  } catch {
    // 错误由拦截器提示
  } finally {
    actionLoading.value = false
  }
}

// 重新开放：必须授权并记录原因
const reopenDialogVisible = ref(false)
const reopenReason = ref('')
const reopenLoading = ref(false)

function openReopenDialog() {
  reopenReason.value = ''
  reopenDialogVisible.value = true
}

async function submitReopen() {
  const reason = reopenReason.value.trim()
  if (!reason) {
    ElMessage.warning('请填写重新开放原因（须授权并记录）')
    return
  }
  if (reason.length < 10) {
    ElMessage.warning('原因描述不少于 10 字')
    return
  }
  reopenLoading.value = true
  try {
    await http.post<ApiResponse<Project>>(
      `/projects/${projectId.value}/reopen`,
      { reason },
    )
    ElMessage.success('项目已重新开放')
    reopenDialogVisible.value = false
    if (reloadProject) await reloadProject()
  } catch {
    // 错误由拦截器提示
  } finally {
    reopenLoading.value = false
  }
}

// ── 初始化 ────────────────────────────────────────────────────
async function loadAll() {
  await Promise.all([loadClosureCheck(), loadSummary()])
}

onMounted(loadAll)
</script>

<template>
  <div class="closure-view">
    <!-- 顶部说明 -->
    <section class="panel toolbar">
      <div class="toolbar-info">
        <h3 class="panel-title">项目结项</h3>
        <p class="panel-hint">
          闭环完整性检查通过后方可完成；归档后只读；重新开放须授权并记录原因。
          案例导出前须脱敏预览（学生姓名→编号、联系方式隐藏）。
        </p>
      </div>
      <div class="toolbar-actions">
        <el-button
          v-if="isActive"
          size="default"
          :loading="actionLoading"
          :disabled="hasBlockers"
          @click="handleClose"
        >
          完成项目
        </el-button>
        <el-button
          v-else-if="isCompleted"
          size="default"
          :loading="actionLoading"
          @click="handleArchive"
        >
          归档
        </el-button>
        <el-button
          v-else-if="isArchived"
          size="default"
          :loading="actionLoading"
          @click="openReopenDialog"
        >
          重新开放
        </el-button>
      </div>
    </section>

    <!-- 1. 闭环完整性检查 -->
    <section class="panel" v-loading="checkLoading">
      <div class="panel-head">
        <h3 class="panel-title">闭环完整性检查</h3>
        <el-tag v-if="!checkLoading && !checkError" size="small" :type="hasBlockers ? 'danger' : 'success'">
          {{ hasBlockers ? '未通过' : '已通过' }}
        </el-tag>
      </div>
      <div v-if="checkError" class="error-bar">
        加载失败：{{ checkError }}
        <el-button text size="small" @click="loadClosureCheck">重试</el-button>
      </div>
      <template v-else>
        <el-alert
          v-if="hasBlockers"
          type="error"
          :closable="false"
          show-icon
          title="存在阻断问题，无法完成项目"
          description="请先处理以下阻断项（未发布反馈或未处理阻断问题），再执行「完成项目」。"
        />
        <el-alert
          v-else-if="!checkLoading"
          type="success"
          :closable="false"
          show-icon
          title="闭环完整性检查通过"
          description="所有反馈已发布、无未处理阻断问题，可执行「完成项目」。"
        />
        <ul v-if="blockers.length > 0" class="issue-list">
          <li v-for="b in blockers" :key="'b-' + b.code" class="issue-item blocker">
            <el-tag size="small" type="danger">阻断</el-tag>
            <span class="issue-field">{{ b.field || b.code }}</span>
            <span class="issue-msg">{{ b.message }}</span>
          </li>
        </ul>
        <ul v-if="warnings.length > 0" class="issue-list">
          <li v-for="w in warnings" :key="'w-' + w.code" class="issue-item warning">
            <el-tag size="small" type="warning">警告</el-tag>
            <span class="issue-field">{{ w.field || w.code }}</span>
            <span class="issue-msg">{{ w.message }}</span>
          </li>
        </ul>
      </template>
    </section>

    <!-- 2. 项目数据摘要 -->
    <section class="panel" v-loading="summaryLoading">
      <div class="panel-head">
        <h3 class="panel-title">项目数据摘要</h3>
      </div>
      <div v-if="summaryError" class="error-bar">
        加载失败：{{ summaryError }}
        <el-button text size="small" @click="loadSummary">重试</el-button>
      </div>
      <div v-else class="summary-grid">
        <div class="stat-card">
          <span class="stat-num">{{ fmtCount(summary?.studentCount) }}</span>
          <span class="stat-label">学生数</span>
        </div>
        <div class="stat-card">
          <span class="stat-num">{{ fmtCount(summary?.taskCount) }}</span>
          <span class="stat-label">任务数</span>
        </div>
        <div class="stat-card">
          <span class="stat-num">{{ fmtCount(summary?.evaluationCount) }}</span>
          <span class="stat-label">评价数</span>
        </div>
        <div class="stat-card">
          <span class="stat-num">{{ fmtRate(summary?.correctionRate) }}</span>
          <span class="stat-label">订正率</span>
        </div>
        <div class="stat-card">
          <span class="stat-num">{{ fmtRate(summary?.evidenceCompletenessRate) }}</span>
          <span class="stat-label">证据完整率</span>
        </div>
        <div class="stat-card stat-card-wide">
          <span class="stat-label">改进效果</span>
          <span class="stat-text">{{ summary?.improvementEffect || '—' }}</span>
        </div>
      </div>
    </section>

    <!-- 3. 教师反思草案 -->
    <section class="panel">
      <div class="panel-head">
        <h3 class="panel-title">教师反思草案</h3>
        <div class="panel-head-meta">
          <span v-if="reflectionSavedAt" class="saved-meta">
            已自动保存 · {{ formatDate(reflectionSavedAt, 'HH:mm:ss') }}
          </span>
          <el-button
            v-if="!isReadOnly"
            text
            size="small"
            :loading="reflectionSaving"
            @click="manualSaveReflection"
          >
            立即保存
          </el-button>
        </div>
      </div>
      <el-alert
        v-if="isReadOnly"
        type="info"
        :closable="false"
        show-icon
        title="项目已归档，反思内容只读"
        :description="''"
      />
      <el-input
        v-model="reflectionText"
        type="textarea"
        :rows="8"
        :disabled="isReadOnly"
        :placeholder="isReadOnly ? '（只读）' : '请撰写教师反思（建议 200-1000 字），涵盖目标达成、证据质量、改进方向等。修改后自动保存。'"
      />
      <div class="reflection-foot">
        <span class="len-tip" :class="{ out: reflectionOutOfRange }">
          {{ reflectionLenTip }}
        </span>
        <div class="confirm-area" v-if="!isReadOnly">
          <el-checkbox
            :model-value="reflectionConfirmed"
            @change="toggleConfirm"
          >
            已人工确认反思内容
          </el-checkbox>
        </div>
        <el-tag v-else size="small" :type="reflectionConfirmed ? 'success' : 'info'">
          {{ reflectionConfirmed ? '已人工确认' : '未确认' }}
        </el-tag>
      </div>
      <div v-if="reflectionError" class="error-bar">反思保存失败：{{ reflectionError }}</div>
    </section>

    <!-- 4. 案例归档与脱敏预览 -->
    <section class="panel">
      <div class="panel-head">
        <h3 class="panel-title">典型案例归档与脱敏预览</h3>
        <div class="anon-switch">
          <span class="anon-label">预览脱敏视图</span>
          <el-switch
            v-model="anonymizePreview"
            :disabled="isReadOnly && !anonymizePreview"
            @change="handleAnonymizeSwitch"
          />
        </div>
      </div>
      <p class="panel-hint">
        开启后将调用脱敏预览接口，展示学生姓名→编号、联系方式隐藏后的案例信息与附件。
      </p>
      <div v-if="!anonymizePreview" class="anon-placeholder">
        关闭脱敏预览。开启后将展示脱敏后的案例信息。
      </div>
      <div v-else v-loading="caseLoading" class="anon-body">
        <div v-if="caseError" class="error-bar">
          加载失败：{{ caseError }}
          <el-button text size="small" @click="loadCaseAnonymization">重试</el-button>
        </div>
        <template v-else-if="anonymizedCase">
          <div class="kv"><span class="k">案例标题</span><span class="v">{{ anonymizedCase.title || '—' }}</span></div>
          <div class="kv"><span class="k">案例描述</span><span class="v">{{ anonymizedCase.description || '—' }}</span></div>

          <div class="anon-subhead">学生姓名脱敏</div>
          <el-empty
            v-if="!anonymizedCase.students || anonymizedCase.students.length === 0"
            description="无学生信息"
            :image-size="50"
          />
          <table v-else class="anon-table">
            <thead>
              <tr><th>原姓名</th><th>脱敏编号</th></tr>
            </thead>
            <tbody>
              <tr v-for="(s, i) in anonymizedCase.students" :key="i">
                <td>{{ s.original }}</td><td>{{ s.anonymized }}</td>
              </tr>
            </tbody>
          </table>

          <div class="anon-subhead">联系方式脱敏</div>
          <el-empty
            v-if="!anonymizedCase.contacts || anonymizedCase.contacts.length === 0"
            description="无联系方式"
            :image-size="50"
          />
          <table v-else class="anon-table">
            <thead>
              <tr><th>字段</th><th>原值</th><th>脱敏后</th></tr>
            </thead>
            <tbody>
              <tr v-for="(c, i) in anonymizedCase.contacts" :key="i">
                <td>{{ c.field }}</td><td>{{ c.original }}</td><td>{{ c.anonymized }}</td>
              </tr>
            </tbody>
          </table>

          <div class="anon-subhead">附件</div>
          <el-empty
            v-if="!anonymizedCase.attachments || anonymizedCase.attachments.length === 0"
            description="无附件"
            :image-size="50"
          />
          <ul v-else class="attach-list">
            <li v-for="(a, i) in anonymizedCase.attachments" :key="i" class="attach-item">
              <span class="attach-name">{{ a.name }}</span>
              <span v-if="a.size" class="attach-size">{{ a.size }}</span>
              <el-link v-if="a.url" :href="a.url" type="primary" :underline="false" target="_blank">
                下载
              </el-link>
            </li>
          </ul>

          <div v-if="anonymizedCase.caseNarrative" class="anon-narrative">
            <div class="anon-subhead">案例叙述（脱敏后）</div>
            <pre class="narrative-text">{{ anonymizedCase.caseNarrative }}</pre>
          </div>
        </template>
      </div>
    </section>

    <p v-if="project?.createdAt" class="footer-meta">
      项目创建于 {{ formatDate(project.createdAt, 'YYYY-MM-DD HH:mm') }}
    </p>

    <!-- 重新开放对话框：必须授权并记录原因 -->
    <el-dialog v-model="reopenDialogVisible" title="重新开放项目" width="520px">
      <el-alert
        type="warning"
        :closable="false"
        show-icon
        title="重新开放需授权并记录原因"
        description="归档项目重新开放将解除只读状态，操作原因将被记录以备审计。"
      />
      <el-form label-width="100px" style="margin-top: 16px">
        <el-form-item label="重新开放原因">
          <el-input
            v-model="reopenReason"
            type="textarea"
            :rows="4"
            placeholder="请说明重新开放原因（不少于 10 字），该原因将记录留痕"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reopenDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="reopenLoading"
          :disabled="reopenReason.trim().length < 10"
          @click="submitReopen"
        >
          确认重新开放
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.closure-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 1080px;
}

.panel {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 16px 20px;
}

.panel.toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.panel-head-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #909399;
}

.saved-meta {
  color: #909399;
}

.panel-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.panel-hint {
  margin: 4px 0 8px;
  font-size: 12px;
  color: #909399;
}

.error-bar {
  padding: 8px 12px;
  background: #fef0f0;
  color: #f56c6c;
  font-size: 13px;
  border-radius: 4px;
  margin-bottom: 8px;
}

/* 完整性检查清单 */
.issue-list {
  list-style: none;
  margin: 12px 0 0;
  padding: 0;
}

.issue-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  font-size: 13px;
}

.issue-field {
  color: #909399;
  font-family: monospace;
  min-width: 120px;
}

.issue-msg {
  color: #303133;
}

/* 数据摘要 */
.summary-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
}

.stat-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  background: #fafbfc;
  border: 1px solid #f0f2f5;
  border-radius: 6px;
  padding: 12px 14px;
}

.stat-card-wide {
  grid-column: span 5;
}

.stat-num {
  font-size: 22px;
  font-weight: 600;
  color: #303133;
}

.stat-label {
  font-size: 12px;
  color: #909399;
  margin-top: 2px;
}

.stat-text {
  font-size: 13px;
  color: #303133;
  margin-top: 4px;
  word-break: break-word;
}

/* 教师反思 */
.reflection-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
  font-size: 12px;
  color: #909399;
}

.len-tip {
  color: #909399;
}

.len-tip.out {
  color: #e6a23c;
}

.confirm-area {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 脱敏预览 */
.anon-switch {
  display: flex;
  align-items: center;
  gap: 8px;
}

.anon-label {
  font-size: 13px;
  color: #606266;
}

.anon-placeholder {
  padding: 20px;
  text-align: center;
  font-size: 13px;
  color: #c0c4cc;
  background: #fafbfc;
  border-radius: 4px;
}

.anon-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.kv {
  display: grid;
  grid-template-columns: 90px 1fr;
  gap: 8px;
  padding: 4px 0;
  font-size: 13px;
}

.kv .k {
  color: #909399;
}

.kv .v {
  color: #303133;
  word-break: break-word;
}

.anon-subhead {
  margin-top: 8px;
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}

.anon-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  margin-top: 4px;
}

.anon-table th,
.anon-table td {
  border: 1px solid #ebeef5;
  padding: 6px 10px;
  text-align: left;
}

.anon-table th {
  background: #fafbfc;
  color: #606266;
  font-weight: 500;
}

.attach-list {
  list-style: none;
  margin: 4px 0 0;
  padding: 0;
}

.attach-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 0;
  font-size: 13px;
}

.attach-name {
  color: #303133;
}

.attach-size {
  color: #909399;
  font-size: 12px;
}

.narrative-text {
  margin: 4px 0 0;
  font-size: 12px;
  color: #303133;
  background: #f7f8fa;
  padding: 8px;
  border-radius: 4px;
  white-space: pre-wrap;
  word-break: break-word;
}

.footer-meta {
  font-size: 12px;
  color: #c0c4cc;
  text-align: right;
}
</style>
