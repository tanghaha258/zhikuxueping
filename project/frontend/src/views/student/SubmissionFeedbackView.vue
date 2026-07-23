<script setup lang="ts">
/**
 * SubmissionFeedbackView - 学生反馈视图（Task 6 / 计划 3.7.4）。
 *
 * 展示与操作：
 * - 正式反馈：已发布的评价记录（teacher/peer/ai/self）与教师评语。
 * - 版本记录：订正版本时间线（attempt_number、状态、教师反馈、二次评价理由）。
 * - 订正入口：canResubmit（returned 状态）时弹出再提交表单，调用 /resubmit。
 * - 二次评价：canRequestReassess（finalized 状态）时弹出理由表单，调用 /reassess。
 *
 * 数据来自 GET /student/submissions/{id}/feedback，后端隐藏教师私有备注与未发布评价。
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Upload, Document, Delete } from '@element-plus/icons-vue'
import { getStudentFeedbackApi, requestReassessApi, resubmitApi } from '@/features/student-space/api'
import { uploadFileApi } from '@/api/submissions'
import {
  EVAL_SOURCE_LABELS,
  EVAL_SOURCE_TYPES,
  REVIEW_STATUS_LABELS,
  REVIEW_STATUS_TYPES,
} from '@/features/student-space/types'
import type { StudentFeedbackView as FeedbackData } from '@/features/student-space/types'
import {
  acquireIdempotencyKey,
  clearIdempotencyKey,
} from '@/features/student-space/draft'

const route = useRoute()
const router = useRouter()
const submissionId = computed(() => route.params.id as string)

const data = ref<FeedbackData | null>(null)
const loading = ref(false)
const operating = ref(false)

// ── 订正再提交对话框 ─────────────────────────────────────────
const resubmitDialogVisible = ref(false)
const resubmitContent = ref('')
const resubmitFiles = ref<{ url: string; name: string; size: number }[]>([])

// ── 二次评价对话框 ───────────────────────────────────────────
const reassessDialogVisible = ref(false)
const reassessReason = ref('')

const submission = computed(() => data.value?.submission || null)
const revisions = computed(() => data.value?.revisions || [])
const evaluations = computed(() => data.value?.evaluations || [])
const canResubmit = computed(() => data.value?.canResubmit ?? false)
const canRequestReassess = computed(() => data.value?.canRequestReassess ?? false)

const latestRevision = computed(() =>
  revisions.value.length > 0 ? revisions.value[revisions.value.length - 1] : null,
)

function statusLabel(status: string): string {
  return REVIEW_STATUS_LABELS[status as keyof typeof REVIEW_STATUS_LABELS] || status
}

function statusType(status: string): string {
  return REVIEW_STATUS_TYPES[status as keyof typeof REVIEW_STATUS_TYPES] || 'info'
}

function sourceLabel(source: string): string {
  return EVAL_SOURCE_LABELS[source] || source
}

function sourceType(source: string): string {
  return EVAL_SOURCE_TYPES[source] || 'info'
}

function formatTime(t?: string | null): string {
  return t ? new Date(t).toLocaleString() : '—'
}

// ============================================================
// 数据加载
// ============================================================
async function fetchData() {
  loading.value = true
  try {
    const res = await getStudentFeedbackApi(submissionId.value)
    data.value = res.data.data
  } catch {
    ElMessage.error('加载反馈失败')
  } finally {
    loading.value = false
  }
}

// ============================================================
// 订正再提交（returned → resubmitted）
// ============================================================
function openResubmit() {
  // 预填最近一次内容，便于在原基础上订正
  resubmitContent.value = submission.value?.content || latestRevision.value?.content || ''
  resubmitFiles.value = (submission.value?.fileUrls || latestRevision.value?.fileUrls || []).map(
    (url) => ({ url, name: extractFilename(url), size: 0 }),
  )
  resubmitDialogVisible.value = true
}

function extractFilename(url: string): string {
  try {
    const u = new URL(url, window.location.origin)
    const seg = u.pathname.split('/').filter(Boolean)
    return seg[seg.length - 1] || url
  } catch {
    return url
  }
}

async function handleResubmitUpload(file: File) {
  const isAllowed = /\.(docx|pdf|txt|jpg|jpeg|png)$/i.test(file.name)
  if (!isAllowed) {
    ElMessage.warning('仅支持 docx/pdf/txt/jpg/png 格式')
    return false
  }
  try {
    const res = await uploadFileApi(file)
    const d = res.data.data
    resubmitFiles.value.push({ url: d.url, name: d.filename, size: d.size })
    ElMessage.success(`已上传: ${d.filename}`)
  } catch {
    ElMessage.error('上传失败')
  }
  return false
}

function removeResubmitFile(file: { url: string }) {
  resubmitFiles.value = resubmitFiles.value.filter((f) => f.url !== file.url)
}

async function submitResubmit() {
  if (!resubmitContent.value.trim() && resubmitFiles.value.length === 0) {
    ElMessage.warning('请填写订正内容或上传文件')
    return
  }
  operating.value = true
  try {
    const idempotencyKey = acquireIdempotencyKey(`resubmit-${submissionId.value}`)
    const res = await resubmitApi(submissionId.value, {
      content: resubmitContent.value,
      file_urls: resubmitFiles.value.map((f) => f.url),
      idempotency_key: idempotencyKey,
    })
    const result = res.data.data
    clearIdempotencyKey(`resubmit-${submissionId.value}`)
    if (result.created) {
      ElMessage.success('订正已提交，等待教师复核')
    } else {
      ElMessage.info('该订正已处理，重复提交已忽略')
    }
    resubmitDialogVisible.value = false
    await fetchData()
  } catch {
    // 错误由拦截器提示
  } finally {
    operating.value = false
  }
}

// ============================================================
// 二次评价（finalized → reassess → resubmitted）
// ============================================================
function openReassess() {
  reassessReason.value = ''
  reassessDialogVisible.value = true
}

async function submitReassess() {
  if (!reassessReason.value.trim()) {
    ElMessage.warning('请填写二次评价理由')
    return
  }
  operating.value = true
  try {
    await requestReassessApi(submissionId.value, { reason: reassessReason.value.trim() })
    ElMessage.success('二次评价请求已提交，等待教师再次复核')
    reassessDialogVisible.value = false
    await fetchData()
  } catch {
    // 错误由拦截器提示
  } finally {
    operating.value = false
  }
}

onMounted(fetchData)
</script>

<template>
  <div class="page-container" v-loading="loading">
    <div style="margin-bottom: 16px;">
      <el-link :underline="false" @click="router.push('/student/tasks')">
        <el-icon><ArrowLeft /></el-icon> 返回任务列表
      </el-link>
    </div>

    <div v-if="submission" class="feedback-view">
      <!-- 提交状态与操作 -->
      <el-card shadow="never" class="page-section">
        <template #header>
          <div class="flex-between">
            <span class="card-title">提交状态</span>
            <el-tag :type="statusType(submission.reviewStatus) as any">
              {{ statusLabel(submission.reviewStatus) }}
            </el-tag>
          </div>
        </template>
        <div class="status-actions">
          <div class="status-meta">
            <span class="meta-label">提交时间</span>
            <span>{{ formatTime(submission.submittedAt) }}</span>
          </div>
          <div class="status-buttons">
            <el-button
              v-if="canResubmit"
              type="primary"
              :icon="Upload"
              @click="openResubmit"
            >
              订正再提交
            </el-button>
            <el-button
              v-if="canRequestReassess"
              type="warning"
              @click="openReassess"
            >
              申请二次评价
            </el-button>
          </div>
        </div>

        <!-- 教师退回反馈提示 -->
        <el-alert
          v-if="canResubmit && latestRevision?.teacherComment"
          type="warning"
          :closable="false"
          show-icon
          style="margin-top: 12px;"
        >
          <template #title>教师退回反馈</template>
          <div>{{ latestRevision.teacherComment }}</div>
        </el-alert>

        <el-alert
          v-if="canRequestReassess"
          type="info"
          :closable="false"
          show-icon
          style="margin-top: 12px;"
        >
          <template #title>该提交已最终确认</template>
          <div>如对评价结果有异议，可申请二次评价，教师将再次复核。</div>
        </el-alert>
      </el-card>

      <!-- 正式反馈：评价记录 -->
      <el-card shadow="never" class="page-section">
        <template #header>
          <span class="card-title">正式反馈（{{ evaluations.length }}）</span>
        </template>
        <div v-if="evaluations.length > 0" class="eval-list">
          <div v-for="ev in evaluations" :key="ev.id" class="eval-card">
            <div class="eval-header">
              <el-tag size="small" :type="sourceType(ev.source) as any">
                {{ sourceLabel(ev.source) }}
              </el-tag>
              <span v-if="ev.totalScore !== null && ev.totalScore !== undefined" class="eval-score">
                {{ ev.totalScore }} 分
              </span>
              <el-tag size="small" type="success">{{ ev.status }}</el-tag>
            </div>
            <p v-if="ev.comment" class="eval-comment">{{ ev.comment }}</p>
            <div class="eval-footer">
              <span v-if="ev.confirmedBy">确认人: {{ ev.confirmedBy }}</span>
              <span>发布: {{ formatTime(ev.publishedAt) }}</span>
            </div>
          </div>
        </div>
        <el-empty v-else description="暂无已发布的评价记录" :image-size="60" />
      </el-card>

      <!-- 版本记录 -->
      <el-card shadow="never" class="page-section">
        <template #header>
          <span class="card-title">版本记录（{{ revisions.length }}）</span>
        </template>
        <div v-if="revisions.length > 0" class="revision-timeline">
          <div
            v-for="rev in revisions"
            :key="rev.id"
            class="revision-item"
          >
            <div class="revision-dot" :class="statusType(rev.reviewStatus)" />
            <div class="revision-content">
              <div class="revision-header">
                <span class="revision-attempt">第 {{ rev.attemptNumber }} 次</span>
                <el-tag size="small" :type="statusType(rev.reviewStatus) as any">
                  {{ statusLabel(rev.reviewStatus) }}
                </el-tag>
              </div>
              <p v-if="rev.content" class="revision-text">{{ rev.content }}</p>
              <div v-if="rev.fileUrls && rev.fileUrls.length > 0" class="revision-files">
                <el-icon><Document /></el-icon>
                <span>{{ rev.fileUrls.length }} 个附件</span>
              </div>
              <el-alert
                v-if="rev.teacherComment"
                type="info"
                :closable="false"
                show-icon
                class="revision-comment"
              >
                <template #title>教师反馈</template>
                <div>{{ rev.teacherComment }}</div>
              </el-alert>
              <el-alert
                v-if="rev.reassessReason"
                type="warning"
                :closable="false"
                show-icon
                class="revision-comment"
              >
                <template #title>二次评价理由</template>
                <div>{{ rev.reassessReason }}</div>
              </el-alert>
              <div class="revision-time">
                <span>提交: {{ formatTime(rev.submittedAt) }}</span>
                <span v-if="rev.reviewedAt"> · 复核: {{ formatTime(rev.reviewedAt) }}</span>
              </div>
            </div>
          </div>
        </div>
        <el-empty v-else description="暂无版本记录" :image-size="60" />
      </el-card>
    </div>

    <!-- 订正再提交对话框 -->
    <el-dialog
      v-model="resubmitDialogVisible"
      title="订正再提交"
      width="640px"
      :close-on-click-modal="false"
    >
      <el-form label-position="top">
        <el-form-item label="订正内容">
          <el-input
            v-model="resubmitContent"
            type="textarea"
            :rows="8"
            placeholder="在原作答基础上订正..."
          />
        </el-form-item>
        <el-form-item label="附件">
          <el-upload
            :auto-upload="false"
            :show-file-list="false"
            :on-change="(f: any) => handleResubmitUpload(f.raw)"
            accept=".docx,.pdf,.txt,.jpg,.jpeg,.png"
          >
            <el-button :icon="Upload">选择文件</el-button>
          </el-upload>
          <div v-for="f in resubmitFiles" :key="f.url" class="uploaded-file">
            <el-icon><Document /></el-icon>
            <span class="file-name">{{ f.name }}</span>
            <el-button text type="danger" :icon="Delete" size="small" @click="removeResubmitFile(f)" />
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resubmitDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="operating" @click="submitResubmit">
          提交订正
        </el-button>
      </template>
    </el-dialog>

    <!-- 二次评价对话框 -->
    <el-dialog
      v-model="reassessDialogVisible"
      title="申请二次评价"
      width="500px"
      :close-on-click-modal="false"
    >
      <el-form label-position="top">
        <el-form-item label="二次评价理由">
          <el-input
            v-model="reassessReason"
            type="textarea"
            :rows="5"
            maxlength="1000"
            show-word-limit
            placeholder="说明希望教师再次复核的具体原因..."
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reassessDialogVisible = false">取消</el-button>
        <el-button type="warning" :loading="operating" @click="submitReassess">
          提交申请
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.feedback-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-section {
  border-radius: 8px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
}

.flex-between {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.status-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.status-meta {
  font-size: 14px;
  color: #606266;
}

.meta-label {
  color: #909399;
  margin-right: 8px;
}

.status-buttons {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.eval-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.eval-card {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 14px;
}

.eval-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.eval-score {
  font-size: 20px;
  font-weight: 700;
  color: #67c23a;
}

.eval-comment {
  font-size: 14px;
  color: #303133;
  line-height: 1.7;
  margin: 0 0 8px;
  white-space: pre-wrap;
}

.eval-footer {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #909399;
  flex-wrap: wrap;
}

.revision-timeline {
  position: relative;
  padding-left: 20px;
}

.revision-timeline::before {
  content: '';
  position: absolute;
  left: 5px;
  top: 6px;
  bottom: 6px;
  width: 2px;
  background: #ebeef5;
}

.revision-item {
  position: relative;
  padding-bottom: 20px;
}

.revision-item:last-child {
  padding-bottom: 0;
}

.revision-dot {
  position: absolute;
  left: -20px;
  top: 4px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #909399;
  border: 2px solid #fff;
  box-shadow: 0 0 0 1px #dcdfe6;
}

.revision-dot.success {
  background: #67c23a;
}

.revision-dot.danger {
  background: #f56c6c;
}

.revision-dot.warning {
  background: #e6a23c;
}

.revision-dot.primary {
  background: #409eff;
}

.revision-content {
  background: #fafbfc;
  border-radius: 6px;
  padding: 12px 14px;
}

.revision-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.revision-attempt {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.revision-text {
  font-size: 13px;
  color: #606266;
  line-height: 1.7;
  margin: 0 0 8px;
  white-space: pre-wrap;
  max-height: 120px;
  overflow-y: auto;
}

.revision-files {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #909399;
  margin-bottom: 8px;
}

.revision-comment {
  margin-bottom: 8px;
}

.revision-time {
  font-size: 12px;
  color: #909399;
}

.uploaded-file {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  margin-top: 8px;
  background: #f5f7fa;
  border-radius: 4px;
  font-size: 13px;
}

.file-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 移动端响应式 */
@media (max-width: 768px) {
  .status-actions {
    flex-direction: column;
    align-items: flex-start;
  }
  .status-buttons {
    width: 100%;
  }
}
</style>
