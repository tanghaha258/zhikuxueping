<script setup lang="ts">
/**
 * ProjectOverviewView - 项目总览（计划 3.5.1）。
 *
 * 展示真实问题与成果摘要、学科贡献摘要、资源/任务进度、证据与评价进度、
 * AI 待审核数与阻断问题、下一步建议。
 *
 * 原则：所有数字来自接口；缺失项如实显示"未配置/未采集"，
 * 不按零分伪装为已完成（计划 3.5.1 验收）。
 */
import { computed, inject, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getDesignSnapshotApi } from '@/features/project-workspace/api'
import { listResourcesApi } from '@/api/resources'
import { listTasksApi } from '@/api/tasks'
import type { Project, Task, Resource } from '@/types'
import type {
  ProjectDesignSnapshot,
  ProjectValidationResult,
} from '@/features/project-workspace/types'
import type { SubjectItem } from '@/types'
import { formatDate } from '@/utils/format'

const route = useRoute()
const router = useRouter()
const projectId = computed(() => route.params.id as string)

const project = inject<import('vue').Ref<Project | null>>('workspaceProject')
const validation = inject<import('vue').Ref<ProjectValidationResult | null>>(
  'workspaceValidation',
)
const subjects = inject<import('vue').Ref<SubjectItem[]>>('workspaceSubjects')

const snapshot = ref<ProjectDesignSnapshot | null>(null)
const resources = ref<Resource[]>([])
const tasks = ref<Task[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

const problem = computed(() => snapshot.value?.problem ?? null)
const contributions = computed(() => snapshot.value?.contributions ?? [])
const goals = computed(() => snapshot.value?.goals ?? [])
const indicators = computed(() => snapshot.value?.indicators ?? [])
const evidencePlans = computed(() => snapshot.value?.evidencePlans ?? [])

const coreContribution = computed(() =>
  contributions.value.find((c) => c.role === 'core'),
)
const supportContributions = computed(() =>
  contributions.value.filter((c) => c.role === 'support'),
)

const subjectName = (id?: string | null) =>
  (id && subjects?.value?.find((s) => s.id === id)?.name) || '未指定'

const completionPct = computed(() =>
  Math.round((validation?.value?.completion ?? 0) * 100),
)

const blockers = computed(() => validation?.value?.blockers ?? [])
const warnings = computed(() => validation?.value?.warnings ?? [])

// 证据计划按阶段分组
const evidenceByStage = computed(() => {
  const groups: Record<string, number> = {
    pre_class: 0,
    in_class: 0,
    post_class: 0,
  }
  for (const p of evidencePlans.value) {
    if (groups[p.stage] !== undefined) groups[p.stage]++
  }
  return groups
})

// 现有任务按状态分组（未分层，仅展示已有进度）
const taskByStatus = computed(() => {
  const groups: Record<string, number> = {}
  for (const t of tasks.value) {
    groups[t.status] = (groups[t.status] || 0) + 1
  }
  return groups
})

async function loadOverview() {
  loading.value = true
  error.value = null
  try {
    const [snapRes, resRes, taskRes] = await Promise.all([
      getDesignSnapshotApi(projectId.value),
      listResourcesApi({ project_id: projectId.value }).catch(() => ({
        data: { data: [] as Resource[] },
      })),
      listTasksApi({ project_id: projectId.value }).catch(() => ({
        data: { data: { items: [] as Task[] } },
      })),
    ])
    snapshot.value = snapRes.data.data
    resources.value = (resRes.data.data as Resource[]) || []
    tasks.value = ((taskRes.data.data as { items?: Task[] })?.items) || []
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

function gotoDesign() {
  router.push({
    name: 'ProjectDesign',
    params: { id: projectId.value },
  })
}

onMounted(loadOverview)
</script>

<template>
  <div class="overview" v-loading="loading">
    <div v-if="error" class="error-bar">
      加载失败：{{ error }}
      <el-button text type="primary" @click="loadOverview">重试</el-button>
    </div>

    <!-- 完整度与下一步 -->
    <section class="panel">
      <div class="panel-head">
        <h3 class="panel-title">项目完整度</h3>
        <span class="completion-text">{{ completionPct }}%</span>
      </div>
      <el-progress
        :percentage="completionPct"
        :stroke-width="10"
        :show-text="false"
        color="#5a6"
      />
      <p class="panel-hint">
        完整度 = (7 - 阻断项数) / 7，依据核心学科、支撑学科、真实问题、目标-指标-证据链等 7 项检查。
      </p>
    </section>

    <!-- 真实问题与成果摘要 -->
    <section class="panel">
      <div class="panel-head">
        <h3 class="panel-title">真实问题与成果</h3>
        <el-button text type="primary" @click="gotoDesign">编辑</el-button>
      </div>
      <template v-if="problem">
        <div class="kv"><span class="k">情境</span><span class="v">{{ problem.context || '—' }}</span></div>
        <div class="kv"><span class="k">对象</span><span class="v">{{ problem.object || '—' }}</span></div>
        <div class="kv"><span class="k">受众</span><span class="v">{{ problem.audience || '—' }}</span></div>
        <div class="kv"><span class="k">约束</span><span class="v">{{ problem.constraints || '—' }}</span></div>
        <div class="kv"><span class="k">最终成果</span><span class="v">{{ problem.deliverable || '—' }}</span></div>
        <div class="kv"><span class="k">成果用途</span><span class="v">{{ problem.usage || '—' }}</span></div>
      </template>
      <el-empty v-else description="尚未填写真实问题" :image-size="60" />
    </section>

    <!-- 学科贡献摘要 -->
    <section class="panel">
      <div class="panel-head">
        <h3 class="panel-title">学科贡献</h3>
        <el-button text type="primary" @click="gotoDesign">编辑</el-button>
      </div>
      <div v-if="contributions.length === 0" class="empty-row">尚未配置学科贡献</div>
      <table v-else class="contribution-table">
        <thead>
          <tr>
            <th>角色</th>
            <th>学科</th>
            <th>知识</th>
            <th>思维</th>
            <th>探究</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="c in contributions" :key="c.id">
            <td>
              <el-tag size="small" :type="c.role === 'core' ? 'primary' : 'info'">
                {{ c.role === 'core' ? '核心' : '支撑' }}
              </el-tag>
            </td>
            <td>{{ subjectName(c.subjectId) }}</td>
            <td>{{ c.knowledge || '—' }}</td>
            <td>{{ c.thinking || '—' }}</td>
            <td>{{ c.inquiry || '—' }}</td>
          </tr>
        </tbody>
      </table>
      <div v-if="!coreContribution" class="risk-row">⚠ 缺少核心学科</div>
      <div v-if="supportContributions.length === 0" class="risk-row">⚠ 缺少支撑学科</div>
    </section>

    <!-- 三级资源覆盖情况 -->
    <section class="panel">
      <div class="panel-head">
        <h3 class="panel-title">资源覆盖</h3>
      </div>
      <div class="stat-row">
        <div class="stat">
          <span class="stat-num">{{ resources.length }}</span>
          <span class="stat-label">现有资源（未分层）</span>
        </div>
        <div class="stat">
          <span class="stat-num muted">—</span>
          <span class="stat-label">基础层</span>
        </div>
        <div class="stat">
          <span class="stat-num muted">—</span>
          <span class="stat-label">提升层</span>
        </div>
        <div class="stat">
          <span class="stat-num muted">—</span>
          <span class="stat-label">拓展层</span>
        </div>
      </div>
      <p class="panel-hint">资源分层与递进检查将在 Task 3 实现。</p>
    </section>

    <!-- 三阶段任务进度 -->
    <section class="panel">
      <div class="panel-head">
        <h3 class="panel-title">任务进度</h3>
      </div>
      <div class="stat-row">
        <div class="stat">
          <span class="stat-num">{{ tasks.length }}</span>
          <span class="stat-label">现有任务（未分阶段）</span>
        </div>
        <div class="stat">
          <span class="stat-num muted">—</span>
          <span class="stat-label">课前</span>
        </div>
        <div class="stat">
          <span class="stat-num muted">—</span>
          <span class="stat-label">课中</span>
        </div>
        <div class="stat">
          <span class="stat-num muted">—</span>
          <span class="stat-label">课后</span>
        </div>
      </div>
      <div v-if="tasks.length > 0" class="task-status-row">
        <span class="task-status-label">按状态：</span>
        <span v-for="(cnt, st) in taskByStatus" :key="st" class="task-status-chip">
          {{ st }}：{{ cnt }}
        </span>
      </div>
      <p class="panel-hint">任务三阶段划分将在 Task 3 实现。</p>
    </section>

    <!-- 证据采集与评价进度 -->
    <section class="panel">
      <div class="panel-head">
        <h3 class="panel-title">证据与评价</h3>
      </div>
      <div class="stat-row">
        <div class="stat">
          <span class="stat-num">{{ goals.length }}</span>
          <span class="stat-label">学习目标</span>
        </div>
        <div class="stat">
          <span class="stat-num">{{ indicators.length }}</span>
          <span class="stat-label">评价指标</span>
        </div>
        <div class="stat">
          <span class="stat-num">{{ evidencePlans.length }}</span>
          <span class="stat-label">证据计划</span>
        </div>
      </div>
      <div class="evidence-stage-row">
        <span>课前证据：{{ evidenceByStage.pre_class }}</span>
        <span>课中证据：{{ evidenceByStage.in_class }}</span>
        <span>课后证据：{{ evidenceByStage.post_class }}</span>
      </div>
      <div v-if="evidencePlans.length === 0" class="risk-row">
        ⚠ 尚无证据计划，缺失证据将显示"未采集"，不计为零分
      </div>
    </section>

    <!-- 阻断与警告 -->
    <section class="panel" v-if="blockers.length > 0 || warnings.length > 0">
      <div class="panel-head">
        <h3 class="panel-title">问题清单</h3>
      </div>
      <ul class="issue-list">
        <li
          v-for="b in blockers"
          :key="'b-' + b.code"
          class="issue-item blocker"
        >
          <el-tag size="small" type="danger">阻断</el-tag>
          <span class="issue-field">{{ b.field }}</span>
          <span class="issue-msg">{{ b.message }}</span>
        </li>
        <li
          v-for="w in warnings"
          :key="'w-' + w.code"
          class="issue-item warning"
        >
          <el-tag size="small" type="warning">警告</el-tag>
          <span class="issue-field">{{ w.field }}</span>
          <span class="issue-msg">{{ w.message }}</span>
        </li>
      </ul>
    </section>

    <p v-if="project?.createdAt" class="footer-meta">
      项目创建于 {{ formatDate(project.createdAt, 'YYYY-MM-DD HH:mm') }}
    </p>
  </div>
</template>

<style scoped>
.overview {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 1080px;
}

.error-bar {
  padding: 8px 12px;
  background: #fef0f0;
  color: #f56c6c;
  font-size: 13px;
  border-radius: 4px;
}

.panel {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 16px 20px;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.panel-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.completion-text {
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}

.panel-hint {
  margin: 8px 0 0;
  font-size: 12px;
  color: #909399;
}

.kv {
  display: grid;
  grid-template-columns: 80px 1fr;
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

.contribution-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.contribution-table th,
.contribution-table td {
  border: 1px solid #ebeef5;
  padding: 8px 10px;
  text-align: left;
}

.contribution-table th {
  background: #fafbfc;
  color: #606266;
  font-weight: 500;
}

.empty-row,
.risk-row {
  font-size: 13px;
  color: #909399;
  padding: 6px 0;
}

.risk-row {
  color: #e6a23c;
}

.stat-row {
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
}

.stat {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}

.stat-num {
  font-size: 22px;
  font-weight: 600;
  color: #303133;
}

.stat-num.muted {
  color: #c0c4cc;
}

.stat-label {
  font-size: 12px;
  color: #909399;
  margin-top: 2px;
}

.task-status-row {
  margin-top: 10px;
  font-size: 12px;
  color: #606266;
}

.task-status-chip {
  margin-left: 8px;
  padding: 2px 8px;
  background: #f4f4f5;
  border-radius: 10px;
}

.evidence-stage-row {
  margin-top: 10px;
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #606266;
}

.issue-list {
  list-style: none;
  margin: 0;
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
}

.issue-msg {
  color: #303133;
}

.footer-meta {
  font-size: 12px;
  color: #c0c4cc;
  text-align: right;
}
</style>
