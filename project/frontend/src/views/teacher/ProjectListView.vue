<script setup lang="ts">
/**
 * ProjectListView - 项目列表（计划 3.3）。
 *
 * 筛选条件写入 URL（刷新保留）；分页来自服务端；行级主操作为"继续"。
 * 完整度按页并行调用 validate-activation 获取真实数值（不写死、不伪造）；
 * 核心学科来自列表接口新增的 core_subject_id 字段。
 */
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listProjectsApi, deleteProjectApi } from '@/api/projects'
import { listSubjectsApi } from '@/api/subjects'
import { validateActivationApi } from '@/features/project-workspace/api'
import type { Project, SubjectItem } from '@/types'
import {
  PROJECT_STATUS_LABELS,
  PROJECT_STATUS_TYPES,
} from '@/utils/constants'
import { formatDate } from '@/utils/format'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const projects = ref<Project[]>([])
const total = ref(0)
const subjects = ref<SubjectItem[]>([])

// 筛选条件同步到 URL query
const page = ref(Number(route.query.page) || 1)
const pageSize = ref(10)
const searchKey = ref((route.query.keyword as string) || '')
const statusFilter = ref((route.query.status as string) || '')
const gradeFilter = ref((route.query.grade as string) || '')

const completionMap = ref<Record<string, number>>({})

const statusOptions = [
  { value: '', label: '全部状态' },
  { value: 'draft', label: '草稿' },
  { value: 'pending_review', label: '待审核' },
  { value: 'active', label: '进行中' },
  { value: 'completed', label: '已完成' },
  { value: 'archived', label: '已归档' },
]

const gradeOptions = [
  { value: '', label: '全部年级' },
  { value: '七年级', label: '七年级' },
  { value: '八年级', label: '八年级' },
  { value: '九年级', label: '九年级' },
]

function subjectName(id?: string) {
  if (!id) return '—'
  return subjects.value.find((s) => s.id === id)?.name || id
}

function syncQuery() {
  router.replace({
    query: {
      page: page.value || undefined,
      keyword: searchKey.value || undefined,
      status: statusFilter.value || undefined,
      grade: gradeFilter.value || undefined,
    },
  })
}

async function fetchProjects() {
  loading.value = true
  completionMap.value = {}
  try {
    const res = await listProjectsApi({
      skip: (page.value - 1) * pageSize.value,
      limit: pageSize.value,
      keyword: searchKey.value,
      status: statusFilter.value,
      grade: gradeFilter.value,
    })
    const data = res.data.data
    projects.value = data.items
    total.value = data.total

    // 按页并行获取完整度（真实数据，不伪造）
    const results = await Promise.allSettled(
      data.items.map((p: Project) => validateActivationApi(p.id)),
    )
    results.forEach((r, idx) => {
      const pid = data.items[idx]?.id
      if (!pid) return
      if (r.status === 'fulfilled') {
        completionMap.value[pid] = Math.round(
          (r.value.data.data.completion ?? 0) * 100,
        )
      }
    })
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  syncQuery()
  fetchProjects()
}

function handlePageChange(p: number) {
  page.value = p
  syncQuery()
  fetchProjects()
}

function gotoWizard() {
  router.push({ name: 'ProjectCreateWizard' })
}

function continueProject(id: string) {
  router.push({ name: 'ProjectOverview', params: { id } })
}

async function handleDelete(project: Project) {
  if (project.status !== 'draft') {
    ElMessage.warning('仅草稿项目可删除，已有任务或评价的项目不可直接删除')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定删除草稿项目「${project.title}」？此操作不可恢复。`,
      '确认删除',
      { type: 'warning' },
    )
    await deleteProjectApi(project.id)
    ElMessage.success('删除成功')
    fetchProjects()
  } catch {
    // cancelled
  }
}

watch(
  () => route.query,
  (q) => {
    page.value = Number(q.page) || 1
    searchKey.value = (q.keyword as string) || ''
    statusFilter.value = (q.status as string) || ''
    gradeFilter.value = (q.grade as string) || ''
  },
)

onMounted(async () => {
  listSubjectsApi().then((res) => {
    subjects.value = res.data.data
  })
  fetchProjects()
})
</script>

<template>
  <div class="page-container">
    <div class="flex-between" style="margin-bottom: 16px;">
      <h2 class="page-title" style="margin-bottom: 0;">跨学科项目</h2>
      <el-button type="primary" :icon="Plus" @click="gotoWizard">创建项目</el-button>
    </div>

    <div class="search-bar">
      <el-input
        v-model="searchKey"
        placeholder="搜索项目名称..."
        :prefix-icon="Search"
        clearable
        style="width: 240px"
        @keyup.enter="handleSearch"
        @clear="handleSearch"
      />
      <el-select v-model="statusFilter" placeholder="项目状态" style="width: 130px" @change="handleSearch">
        <el-option v-for="opt in statusOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
      </el-select>
      <el-select v-model="gradeFilter" placeholder="年级" style="width: 130px" @change="handleSearch">
        <el-option v-for="opt in gradeOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
      </el-select>
      <el-button :icon="Refresh" @click="handleSearch">刷新</el-button>
    </div>

    <el-card shadow="never" style="border-radius: 8px;">
      <el-table :data="projects" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="title" label="项目名称" min-width="200">
          <template #default="{ row }">
            <el-link type="primary" :underline="false" @click="continueProject(row.id)">
              {{ row.title }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column label="核心学科" width="110">
          <template #default="{ row }">
            {{ subjectName(row.coreSubjectId) }}
          </template>
        </el-table-column>
        <el-table-column prop="grade" label="年级" width="90" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="(PROJECT_STATUS_TYPES[row.status] as any) || 'info'" size="small">
              {{ PROJECT_STATUS_LABELS[row.status] || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="完整度" width="100">
          <template #default="{ row }">
            <span v-if="completionMap[row.id] !== undefined">
              {{ completionMap[row.id] }}%
            </span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="createdAt" label="创建时间" width="120">
          <template #default="{ row }">
            {{ row.createdAt ? formatDate(row.createdAt, 'YYYY-MM-DD') : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="continueProject(row.id)">
              继续
            </el-button>
            <el-button
              text
              type="danger"
              size="small"
              :disabled="row.status !== 'draft'"
              @click="handleDelete(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <div v-if="!loading && projects.length === 0" class="empty-state">
        <el-empty description="暂无项目，点击右上角创建">
          <el-button type="primary" @click="gotoWizard">创建项目</el-button>
        </el-empty>
      </div>
      <div style="display: flex; justify-content: flex-end; margin-top: 16px;">
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="total"
          layout="prev, pager, next, total"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.muted {
  color: #c0c4cc;
}
.empty-state {
  padding: 32px 0;
}
</style>
