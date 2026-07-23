<script setup lang="ts">
import TiptapEditor from './TiptapEditor.vue'

defineProps<{
  answer: string
  analysis: string
}>()

const emit = defineEmits<{
  'update:answer': [value: string]
  'update:analysis': [value: string]
}>()
</script>

<template>
  <div class="answer-analysis">
    <div class="field-row">
      <span class="field-label">答案：</span>
      <el-input :model-value="answer" @update:model-value="emit('update:answer', $event)" size="small" style="width:200px" />
    </div>
    <div class="field-row">
      <span class="field-label">解析：</span>
      <TiptapEditor :model-value="analysis" @update:model-value="emit('update:analysis', $event)" />
    </div>
  </div>
</template>

<style scoped>
.answer-analysis { margin-top: 8px; padding-top: 8px; border-top: 1px dashed #e4e7ed; }
.field-row { display: flex; align-items: flex-start; gap: 8px; margin-bottom: 6px; }
.field-label { font-size: 12px; color: #909399; white-space: nowrap; line-height: 28px; }
</style>
