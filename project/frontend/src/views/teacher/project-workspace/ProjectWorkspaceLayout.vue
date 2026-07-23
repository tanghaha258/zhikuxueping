<script setup lang="ts">
/**
 * ProjectWorkspaceLayout - 项目工作区父布局（计划 3.5）。
 *
 * 顶部展示项目标题、状态、班级、核心学科、完整度与最近保存时间；
 * 左侧阶段导航在总览/设计之间切换，并提供旧版详情入口（保护现有功能）；
 * 右侧下一步操作由确定性规则产生（resolveNextStep）。
 *
 * 项目与完整性校验结果通过 provide 注入子视图，避免重复请求。
 */
import { computed, onMounted, provide, ref } from 'vue'
import { useRoute, useRouter, onBeforeRouteLeave } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { getProjectApi } from '@/api/projects'
import { listSubjectsApi } from '@/api/subjects'
import { listClassesBySchoolApi } from '@/api/schools'
import { useUserStore } from '@/stores/user'
import {
  resolveNextStep,
  canEditDesign,
} from '@/features/project-workspace/composables/useProjectWorkspace'
import { validateActivationApi } from '@/features/project-workspace/api'
import type { Project, SubjectItem, ClassItem } from '@/types'
import type {
  ProjectValidationResult,
} from '@/features/project-workspace/types'
import {
  PROJECT_STATUS_LABELS,
  PROJECT_STATUS_TYPES,
} from '@/utils/constants'
import { formatDate } from '@/utils/format'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const projectId = computed(() => route.params.id as string)

const project = ref<Project | null>(null)
const validation = ref<ProjectValidationResult | null>(null)
const subjects = ref<SubjectItem[]>([])
const classes = ref<ClassItem[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

// 阶段导航：总览/设计/资源/任务链为本任务实现；评价/AI 暂指向旧版详情
const navItems = computed(() => [
  { name: 'ProjectOverview', label: '总览', disabled: false },
  { name: 'ProjectDesign', label: '设计', disabled: false },
  { name: 'ProjectResources', label: '资源', disabled: false },
  { name: 'ProjectTaskChain', label: '任务链', disabled: false },
  { name: 'ProjectEvaluationPlan', label: '评价计划', disabled: false },
  { name: 'ProjectReview', label: '复核', disabled: false },
  { name: 'ProjectAiContent', label: 'AI 内容', disabled: false },
  { name: 'ProjectInsights', label: '学情', disabled: false },
  { name: 'ProjectClosure', label: '结项', disabled: false },
  { name: 'ProjectDetail', label: '评价·AI（旧版）', disabled: false },
])

const activeName = computed(() => route.name as string)

const coreSubjectName = computed(() => {
  const id = project.value?.coreSubjectId
  if (!id) return '未指定'
  return subjects.value.find((s) => s.id === id)?.name || '未指定'
})

const className = computed(() => {
  const ids = project.value?.classIds || []
  if (ids.length === 0) return '未分配'
  const names = ids
    .map((id) => classes.value.find((c) => c.id === id)?.name)
    .filter(Boolean)
  return names.length > 0 ? names.join('、') : '未分配'
})

const completionPct = computed(() =>
  Math.round((validation.value?.completion ?? 0) * 100),
)

const nextStep = computed(() =>
  resolveNextStep(
    projectId.value,
    project.value?.status || 'draft',
    validation.value,
    null,
  ),
)

const editable = computed(() =>
  canEditDesign(project.value?.status || 'draft'),
)

async function loadProject() {
  loading.value = true
  error.value = null
  try {
    const [projRes, valRes] = await Promise.all([
      getProjectApi(projectId.value),
      validateActivationApi(projectId.value).catch(() => null),
    ])
    project.value = projRes.data.data
    if (valRes) validation.value = valRes.data.data
    // 并行加载学科与班级元数据
    const schoolId = userStore.userInfo?.schoolId
    const [subjRes, clsRes] = await Promise.all([
      listSubjectsApi(),
      schoolId
        ? listClassesBySchoolApi(schoolId)
        : Promise.resolve({ data: { data: [] as ClassItem[] } }),
    ])
    subjects.value = subjRes.data.data
    classes.value = (clsRes.data.data as ClassItem[]) || []
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

function goNextStep() {
  if (!nextStep.value.actionable) return
  router.push(nextStep.value.route)
}

function handleNav(name: string) {
  router.push({ name, params: { id: projectId.value } })
}

// 离开保护：加载失败时不阻拦
onBeforeRouteLeave((_to, _from) => {
  // 工作区子路由间切换不拦截；仅在同窗口跳出到非工作区时由各子视图自行提示
  return true
})

onMounted(loadProject)

// 注入给子视图
provide('workspaceProject', project)
provide('workspaceValidation', validation)
provide('workspaceSubjects', subjects)
provide('workspaceClasses', classes)
provide('workspaceEditable', editable)
provide('workspaceReload', loadProject)
</script>

<template>
  <div class="workspace-layout">
    <header class="workspace-header">
      <div class="header-top">
        <el-link
          :underline="false"
          href="#/teacher/projects"
          class="back-link"
        >
          <el-icon><ArrowLeft /></el-icon> 项目列表
        </el-link>
        <h2 class="project-title">{{ project?.title || '加载中…' }}</h2>
      </div>

      <div v-if="project" class="header-meta">
        <el-tag
          size="small"
          :type="(PROJECT_STATUS_TYPES[project.status] as any) || 'info'"
        >
          {{ PROJECT_STATUS_LABELS[project.status] || project.status }}
        </el-tag>
        <span class="meta-item">年级：{{ project.grade || '未设置' }}</span>
        <span class="meta-item">班级：{{ className }}</span>
        <span class="meta-item">核心学科：{{ coreSubjectName }}</span>
        <span class="meta-item">
          完整度：
          <span class="completion">{{ completionPct }}%</span>
        </span>
      </div>

      <div class="header-body">
        <nav class="stage-nav">
          <button
            v-for="item in navItems"
            :key="item.name"
            type="button"
            class="stage-nav-item"
            :class="{ active: activeName === item.name }"
            :disabled="item.disabled"
            @click="handleNav(item.name)"
          >
            {{ item.label }}
          </button>
        </nav>

        <div class="header-actions">
          <el-button
            type="primary"
            :disabled="!nextStep.actionable"
            @click="goNextStep"
          >
            {{ nextStep.label }}
          </el-button>
        </div>
      </div>

      <div v-if="error" class="header-error">
        加载失败：{{ error }}
        <el-button text type="primary" @click="loadProject">重试</el-button>
      </div>
    </header>

    <main class="workspace-content" v-loading="loading">
      <router-view />
    </main>
  </div>
</template>

<style scoped>
.workspace-layout {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #f7f8fa;
}

.workspace-header {
  background: #fff;
  border-bottom: 1px solid #e6e8eb;
  padding: 16px 24px 0;
  flex-shrink: 0;
}

.header-top {
  display: flex;
  align-items: center;
  gap: 12px;
}

.back-link {
  font-size: 13px;
  color: #909399;
}

.project-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}

.header-meta {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 10px;
  font-size: 13px;
  color: #606266;
  flex-wrap: wrap;
}

.meta-item {
  color: #606266;
}

.completion {
  font-weight: 600;
  color: #303133;
}

.header-body {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  margin-top: 16px;
}

.stage-nav {
  display: flex;
  gap: 4px;
}

.stage-nav-item {
  appearance: none;
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  padding: 8px 16px;
  font-size: 14px;
  color: #606266;
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s;
}

.stage-nav-item:hover:not(:disabled) {
  color: #303133;
}

.stage-nav-item.active {
  color: #303133;
  border-bottom-color: #303133;
  font-weight: 500;
}

.stage-nav-item:disabled {
  color: #c0c4cc;
  cursor: not-allowed;
}

.header-actions {
  padding-bottom: 6px;
}

.header-error {
  margin-top: 12px;
  padding: 8px 12px;
  background: #fef0f0;
  color: #f56c6c;
  font-size: 13px;
  border-radius: 4px;
}

.workspace-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
}
</style>
