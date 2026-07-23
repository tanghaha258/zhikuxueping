<script setup lang="ts">
type AlertTone = 'blocker' | 'warning' | 'info' | 'success'

withDefaults(defineProps<{
  tone: AlertTone
  title: string
  description?: string
  actionLabel?: string
}>(), {
  description: '',
  actionLabel: '',
})

defineEmits<{ action: [] }>()
</script>

<template>
  <div data-ui="inline-alert" class="ui-alert" :class="`ui-alert--${tone}`" role="alert">
    <div class="ui-alert__body">
      <p class="ui-alert__title">{{ title }}</p>
      <p v-if="description" class="ui-alert__desc">{{ description }}</p>
    </div>
    <button v-if="actionLabel" type="button" data-ui="alert-action" class="ui-clickable" @click="$emit('action')">
      {{ actionLabel }}
    </button>
  </div>
</template>

<style scoped>
.ui-alert { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--ui-space-4); padding: var(--ui-space-3) var(--ui-space-4); border-radius: var(--ui-radius-md); border: 1px solid var(--ui-border); background: var(--ui-bg-surface); }
.ui-alert__body { display: flex; flex-direction: column; gap: var(--ui-space-1); min-width: 0; }
.ui-alert__title { margin: 0; font-size: var(--ui-font-size-sm); font-weight: 600; }
.ui-alert__desc { margin: 0; font-size: var(--ui-font-size-xs); color: var(--ui-text-secondary); }
.ui-alert--blocker { background: #fdf2f2; border-color: var(--ui-danger); }
.ui-alert--blocker .ui-alert__title { color: var(--ui-danger); }
.ui-alert--warning { background: #fdf6ed; border-color: var(--ui-warning); }
.ui-alert--warning .ui-alert__title { color: var(--ui-warning); }
.ui-alert--info { background: var(--ui-bg-subtle); border-color: var(--ui-border); }
.ui-alert--success { background: #f1f8f3; border-color: var(--ui-success); }
.ui-alert--success .ui-alert__title { color: var(--ui-success); }
</style>
