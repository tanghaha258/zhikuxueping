<script setup lang="ts">
withDefaults(defineProps<{
  modelValue: boolean
  title: string
  impactSummary?: string
  confirmLabel?: string
  cancelLabel?: string
  loading?: boolean
  danger?: boolean
}>(), {
  impactSummary: '',
  confirmLabel: '确认',
  cancelLabel: '取消',
  loading: false,
  danger: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  confirm: []
  cancel: []
}>()

function close(val: boolean) { emit('update:modelValue', val) }
function onCancel() { emit('cancel'); close(false) }
function onConfirm() { emit('confirm'); close(false) }
</script>

<template>
  <div v-if="modelValue" data-ui="confirm-dialog" class="ui-confirm-dialog" role="dialog" aria-modal="true">
    <div class="ui-confirm-dialog__panel" :class="{ 'is-danger': danger }">
      <h2 class="ui-confirm-dialog__title">{{ title }}</h2>
      <p v-if="impactSummary" class="ui-confirm-dialog__impact">{{ impactSummary }}</p>
      <div class="ui-confirm-dialog__actions">
        <button type="button" data-ui="dialog-cancel" class="ui-clickable" @click="onCancel">{{ cancelLabel }}</button>
        <button type="button" data-ui="dialog-confirm" class="ui-clickable ui-clickable--primary" :disabled="loading" @click="onConfirm">{{ confirmLabel }}</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ui-confirm-dialog { position: fixed; inset: 0; display: flex; align-items: center; justify-content: center; background: rgba(31, 41, 51, 0.45); z-index: 1000; padding: var(--ui-space-4); }
.ui-confirm-dialog__panel { width: 100%; max-width: 420px; background: var(--ui-bg-surface); border-radius: var(--ui-radius-lg); border: 1px solid var(--ui-border); padding: var(--ui-space-6); display: flex; flex-direction: column; gap: var(--ui-space-3); box-shadow: 0 8px 24px rgba(31, 41, 51, 0.12); }
.ui-confirm-dialog__title { margin: 0; font-size: var(--ui-font-size-md); font-weight: 600; color: var(--ui-text-primary); }
.ui-confirm-dialog__impact { margin: 0; font-size: var(--ui-font-size-sm); color: var(--ui-text-secondary); }
.ui-confirm-dialog__actions { display: flex; justify-content: flex-end; gap: var(--ui-space-2); }
.ui-confirm-dialog__panel.is-danger .ui-confirm-dialog__title { color: var(--ui-danger); }
</style>
