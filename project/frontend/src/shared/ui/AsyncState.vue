<script setup lang="ts">
type AsyncStateName = 'loading' | 'ready' | 'empty' | 'error' | 'forbidden'

withDefaults(defineProps<{
  state: AsyncStateName
  message?: string
  emptyHint?: string
  retryLabel?: string
}>(), {
  message: '',
  emptyHint: '',
  retryLabel: '重试',
})

const emit = defineEmits<{ retry: [] }>()
</script>

<template>
  <div data-ui="async-state" class="ui-async-state">
    <div v-if="state === 'loading'" data-ui="state-loading" class="ui-async-state__block" role="status" aria-live="polite">
      <span class="ui-async-state__spinner" aria-hidden="true" />
      <span>加载中…</span>
    </div>
    <div v-else-if="state === 'empty'" data-ui="state-empty" class="ui-async-state__block" role="status">
      <p class="ui-async-state__text">{{ emptyHint || '暂无数据' }}</p>
    </div>
    <div v-else-if="state === 'error'" data-ui="state-error" class="ui-async-state__block" role="alert">
      <p class="ui-async-state__text">{{ message || '加载失败' }}</p>
      <button type="button" data-ui="retry" class="ui-clickable" @click="emit('retry')">{{ retryLabel }}</button>
    </div>
    <div v-else-if="state === 'forbidden'" data-ui="state-forbidden" class="ui-async-state__block" role="status">
      <p class="ui-async-state__text">{{ message || '无权限访问' }}</p>
    </div>
    <slot v-else-if="state === 'ready'" />
  </div>
</template>

<style scoped>
.ui-async-state { width: 100%; }
.ui-async-state__block { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: var(--ui-space-3); padding: var(--ui-space-8) var(--ui-space-4); color: var(--ui-text-secondary); text-align: center; }
.ui-async-state__text { margin: 0; font-size: var(--ui-font-size-sm); }
.ui-async-state__spinner { width: 18px; height: 18px; border: 2px solid var(--ui-border); border-top-color: var(--ui-primary); border-radius: 50%; display: inline-block; animation: ui-spin 0.8s linear infinite; }
@keyframes ui-spin { to { transform: rotate(360deg); } }
</style>
