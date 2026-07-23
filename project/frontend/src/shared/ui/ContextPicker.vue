<script setup lang="ts">
import { computed } from 'vue'

type PickerMode = 'standalone' | 'linked'
type ProjectPhase =
  | 'diagnosis' | 'design' | 'preparation' | 'implementation'
  | 'evaluation' | 'improvement' | 'closure'

interface ProjectOption { id: string; name: string }
interface PhaseOption { key: string; label: string }

interface ContextPickerValue {
  mode: PickerMode
  projectId?: string
  phase?: ProjectPhase
}

const props = defineProps<{
  modelValue: ContextPickerValue
  projects?: ProjectOption[]
  phases?: PhaseOption[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: ContextPickerValue]
  change: [value: ContextPickerValue]
}>()

const value = computed(() => props.modelValue)
const needsProject = computed(() => value.value.mode === 'linked' && !value.value.projectId)

function emitNext(next: ContextPickerValue) {
  emit('update:modelValue', next)
  emit('change', next)
}

function onMode(e: Event) {
  const mode = (e.target as HTMLSelectElement).value as PickerMode
  emitNext({ mode })
}

function onProject(e: Event) {
  const projectId = (e.target as HTMLSelectElement).value
  emitNext({ ...value.value, mode: 'linked', projectId })
}

function onPhase(e: Event) {
  const phase = (e.target as HTMLSelectElement).value as ProjectPhase
  emitNext({ ...value.value, phase })
}
</script>

<template>
  <div data-ui="context-picker" class="ui-context-picker">
    <label class="ui-context-picker__field">
      <span class="ui-context-picker__label">模式</span>
      <select data-ui="mode-select" class="ui-context-picker__select" :value="value.mode" @change="onMode">
        <option value="standalone">独立</option>
        <option value="linked">关联项目</option>
      </select>
    </label>
    <template v-if="value.mode === 'linked'">
      <span v-if="needsProject" data-ui="project-required" class="ui-context-picker__required">请选择项目</span>
      <label class="ui-context-picker__field">
        <span class="ui-context-picker__label">项目</span>
        <select data-ui="project-select" class="ui-context-picker__select" :value="value.projectId ?? ''" @change="onProject">
          <option value="" disabled>请选择</option>
          <option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</option>
        </select>
      </label>
      <label v-if="phases && phases.length" class="ui-context-picker__field">
        <span class="ui-context-picker__label">阶段</span>
        <select data-ui="phase-select" class="ui-context-picker__select" :value="value.phase ?? ''" @change="onPhase">
          <option value="" disabled>请选择</option>
          <option v-for="ph in phases" :key="ph.key" :value="ph.key">{{ ph.label }}</option>
        </select>
      </label>
    </template>
  </div>
</template>

<style scoped>
.ui-context-picker { display: flex; align-items: center; gap: var(--ui-space-3); flex-wrap: wrap; padding: var(--ui-space-2) var(--ui-space-4); background: var(--ui-bg-subtle); border: 1px solid var(--ui-border-light); border-radius: var(--ui-radius-md); }
.ui-context-picker__field { display: flex; flex-direction: column; gap: var(--ui-space-1); font-size: var(--ui-font-size-xs); color: var(--ui-text-muted); }
.ui-context-picker__select { min-height: 36px; padding: 0 var(--ui-space-2); border: 1px solid var(--ui-border); border-radius: var(--ui-radius-sm); background: var(--ui-bg-surface); color: var(--ui-text-primary); font-size: var(--ui-font-size-sm); }
.ui-context-picker__required { color: var(--ui-warning); font-size: var(--ui-font-size-xs); }
</style>
