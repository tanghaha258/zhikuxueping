<script setup lang="ts">
import { computed } from 'vue'

interface Breadcrumb { label: string; to?: string }
interface StatusInfo { label: string; tone?: 'primary' | 'success' | 'warning' | 'danger' | 'muted' }
interface SecondaryAction { key: string; label: string; icon?: string }

const props = withDefaults(defineProps<{
  title: string
  subtitle?: string
  breadcrumbs?: Breadcrumb[]
  status?: StatusInfo | null
  primaryLabel?: string
  primaryIcon?: string
  secondaryActions?: SecondaryAction[]
}>(), {
  subtitle: '',
  breadcrumbs: () => [],
  status: null,
  primaryLabel: '',
  primaryIcon: '',
  secondaryActions: () => [],
})

const emit = defineEmits<{
  primary: []
  secondary: [key: string]
}>()

const crumbs = computed(() => props.breadcrumbs)
</script>

<template>
  <header data-ui="page-header" class="ui-page-header">
    <nav v-if="crumbs.length" class="ui-page-header__crumbs" aria-label="面包屑">
      <template v-for="(crumb, i) in crumbs" :key="i">
        <span class="ui-page-header__crumb">{{ crumb.label }}</span>
        <span v-if="i < crumbs.length - 1" class="ui-page-header__sep">/</span>
      </template>
    </nav>
    <div class="ui-page-header__main">
      <div class="ui-page-header__titles">
        <h1 class="ui-page-header__title">{{ title }}</h1>
        <p v-if="subtitle" class="ui-page-header__subtitle">{{ subtitle }}</p>
      </div>
      <span v-if="status" class="ui-page-header__status" :data-tone="status.tone ?? 'muted'">{{ status.label }}</span>
      <div class="ui-page-header__actions">
        <button
          v-for="action in secondaryActions"
          :key="action.key"
          type="button"
          class="ui-clickable"
          @click="emit('secondary', action.key)"
        >
          <span v-if="action.icon" :class="action.icon" aria-hidden="true" />
          {{ action.label }}
        </button>
        <button
          v-if="primaryLabel"
          type="button"
          data-ui="primary-action"
          class="ui-clickable ui-clickable--primary"
          @click="emit('primary')"
        >
          <span v-if="primaryIcon" :class="primaryIcon" aria-hidden="true" />
          {{ primaryLabel }}
        </button>
      </div>
    </div>
  </header>
</template>

<style scoped>
.ui-page-header { display: flex; flex-direction: column; gap: var(--ui-space-2); }
.ui-page-header__crumbs { font-size: var(--ui-font-size-xs); color: var(--ui-text-muted); display: flex; gap: var(--ui-space-1); flex-wrap: wrap; }
.ui-page-header__main { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--ui-space-4); flex-wrap: wrap; }
.ui-page-header__titles { display: flex; flex-direction: column; gap: var(--ui-space-1); min-width: 0; flex: 1 1 auto; }
.ui-page-header__title { margin: 0; font-size: var(--ui-font-size-lg); font-weight: 600; color: var(--ui-text-primary); }
.ui-page-header__subtitle { margin: 0; font-size: var(--ui-font-size-sm); color: var(--ui-text-secondary); }
.ui-page-header__status { font-size: var(--ui-font-size-xs); padding: 2px var(--ui-space-2); border-radius: var(--ui-radius-sm); border: 1px solid var(--ui-border); color: var(--ui-text-secondary); white-space: nowrap; }
.ui-page-header__actions { display: flex; align-items: center; gap: var(--ui-space-2); flex-wrap: wrap; }
</style>
