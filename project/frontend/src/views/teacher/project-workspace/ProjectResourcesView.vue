<script setup lang="ts">
/**
 * ProjectResourcesView - 三级资源页与递进检查（计划 Task 3.5）。
 *
 * - 顶部展示三级递进覆盖检查（foundation/enhancement/extension 是否各有已发布资源）。
 * - 三列布局按层级展示资源，支持按教学阶段过滤。
 * - 教师可新建/编辑资源，含层级、阶段、审核状态、来源等字段。
 * - 审核状态流转通过编辑对话框更新（draft → pending_review → approved → published）。
 * - 历史未分层资源单独一区展示，便于教师补充分层。
 */
import { computed, inject, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createResourceApi,
  deleteResourceApi,
  getResourceTierCoverageApi,
  listResourcesApi,
  updateResourceApi,
} from '@/api/resources'
import { canEditDesign } from '@/features/project-workspace/composables/useProjectWorkspace'
import type {
  Project,
  Resource,
  ResourceTierCoverage,
} from '@/types'

type Ref<T> = import('vue').Ref<T>

const route = useRoute()
const projectId = computed(() => route.params.id as string)
const project = inject<Ref<Project | null>>('workspaceProject')

const editable = computed(() =>
  canEditDesign(project?.value?.status || 'draft'),
)

const resources = ref<Resource[]>([])
const coverage = ref<ResourceTierCoverage | null>(null)
const loading = ref(false)
const stageFilter = ref<string>('') // 空=全部

// ── 常量映射 ───────────────────────────────────────────────
const TIER_LABELS: Record<string, string> = {
  foundation: '基础',
  enhancement: '提升',
  extension: '拓展',
}
const TIER_ORDER = ['foundation', 'enhancement', 'extension']
const STAGE_LABELS: Record<string, string> = {
  pre_class: '课前',
  in_class: '课中',
  post_class: '课后',
}
const STAGE_OPTIONS = [
  { value: '', label: '全部阶段' },
  { value: 'pre_class', label: '课前' },
  { value: 'in_class', label: '课中' },
  { value: 'post_class', label: '课后' },
]
const REVIEW_LABELS: Record<string, string> = {
  draft: '草稿',
  pending_review: '待审核',
  approved: '已通过',
  returned: '已退回',
  published: '已发布',
  archived: '已归档',
}
const REVIEW_TAG_TYPE: Record<string, string> = {
  draft: 'info',
  pending_review: 'warning',
  approved: 'success',
  returned: 'danger',
  published: 'success',
  archived: 'info',
}
const REVIEW_OPTIONS = Object.entries(REVIEW_LABELS).map(([value, label]) => ({
  value,
  label,
}))

// ── 数据加载 ───────────────────────────────────────────────
async function loadAll() {
  loading.value = true
  try {
    const [resRes, covRes] = await Promise.all([
      listResourcesApi({ project_id: projectId.value }),
      getResourceTierCoverageApi(projectId.value),
    ])
    resources.value = resRes.data.data
    coverage.value = covRes.data.data
  } catch (e) {
    ElMessage.error('加载资源失败')
  } finally {
    loading.value = false
  }
}

// ── 分组与过滤 ─────────────────────────────────────────────
const filtered = computed(() => {
  if (!stageFilter.value) return resources.value
  return resources.value.filter((r) => r.stage === stageFilter.value)
})

const byTier = computed(() => {
  const groups: Record<string, Resource[]> = {
    foundation: [],
    enhancement: [],
    extension: [],
  }
  const unassigned: Resource[] = []
  for (const r of filtered.value) {
    if (r.tier && groups[r.tier]) groups[r.tier].push(r)
    else unassigned.push(r)
  }
  return { groups, unassigned }
})

const coverageMissingText = computed(() => {
  if (!coverage.value) return ''
  if (coverage.value.missing.length === 0) return '三级资源已全部覆盖'
  return `缺失层级：${coverage.value.missing.map((m) => TIER_LABELS[m] || m).join('、')}`
})

// ── 新建/编辑对话框 ────────────────────────────────────────
const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const form = ref({
  id: '',
  title: '',
  res_type: 'document',
  url: '',
  tier: '' as string,
  stage: '' as string,
  review_status: 'draft' as string,
  source_type: 'manual' as string,
  source_ref: '',
  usage_tip: '',
  cognitive_level: '',
  reading_level: '',
  prerequisites: '',
})

function openCreate() {
  dialogMode.value = 'create'
  form.value = {
    id: '', title: '', res_type: 'document', url: '',
    tier: '', stage: '', review_status: 'draft',
    source_type: 'manual', source_ref: '', usage_tip: '',
    cognitive_level: '', reading_level: '', prerequisites: '',
  }
  dialogVisible.value = true
}

function openEdit(r: Resource) {
  dialogMode.value = 'edit'
  form.value = {
    id: r.id,
    title: r.title,
    res_type: r.resType,
    url: r.url || '',
    tier: r.tier || '',
    stage: r.stage || '',
    review_status: r.reviewStatus || 'draft',
    source_type: r.sourceType || 'manual',
    source_ref: r.sourceRef || '',
    usage_tip: r.usageTip || '',
    cognitive_level: r.cognitiveLevel || '',
    reading_level: r.readingLevel || '',
    prerequisites: r.prerequisites || '',
  }
  dialogVisible.value = true
}

function buildPayload() {
  const f = form.value
  const payload: Record<string, string | undefined> = {
    title: f.title,
    res_type: f.res_type,
    url: f.url || undefined,
    tier: f.tier || undefined,
    stage: f.stage || undefined,
    review_status: f.review_status,
    source_type: f.source_type || undefined,
    source_ref: f.source_ref || undefined,
    usage_tip: f.usage_tip || undefined,
    cognitive_level: f.cognitive_level || undefined,
    reading_level: f.reading_level || undefined,
    prerequisites: f.prerequisites || undefined,
  }
  return payload
}

async function submitForm() {
  if (!form.value.title.trim()) {
    ElMessage.warning('请填写资源标题')
    return
  }
  try {
    if (dialogMode.value === 'create') {
      await createResourceApi({
        project_id: projectId.value,
        ...buildPayload(),
      } as any)
      ElMessage.success('资源已创建')
    } else {
      await updateResourceApi(form.value.id, buildPayload() as any)
      ElMessage.success('资源已更新')
    }
    dialogVisible.value = false
    await loadAll()
  } catch (e) {
    // 拦截器已提示错误
  }
}

async function removeResource(r: Resource) {
  try {
    await ElMessageBox.confirm(`确认删除资源「${r.title}」？`, '删除确认', {
      type: 'warning',
    })
    await deleteResourceApi(r.id)
    ElMessage.success('已删除')
    await loadAll()
  } catch (e) {
    // 取消或失败
  }
}

onMounted(loadAll)
</script>

<template>
  <div class="resources-view" v-loading="loading">
    <!-- 递进覆盖检查 -->
    <el-card class="coverage-card" shadow="never">
      <template #header>
        <div class="coverage-header">
          <span>三级资源递进覆盖检查</span>
          <el-tag v-if="coverage" size="small" :type="coverage.missing.length === 0 ? 'success' : 'warning'">
            {{ coverageMissingText }}
          </el-tag>
        </div>
      </template>
      <div v-if="coverage" class="coverage-badges">
        <div
          v-for="tier in TIER_ORDER"
          :key="tier"
          class="coverage-badge"
          :class="{ covered: (coverage as any)[tier] }"
        >
          <el-icon v-if="(coverage as any)[tier]"><CircleCheck /></el-icon>
          <el-icon v-else><CircleClose /></el-icon>
          <span class="badge-label">{{ TIER_LABELS[tier] }}</span>
          <span class="badge-count">{{ coverage.counts[tier] || 0 }} 项</span>
        </div>
        <div class="coverage-badge unassigned">
          <span class="badge-label">未分层</span>
          <span class="badge-count">{{ coverage.counts.unassigned || 0 }} 项</span>
        </div>
        <div class="coverage-total">资源总数：{{ coverage.total }}</div>
      </div>
    </el-card>

    <!-- 过滤与操作栏 -->
    <div class="toolbar">
      <el-select v-model="stageFilter" placeholder="按阶段过滤" style="width: 160px">
        <el-option
          v-for="opt in STAGE_OPTIONS"
          :key="opt.value"
          :label="opt.label"
          :value="opt.value"
        />
      </el-select>
      <el-button type="primary" :disabled="!editable" @click="openCreate">
        新建资源
      </el-button>
    </div>

    <!-- 三列布局 -->
    <div class="tier-columns">
      <el-card
        v-for="tier in TIER_ORDER"
        :key="tier"
        class="tier-column"
        :class="tier"
        shadow="never"
      >
        <template #header>
          <div class="tier-header">
            <span>{{ TIER_LABELS[tier] }}</span>
            <el-tag size="small" :type="(coverage && (coverage as any)[tier]) ? 'success' : 'info'">
              {{ (coverage && (coverage as any)[tier]) ? '已覆盖' : '未覆盖' }}
            </el-tag>
          </div>
        </template>
        <div v-if="byTier.groups[tier].length === 0" class="empty-cell">
          暂无{{ TIER_LABELS[tier] }}资源
        </div>
        <div
          v-for="r in byTier.groups[tier]"
          :key="r.id"
          class="resource-card"
        >
          <div class="resource-title">{{ r.title }}</div>
          <div class="resource-meta">
            <el-tag size="small" :type="(REVIEW_TAG_TYPE[r.reviewStatus || 'draft'] as any)">
              {{ REVIEW_LABELS[r.reviewStatus || 'draft'] || r.reviewStatus }}
            </el-tag>
            <span v-if="r.stage" class="meta-text">{{ STAGE_LABELS[r.stage] || r.stage }}</span>
            <span v-if="r.sourceType" class="meta-text">来源：{{ r.sourceType }}</span>
          </div>
          <div v-if="r.usageTip" class="usage-tip">{{ r.usageTip }}</div>
          <div class="resource-actions">
            <el-button text size="small" :disabled="!editable" @click="openEdit(r)">编辑</el-button>
            <el-button text size="small" type="danger" :disabled="!editable" @click="removeResource(r)">删除</el-button>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 未分层资源 -->
    <el-card v-if="byTier.unassigned.length > 0" class="unassigned-card" shadow="never">
      <template #header>未分层资源（历史资源，建议补充分层）</template>
      <div class="unassigned-list">
        <div v-for="r in byTier.unassigned" :key="r.id" class="resource-card inline">
          <span class="resource-title">{{ r.title }}</span>
          <el-tag size="small" :type="(REVIEW_TAG_TYPE[r.reviewStatus || 'draft'] as any)">
            {{ REVIEW_LABELS[r.reviewStatus || 'draft'] || r.reviewStatus }}
          </el-tag>
          <el-button text size="small" :disabled="!editable" @click="openEdit(r)">补充分层</el-button>
        </div>
      </div>
    </el-card>

    <!-- 新建/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogMode === 'create' ? '新建资源' : '编辑资源'"
      width="560px"
    >
      <el-form :model="form" label-width="90px" label-position="right">
        <el-form-item label="标题" required>
          <el-input v-model="form.title" placeholder="资源标题" />
        </el-form-item>
        <el-form-item label="类型">
          <el-input v-model="form.res_type" placeholder="document/video/link..." />
        </el-form-item>
        <el-form-item label="链接">
          <el-input v-model="form.url" placeholder="资源 URL（可选）" />
        </el-form-item>
        <el-form-item label="层级">
          <el-select v-model="form.tier" placeholder="选择层级" clearable style="width: 100%">
            <el-option label="基础" value="foundation" />
            <el-option label="提升" value="enhancement" />
            <el-option label="拓展" value="extension" />
          </el-select>
        </el-form-item>
        <el-form-item label="教学阶段">
          <el-select v-model="form.stage" placeholder="选择阶段" clearable style="width: 100%">
            <el-option label="课前" value="pre_class" />
            <el-option label="课中" value="in_class" />
            <el-option label="课后" value="post_class" />
          </el-select>
        </el-form-item>
        <el-form-item label="审核状态">
          <el-select v-model="form.review_status" style="width: 100%">
            <el-option
              v-for="opt in REVIEW_OPTIONS"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="来源类型">
          <el-select v-model="form.source_type" style="width: 100%">
            <el-option label="手动" value="manual" />
            <el-option label="AI 生成" value="ai" />
            <el-option label="导入" value="imported" />
          </el-select>
        </el-form-item>
        <el-form-item label="出处">
          <el-input v-model="form.source_ref" placeholder="版权/出处（可选）" />
        </el-form-item>
        <el-form-item label="使用建议">
          <el-input v-model="form.usage_tip" type="textarea" :rows="2" placeholder="资源使用建议（可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.resources-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.coverage-card {
  border: 1px solid #e6e8eb;
}

.coverage-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
  color: #303133;
}

.coverage-badges {
  display: flex;
  align-items: center;
  gap: 24px;
  flex-wrap: wrap;
}

.coverage-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: 6px;
  background: #f4f4f5;
  color: #909399;
  font-size: 13px;
}

.coverage-badge.covered {
  background: #f0f9eb;
  color: #67c23a;
}

.coverage-badge.unassigned {
  background: #fdf6ec;
  color: #e6a23c;
}

.badge-label {
  font-weight: 600;
}

.badge-count {
  margin-left: 4px;
  font-size: 12px;
}

.coverage-total {
  margin-left: auto;
  font-size: 13px;
  color: #606266;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.tier-columns {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.tier-column {
  border: 1px solid #e6e8eb;
}

.tier-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
  color: #303133;
}

.empty-cell {
  padding: 24px 0;
  text-align: center;
  color: #c0c4cc;
  font-size: 13px;
}

.resource-card {
  padding: 10px 0;
  border-bottom: 1px solid #f0f0f0;
}

.resource-card:last-child {
  border-bottom: none;
}

.resource-card.inline {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
}

.resource-title {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
  margin-bottom: 6px;
}

.resource-card.inline .resource-title {
  margin-bottom: 0;
  flex: 1;
}

.resource-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #909399;
  flex-wrap: wrap;
}

.meta-text {
  color: #909399;
}

.usage-tip {
  margin-top: 4px;
  font-size: 12px;
  color: #606266;
  background: #f7f8fa;
  padding: 4px 8px;
  border-radius: 4px;
}

.resource-actions {
  margin-top: 6px;
  display: flex;
  gap: 4px;
}

.unassigned-card {
  border: 1px dashed #dcdfe6;
}

.unassigned-list {
  display: flex;
  flex-direction: column;
}

@media (max-width: 1024px) {
  .tier-columns {
    grid-template-columns: 1fr;
  }
}
</style>
