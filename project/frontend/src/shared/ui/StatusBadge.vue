<script setup lang="ts">
import { computed } from 'vue'

type BadgeTone = 'primary' | 'success' | 'warning' | 'danger' | 'muted'

interface StatusMapping { label: string; tone: BadgeTone }

const DEFAULT_MAP: Record<string, StatusMapping> = {
  draft: { label: '草稿', tone: 'muted' },
  in_progress: { label: '进行中', tone: 'warning' },
  ready: { label: '待发布', tone: 'primary' },
  published: { label: '已发布', tone: 'success' },
  done: { label: '已完成', tone: 'success' },
  archived: { label: '已归档', tone: 'muted' },
  blocked: { label: '阻断', tone: 'danger' },
}

const props = defineProps<{
  status: string
  mapping?: Record<string, StatusMapping>
}>()

const resolved = computed<StatusMapping>(() => {
  const map = props.mapping ? { ...DEFAULT_MAP, ...props.mapping } : DEFAULT_MAP
  return map[props.status] ?? { label: props.status, tone: 'muted' }
})
</script>

<template>
  <span data-ui="status-badge" class="ui-badge" :class="`ui-badge--${resolved.tone}`">{{ resolved.label }}</span>
</template>

<style scoped>
.ui-badge { display: inline-flex; align-items: center; padding: 2px var(--ui-space-2); border-radius: var(--ui-radius-sm); font-size: var(--ui-font-size-xs); line-height: 1.5; border: 1px solid transparent; white-space: nowrap; }
.ui-badge--primary { color: var(--ui-primary); background: #eaf2fb; border-color: #d4e4f5; }
.ui-badge--success { color: var(--ui-success); background: #e8f3ec; border-color: #d4e8db; }
.ui-badge--warning { color: var(--ui-warning); background: #fbeede; border-color: #f0dcc0; }
.ui-badge--danger { color: var(--ui-danger); background: #f6e3e3; border-color: #eccfcf; }
.ui-badge--muted { color: var(--ui-text-muted); background: var(--ui-bg-subtle); border-color: var(--ui-border-light); }
</style>
