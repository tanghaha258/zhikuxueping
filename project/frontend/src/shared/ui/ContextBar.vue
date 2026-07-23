<script setup lang="ts">
import { computed } from 'vue'

interface ProjectRef { id: string; name: string }

const props = withDefaults(defineProps<{
  project?: ProjectRef | null
  className?: string
  subjectName?: string
  timeRange?: string
  dirty?: boolean
}>(), {
  project: null,
  className: '',
  subjectName: '',
  timeRange: '',
  dirty: false,
})

defineEmits<{ change: [] }>()

const items = computed(() => {
  const list: string[] = []
  if (props.project) list.push(props.project.name)
  if (props.className) list.push(props.className)
  if (props.subjectName) list.push(props.subjectName)
  return list
})
</script>

<template>
  <div data-ui="context-bar" class="ui-context-bar">
    <span v-for="(item, i) in items" :key="i" class="ui-context-bar__item">{{ item }}</span>
    <span v-if="timeRange" class="ui-context-bar__item ui-text-muted">{{ timeRange }}</span>
    <span v-if="dirty" data-ui="dirty-hint" class="ui-context-bar__dirty" role="status">未保存</span>
  </div>
</template>

<style scoped>
.ui-context-bar { display: flex; align-items: center; gap: var(--ui-space-2); flex-wrap: wrap; padding: var(--ui-space-2) var(--ui-space-4); background: var(--ui-bg-subtle); border: 1px solid var(--ui-border-light); border-radius: var(--ui-radius-md); font-size: var(--ui-font-size-sm); color: var(--ui-text-secondary); }
.ui-context-bar__item:not(:last-child)::after { content: '·'; margin-left: var(--ui-space-2); color: var(--ui-text-muted); }
.ui-context-bar__dirty { margin-left: auto; color: var(--ui-warning); font-size: var(--ui-font-size-xs); }
</style>
