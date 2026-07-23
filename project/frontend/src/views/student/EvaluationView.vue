<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { listMySubmissionsApi } from '@/api/submissions'
import { listStudentEvaluationsApi } from '@/api/evaluations'
import { useUserStore } from '@/stores/user'
import type { Submission, Evaluation } from '@/types'

const userStore = useUserStore()
const activeTab = ref('all')

const submissions = ref<Submission[]>([])
const evaluations = ref<Evaluation[]>([])
const loading = ref(false)

const typeConfig: Record<string, { label: string; type: string }> = {
  teacher: { label: '教师评价', type: 'primary' },
  peer: { label: '互评', type: 'success' },
  ai: { label: 'AI 评价', type: 'warning' },
  self: { label: '自评', type: 'info' },
}

async function fetchData() {
  loading.value = true
  try {
    const subRes = await listMySubmissionsApi()
    submissions.value = subRes.data.data

    if (userStore.userInfo?.id) {
      const evalRes = await listStudentEvaluationsApi(userStore.userInfo.id)
      evaluations.value = evalRes.data.data
    }
  } finally {
    loading.value = false
  }
}

const filteredEvaluations = computed(() => {
  if (activeTab.value === 'all') return evaluations.value
  return evaluations.value.filter((e) => e.evalType === activeTab.value)
})

const pendingCount = computed(() => {
  return submissions.value.filter((s) => s.score === null || s.score === undefined).length
})

onMounted(fetchData)
</script>

<script lang="ts">
import { computed } from 'vue'
</script>

<template>
  <div class="page-container">
    <h2 class="page-title">我的评价</h2>

    <el-card v-if="pendingCount > 0" shadow="never" class="page-section" style="border-left: 4px solid #e6a23c; margin-bottom: 16px;">
      <div class="flex-between">
        <div class="flex" style="align-items: center; gap: 12px;">
          <el-icon size="24" color="#e6a23c"><WarningFilled /></el-icon>
          <div>
            <span style="font-weight: 500;">{{ pendingCount }} 个提交待批阅</span>
            <p style="margin: 4px 0 0; font-size: 13px; color: #909399;">等待老师评分后可查看评价</p>
          </div>
        </div>
      </div>
    </el-card>

    <el-card shadow="never">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="全部" name="all" />
        <el-tab-pane label="自评" name="self" />
        <el-tab-pane label="互评" name="peer" />
        <el-tab-pane label="教师评价" name="teacher" />
        <el-tab-pane label="AI 评价" name="ai" />
      </el-tabs>

      <div v-if="loading" v-loading="loading" style="min-height: 200px;" />

      <div v-else-if="filteredEvaluations.length > 0" class="eval-list">
        <div v-for="ev in filteredEvaluations" :key="ev.id" class="eval-card">
          <div class="eval-card-header">
            <div class="eval-card-left">
              <el-tag :type="(typeConfig[ev.evalType]?.type as any)" size="small">
                {{ typeConfig[ev.evalType]?.label || ev.evalType }}
              </el-tag>
              <span class="eval-task-name">任务 {{ ev.taskId }}</span>
            </div>
            <div class="eval-score" :class="{ high: ev.score >= 85, mid: ev.score >= 70 && ev.score < 85, low: ev.score < 70 }">
              {{ ev.score }} 分
            </div>
          </div>
          <p class="eval-comment">{{ ev.comment || '无评语' }}</p>
          <div class="eval-footer">
            <span class="eval-evaluator">评价人: {{ ev.evaluatorId }}</span>
            <span class="eval-date">{{ ev.createdAt ? new Date(ev.createdAt).toLocaleDateString() : '-' }}</span>
          </div>
        </div>
      </div>

      <div v-else class="empty-state">
        <el-empty description="暂无评价记录" />
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.eval-list { display: flex; flex-direction: column; gap: 4px; }
.eval-card {
  padding: 16px 0; border-bottom: 1px solid #f0f0f0;
}
.eval-card:last-child { border-bottom: none; }
.eval-card-header {
  display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;
}
.eval-card-left { display: flex; align-items: center; gap: 10px; }
.eval-task-name { font-size: 15px; font-weight: 500; color: #303133; }
.eval-score {
  font-size: 22px; font-weight: 700; flex-shrink: 0;
}
.eval-score.high { color: #67c23a; }
.eval-score.mid { color: #e6a23c; }
.eval-score.low { color: #f56c6c; }
.eval-comment {
  font-size: 14px; color: #606266; line-height: 1.7; margin: 0 0 10px;
}
.eval-footer { display: flex; gap: 12px; font-size: 12px; color: #909399; }
</style>
