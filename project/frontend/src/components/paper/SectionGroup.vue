<script setup lang="ts">
import draggable from 'vuedraggable'
import QuestionCard from './QuestionCard.vue'

interface Question {
  index: number; type: string; score: number; content: string
  options?: string[]; answer?: string; analysis?: string; _editIdx?: number; _sectionId?: string
}
interface Section {
  id: string; label: string; type: string; count: number; score_per: number; total: number
  questions: Question[]
}

const props = defineProps<{
  section: Section
  startIndex: number
}>()

const emit = defineEmits<{
  'update-question': [sectionId: string, idx: number, question: Question]
  'delete-question': [sectionId: string, idx: number]
}>()

function handleUpdate(idx: number, q: Question) {
  emit('update-question', props.section.id, idx, q)
}

function handleDelete(idx: number) {
  emit('delete-question', props.section.id, idx)
}
</script>

<template>
  <div class="section-group">
    <div class="section-header">
      <span class="section-drag-handle">⋮⋮</span>
      <span class="section-title">{{ section.label }}</span>
      <span class="section-stats">（共 {{ section.questions.length }} 题，{{ section.questions.reduce((s, q) => s + (Number(q.score) || 0), 0) }} 分）</span>
    </div>
    <draggable
      :list="section.questions"
      item-key="_editIdx"
      handle=".q-drag-handle"
      ghost-class="ghost"
      class="question-list"
    >
      <template #item="{ element, index }">
        <QuestionCard
          :question="element"
          :question-number="startIndex + index + 1"
          @update="handleUpdate(index, $event)"
          @delete="handleDelete(index)"
        />
      </template>
    </draggable>
  </div>
</template>

<style scoped>
.section-group { margin-bottom: 20px; }
.section-header { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; padding: 8px 12px; background: #f5f7fa; border-radius: 6px; }
.section-drag-handle { cursor: grab; color: #c0c4cc; font-size: 16px; user-select: none; }
.section-drag-handle:active { cursor: grabbing; }
.section-title { font-weight: 600; font-size: 14px; }
.section-stats { font-size: 12px; color: #909399; }
.question-list { min-height: 40px; }
.ghost { opacity: 0.4; }
</style>
