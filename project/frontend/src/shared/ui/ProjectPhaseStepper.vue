<script setup lang="ts">
import { computed } from 'vue'

type PhaseStatus = 'done' | 'current' | 'warning' | 'blocked' | 'pending'

interface PhaseStep {
  key: string
  label: string
  status: PhaseStatus
}

const props = defineProps<{
  phases: PhaseStep[]
  readOnly?: boolean
}>()

const emit = defineEmits<{ select: [key: string] }>()

const ALLOWED: PhaseStatus[] = ['done', 'current', 'warning', 'blocked', 'pending']

const normalized = computed<PhaseStep[]>(() =>
  props.phases.map((p) => ({
    key: p.key,
    label: p.label,
    status: ALLOWED.includes(p.status) ? p.status : 'pending',
  }))
)

function onSelect(key: string) {
  if (props.readOnly) return
  emit('select', key)
}
</script>

<template>
  <nav data-ui="phase-stepper" class="ui-phase-stepper" aria-label="项目阶段">
    <button
      v-for="(phase, i) in normalized"
      :key="phase.key"
      type="button"
      data-ui="phase-step"
      class="ui-phase-step"
      :class="`ui-phase-step--${phase.status}`"
      :disabled="readOnly"
      :aria-current="phase.status === 'current' ? 'step' : undefined"
      @click="onSelect(phase.key)"
    >
      <span class="ui-phase-step__index">{{ i + 1 }}</span>
      <span class="ui-phase-step__label">{{ phase.label }}</span>
    </button>
  </nav>
</template>

<style scoped>
.ui-phase-stepper { display: flex; align-items: center; gap: var(--ui-space-1); flex-wrap: wrap; }
.ui-phase-step { display: inline-flex; align-items: center; gap: var(--ui-space-2); padding: var(--ui-space-1) var(--ui-space-3); border: 1px solid var(--ui-border-light); background: var(--ui-bg-surface); border-radius: var(--ui-radius-md); color: var(--ui-text-secondary); font-size: var(--ui-font-size-xs); cursor: pointer; min-height: 32px; }
.ui-phase-step:hover { background: var(--ui-bg-subtle); }
.ui-phase-step:disabled { cursor: not-allowed; opacity: 0.7; }
.ui-phase-step__index { display: inline-flex; align-items: center; justify-content: center; width: 18px; height: 18px; border-radius: 50%; background: var(--ui-bg-subtle); color: var(--ui-text-muted); font-size: var(--ui-font-size-xs); }
.ui-phase-step--done { color: var(--ui-success); border-color: var(--ui-success); }
.ui-phase-step--done .ui-phase-step__index { background: var(--ui-success); color: #fff; }
.ui-phase-step--current { color: var(--ui-primary); border-color: var(--ui-primary); }
.ui-phase-step--current .ui-phase-step__index { background: var(--ui-primary); color: #fff; }
.ui-phase-step--warning { color: var(--ui-warning); border-color: var(--ui-warning); }
.ui-phase-step--blocked { color: var(--ui-danger); border-color: var(--ui-danger); }
.ui-phase-step--blocked .ui-phase-step__index { background: var(--ui-danger); color: #fff; }
</style>
