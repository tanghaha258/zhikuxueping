<script setup lang="ts">
withDefaults(defineProps<{
  primaryLabel?: string
  secondaryLabel?: string
  primaryDisabled?: boolean
  disabledReason?: string
  loading?: boolean
}>(), {
  primaryLabel: '',
  secondaryLabel: '',
  primaryDisabled: false,
  disabledReason: '',
  loading: false,
})

const emit = defineEmits<{ primary: []; secondary: [] }>()
</script>

<template>
  <div data-ui="sticky-action-bar" class="ui-sticky-bar">
    <div class="ui-sticky-bar__reason">
      <span v-if="primaryDisabled && disabledReason" class="ui-sticky-bar__disabled" role="status">{{ disabledReason }}</span>
    </div>
    <div class="ui-sticky-bar__actions">
      <button v-if="secondaryLabel" type="button" class="ui-clickable" @click="emit('secondary')">{{ secondaryLabel }}</button>
      <button
        v-if="primaryLabel"
        type="button"
        data-ui="primary-action"
        class="ui-clickable ui-clickable--primary"
        :disabled="primaryDisabled || loading"
        :aria-disabled="primaryDisabled || loading"
        :title="primaryDisabled && disabledReason ? disabledReason : undefined"
        @click="emit('primary')"
      >
        {{ loading ? '处理中…' : primaryLabel }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.ui-sticky-bar { position: sticky; bottom: 0; display: flex; align-items: center; justify-content: space-between; gap: var(--ui-space-4); padding: var(--ui-space-3) var(--ui-space-4); background: var(--ui-bg-surface); border-top: 1px solid var(--ui-border); z-index: 10; }
.ui-sticky-bar__reason { min-height: 20px; font-size: var(--ui-font-size-xs); }
.ui-sticky-bar__disabled { color: var(--ui-warning); }
.ui-sticky-bar__actions { display: flex; align-items: center; gap: var(--ui-space-2); }
</style>
