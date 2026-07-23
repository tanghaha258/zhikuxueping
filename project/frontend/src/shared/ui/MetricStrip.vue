<script setup lang="ts">
type MetricTone = 'default' | 'primary' | 'success' | 'warning' | 'danger'

interface Metric {
  label: string
  value: string | number
  hint?: string
  tone?: MetricTone
}

defineProps<{ metrics: Metric[] }>()
</script>

<template>
  <div data-ui="metric-strip" class="ui-metric-strip">
    <div
      v-for="m in metrics"
      :key="m.label"
      data-ui="metric-item"
      class="ui-metric"
      :data-tone="m.tone ?? 'default'"
    >
      <span class="ui-metric__label">{{ m.label }}</span>
      <span class="ui-metric__value">{{ m.value }}</span>
      <span v-if="m.hint" class="ui-metric__hint">{{ m.hint }}</span>
    </div>
  </div>
</template>

<style scoped>
.ui-metric-strip { display: flex; align-items: stretch; gap: var(--ui-space-4); flex-wrap: wrap; padding: var(--ui-space-3) var(--ui-space-4); background: var(--ui-bg-surface); border: 1px solid var(--ui-border-light); border-radius: var(--ui-radius-md); }
.ui-metric { display: flex; flex-direction: column; gap: var(--ui-space-1); min-width: 96px; }
.ui-metric__label { font-size: var(--ui-font-size-xs); color: var(--ui-text-muted); }
.ui-metric__value { font-size: var(--ui-font-size-md); font-weight: 600; color: var(--ui-text-primary); }
.ui-metric__hint { font-size: var(--ui-font-size-xs); color: var(--ui-text-muted); }
.ui-metric[data-tone='primary'] .ui-metric__value { color: var(--ui-primary); }
.ui-metric[data-tone='success'] .ui-metric__value { color: var(--ui-success); }
.ui-metric[data-tone='warning'] .ui-metric__value { color: var(--ui-warning); }
.ui-metric[data-tone='danger'] .ui-metric__value { color: var(--ui-danger); }
</style>
