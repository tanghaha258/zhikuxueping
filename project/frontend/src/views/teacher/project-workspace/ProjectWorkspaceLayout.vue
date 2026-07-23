<script setup lang="ts">
/**
 * ProjectWorkspaceLayout - 项目工作区外壳（Task 4 重写）。
 *
 * 设计要点（计划 Task 4 Step 3 / 规格 §5.2）：
 * - 复用 Task 1 的 PageHeader、ProjectPhaseStepper、AsyncState。
 * - 通过 Task 3 的 project-context store 读取项目、阶段、权限和唯一主操作；
 *   上下文在本外壳加载一次，子页共享，不重复请求项目详情。
 * - 顶部固定项目状态、班级、阶段和唯一主操作；归档时全部编辑动作只读。
 * - 为兼容尚未迁移的旧子页（ProjectOverviewView/ProjectDesignView 等，归后续 Task），
 *   保留 workspace* provide/inject 合同，但数据源改为 store 派生，
 *   不再单独调用 getProjectApi/validateActivationApi。
 */
import { computed, onMounted, onBeforeUnmount, provide, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useProjectContextStore } from '@/features/project-context/store'
import type {
  PhaseKey,
  PhaseStatus,
  ProjectWorkspacePhase,
} from '@/features/project-context/types'
import PageHeader from '@/shared/ui/PageHeader.vue'
import ProjectPhaseStepper from '@/shared/ui/ProjectPhaseStepper.vue'
import AsyncState from '@/shared/ui/AsyncState.vue'
import { listSubjectsApi } from '@/api/subjects'
import { listClassesBySchoolApi } from '@/api/schools'
import { useUserStore } from '@/stores/user'
import type { Project, SubjectItem, ClassItem } from '@/types'
import type { ProjectValidationResult } from '@/features/project-workspace/types'
import { PROJECT_STATUS_LABELS } from '@/utils/constants'

// ── 路由与 store ───────────────────────────────────────────────
const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const store = useProjectContextStore()

const projectId = computed(() => route.params.id as string)

// ── 阶段固定映射（与后端 PHASE_ORDER 单一来源一致）──────────────
const PHASE_LABELS: Record<PhaseKey, string> = {
  diagnosis: '学情诊断',
  design: '跨学科设计',
  preparation: '备课与资源',
  implementation: '教学实施',
  evaluation: '评价与反馈',
  improvement: '改进与再评价',
  closure: '结项',
}

/** 阶段 → 项目工作区路由名映射；用于阶段导航点击。 */
const PHASE_ROUTE_NAME: Record<PhaseKey, string> = {
  diagnosis: 'ProjectDiagnosis',
  design: 'ProjectDesign',
  preparation: 'ProjectPreparation',
  implementation: 'ProjectTaskChain',
  evaluation: 'ProjectEvaluation',
  improvement: 'ProjectInsights',
  closure: 'ProjectClosure',
}

function mapPhaseStatus(
  status: PhaseStatus,
): 'done' | 'current' | 'warning' | 'blocked' | 'pending' {
  switch (status) {
    case 'completed':
      return 'done'
    case 'in_progress':
      return 'current'
    case 'blocked':
      return 'blocked'
    default:
      return 'pending'
  }
}

// ── 学校级元数据（学科、班级），非项目详情，独立加载一次 ─────────
const subjects = ref<SubjectItem[]>([])
const classes = ref<ClassItem[]>([])

async function loadSchoolMeta() {
  const schoolId = userStore.userInfo?.schoolId
  const [subjRes, clsRes] = await Promise.all([
    listSubjectsApi().catch(() => ({ data: { data: [] as SubjectItem[] } })),
    schoolId
      ? listClassesBySchoolApi(schoolId).catch(() => ({ data: { data: [] as ClassItem[] } }))
      : Promise.resolve({ data: { data: [] as ClassItem[] } }),
  ])
  subjects.value = subjRes.data.data
  classes.value = (clsRes.data.data as ClassItem[]) || []
}

// ── 上下文加载（唯一项目详情请求）──────────────────────────────
async function loadContext() {
  if (!projectId.value) return
  await store.loadContext(projectId.value)
}

async function reloadAll() {
  await Promise.all([store.refreshContext(), loadSchoolMeta()])
}

onMounted(async () => {
  await Promise.all([loadContext(), loadSchoolMeta()])
})

watch(projectId, (next, prev) => {
  if (next && next !== prev) {
    loadContext()
  }
})

onBeforeUnmount(() => {
  // 离开项目工作区时清空上下文缓存，避免回到列表后残留
  store.clear()
})

// ── 派生状态 ───────────────────────────────────────────────────
const context = computed(() => store.currentContext)
const loading = computed(() => store.loading)
const errorState = computed(() => store.error)

const asyncState = computed<'loading' | 'ready' | 'empty' | 'error' | 'forbidden'>(() => {
  if (loading.value && !context.value) return 'loading'
  if (errorState.value?.forbidden) return 'forbidden'
  if (errorState.value && !context.value) return 'error'
  if (!context.value) return 'loading'
  return 'ready'
})

const errorMessage = computed(() => {
  if (!errorState.value) return ''
  if (errorState.value.notFound) return '项目不存在或已删除'
  return errorState.value.message || '加载失败'
})

// ── 项目摘要与顶部信息 ─────────────────────────────────────────
const project = computed(() => context.value?.project ?? null)
const projectTitle = computed(() => project.value?.title || '项目工作区')
const projectStatusLabel = computed(
  () => PROJECT_STATUS_LABELS[project.value?.status ?? ''] || project.value?.status || '—',
)
const projectStatusTone = computed<'primary' | 'success' | 'warning' | 'danger' | 'muted'>(() => {
  switch (project.value?.status) {
    case 'active':
      return 'primary'
    case 'completed':
      return 'success'
    case 'pending_review':
      return 'warning'
    case 'archived':
      return 'muted'
    default:
      return 'muted'
  }
})

const className = computed(() => {
  const ids = project.value?.classIds || []
  if (ids.length === 0) return '未分配'
  const names = ids
    .map((id) => classes.value.find((c) => c.id === id)?.name)
    .filter(Boolean)
  return names.length > 0 ? names.join('、') : '未分配'
})

const gradeName = computed(() => project.value?.grade || '未设置')

const activePhase = computed<ProjectWorkspacePhase | null>(() => store.activePhase ?? null)
const activePhaseLabel = computed(() => {
  if (!activePhase.value) return '全部阶段已完成'
  return PHASE_LABELS[activePhase.value.phase] ?? activePhase.value.phase
})

// ── 阶段步进器 ─────────────────────────────────────────────────
const stepperPhases = computed(() => {
  const ctx = context.value
  if (!ctx) return []
  return ctx.phases.map((p) => ({
    key: p.phase,
    label: PHASE_LABELS[p.phase] ?? p.phase,
    status: mapPhaseStatus(p.status),
  }))
})

function handlePhaseSelect(key: string) {
  if (!projectId.value) return
  const phase = key as PhaseKey
  const routeName = PHASE_ROUTE_NAME[phase]
  if (routeName) {
    router.push({ name: routeName, params: { id: projectId.value } })
  }
}

// ── 唯一主操作 ─────────────────────────────────────────────────
const primaryAction = computed(() => store.primaryAction)
const primaryLabel = computed(() => {
  if (store.isArchived) return ''
  return primaryAction.value?.label || ''
})

function handlePrimary() {
  const action = primaryAction.value
  if (!action || store.isArchived) return
  if (action.route) {
    router.push(action.route)
  }
}

// ── 归档只读 ───────────────────────────────────────────────────
const archived = computed(() => store.isArchived)

// ── 兼容旧子页 provide/inject 合同 ─────────────────────────────
// 旧子页（ProjectOverviewView/ProjectDesignView 等）inject workspace* Ref；
// 数据源统一从 store 派生，不再单独请求 getProjectApi/validateActivationApi。
const workspaceProject = computed<Project | null>(() => {
  const p = project.value
  if (!p) return null
  return {
    id: p.id,
    title: p.title,
    description: p.description ?? undefined,
    status: p.status,
    creatorId: p.creatorId,
    schoolId: p.schoolId ?? undefined,
    grade: p.grade ?? undefined,
    startDate: p.startDate ?? undefined,
    endDate: p.endDate ?? undefined,
    isTemplate: false,
    createdAt: p.createdAt ?? undefined,
    subjectIds: p.subjectIds,
    classIds: p.classIds,
    projectType: p.projectType ?? undefined,
    coreSubjectId: p.coreSubjectId ?? undefined,
    reviewStatus: p.reviewStatus ?? undefined,
  }
})

const workspaceValidation = computed<ProjectValidationResult | null>(() => {
  const ctx = context.value
  if (!ctx) return null
  const total = ctx.phases.length
  const completed = ctx.phases.filter((p) => p.status === 'completed').length
  return {
    canActivate: ctx.blockers.length === 0,
    blockers: ctx.blockers.map((b) => ({ code: b.code, field: b.field, message: b.message })),
    warnings: ctx.warnings.map((w) => ({ code: w.code, field: w.field, message: w.message })),
    completion: total > 0 ? completed / total : 0,
    details: {},
  }
})

const workspaceEditable = computed(() => store.canManage && !store.isArchived)

provide('workspaceProject', workspaceProject)
provide('workspaceValidation', workspaceValidation)
provide('workspaceSubjects', subjects)
provide('workspaceClasses', classes)
provide('workspaceEditable', workspaceEditable)
provide('workspaceReload', reloadAll)
</script>

<template>
  <div class="workspace-layout" data-ui="project-workspace">
    <!-- 顶部：项目状态、班级、阶段、唯一主操作（固定） -->
    <header class="workspace-header">
      <PageHeader
        :title="projectTitle"
        :status="{ label: projectStatusLabel, tone: projectStatusTone }"
        :primary-label="primaryLabel"
        :breadcrumbs="[
          { label: '智跨学评' },
          { label: '我的跨学科项目', to: '/teacher/projects' },
        ]"
        @primary="handlePrimary"
      />

      <!-- 上下文条：班级、年级、当前阶段；归档提示 -->
      <div class="workspace-context-bar">
        <div class="workspace-context-bar__group">
          <span class="workspace-context-bar__item">
            <span class="workspace-context-bar__k">班级</span>
            <span class="workspace-context-bar__v">{{ className }}</span>
          </span>
          <span class="workspace-context-bar__item">
            <span class="workspace-context-bar__k">年级</span>
            <span class="workspace-context-bar__v">{{ gradeName }}</span>
          </span>
          <span class="workspace-context-bar__item">
            <span class="workspace-context-bar__k">当前阶段</span>
            <span class="workspace-context-bar__v">{{ activePhaseLabel }}</span>
          </span>
        </div>
        <span v-if="archived" class="workspace-context-bar__archived" role="status">
          项目已归档，全部内容只读
        </span>
      </div>

      <!-- 阶段步进器 -->
      <div v-if="stepperPhases.length" class="workspace-stepper">
        <ProjectPhaseStepper
          :phases="stepperPhases"
          @select="handlePhaseSelect"
        />
      </div>
    </header>

    <!-- 主内容：AsyncState 包裹 router-view，统一 loading/error/forbidden/ready -->
    <main class="workspace-content">
      <AsyncState
        :state="asyncState"
        :message="errorMessage"
        @retry="reloadAll"
      >
        <router-view />
      </AsyncState>
    </main>
  </div>
</template>

<style scoped>
.workspace-layout {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--ui-bg-app, #f4f6f8);
}

.workspace-header {
  background: var(--ui-bg-surface, #fff);
  border-bottom: 1px solid var(--ui-border, #d9dee5);
  padding: var(--ui-space-4, 16px) var(--ui-space-6, 24px) var(--ui-space-3, 12px);
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: var(--ui-space-3, 12px);
}

.workspace-context-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ui-space-3, 12px);
  flex-wrap: wrap;
}

.workspace-context-bar__group {
  display: flex;
  align-items: center;
  gap: var(--ui-space-6, 24px);
  flex-wrap: wrap;
}

.workspace-context-bar__item {
  display: inline-flex;
  align-items: baseline;
  gap: var(--ui-space-1, 4px);
  font-size: var(--ui-font-size-sm, 14px);
}

.workspace-context-bar__k {
  color: var(--ui-text-muted, #7b8794);
  font-size: var(--ui-font-size-xs, 12px);
}

.workspace-context-bar__v {
  color: var(--ui-text-primary, #1f2933);
  font-weight: 500;
}

.workspace-context-bar__archived {
  font-size: var(--ui-font-size-xs, 12px);
  padding: 2px var(--ui-space-2, 8px);
  border-radius: var(--ui-radius-sm, 4px);
  background: var(--ui-bg-subtle, #f8f9fb);
  color: var(--ui-text-muted, #7b8794);
  border: 1px solid var(--ui-border, #d9dee5);
}

.workspace-stepper {
  overflow-x: auto;
}

.workspace-content {
  flex: 1;
  overflow-y: auto;
  padding: var(--ui-space-6, 24px);
}
</style>
