<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Upload, Delete, Document, VideoCamera, Picture, Link } from '@element-plus/icons-vue'
import { listResourcesApi, createResourceApi, deleteResourceApi } from '@/api/resources'
import { listProjectsApi } from '@/api/projects'
import { uploadFileApi } from '@/api/upload'
import type { Resource, Project } from '@/types'
import { formatDate } from '@/utils/format'

const resources = ref<Resource[]>([])
const projects = ref<Project[]>([])
const loading = ref(false)
const selectedProjectId = ref('')
const activeType = ref('all')
const searchKeyword = ref('')

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

    <div class="search-bar">
      <el-select
        v-model="selectedProjectId"
        placeholder="选择项目"
        clearable
        style="width: 260px"
        @change="fetchResources"
      >
        <el-option v-for="p in projects" :key="p.id" :label="p.title" :value="p.id" />
      </el-select>
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
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
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
  </div>
</template>
