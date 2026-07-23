<script setup lang="ts">
/**
 * TaskSubmitView - 学生任务提交页（Task 6 / 计划 3.7.3）。
 *
 * 能力：
 * - 客户端自动保存：按 task_id 持久化到 localStorage（防抖 1s），刷新/重开可恢复。
 * - 服务端草稿：输入失焦时调用 /student/drafts 保存（跨设备，best-effort）。
 * - 幂等提交键：每次提交尝试复用同一 UUID，重复点击/网络重试不生成重复版本。
 * - 草稿恢复：进入页面优先恢复 localStorage 草稿，其次服务端提交内容。
 * - 离开保护：有未保存改动时 beforeRouteLeave 弹窗确认。
 * - 状态机：仅 draft/returned 可提交；其余状态只读并引导至反馈视图。
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, onBeforeRouteLeave, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload, Document, Delete } from '@element-plus/icons-vue'
import { getTaskApi } from '@/api/tasks'
import { getMyTaskSubmissionApi, uploadFileApi } from '@/api/submissions'
import { idempotentSubmitApi, saveDraftApi } from '@/features/student-space/api'
import {
  REVIEW_STATUS_LABELS,
} from '@/features/student-space/types'
import type { SubmissionReviewStatus } from '@/features/student-space/types'
import { canSubmit as canSubmitFlow } from '@/features/student-space/flow'
import {
  acquireIdempotencyKey,
  clearDraft,
  clearIdempotencyKey,
  hasDraftContent,
  loadDraft,
  saveDraft,
} from '@/features/student-space/draft'
import type { Task, Submission } from '@/types'

const route = useRoute()
const router = useRouter()
const taskId = route.params.id as string

const taskDetail = ref<Task | null>(null)
const submission = ref<Submission | null>(null)
const loading = ref(true)
const submitting = ref(false)
const savingDraft = ref(false)

const submitContent = ref('')
const uploadFileList = ref<{ url: string; name: string; size: number }[]>([])
/** 是否有未持久化的改动（用于离开保护）。 */
const dirty = ref(false)
/** 最近一次自动保存时间，用于提示。 */
const lastSavedAt = ref<string | null>(null)
/** 自动保存定时器。 */
let autosaveTimer: ReturnType<typeof setTimeout> | null = null

// ── 当前提交的复核状态（兼容旧 status 字段） ───────────────────
const reviewStatus = computed<SubmissionReviewStatus | undefined>(() => {
  const s = submission.value?.status as string | undefined
  if (!s) return undefined
  // status 字段镜像 review_status.value；returned/finalized/resubmitted 为字面量
  return s as SubmissionReviewStatus
})

/** 是否可提交（draft / returned / 无提交）。 */
const submittable = computed(() => canSubmitFlow(reviewStatus.value))

const submitButtonText = computed(() => {
  if (submitting.value) return '提交中...'
  if (reviewStatus.value === 'returned') return '订正再提交'
  if (submission.value) return '更新提交'
  return '提交作业'
})

// ============================================================
// 数据加载与草稿恢复
// ============================================================
async function fetchData() {
  loading.value = true
  try {
    const taskRes = await getTaskApi(taskId)
    taskDetail.value = taskRes.data.data

    try {
      const subRes = await getMyTaskSubmissionApi(taskId)
      submission.value = subRes.data.data || null
    } catch {
      submission.value = null
    }

    // 草稿恢复：优先 localStorage（进行中的本地草稿），其次服务端内容
    const localDraft = loadDraft(taskId)
    if (hasDraftContent(localDraft)) {
      submitContent.value = localDraft!.content
      uploadFileList.value = (localDraft!.fileUrls || []).map((url) => ({
        url,
        name: extractFilename(url),
        size: 0,
      }))
      ElMessage.info('已恢复本地未保存的草稿')
    } else if (submission.value) {
      submitContent.value = submission.value.content || ''
      uploadFileList.value = (submission.value.fileUrls || []).map((url) => ({
        url,
        name: extractFilename(url),
        size: 0,
      }))
    }
    dirty.value = false
  } finally {
    loading.value = false
  }
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

// ============================================================
// 客户端自动保存（localStorage，防抖 1s）
// ============================================================
function scheduleAutosave() {
  if (autosaveTimer) clearTimeout(autosaveTimer)
  autosaveTimer = setTimeout(() => {
    persistLocalDraft()
  }, 1000)
}

function persistLocalDraft() {
  if (!submittable.value) return
  saveDraft(taskId, {
    content: submitContent.value,
    fileUrls: uploadFileList.value.map((f) => f.url),
  })
  lastSavedAt.value = new Date().toLocaleTimeString()
  dirty.value = false
}

// 内容变化触发自动保存
watch([submitContent, uploadFileList], () => {
  if (loading.value) return
  dirty.value = true
  scheduleAutosave()
}, { deep: true })

// 失焦时同步保存到服务端草稿（跨设备，best-effort）
async function handleBlurSave() {
  if (!submittable.value || submitting.value) return
  if (!submitContent.value.trim() && uploadFileList.value.length === 0) return
  savingDraft.value = true
  try {
    await saveDraftApi({
      task_id: taskId,
      content: submitContent.value,
      file_urls: uploadFileList.value.map((f) => f.url),
    })
  } catch {
    // 服务端草稿保存失败不阻断本地编辑（拦截器已提示）
  } finally {
    savingDraft.value = false
  }
}

// ============================================================
// 幂等提交
// ============================================================
async function handleSubmit() {
  if (!submitContent.value.trim() && uploadFileList.value.length === 0) {
    ElMessage.warning('请填写作业内容或上传文件')
    return
  }
  submitting.value = true
  try {
    const idempotencyKey = acquireIdempotencyKey(taskId)
    const res = await idempotentSubmitApi({
      task_id: taskId,
      content: submitContent.value,
      file_urls: uploadFileList.value.map((f) => f.url),
      idempotency_key: idempotencyKey,
    })
    const result = res.data.data
    if (result.created) {
      ElMessage.success('提交成功')
    } else {
      ElMessage.info('该提交已处理，重复提交已忽略')
    }
    // 提交成功：清理本地草稿与幂等键
    clearDraft(taskId)
    clearIdempotencyKey(taskId)
    dirty.value = false
    // 跳转到反馈视图
    router.push(`/student/submissions/${result.submissionId}/feedback`)
  } catch {
    // 错误由拦截器提示；保留幂等键以便重试
  } finally {
    submitting.value = false
  }
}

// ============================================================
// 文件上传
// ============================================================
async function handleUpload(file: File) {
  const isAllowed = /\.(docx|pdf|txt|jpg|jpeg|png)$/i.test(file.name)
  if (!isAllowed) {
    ElMessage.warning('仅支持 docx/pdf/txt/jpg/png 格式')
    return false
  }
  try {
    const res = await uploadFileApi(file)
    const data = res.data.data
    uploadFileList.value.push({
      url: data.url,
      name: data.filename,
      size: data.size,
    })
    ElMessage.success(`已上传: ${data.filename}`)
  } catch {
    ElMessage.error('上传失败')
  }
  return false
}

function removeFile(file: { url: string }) {
  uploadFileList.value = uploadFileList.value.filter((f) => f.url !== file.url)
}

function goToFeedback() {
  if (submission.value) {
    router.push(`/student/submissions/${submission.value.id}/feedback`)
  }
}

// ============================================================
// 离开保护
// ============================================================
onBeforeRouteLeave(async (_to, _from) => {
  if (!dirty.value) return true
  try {
    await ElMessageBox.confirm(
      '有未保存的改动，离开将丢失本地未保存内容（已自动保存的内容仍保留）。确认离开？',
      '离开确认',
      { type: 'warning', confirmButtonText: '离开', cancelButtonText: '继续编辑' },
    )
    return true
  } catch {
    return false
  }
})

onBeforeUnmount(() => {
  if (autosaveTimer) clearTimeout(autosaveTimer)
  // 组件卸载前确保本地草稿已写入
  if (dirty.value) persistLocalDraft()
})

onMounted(fetchData)
</script>

<template>
  <div class="page-container">
    <div style="margin-bottom: 16px;">
      <el-link :underline="false" @click="router.push('/student/tasks')">
        <el-icon><ArrowLeft /></el-icon> 返回任务列表
      </el-link>
    </div>

    <div v-loading="loading" style="min-height: 300px;">
      <div v-if="taskDetail" class="submit-layout">
        <div class="submit-main">
          <el-card shadow="never" class="page-section">
            <template #header>
              <div class="flex-between">
                <span class="card-title">{{ taskDetail.title }}</span>
                <el-tag :type="taskDetail.deadline ? 'warning' : 'info'">
                  {{ taskDetail.deadline ? '截止: ' + new Date(taskDetail.deadline).toLocaleDateString() : '无截止日期' }}
                </el-tag>
              </div>
            </template>
            <p class="task-desc">{{ taskDetail.description || '暂无描述' }}</p>
            <div style="margin-top: 12px;">
              <span style="font-size: 13px; color: #909399;">满分: {{ taskDetail.maxScore }}</span>
              <el-tag size="small" :type="taskDetail.taskType === 'individual' ? 'default' : 'success'" style="margin-left: 8px;">
                {{ taskDetail.taskType === 'individual' ? '个人任务' : '小组任务' }}
              </el-tag>
            </div>
          </el-card>

          <!-- 已提交且不可再提交：只读提示 -->
          <el-card v-if="!submittable && submission" shadow="never" class="page-section">
            <template #header>
              <span class="card-title">提交状态</span>
            </template>
            <el-alert
              :title="`当前状态：${REVIEW_STATUS_LABELS[reviewStatus!] || reviewStatus}，暂无法在此页修改`"
              type="info"
              :closable="false"
              show-icon
            >
              <template #default>
                如需查看反馈或发起订正/二次评价，请前往反馈视图。
              </template>
            </el-alert>
            <div style="margin-top: 12px;">
              <el-button type="primary" @click="goToFeedback">查看反馈</el-button>
            </div>
          </el-card>

          <!-- 可提交：编辑表单 -->
          <el-card v-else shadow="never" class="page-section">
            <template #header>
              <div class="flex-between">
                <span class="card-title">
                  {{ reviewStatus === 'returned' ? '订正再提交' : (submission ? '重新提交' : '提交作业') }}
                </span>
                <span class="autosave-hint">
                  <span v-if="savingDraft">草稿同步中...</span>
                  <span v-else-if="lastSavedAt">本地已自动保存 {{ lastSavedAt }}</span>
                  <span v-else>编辑时自动保存到本地</span>
                </span>
              </div>
            </template>
            <el-form label-position="top">
              <el-form-item label="作业内容">
                <el-input
                  v-model="submitContent"
                  type="textarea"
                  :rows="10"
                  placeholder="在此输入作业内容..."
                  @blur="handleBlurSave"
                />
              </el-form-item>
              <el-form-item label="上传附件">
                <el-upload
                  :auto-upload="false"
                  :show-file-list="false"
                  :on-change="(f: any) => handleUpload(f.raw)"
                  accept=".docx,.pdf,.txt,.jpg,.jpeg,.png"
                >
                  <el-button :icon="Upload">选择文件</el-button>
                  <template #tip>
                    <span style="font-size: 12px; color: #909399;">支持 docx/pdf/txt/jpg/png 格式</span>
                  </template>
                </el-upload>
                <div v-for="f in uploadFileList" :key="f.url" class="uploaded-file">
                  <el-icon><Document /></el-icon>
                  <span class="file-name">{{ f.name }}</span>
                  <el-button text type="danger" :icon="Delete" size="small" @click="removeFile(f)" />
                </div>
              </el-form-item>
              <el-form-item>
                <el-button
                  type="primary"
                  size="large"
                  :loading="submitting"
                  :icon="Upload"
                  @click="handleSubmit"
                >
                  {{ submitButtonText }}
                </el-button>
                <span class="idempotency-hint">重复点击不会生成重复提交</span>
              </el-form-item>
            </el-form>
          </el-card>
        </div>

        <!-- 右侧提交记录 -->
        <div class="submit-side">
          <el-card v-if="submission" shadow="never">
            <template #header>
              <span class="card-title">提交记录</span>
            </template>
            <div class="history-item">
              <div class="history-version">
                当前状态：
                <el-tag size="small" type="info">
                  {{ REVIEW_STATUS_LABELS[reviewStatus!] || reviewStatus || '—' }}
                </el-tag>
              </div>
              <div class="history-time">
                {{ submission.submittedAt ? new Date(submission.submittedAt).toLocaleString() : '未提交' }}
              </div>
              <div v-if="submission.score !== null && submission.score !== undefined" style="margin-top: 8px;">
                <span style="font-size: 24px; font-weight: 700; color: #67c23a;">{{ submission.score }}</span>
                <span style="color: #909399; font-size: 13px;"> / {{ taskDetail.maxScore }} 分</span>
              </div>
              <p v-if="submission.comment" style="margin-top: 8px; font-size: 14px; color: #606266;">
                {{ submission.comment }}
              </p>
              <el-button
                v-if="submission"
                text
                type="primary"
                size="small"
                style="margin-top: 8px;"
                @click="goToFeedback"
              >
                查看完整反馈
              </el-button>
            </div>
          </el-card>
          <el-card v-else shadow="never">
            <template #header>
              <span class="card-title">提交记录</span>
            </template>
            <el-empty description="暂无提交记录" :image-size="60" />
          </el-card>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.submit-layout {
  display: grid;
  grid-template-columns: 3fr 2fr;
  gap: 20px;
  align-items: start;
}

.submit-main {
  min-width: 0;
}

.page-section {
  margin-bottom: 16px;
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

.task-desc {
  font-size: 14px;
  color: #606266;
  line-height: 1.8;
  margin: 0;
}

.autosave-hint {
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

.idempotency-hint {
  margin-left: 12px;
  font-size: 12px;
  color: #909399;
}

.history-item {
  padding: 12px 0;
}

.history-version {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
  display: flex;
  align-items: center;
  gap: 8px;
}

.history-time {
  font-size: 12px;
  color: #909399;
  margin: 8px 0;
}

/* 平板与移动端响应式 */
@media (max-width: 1024px) {
  .submit-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .flex-between {
    flex-direction: column;
    align-items: flex-start;
  }
  .autosave-hint {
    font-size: 11px;
  }
}
</style>
