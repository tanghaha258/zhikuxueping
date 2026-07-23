<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listProvidersApi, createProviderApi, updateProviderApi, deleteProviderApi, testProviderApi } from '@/api/ai'
import type { AiProvider } from '@/types'

const providers = ref<AiProvider[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('新增 Provider')
const editingId = ref<string | null>(null)
const testingId = ref<string | null>(null)

const form = ref({
  name: '',
  apiUrl: '',
  model: '',
  apiKey: '',
})

const presets = [
  { name: 'DeepSeek', apiUrl: 'https://api.deepseek.com/v1', model: 'deepseek-chat', multimodal: false },
  { name: '通义千问', apiUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1', model: 'qwen-plus', multimodal: true },
  { name: '智谱清言', apiUrl: 'https://open.bigmodel.cn/api/paas/v4', model: 'glm-4', multimodal: true },
  { name: '文心一言', apiUrl: 'https://aip.baidubce.com/rpc/2.0/ai_custom/v1', model: 'ernie-4.0', multimodal: false },
  { name: '讯飞星火', apiUrl: 'https://spark-api.xf-yun.com/v3.5', model: 'generalv3.5', multimodal: false },
]

function applyPreset(preset: typeof presets[0]) {
  form.value.name = preset.name
  form.value.apiUrl = preset.apiUrl
  form.value.model = preset.model
}

async function fetchProviders() {
  loading.value = true
  try {
    const res = await listProvidersApi()
    providers.value = res.data.data
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  dialogTitle.value = '新增 Provider'
  form.value = { name: '', apiUrl: '', model: '', apiKey: '' }
  dialogVisible.value = true
}

function openEdit(row: AiProvider) {
  editingId.value = row.id
  dialogTitle.value = '编辑 Provider'
  form.value = {
    name: row.name,
    apiUrl: row.apiUrl,
    model: row.model,
    apiKey: '',
  }
  dialogVisible.value = true
}

async function handleSave() {
  if (!form.value.name || !form.value.apiUrl || !form.value.model) {
    ElMessage.warning('请填写完整信息')
    return
  }
  try {
    if (editingId.value) {
      const payload: Record<string, unknown> = { name: form.value.name, api_url: form.value.apiUrl, model: form.value.model }
      if (form.value.apiKey) payload.api_key = form.value.apiKey
      await updateProviderApi(editingId.value, payload)
      ElMessage.success('更新成功')
    } else {
      await createProviderApi({ name: form.value.name, api_url: form.value.apiUrl, model: form.value.model, api_key: form.value.apiKey })
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchProviders()
  } catch { /* error already handled by interceptor */ }
}

async function handleDelete(row: AiProvider) {
  try {
    await ElMessageBox.confirm('确定要删除该 Provider 吗？', '确认删除', { type: 'warning' })
    await deleteProviderApi(row.id)
    ElMessage.success('删除成功')
    fetchProviders()
  } catch { /* cancelled or error */ }
}

async function toggleStatus(row: AiProvider) {
  const newStatus = row.status === 'active' ? 'inactive' : 'active'
  try {
    await updateProviderApi(row.id, { status: newStatus })
    ElMessage.success(newStatus === 'active' ? '已启用' : '已禁用')
    fetchProviders()
  } catch { /* error handled */ }
}

async function testConnection(row: AiProvider) {
  testingId.value = row.id
  try {
    await testProviderApi(row.id)
    ElMessage.success('连接成功')
  } catch { /* error handled */ }
  finally {
    testingId.value = null
  }
}

onMounted(fetchProviders)
</script>

<template>
  <div class="page-container">
    <div class="flex-between" style="margin-bottom: 20px;">
      <h2 class="page-title" style="margin-bottom: 0;">AI Provider 配置</h2>
      <el-button type="primary" @click="openCreate">新增 Provider</el-button>
    </div>

    <el-card shadow="never">
      <el-table :data="providers" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="name" label="名称" min-width="140" />
        <el-table-column prop="apiUrl" label="API 地址" min-width="240" />
        <el-table-column prop="model" label="模型" width="140" />
        <el-table-column label="API Key" width="180">
          <template #default="{ row }">
            <code style="font-size: 12px; color: #909399;">{{ row.apiKey }}</code>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
              {{ row.status === 'active' ? '已启用' : '已禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button size="small" :type="row.status === 'active' ? 'warning' : 'success'" plain @click="toggleStatus(row)">
              {{ row.status === 'active' ? '禁用' : '启用' }}
            </el-button>
            <el-button size="small" :loading="testingId === row.id" :disabled="testingId !== null" @click="testConnection(row)">
              {{ testingId === row.id ? '测试中...' : '测试' }}
            </el-button>
            <el-button text type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button text type="danger" size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loading && providers.length === 0" description="暂无 Provider，请点击上方按钮新增" />
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="520px" :close-on-click-modal="false">
      <div style="margin-bottom: 16px;">
        <span style="font-size: 13px; color: #909399; margin-bottom: 8px; display: block;">快速预设：</span>
        <div style="display: flex; gap: 8px; flex-wrap: wrap;">
          <el-tag
            v-for="p in presets" :key="p.name"
            style="cursor: pointer; padding: 4px 12px;"
            :type="p.multimodal ? 'primary' : 'info'"
            @click="applyPreset(p)"
          >
            {{ p.name }}
            <el-tooltip v-if="p.multimodal" content="支持图片分析" placement="top">
              <span style="margin-left: 4px; font-size: 11px;">🖼️</span>
            </el-tooltip>
          </el-tag>
        </div>
      </div>
      <el-form :model="form" label-position="top">
        <el-form-item label="Provider 名称" required>
          <el-input v-model="form.name" placeholder="如：OpenAI、文心一言" />
        </el-form-item>
        <el-form-item label="API 地址" required>
          <el-input v-model="form.apiUrl" placeholder="https://api.openai.com/v1" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="模型名称" required>
              <el-input v-model="form.model" placeholder="如：gpt-4o" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="API Key" :required="!editingId">
              <el-input v-model="form.apiKey" type="password" show-password :placeholder="editingId ? '留空则不修改' : '请输入 API Key'" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>
