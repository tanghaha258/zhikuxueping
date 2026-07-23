<script setup lang="ts">
import TiptapEditor from './TiptapEditor.vue'
import OptionEditor from './OptionEditor.vue'
import AnswerAnalysis from './AnswerAnalysis.vue'

interface Question {
  index: number
  type: string
  score: number
  content: string
  options?: string[]
  answer?: string
  analysis?: string
  _editIdx?: number
}

const props = defineProps<{
  question: Question
  questionNumber: number
}>()

const emit = defineEmits<{
  'update': [value: Question]
  'delete': []
}>()

function update(field: string, value: any) {
  emit('update', { ...props.question, [field]: value })
}
</script>

<template>
  <div class="question-card">
    <div class="q-header">
      <span class="q-drag-handle">⋮⋮</span>
      <span class="q-number">{{ questionNumber }}.</span>
      <el-select :model-value="question.type" @update:model-value="update('type', $event)" size="small" style="width:90px">
        <el-option label="选择题" value="choice" />
        <el-option label="填空题" value="fill" />
        <el-option label="简答题" value="essay" />
      </el-select>
      <span class="score-label">分值：</span>
      <el-input-number :model-value="question.score" @update:model-value="update('score', $event)" :min="1" :max="50" size="small" style="width:80px" />
      <el-button size="small" text type="danger" @click="emit('delete')">删除</el-button>
    </div>
    <TiptapEditor :model-value="question.content" @update:model-value="update('content', $event)" placeholder="请输入题目内容..." />
    <OptionEditor
      v-if="question.type === 'choice'"
      :options="question.options || ['', '', '', '']"
      :answer="question.answer || ''"
      @update:options="update('options', $event)"
      @update:answer="update('answer', $event)"
    />
    <AnswerAnalysis
      :answer="question.answer || ''"
      :analysis="question.analysis || ''"
      @update:answer="update('answer', $event)"
      @update:analysis="update('analysis', $event)"
    />
  </div>
</template>

<style scoped>
.question-card { border: 1px solid #e4e7ed; border-radius: 8px; padding: 16px; margin-bottom: 12px; background: #fff; }
.q-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.q-drag-handle { cursor: grab; color: #c0c4cc; font-size: 16px; user-select: none; }
.q-drag-handle:active { cursor: grabbing; }
.q-number { font-weight: 600; font-size: 14px; min-width: 24px; }
.score-label { font-size: 12px; color: #909399; margin-left: 8px; }
</style>
