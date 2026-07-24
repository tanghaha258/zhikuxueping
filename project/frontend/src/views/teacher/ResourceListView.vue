<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Upload, Delete, Document, VideoCamera, Picture, Link, Connection } from '@element-plus/icons-vue'
import { listResourcesApi, createResourceApi, deleteResourceApi } from '@/api/resources'
import { listProjectsApi } from '@/api/projects'
import { uploadFileApi } from '@/api/upload'
import { linkContextApi, listContextLinksByArtifactApi, type ContextLink } from '@/features/tool-context/api'
import { validateToolContext, type ProjectPhase, type ToolContext } from '@/features/tool-context/types'
import type { Resource, Project } from '@/types'
import { formatDate } from '@/utils/format'

const resources = ref<Resource[]>([])
const projects = ref<Project[]>([])
const loading = ref(false)
const activeType = ref('all')
const searchKeyword = ref('')

// ── Task 8：工具上下文（独立 / 关联项目）─────────────────────────
// 独立工具页默认 independent；教师可切换为 project 模式查看项目资源并上传带项目的资源。
// 独立资源可通过"加入项目"操作建立一条 resource 引用，不复制资产本体。
const context = ref<ToolContext>({ mode: 'independent' })
const joinDialog = ref(false)
const joinTarget = ref<Resource | null>(null)
const joinProjectId = ref('')
const joinPhase = ref<ProjectPhase>('preparation')
const joining = ref(false)

const isProjectMode = computed(() => context.value.mode === 'project')
const contextValidation = computed(() => validateToolContext(context.value))
/** 列表筛选与上传关联都跟随当前上下文模式。 */
const selectedProjectId = computed(() =>
  isProjectMode.value && contextValidation.value.valid
    ? (context.value as Extract<ToolContext, { mode: 'project' }>).projectId
    : '',
)

function switchMode(mode: 'independent' | 'project') {
  if (mode === 'independent') {
    context.value = { mode: 'independent' }
  } else {
    context.value = { mode: 'project', projectId: '', phase: 'preparation' }
  }
  fetchResources()
}

function onProjectChange(projectId: string) {
  if (context.value.mode === 'project') {
    context.value = { ...context.value, projectId }
    fetchResources()
  }
}

const uploadDialog = ref(false)
const uploadRef = ref()
const uploadTitle = ref('')
const uploadResType = ref('document')
const uploadUrl = ref('')
const selectedFile = ref<File | null>(null)
const uploading = ref(false)
const uploadProgress = ref(0)

const typeLabel: Record<string, string> = {
  document: '文档',
  video: '视频',
  image: '图片',
  link: '链接',
  other: '其他',
}

const typeColors: Record<string, string> = {
  document: '#409EFF',
  video: '#9B59B6',
  image: '#67C23A',
  link: '#00BCD4',
  other: '#909399',
}

const filteredResources = computed(() => {
  let list = resources.value
  if (activeType.value !== 'all') {
    list = list.filter((r) => r.resType === activeType.value)
  }
  if (searchKeyword.value) {
    const kw = searchKeyword.value.toLowerCase()
    list = list.filter((r) => r.title.toLowerCase().includes(kw))
  }
  return list
})

function formatSize(bytes?: number): string {
  if (bytes == null) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function getResourceIcon(type: string) {
  switch (type) {
    case 'document': return Document
    case 'video': return VideoCamera
    case 'image': return Picture
    default: return Link
  }
}

async function fetchProjects() {
  try {
    const res = await listProjectsApi({ limit: 200 })
    projects.value = res.data.data.items
  } catch {
    /* handled by interceptor */
  }
}

async function fetchResources() {
  loading.value = true
  try {
    const params: { project_id?: string } = {}
    if (selectedProjectId.value) {
      params.project_id = selectedProjectId.value
    }
    const res = await listResourcesApi(params)
    resources.value = res.data.data
  } catch {
    resources.value = []
  } finally {
    loading.value = false
  }
}

function beforeUploadCheck(file: File): boolean {
  if (file.size > 10 * 1024 * 1024) {
    ElMessage.warning('文件大小不能超过 10MB')
    return false
  }
  return true
}

function onFileChange(uploadFile: any, uploadFiles: any[]) {
  const raw = uploadFile.raw
  if (raw instanceof File) {
    if (!beforeUploadCheck(raw)) {
      uploadRef.value?.clearFiles()
      return
    }
    selectedFile.value = raw
  } else if (uploadFiles.length === 0) {
    selectedFile.value = null
  }
}

function onFileRemove() {
  selectedFile.value = null
}

function resetUploadForm() {
  uploadTitle.value = ''
  uploadResType.value = 'document'
  uploadUrl.value = ''
  selectedFile.value = null
  uploadProgress.value = 0
  uploadRef.value?.clearFiles()
}

async function handleUpload() {
  if (!uploadTitle.value) {
    ElMessage.warning('请输入资源标题')
    return
  }
  if (uploadResType.value === 'link') {
    if (!uploadUrl.value) {
      ElMessage.warning('请输入资源链接')
      return
    }
  } else if (!selectedFile.value) {
    ElMessage.warning('请选择文件')
    return
  }

  uploading.value = true
  uploadProgress.value = 0
  try {
    let url = ''
    if (uploadResType.value === 'link') {
      url = uploadUrl.value
    } else {
      const res = await uploadFileApi(selectedFile.value!, (pct) => {
        uploadProgress.value = pct
      })
      url = res.data.data.url
    }

    await createResourceApi({
      project_id: selectedProjectId.value || undefined,
      title: uploadTitle.value,
      res_type: uploadResType.value,
      url: url || undefined,
    })

    ElMessage.success('上传成功')
    uploadDialog.value = false
    resetUploadForm()
    fetchResources()
  } catch {
    /* handled by interceptor */
  } finally {
    uploading.value = false
  }
}

async function handleDelete(id: string) {
  try {
    await ElMessageBox.confirm('确定要删除此资源吗？删除后不可恢复。', '删除确认', {
      type: 'warning',
      confirmButtonText: '确认删除',
      cancelButtonText: '取消',
    })
    await deleteResourceApi(id)
    ElMessage.success('删除成功')
    fetchResources()
  } catch {
    /* cancelled or handled by interceptor */
  }
}

// ── Task 8：独立资源加入项目（只建引用，不复制资产）──────────────
function openJoinDialog(resource: Resource) {
  joinTarget.value = resource
  joinProjectId.value = ''
  joinPhase.value = 'preparation'
  joinDialog.value = true
}

async function confirmJoin() {
  if (!joinTarget.value) return
  if (!joinProjectId.value) {
    ElMessage.warning('请选择要加入的项目')
    return
  }
  joining.value = true
  try {
    await linkContextApi('resource', joinTarget.value.id, {
      mode: 'project',
      projectId: joinProjectId.value,
      phase: joinPhase.value,
    })
    ElMessage.success('资源已加入项目，资产本体保留')
    joinDialog.value = false
  } catch {
    ElMessage.error('加入项目失败，请确认是否有该项目权限')
  } finally {
    joining.value = false
  }
}

onMounted(() => {
  fetchProjects()
  fetchResources()
})
</script>

<template>
  <div class="page-container">
    <div class="flex-between" style="margin-bottom: 20px;">
      <h2 class="page-title" style="margin-bottom: 0;">资源中心</h2>
      <el-button type="primary" :icon="Upload" @click="uploadDialog = true">
        上传资源
      </el-button>
    </div>

    <!-- Task 8：上下文选择条。独立模式列出独立资源；项目模式锁定到指定项目。 -->
    <div class="context-bar" data-ui="resource-context-bar">
      <el-radio-group :model-value="context.mode" @change="switchMode">
        <el-radio-button value="independent">独立资源</el-radio-button>
        <el-radio-button value="project">关联项目</el-radio-button>
      </el-radio-group>
      <template v-if="isProjectMode">
        <el-select
          :model-value="(context as any).projectId"
          placeholder="选择项目"
          style="width: 220px"
          @change="onProjectChange"
        >
          <el-option v-for="p in projects" :key="p.id" :label="p.title" :value="p.id" />
        </el-select>
        <span v-if="!contextValidation.valid" class="context-bar__error">
          {{ contextValidation.error }}
        </span>
      </template>
      <span v-else class="context-bar__hint">独立资源不归属项目，可稍后加入项目</span>
    </div>

    <div class="search-bar">
      <el-input
        v-model="searchKeyword"
        placeholder="搜索资源名称..."
        :prefix-icon="Search"
        clearable
        style="width: 280px"
      />
    </div>

    <el-card shadow="never">
      <el-tabs v-model="activeType" style="margin-bottom: 12px;">
        <el-tab-pane label="全部" name="all" />
        <el-tab-pane label="文档" name="document" />
        <el-tab-pane label="视频" name="video" />
        <el-tab-pane label="图片" name="image" />
        <el-tab-pane label="链接" name="link" />
      </el-tabs>

      <el-table :data="filteredResources" v-loading="loading" stripe style="width: 100%">
        <el-table-column label="资源名称" min-width="240">
          <template #default="{ row }">
            <div class="flex" style="align-items: center; gap: 8px;">
              <el-icon :size="18" :color="typeColors[row.resType] || '#909399'">
                <component :is="getResourceIcon(row.resType)" />
              </el-icon>
              <el-link type="primary" :underline="false" :href="row.url" :disabled="!row.url" target="_blank">
                {{ row.title }}
              </el-link>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="100">
          <template #default="{ row }">
            <el-tag
              :style="{
                background: (typeColors[row.resType] || '#909399') + '18',
                color: typeColors[row.resType] || '#909399',
                borderColor: (typeColors[row.resType] || '#909399') + '30',
              }"
              size="small"
              effect="plain"
            >
              {{ typeLabel[row.resType] || row.resType }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="uploadedBy" label="上传者" width="120" />
        <el-table-column label="上传时间" width="170">
          <template #default="{ row }">
            {{ formatDate(row.createdAt, 'YYYY-MM-DD HH:mm') }}
          </template>
        </el-table-column>
        <el-table-column label="大小" width="100">
          <template #default="{ row }">
            {{ formatSize(row.fileSize) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="!isProjectMode"
              text
              type="primary"
              size="small"
              :icon="Connection"
              @click="openJoinDialog(row)"
            >加入项目</el-button>
            <el-button text type="danger" size="small" :icon="Delete" @click="handleDelete(row.id)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="!loading && filteredResources.length === 0" class="empty-state">
        <el-empty description="暂无资源" />
      </div>
    </el-card>

    <el-dialog v-model="uploadDialog" title="上传资源" width="520px" :close-on-click-modal="false" @closed="resetUploadForm">
      <el-form label-position="top">
        <el-form-item label="资源标题">
          <el-input v-model="uploadTitle" placeholder="请输入资源标题" maxlength="100" />
        </el-form-item>
        <el-form-item label="资源类型">
          <el-select v-model="uploadResType" style="width: 100%">
            <el-option label="文档" value="document" />
            <el-option label="视频" value="video" />
            <el-option label="图片" value="image" />
            <el-option label="链接" value="link" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="uploadResType !== 'link'" label="上传文件">
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :on-change="onFileChange"
            :on-remove="onFileRemove"
            :accept="uploadResType === 'image' ? 'image/*' : '*'"
          >
            <template #trigger>
              <el-button type="primary">选择文件</el-button>
            </template>
            <template #tip>
              <div class="el-upload__tip" style="color: #909399; font-size: 12px; line-height: 1.4; margin-top: 6px;">
                支持常见文件格式，大小不超过 10MB
              </div>
            </template>
          </el-upload>
        </el-form-item>
        <el-form-item v-else label="资源链接">
          <el-input v-model="uploadUrl" placeholder="请输入资源链接 URL" />
        </el-form-item>
        <el-form-item v-if="uploading">
          <el-progress :percentage="uploadProgress" :stroke-width="8" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="uploadDialog = false" :disabled="uploading">取消</el-button>
        <el-button type="primary" @click="handleUpload" :loading="uploading">确认上传</el-button>
      </template>
    </el-dialog>

    <!-- Task 8：独立资源加入项目（只建引用，不复制资产/文件） -->
    <el-dialog
      v-model="joinDialog"
      title="加入项目"
      width="460px"
      :close-on-click-modal="false"
    >
      <p class="join-tip" v-if="joinTarget">
        将资源「{{ joinTarget.title }}」加入项目，仅建立引用，资产本体与文件保留。
      </p>
      <el-form label-position="top">
        <el-form-item label="目标项目">
          <el-select v-model="joinProjectId" placeholder="选择项目" style="width: 100%">
            <el-option v-for="p in projects" :key="p.id" :label="p.title" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="项目阶段">
          <el-select v-model="joinPhase" style="width: 100%">
            <el-option label="诊断" value="diagnosis" />
            <el-option label="设计" value="design" />
            <el-option label="备课" value="preparation" />
            <el-option label="实施" value="implementation" />
            <el-option label="评价" value="evaluation" />
            <el-option label="改进" value="improvement" />
            <el-option label="结项" value="closure" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="joinDialog = false" :disabled="joining">取消</el-button>
        <el-button type="primary" @click="confirmJoin" :loading="joining">确认加入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-container {
  padding: 8px;
}

.page-title {
  font-size: 22px;
  font-weight: 700;
  color: #303133;
  margin: 0;
}

.flex-between {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.context-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 10px 14px;
  margin-bottom: 12px;
  background: #f5f7fa;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
}

.context-bar__error {
  color: #f56c6c;
  font-size: 12px;
}

.context-bar__hint {
  color: #909399;
  font-size: 12px;
}

.search-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.empty-state {
  padding: 40px 0;
}

.join-tip {
  margin: 0 0 12px;
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 4px;
  color: #606266;
  font-size: 13px;
  line-height: 1.5;
}
</style>
