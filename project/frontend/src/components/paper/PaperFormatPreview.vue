<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps<{
  formattedHtml: string
  loading?: boolean
}>()

const emit = defineEmits<{
  save: [html: string]
  exportPdf: []
}>()

const isEditMode = ref(false)
const editableHtml = ref('')
const editLoading = ref(false)

function toggleEdit() {
  if (!isEditMode.value) {
    editableHtml.value = props.formattedHtml
  }
  isEditMode.value = !isEditMode.value
}

async function handleSave() {
  editLoading.value = true
  try {
    emit('save', editableHtml.value)
    isEditMode.value = false
    ElMessage.success('保存成功')
  } catch {
    ElMessage.error('保存失败')
  } finally {
    editLoading.value = false
  }
}
</script>

<template>
  <div class="format-preview">
    <div class="toolbar no-print">
      <el-button-group>
        <el-button :type="!isEditMode ? 'primary' : 'default'" size="small" @click="isEditMode = false">
          预览
        </el-button>
        <el-button :type="isEditMode ? 'primary' : 'default'" size="small" @click="toggleEdit">
          编辑
        </el-button>
      </el-button-group>
      <el-button size="small" type="success" @click="$emit('exportPdf')" v-if="!isEditMode">
        导出 PDF
      </el-button>
      <el-button size="small" type="primary" @click="handleSave" :loading="editLoading" v-if="isEditMode">
        保存修改
      </el-button>
    </div>

    <div v-if="loading" class="loading-state">
      <div class="loading-spinner" />
      <p>正在生成排版...</p>
    </div>

    <iframe v-else-if="!isEditMode && formattedHtml" :srcdoc="formattedHtml" class="preview-iframe" />
    <div v-else-if="isEditMode" class="edit-area">
      <textarea v-model="editableHtml" class="edit-textarea" spellcheck="false"></textarea>
    </div>
    <div v-else class="empty-state">
      <p>点击「试卷转换」生成专业排版</p>
    </div>
  </div>
</template>

<style scoped>
.format-preview { border: 1px solid #e4e7ed; border-radius: 8px; overflow: hidden; }
.toolbar { display: flex; align-items: center; gap: 12px; padding: 8px 16px; background: #f5f7fa; border-bottom: 1px solid #e4e7ed; }
.preview-iframe { width: 100%; height: 800px; border: none; }
.loading-state { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 80px; color: #909399; }
.loading-spinner { width: 36px; height: 36px; border: 3px solid #e4e7ed; border-top-color: #409eff; border-radius: 50%; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.edit-area { padding: 0; }
.edit-textarea { width: 100%; height: 800px; border: none; padding: 16px; font-family: 'Courier New', monospace; font-size: 13px; resize: vertical; outline: none; }
.empty-state { text-align: center; padding: 80px; color: #c0c4cc; }
</style>
