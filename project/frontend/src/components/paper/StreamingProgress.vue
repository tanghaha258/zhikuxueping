<script setup lang="ts">
import { ref, computed, reactive, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { STORAGE_KEYS } from '@/utils/constants'

const emit = defineEmits<{
  complete: [data: any, questions: any[]]
  error: [message: string]
  retry: []
  cancel: []
}>()

const visible = ref(true)
const questions = ref<any[]>([])
const totalQuestions = ref(0)
const status = ref<'generating' | 'done' | 'error'>('generating')
const errorMessage = ref('')
const elapsed = ref(0)
let reader: ReadableStreamDefaultReader<Uint8Array> | null = null
let timerHandle: ReturnType<typeof setInterval> | null = null
let streamAborted = false
const twPositions = reactive<Record<number, number>>({})
let twInterval: ReturnType<typeof setInterval> | null = null
let pendingDoneData: any = null
let pendingPaperId = ''

// Adaptive columns: >= 8 questions → 2 columns, >= 16 → 3 columns
const columnClass = computed(() => {
  const n = questions.value.length
  if (n >= 16) return 'cols-3'
  if (n >= 8) return 'cols-2'
  return 'cols-1'
})

const progressPercent = computed(() => {
  if (totalQuestions.value === 0) return 0
  return Math.min(95, Math.round((questions.value.length / Math.max(totalQuestions.value, 1)) * 100))
})

function startTimer() {
  elapsed.value = 0
  timerHandle = setInterval(() => {
    elapsed.value++
  }, 1000)
}

function stopTimer() {
  if (timerHandle) { clearInterval(timerHandle); timerHandle = null }
}

function ensureTypewriter() {
  if (twInterval) return
  let interval = 50
  // Auto-speedup: 检测最长未完成内容，超过 150 字则加速到 25ms
  const maxPending = Math.max(0, ...questions.value.map((q, i) => {
    if (!q) return 0
    const pos = twPositions[i] ?? 0
    return (q.content || '').length - pos
  }))
  if (maxPending > 150) interval = 25
  twInterval = setInterval(() => {
    if (status.value === 'error') {
      clearInterval(twInterval!)
      twInterval = null
      return
    }
    let allDone = true
    for (let i = 0; i < questions.value.length; i++) {
      const q = questions.value[i]
      if (!q) continue
      const pos = twPositions[i] ?? 0
      const len = (q.content || '').length
      if (pos < len) {
        twPositions[i] = pos + 1
        allDone = false
      }
    }
    if (allDone && status.value !== 'generating') {
      clearInterval(twInterval!)
      twInterval = null
    }
  }, interval)
}

function fastCompleteTypewriter() {
  for (let i = 0; i < questions.value.length; i++) {
    const q = questions.value[i]
    if (q) twPositions[i] = (q.content || '').length
  }
  if (twInterval) { clearInterval(twInterval); twInterval = null }
}

function emitComplete() {
  const doneData = pendingDoneData || {}
  const allQuestions = questions.value
  const resultData = { ...doneData, id: pendingPaperId || doneData.id || '' }
  if (resultData.questions) {
    emit('complete', resultData, resultData.questions)
  } else {
    emit('complete', resultData, allQuestions)
  }
}

function startStream(url: string, body: object) {
  startTimer()
  const token = localStorage.getItem(STORAGE_KEYS.TOKEN) || ''
  const xhr = new XMLHttpRequest()
  let sseBuf = ''

  xhr.open('POST', url, true)
  xhr.setRequestHeader('Content-Type', 'application/json')
  xhr.setRequestHeader('Authorization', `Bearer ${token}`)

  xhr.onprogress = () => {
    if (streamAborted) { xhr.abort(); return }
    // xhr.responseText 包含至今收到的所有数据，取新增部分
    const newText = xhr.responseText.slice((xhr as any)._lastLen || 0)
    ;(xhr as any)._lastLen = xhr.responseText.length
    sseBuf += newText

    // 逐行解析 SSE
    const lines = sseBuf.split('\n')
    sseBuf = lines.pop() || ''
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const event = JSON.parse(line.slice(6))
          if (event.type === 'question') {
            const idx = questions.value.length
            questions.value.push({ ...event.data })
            totalQuestions.value = event.index || questions.value.length
            twPositions[idx] = 0
            ensureTypewriter()
          } else if (event.type === 'done') {
            fastCompleteTypewriter()
            pendingDoneData = event.data
            status.value = 'generating'
          } else if (event.type === 'paper_saved') {
            pendingPaperId = event.id || ''
            stopTimer()
            status.value = 'done'
            emitComplete()
          } else if (event.type === 'error') {
            stopTimer()
            status.value = 'error'
            errorMessage.value = event.message
          }
        } catch { /* skip */ }
      }
    }
  }

  xhr.onload = () => {
    if (pendingPaperId || pendingDoneData) {
      stopTimer()
      status.value = 'done'
      emitComplete()
      return
    }
    if (sseBuf.trim() && sseBuf.startsWith('data: ')) {
      try {
        const event = JSON.parse(sseBuf.slice(6))
        if (event.type === 'done') {
          fastCompleteTypewriter()
          pendingDoneData = event.data
          status.value = 'done'
          emitComplete()
          return
        }
      } catch { /* skip */ }
    }
    stopTimer()
    if (!streamAborted && questions.value.length > 0) {
      fastCompleteTypewriter()
      status.value = 'done'
      emitComplete()
    }
  }

  xhr.onerror = () => {
    stopTimer()
    if (!streamAborted) {
      status.value = 'error'
      errorMessage.value = '网络错误'
      emit('error', '网络错误')
    }
  }

  xhr.send(JSON.stringify(body))
  reader = { cancel: () => xhr.abort() } as any
}

function close() {
  streamAborted = true
  reader?.cancel()
  fastCompleteTypewriter()
  stopTimer()
  visible.value = false
}

defineExpose({ startStream })

onUnmounted(() => {
  streamAborted = true
  reader?.cancel()
  if (twInterval) clearInterval(twInterval)
  stopTimer()
})
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="streaming-overlay" @click.self="close">
      <div class="streaming-dialog" :class="{ 'is-done': status === 'done' }">
        <!-- Header -->
        <div class="dialog-header">
          <div class="header-left">
            <span class="header-icon">{{ status === 'generating' ? '🤖' : status === 'done' ? '✅' : '❌' }}</span>
            <h3>{{ status === 'generating' ? 'AI 正在出卷' : status === 'done' ? '生成完成' : '生成失败' }}</h3>
          </div>
          <div class="header-right">
            <span class="badge">{{ questions.length }} / {{ totalQuestions || '?' }} 题</span>
            <span v-if="status === 'generating'" class="timer">{{ elapsed }}s</span>
            <button class="close-btn" @click="close">&times;</button>
          </div>
        </div>

        <!-- Progress bar -->
        <div v-if="status === 'generating'" class="progress-track">
          <div class="progress-bar" :style="{ width: progressPercent + '%' }"></div>
        </div>

        <!-- Body -->
        <div class="dialog-body">
          <div v-if="questions.length === 0" class="empty-state">
            <div class="spinner"></div>
            <p>正在连接 AI 并生成题目...</p>
          </div>
          <div v-else :class="['questions-grid', columnClass]">
            <TransitionGroup name="q-pop">
              <div v-for="(q, i) in questions" :key="'q-' + i" class="question-card" :class="'type-' + (q.type || 'choice')">
                <div class="q-num">{{ i + 1 }}</div>
                <div class="q-body">
                  <div class="q-type">{{ ({ choice:'选择题', fill:'填空题', judge:'判断题', essay:'解答题', reading:'阅读理解', cloze:'完形填空' } as Record<string, string>)[q.type] || q.type }}</div>
                  <div class="q-preview">
                    <span class="tw-text">{{ (q.content || '').replace(/<[^>]*>/g,'').substring(0, twPositions[i] ?? 0) }}</span><span v-if="(twPositions[i] ?? 0) < (q.content || '').length" class="tw-cursor">|</span>
                  </div>
                  <div class="q-footer">
                    <span class="q-score">{{ q.score }} 分</span>
                    <span class="q-subject" v-if="q.type === 'choice'">{{ q.options?.length || 0 }} 选项</span>
                  </div>
                </div>
              </div>
            </TransitionGroup>
          </div>
          <div v-if="status === 'generating' && questions.length > 0" class="generating-hint">
            <span class="dot-pulse"></span>
            <span>正在生成下一题...</span>
          </div>
        </div>

        <!-- Footer -->
        <div class="dialog-footer">
          <div class="footer-status">
            <span v-if="status === 'generating'" class="text-muted">已用 {{ elapsed }} 秒</span>
            <span v-else-if="status === 'done'" class="text-success">✅ 共 {{ questions.length }} 题生成完毕</span>
            <span v-else-if="status === 'error'" class="text-error">❌ {{ errorMessage || '生成失败' }}</span>
          </div>
          <div class="footer-actions">
            <button v-if="status === 'error'" class="btn btn-outline" @click="close">取消</button>
            <button v-if="status === 'error'" class="btn btn-primary" @click="$emit('retry')">重试</button>
            <button v-if="status === 'done'" class="btn btn-primary" @click="close">完成，进入编辑</button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.streaming-overlay {
  position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.35);
  display: flex; align-items: center; justify-content: center;
  z-index: 9999;
  backdrop-filter: blur(2px);
}
.streaming-dialog {
  background: #fff;
  border-radius: 16px;
  width: 90vw;
  max-width: 900px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 16px 56px rgba(0,0,0,0.18);
  animation: dialogIn .35s ease-out;
}
.streaming-dialog.is-done { animation: dialogIn .35s ease-out; }
@keyframes dialogIn {
  from { opacity:0; transform:scale(.96) translateY(12px); }
  to { opacity:1; transform:scale(1) translateY(0); }
}

/* Header */
.dialog-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 18px 24px; border-bottom: 1px solid #ebeef5; flex-shrink: 0;
}
.header-left { display: flex; align-items: center; gap: 10px; }
.header-icon { font-size: 20px; }
.dialog-header h3 { margin:0; font-size: 17px; font-weight: 600; }
.header-right { display: flex; align-items: center; gap: 12px; }
.badge {
  font-size: 12px; background: #ecf5ff; color: #4f6ef7;
  padding: 3px 12px; border-radius: 12px; font-weight: 500;
}
.timer { font-size: 12px; color: #909399; font-variant-numeric: tabular-nums; }
.close-btn {
  background: none; border: none; font-size: 22px; color: #c0c4cc;
  cursor: pointer; padding: 0 4px; line-height: 1;
}
.close-btn:hover { color: #606266; }

/* Progress */
.progress-track {
  height: 3px; background: #e4e7ed; flex-shrink: 0;
}
.progress-bar {
  height: 100%; background: linear-gradient(90deg, #4f6ef7, #7c5cfc);
  transition: width .5s ease; border-radius: 0 2px 2px 0;
}

/* Timeout banner */
.timeout-banner {
  background: #fdf6ec; border: 1px solid #faecd8; border-radius: 8px;
  padding: 10px 16px; margin-bottom: 12px; font-size: 13px; color: #e6a23c;
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
}
.link-btn {
  background: none; border: none; color: #4f6ef7; cursor: pointer;
  font-size: 13px; font-weight: 500; padding: 0 2px; text-decoration: underline;
}

/* Body */
.dialog-body {
  flex: 1; overflow-y: auto; padding: 16px 24px; min-height: 240px;
}
.empty-state {
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; padding: 60px 0; color: #909399;
}
.spinner {
  width: 36px; height: 36px; border: 3px solid #e4e7ed;
  border-top-color: #4f6ef7; border-radius: 50%;
  animation: spin .8s linear infinite; margin-bottom: 16px;
}
@keyframes spin { to { transform: rotate(360deg); } }
.empty-state p { font-size: 14px; }

/* Questions grid */
.questions-grid { display: grid; gap: 10px; }
.questions-grid.cols-1 { grid-template-columns: 1fr; }
.questions-grid.cols-2 { grid-template-columns: 1fr 1fr; }
.questions-grid.cols-3 { grid-template-columns: 1fr 1fr 1fr; }

.question-card {
  display: flex; gap: 10px; padding: 12px 14px; border-radius: 10px;
  background: #f5f7fa; border-left: 3px solid #4f6ef7;
  transition: all .2s; min-width: 0;
}
.question-card:hover { background: #eef1f6; }
.question-card.type-fill { border-left-color: #67c23a; }
.question-card.type-essay { border-left-color: #e6a23c; }
.question-card.type-judge { border-left-color: #f56c6c; }
.q-num {
  width: 26px; height: 26px; background: #4f6ef7; color: #fff;
  border-radius: 50%; display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 600; flex-shrink: 0;
}
.question-card.type-fill .q-num { background: #67c23a; }
.question-card.type-essay .q-num { background: #e6a23c; }
.question-card.type-judge .q-num { background: #f56c6c; }
.q-body { flex: 1; min-width: 0; }
.q-type { font-size: 11px; color: #909399; margin-bottom: 2px; }
.q-preview { font-size: 13px; color: #303133; line-height: 1.5; word-break: break-word; min-height: 1.2em; }
.q-footer { display: flex; gap: 8px; margin-top: 3px; }
.q-score { font-size: 11px; color: #e6a23c; }
.q-subject { font-size: 11px; color: #909399; }

.generating-hint {
  display: flex; align-items: center; gap: 8px;
  padding: 16px 0; color: #909399; font-size: 13px;
}
.dot-pulse {
  width: 8px; height: 8px; background: #4f6ef7; border-radius: 50%;
  animation: pulse 1s ease-in-out infinite;
}
@keyframes pulse { 0%,100% { opacity:.4; transform:scale(.8); } 50% { opacity:1; transform:scale(1.2); } }

/* Footer */
.dialog-footer {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 24px; border-top: 1px solid #ebeef5; flex-shrink: 0;
}
.footer-actions { display: flex; gap: 8px; }
.text-muted { font-size: 13px; color: #909399; }
.text-success { font-size: 13px; color: #67c23a; }
.text-error { font-size: 13px; color: #f56c6c; }

.btn {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 7px 18px; border: none; border-radius: 8px;
  font-size: 13px; font-weight: 500; cursor: pointer; transition: all .2s;
}
.btn-primary { background: #4f6ef7; color: #fff; }
.btn-primary:hover { background: #3d5ce5; }
.btn-outline { background: #fff; color: #606266; border: 1px solid #dcdfe6; }
.btn-outline:hover { border-color: #4f6ef7; color: #4f6ef7; }

/* Typewriter cursor */
.tw-cursor {
  display: inline-block;
  color: #4f6ef7;
  font-weight: 700;
  animation: blink .8s step-end infinite;
  margin-left: 1px;
}
@keyframes blink { 50% { opacity: 0; } }

/* Animation */
.q-pop-enter-active { transition: all .35s ease-out; }
.q-pop-enter-from { opacity: 0; transform: translateY(16px) scale(.96); }

@media (max-width: 680px) {
  .streaming-dialog { width: 96vw; max-height: 90vh; }
  .dialog-body { padding: 12px 16px; }
  .questions-grid.cols-2, .questions-grid.cols-3 { grid-template-columns: 1fr; }
}
</style>
