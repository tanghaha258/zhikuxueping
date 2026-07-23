<script setup lang="ts">
/**
 * ProjectReviewView - 三栏复核工作台（计划 Task 4.6 / 验收标准 5/6）。
 *
 * 左栏：复核队列（低置信度/边界分/规则冲突/申诉），点击选中查看详情。
 * 中栏：选中提交的评价记录 + 分维度评分（AI 建议 vs 教师最终），
 *       教师可修改最终分数并填写人机差异原因，确认后提交转 finalized。
 * 右栏：关联量规维度与证据参考。
 *
 * 验收：教师修改 AI 分数必须记录差异原因；教师确认前不得发布。
 */
import { computed, inject, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { Ref } from 'vue'
import {
  confirmReviewApi,
  getReviewQueueApi,
  listScoresApi,
} from '@/features/evaluation-plan/api'
import type {
  EvaluationScore,
  ReviewQueueItem,
} from '@/features/evaluation-plan/types'
import { getPlanSnapshotApi } from '@/features/evaluation-plan/api'
import type { EvaluationPlanSnapshot } from '@/features/evaluation-plan/types'
import { listTasksApi } from '@/api/tasks'
import type { Task, Project } from '@/types'

const route = useRoute()
const projectId = computed(() => route.params.id as string)
const project = inject<Ref<Project | null>>('workspaceProject')

// ── 常量 ─────────────────────────────────────────────────────
const REVIEW_STATUS_LABELS: Record<string, string> = {
  draft: '草稿',
  submitted: '已提交',
  ai_reviewed: 'AI 已评',
  teacher_reviewed: '教师已评',
  returned: '已退回',
  resubmitted: '已重提',
  finalized: '已定稿',
}
const REASON_LABELS: Record<string, string> = {
  低置信度: '低置信度',
  边界分: '边界分',
  规则冲突: '规则冲突',
  学生申诉: '学生申诉',
}
const REASON_TAG_TYPES: Record<string, string> = {
  低置信度: 'warning',
  边界分: 'info',
  规则冲突: 'danger',
  学生申诉: 'danger',
}

// ── 数据 ─────────────────────────────────────────────────────
const queue = ref<ReviewQueueItem[]>([])
const tasks = ref<Task[]>([])
const snapshot = ref<EvaluationPlanSnapshot | null>(null)
const loading = ref(false)
const selectedItem = ref<ReviewQueueItem | null>(null)
const scores = ref<EvaluationScore[]>([])
const scoresLoading = ref(false)

// 教师输入的最终分数与差异原因
const scoreInputs = ref<Record<string, { finalScore: number | null; differenceReason: string; evidenceRef: string }>>({})
const totalScoreInput = ref<number | null>(null)
const commentInput = ref<string>('')
const confirming = ref(false)

async function loadAll() {
  loading.value = true
  try {
    const [queueRes, tasksRes, snapRes] = await Promise.all([
      getReviewQueueApi({ project_id: projectId.value }),
      listTasksApi({ project_id: projectId.value, limit: 500 }),
      getPlanSnapshotApi(projectId.value),
    ])
    queue.value = queueRes.data.data
    tasks.value = tasksRes.data.data.items
    snapshot.value = snapRes.data.data
  } catch {
    ElMessage.error('加载复核队列失败')
  } finally {
    loading.value = false
  }
}

function taskTitle(id: string): string {
  return tasks.value.find((t) => t.id === id)?.title || id.slice(0, 8)
}

// ── 选中队列项 ──────────────────────────────────────────────
async function selectItem(item: ReviewQueueItem) {
  selectedItem.value = item
  scores.value = []
  scoreInputs.value = {}
  totalScoreInput.value = item.totalScore ?? null
  commentInput.value = ''
  if (!item.recordId) return
  scoresLoading.value = true
  try {
    const res = await listScoresApi(item.recordId)
    scores.value = res.data.data
    // 初始化输入
    for (const s of scores.value) {
      scoreInputs.value[s.criterionId] = {
        finalScore: s.finalScore ?? null,
        differenceReason: s.differenceReason || '',
        evidenceRef: s.evidenceRef || '',
      }
    }
  } catch {
    ElMessage.error('加载评分失败')
  } finally {
    scoresLoading.value = false
  }
}

// ── 差异检测 ────────────────────────────────────────────────
function hasDifference(score: EvaluationScore): boolean {
  const input = scoreInputs.value[score.criterionId]
  if (!input || !score.suggestedScore || input.finalScore === null) return false
  return Math.abs(score.suggestedScore - input.finalScore) > 0.01
}

function needsReason(score: EvaluationScore): boolean {
  return hasDifference(score) && !scoreInputs.value[score.criterionId]?.differenceReason
}

// ── 量规维度查找 ────────────────────────────────────────────
const criteriaMap = computed(() => {
  const map: Record<string, { dimension: string; weight: number; levels: unknown[] }> = {}
  for (const c of snapshot.value?.criteria || []) {
    map[c.id] = { dimension: c.dimension, weight: c.weight, levels: c.levels || [] }
  }
  return map
})

function criterionName(id: string): string {
  return criteriaMap.value[id]?.dimension || id.slice(0, 8)
}

// ── 确认复核 ────────────────────────────────────────────────
const canConfirm = computed(() => {
  if (!selectedItem.value) return false
  // 所有有人机差异的维度必须填写差异原因
  for (const s of scores.value) {
    if (needsReason(s)) return false
  }
  return true
})

async function handleConfirm() {
  if (!selectedItem.value) return
  if (!canConfirm.value) {
    ElMessage.warning('存在人机差异未填写差异原因')
    return
  }
  confirming.value = true
  try {
    const scoresPayload = scores.value.map((s) => {
      const input = scoreInputs.value[s.criterionId]
      return {
        criterionId: s.criterionId,
        finalScore: input?.finalScore ?? null,
        evidenceRef: input?.evidenceRef || null,
        differenceReason: input?.differenceReason || null,
      }
    })
    await confirmReviewApi(selectedItem.value.submissionId, {
      scores: scoresPayload,
      totalScore: totalScoreInput.value,
      comment: commentInput.value || null,
    })
    ElMessage.success('已确认复核，提交已定稿')
    selectedItem.value = null
    await loadAll()
  } catch {
    // 错误由拦截器提示
  } finally {
    confirming.value = false
  }
}

onMounted(loadAll)
</script>

<template>
  <div class="review-workbench" v-loading="loading">
    <!-- 左栏：复核队列 -->
    <aside class="review-column review-queue-column">
      <div class="column-header">
        <h3 class="column-title">复核队列</h3>
        <el-badge :value="queue.length" :hidden="queue.length === 0" type="warning" />
      </div>
      <div class="column-body">
        <el-empty v-if="queue.length === 0" description="队列为空" :image-size="60" />
        <div
          v-for="item in queue"
          :key="item.submissionId"
          class="queue-item"
          :class="{ active: selectedItem?.submissionId === item.submissionId }"
          @click="selectItem(item)"
        >
          <div class="queue-item-top">
            <span class="queue-task">{{ taskTitle(item.taskId) }}</span>
            <el-tag size="small" :type="(REASON_TAG_TYPES[item.reasons[0]] as any) || 'info'">
              {{ REVIEW_STATUS_LABELS[item.reviewStatus] || item.reviewStatus }}
            </el-tag>
          </div>
          <div class="queue-item-reasons">
            <el-tag
              v-for="r in item.reasons"
              :key="r"
              size="small"
              :type="(REASON_TAG_TYPES[r] as any) || 'info'"
              effect="plain"
            >
              {{ REASON_LABELS[r] || r }}
            </el-tag>
          </div>
          <div class="queue-item-meta">
            <span v-if="item.totalScore !== null && item.totalScore !== undefined">
              总分：{{ item.totalScore }}
            </span>
            <span v-if="item.aiConfidence !== null && item.aiConfidence !== undefined">
              置信度：{{ (item.aiConfidence * 100).toFixed(0) }}%
            </span>
          </div>
        </div>
      </div>
    </aside>

    <!-- 中栏：评价详情与教师确认 -->
    <main class="review-column review-detail-column">
      <div class="column-header">
        <h3 class="column-title">评价详情</h3>
      </div>
      <div class="column-body">
        <el-empty v-if="!selectedItem" description="请从左侧选择待复核项" :image-size="80" />
        <div v-else v-loading="scoresLoading" class="detail-content">
          <!-- 提交信息 -->
          <div class="detail-section">
            <div class="detail-label">提交信息</div>
            <div class="detail-info">
              <span>任务：{{ taskTitle(selectedItem.taskId) }}</span>
              <span>状态：{{ REVIEW_STATUS_LABELS[selectedItem.reviewStatus] || selectedItem.reviewStatus }}</span>
            </div>
          </div>

          <!-- 分维度评分 -->
          <div v-if="scores.length > 0" class="detail-section">
            <div class="detail-label">分维度评分</div>
            <div class="scores-list">
              <div v-for="s in scores" :key="s.id" class="score-row">
                <div class="score-header">
                  <span class="score-dimension">{{ criterionName(s.criterionId) }}</span>
                  <span v-if="s.aiConfidence !== null && s.aiConfidence !== undefined"
                        class="score-confidence"
                        :class="{ 'low-confidence': (s.aiConfidence ?? 1) < 0.6 }">
                    置信度 {{ ((s.aiConfidence ?? 0) * 100).toFixed(0) }}%
                  </span>
                </div>
                <div class="score-scores">
                  <div class="score-pair">
                    <span class="score-label">AI 建议：</span>
                    <span class="score-value">{{ s.suggestedScore ?? '—' }}</span>
                  </div>
                  <div class="score-pair">
                    <span class="score-label">教师最终：</span>
                    <el-input-number
                      v-model="scoreInputs[s.criterionId].finalScore"
                      :min="0"
                      :max="100"
                      :step="1"
                      size="small"
                      style="width: 100px"
                    />
                  </div>
                </div>
                <!-- 人机差异原因 -->
                <div v-if="hasDifference(s)" class="difference-reason">
                  <el-input
                    v-model="scoreInputs[s.criterionId].differenceReason"
                    placeholder="请填写人机差异原因（必填）"
                    size="small"
                    :class="{ 'reason-required': needsReason(s) }"
                  />
                </div>
                <div class="score-evidence">
                  <el-input
                    v-model="scoreInputs[s.criterionId].evidenceRef"
                    placeholder="证据引用（可选）"
                    size="small"
                  />
                </div>
              </div>
            </div>
          </div>
          <div v-else class="detail-section">
            <div class="detail-label">暂无分维度评分</div>
          </div>

          <!-- 总分与评语 -->
          <div class="detail-section">
            <div class="detail-label">总分与评语</div>
            <div class="total-input">
              <span class="score-label">总分：</span>
              <el-input-number
                v-model="totalScoreInput"
                :min="0"
                :max="100"
                :step="1"
                size="small"
              />
            </div>
            <el-input
              v-model="commentInput"
              type="textarea"
              :rows="3"
              placeholder="评语"
              size="small"
              style="margin-top: 8px"
            />
          </div>

          <!-- 确认按钮 -->
          <div class="confirm-actions">
            <el-button
              type="primary"
              :disabled="!canConfirm"
              :loading="confirming"
              @click="handleConfirm"
            >
              确认复核
            </el-button>
            <span v-if="!canConfirm" class="confirm-hint">
              存在人机差异未填写差异原因
            </span>
          </div>
        </div>
      </div>
    </main>

    <!-- 右栏：量规与证据参考 -->
    <aside class="review-column review-reference-column">
      <div class="column-header">
        <h3 class="column-title">参考</h3>
      </div>
      <div class="column-body">
        <div v-if="snapshot?.rubric" class="reference-section">
          <div class="reference-label">当前量规</div>
          <div class="reference-info">
            版本 v{{ snapshot.rubric.version }} ·
            {{ snapshot.rubric.status === 'published' ? '已发布' : snapshot.rubric.status }}
          </div>
        </div>
        <div v-if="snapshot && snapshot.criteria.length > 0" class="reference-section">
          <div class="reference-label">量规维度（{{ snapshot.criteria.length }}）</div>
          <div class="reference-criteria">
            <div v-for="c in snapshot.criteria" :key="c.id" class="reference-criterion">
              <div class="criterion-header">
                <span>{{ c.dimension }}</span>
                <span class="criterion-weight">{{ (c.weight * 100).toFixed(0) }}%</span>
              </div>
              <div v-if="c.levels && c.levels.length > 0" class="criterion-levels">
                <div v-for="(lv, i) in c.levels" :key="i" class="criterion-level">
                  {{ lv.level }}({{ lv.score }}): {{ lv.description }}
                </div>
              </div>
            </div>
          </div>
        </div>
        <div v-if="snapshot && snapshot.evidenceArtifacts.length > 0" class="reference-section">
          <div class="reference-label">证据（{{ snapshot.evidenceArtifacts.length }}）</div>
          <div class="reference-artifacts">
            <div
              v-for="a in snapshot.evidenceArtifacts"
              :key="a.id"
              class="reference-artifact"
            >
              <div class="artifact-source">{{ a.sourceType }}</div>
              <div class="artifact-content">{{ a.contentRef }}</div>
            </div>
          </div>
        </div>
        <el-empty
          v-if="!snapshot || (snapshot.criteria.length === 0 && snapshot.evidenceArtifacts.length === 0)"
          description="无参考数据"
          :image-size="60"
        />
      </div>
    </aside>
  </div>
</template>

<style scoped>
.review-workbench {
  display: grid;
  grid-template-columns: 280px 1fr 280px;
  gap: 16px;
  height: 100%;
  min-height: 600px;
}

.review-column {
  background: #fff;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.column-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid #f0f0f0;
}

.column-title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.column-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

/* ── 左栏队列 ──────────────────────────────────────────── */
.queue-item {
  padding: 10px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
  margin-bottom: 6px;
  border: 1px solid transparent;
}

.queue-item:hover {
  background: #f5f7fa;
}

.queue-item.active {
  background: #ecf5ff;
  border-color: #409eff;
}

.queue-item-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}

.queue-task {
  font-size: 13px;
  font-weight: 500;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.queue-item-reasons {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 4px;
}

.queue-item-meta {
  font-size: 12px;
  color: #909399;
  display: flex;
  gap: 10px;
}

/* ── 中栏详情 ──────────────────────────────────────────── */
.detail-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.detail-section {
  font-size: 13px;
}

.detail-label {
  font-weight: 600;
  color: #303133;
  margin-bottom: 8px;
  padding-bottom: 4px;
  border-bottom: 1px solid #f0f0f0;
}

.detail-info {
  display: flex;
  gap: 16px;
  color: #606266;
}

.scores-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.score-row {
  padding: 10px;
  background: #fafafa;
  border-radius: 6px;
}

.score-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.score-dimension {
  font-weight: 500;
  color: #303133;
}

.score-confidence {
  font-size: 12px;
  color: #909399;
}

.score-confidence.low-confidence {
  color: #e6a23c;
  font-weight: 600;
}

.score-scores {
  display: flex;
  gap: 20px;
  margin-bottom: 6px;
}

.score-pair {
  display: flex;
  align-items: center;
  gap: 4px;
}

.score-label {
  font-size: 12px;
  color: #606266;
}

.score-value {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
}

.difference-reason {
  margin-bottom: 6px;
}

.reason-required :deep(.el-input__wrapper) {
  box-shadow: 0 0 0 1px #f56c6c inset;
}

.score-evidence {
  margin-top: 4px;
}

.total-input {
  display: flex;
  align-items: center;
  gap: 8px;
}

.confirm-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-top: 8px;
  border-top: 1px solid #f0f0f0;
}

.confirm-hint {
  font-size: 12px;
  color: #e6a23c;
}

/* ── 右栏参考 ──────────────────────────────────────────── */
.reference-section {
  margin-bottom: 16px;
}

.reference-label {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 6px;
}

.reference-info {
  font-size: 12px;
  color: #606266;
}

.reference-criteria {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.reference-criterion {
  padding: 8px;
  background: #fafafa;
  border-radius: 4px;
}

.criterion-header {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  font-weight: 500;
  color: #303133;
  margin-bottom: 4px;
}

.criterion-weight {
  color: #909399;
}

.criterion-levels {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.criterion-level {
  font-size: 11px;
  color: #606266;
}

.reference-artifacts {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.reference-artifact {
  padding: 6px 8px;
  background: #fafafa;
  border-radius: 4px;
}

.artifact-source {
  font-size: 11px;
  color: #909399;
  margin-bottom: 2px;
}

.artifact-content {
  font-size: 12px;
  color: #606266;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
</style>
