<script setup lang="ts">
import TiptapEditor from './TiptapEditor.vue'

const props = defineProps<{
  options: string[]
  answer: string
}>()

const emit = defineEmits<{
  'update:options': [value: string[]]
  'update:answer': [value: string]
}>()

function updateOption(idx: number, val: string) {
  const opts = [...props.options]
  opts[idx] = val
  emit('update:options', opts)
}

function addOption() {
  emit('update:options', [...props.options, ''])
}

function removeOption(idx: number) {
  const opts = props.options.filter((_, i) => i !== idx)
  const removed = props.options[idx]
  if (props.answer === removed) {
    emit('update:answer', '')
  }
  emit('update:options', opts)
}
</script>

<template>
  <div class="option-editor">
    <div v-for="(opt, idx) in options" :key="idx" class="option-row">
      <el-tag :type="answer === opt ? 'success' : 'info'" size="small" style="width:28px;text-align:center;min-width:28px">
        {{ String.fromCharCode(65 + idx) }}
      </el-tag>
      <TiptapEditor :model-value="opt" @update:model-value="updateOption(idx, $event)" />
      <el-radio :model-value="answer" :value="opt" size="small" @update:model-value="emit('update:answer', $event)">正确答案</el-radio>
      <el-button text type="danger" size="small" @click="removeOption(idx)">×</el-button>
    </div>
    <el-button text type="primary" size="small" @click="addOption">+ 添加选项</el-button>
  </div>
</template>

<style scoped>
.option-editor { margin: 8px 0; }
.option-row { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
</style>
