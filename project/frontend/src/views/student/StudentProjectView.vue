<script setup lang="ts">
/**
 * StudentProjectView - 学生项目空间（Task 6 / 计划 3.7.2）。
 *
 * 只读视图：项目基本信息、真实问题设计、可见任务列表、
 * 三级分层资源（foundation/enhancement/extension）。
 * 数据来自 GET /student/projects/{project_id}，后端按班级授权与发布状态过滤。
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getStudentProjectApi } from '@/features/student-space/api'
import {
  TIER_LABELS,
} from '@/features/student-space/types'
import type {
  StudentProjectResource,
  StudentProjectView as StudentProjectViewData,
} from '@/features/student-space/types'

const route = useRoute()
const router = useRouter()
const projectId = computed(() => route.params.id as string)

const data = ref<StudentProjectViewData | null>(null)
const loading = ref(false)
const activeTier = ref<'foundation' | 'enhancement' | 'extension'>('foundation')

const project = computed(() => data.value?.project || null)
const problem = computed(() => data.value?.problem || null)
const tasks = computed(() => data.value?.tasks || [])
const resources = computed(() => data.value?.resources || {
  foundation: [],
  enhancement: [],
  extension: [],
})

const tierTabs = computed(() => {
  const r = resources.value
  return [
    { key: 'foundation' as const, label: TIER_LABELS.foundation, count: r.foundation.length },
    { key: 'enhancement' as const, label: TIER_LABELS.enhancement, count: r.enhancement.length },
    { key: 'extension' as const, label: TIER_LABELS.extension, count: r.extension.length },
  ]
})

const currentResources = computed<StudentProjectResource[]>(
  () => resources.value[activeTier.value] || [],
)

const problemFields = computed(() => {
  if (!problem.value) return []
  const p = problem.value
  const items: { label: string; value?: string | null }[] = [
    { label: '情境', value: p.context },
    { label: '对象', value: p.object },
    { label: '受众', value: p.audience },
    { label: '约束', value: p.constraints },
    { label: '成果', value: p.deliverable },
    { label: '用途', value: p.usage },
  ]
  return items.filter((i) => i.value)
})

function goToTask(taskId: string) {
  router.push(`/student/tasks/${taskId}/submit`)
}

function openResource(url?: string | null) {
  if (url) window.open(url, '_blank', 'noopener')
}

async function fetchData() {
  loading.value = true
  try {
    const res = await getStudentProjectApi(projectId.value)
    data.value = res.data.data
  } catch {
    ElMessage.error('加载项目空间失败')
  } finally {
    loading.value = false
  }
}

onMounted(fetchData)
</script>

<template>
  <div class="page-container" v-loading="loading">
    <div style="margin-bottom: 16px;">
      <el-link :underline="false" @click="router.push('/student/dashboard')">
        <el-icon><ArrowLeft /></el-icon> 返回工作台
      </el-link>
    </div>

    <div v-if="project" class="project-view">
      <!-- 项目基本信息 -->
      <el-card shadow="never" class="page-section">
        <template #header>
          <div class="flex-between">
            <span class="card-title">{{ project.title }}</span>
            <el-tag :type="project.status === 'active' ? 'success' : 'info'">
              {{ project.status === 'active' ? '进行中' : project.status }}
            </el-tag>
          </div>
        </template>
        <p class="project-desc">{{ project.description || '暂无描述' }}</p>
      </el-card>

      <!-- 真实问题（只读设计） -->
      <el-card v-if="problemFields.length > 0" shadow="never" class="page-section">
        <template #header>
          <span class="card-title">真实问题</span>
        </template>
        <div class="problem-grid">
          <div v-for="field in problemFields" :key="field.label" class="problem-item">
            <div class="problem-label">{{ field.label }}</div>
            <div class="problem-value">{{ field.value }}</div>
          </div>
        </div>
      </el-card>

      <!-- 任务列表 -->
      <el-card v-if="tasks.length > 0" shadow="never" class="page-section">
        <template #header>
          <span class="card-title">任务列表（{{ tasks.length }}）</span>
        </template>
        <div class="task-list">
          <div v-for="t in tasks" :key="t.id" class="task-row" @click="goToTask(t.id)">
            <div class="task-row-left">
              <span class="task-row-title">{{ t.title }}</span>
              <div class="task-row-tags">
                <el-tag v-if="t.stage" size="small" type="info">{{ t.stage }}</el-tag>
                <el-tag v-if="t.tier" size="small" type="warning">{{ t.tier }}</el-tag>
                <el-tag size="small">满分 {{ t.maxScore }}</el-tag>
              </div>
            </div>
            <div class="task-row-right">
              <span v-if="t.deadline" class="task-row-deadline">
                截止 {{ new Date(t.deadline).toLocaleDateString() }}
              </span>
              <el-button text type="primary" size="small">去完成</el-button>
            </div>
          </div>
        </div>
      </el-card>

      <!-- 三级分层资源 -->
      <el-card shadow="never" class="page-section">
        <template #header>
          <span class="card-title">学习资源</span>
        </template>
        <el-tabs v-model="activeTier">
          <el-tab-pane
            v-for="tab in tierTabs"
            :key="tab.key"
            :name="tab.key"
          >
            <template #label>
              {{ tab.label }}（{{ tab.count }}）
            </template>
          </el-tab-pane>
        </el-tabs>

        <div v-if="currentResources.length > 0" class="resource-list">
          <div
            v-for="r in currentResources"
            :key="r.id"
            class="resource-card"
            :class="{ clickable: !!r.url }"
            @click="openResource(r.url)"
          >
            <div class="resource-card-header">
              <el-icon><Document /></el-icon>
              <span class="resource-title">{{ r.title }}</span>
              <el-tag size="small" type="info">{{ r.resType }}</el-tag>
            </div>
            <p v-if="r.usageTip" class="resource-tip">{{ r.usageTip }}</p>
            <div v-if="r.url" class="resource-link">
              <el-link type="primary" :underline="false" :href="r.url" target="_blank">
                打开资源
              </el-link>
            </div>
          </div>
        </div>
        <el-empty v-else description="该层级暂无资源" :image-size="60" />
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.project-view {
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

.project-desc {
  font-size: 14px;
  color: #606266;
  line-height: 1.8;
  margin: 0;
}

.problem-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.problem-item {
  background: #f5f7fa;
  border-radius: 6px;
  padding: 12px 14px;
}

.problem-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 6px;
}

.problem-value {
  font-size: 14px;
  color: #303133;
  line-height: 1.6;
}

.task-list {
  display: flex;
  flex-direction: column;
}

.task-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid #f0f0f0;
  cursor: pointer;
  gap: 12px;
  transition: background 0.2s;
}

.task-row:hover {
  background: #fafbfc;
}

.task-row:last-child {
  border-bottom: none;
}

.task-row-left {
  flex: 1;
  min-width: 0;
}

.task-row-title {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
  display: block;
  margin-bottom: 6px;
}

.task-row-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.task-row-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.task-row-deadline {
  font-size: 12px;
  color: #909399;
  white-space: nowrap;
}

.resource-list {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.resource-card {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 14px;
  transition: all 0.2s;
}

.resource-card.clickable {
  cursor: pointer;
}

.resource-card.clickable:hover {
  border-color: #409eff;
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.1);
}

.resource-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.resource-title {
  flex: 1;
  font-size: 14px;
  font-weight: 500;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.resource-tip {
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
  margin: 0 0 8px;
}

.resource-link {
  font-size: 13px;
}

/* 平板与移动端响应式 */
@media (max-width: 1024px) {
  .problem-grid {
    grid-template-columns: 1fr;
  }
  .resource-list {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .task-row {
    flex-direction: column;
    align-items: flex-start;
  }
  .task-row-right {
    width: 100%;
    justify-content: flex-end;
  }
}
</style>
