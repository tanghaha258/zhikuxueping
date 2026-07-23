<script setup lang="ts">
import { computed } from 'vue'

type EvidenceKind = 'submission' | 'rubric' | 'ai_call'

interface Evidence {
  kind: EvidenceKind
  label: string
  href?: string
  verified?: boolean
}

const props = defineProps<{ evidence: Evidence }>()
const emit = defineEmits<{ open: [evidence: Evidence] }>()

const verified = computed(() => props.evidence.verified === true)
const kindLabel = computed(() => {
  switch (props.evidence.kind) {
    case 'submission': return '提交'
    case 'rubric': return '量规'
    case 'ai_call': return 'AI'
    default: return props.evidence.kind
  }
})

function onOpen() { emit('open', props.evidence) }
</script>

<template>
  <button
    v-if="!evidence.href"
    type="button"
    data-ui="evidence-link"
    class="ui-evidence-link"
    :class="{ 'is-unverified': !verified }"
    @click="onOpen"
  >
    <span class="ui-evidence-link__kind">{{ kindLabel }}</span>
    <span class="ui-evidence-link__label">{{ evidence.label }}</span>
    <span v-if="!verified" class="ui-evidence-link__marker">未验证</span>
  </button>
  <a
    v-else
    data-ui="evidence-link"
    class="ui-evidence-link"
    :href="evidence.href"
    :class="{ 'is-unverified': !verified }"
    @click.prevent="onOpen"
  >
    <span class="ui-evidence-link__kind">{{ kindLabel }}</span>
    <span class="ui-evidence-link__label">{{ evidence.label }}</span>
    <span v-if="!verified" class="ui-evidence-link__marker">未验证</span>
  </a>
</template>

<style scoped>
.ui-evidence-link { display: inline-flex; align-items: center; gap: var(--ui-space-1); padding: 2px var(--ui-space-2); border: 1px solid var(--ui-border-light); border-radius: var(--ui-radius-sm); background: var(--ui-bg-surface); color: var(--ui-text-secondary); font-size: var(--ui-font-size-xs); cursor: pointer; text-decoration: none; min-height: 28px; }
.ui-evidence-link:hover { background: var(--ui-bg-subtle); }
.ui-evidence-link__kind { color: var(--ui-text-muted); }
.ui-evidence-link__label { color: var(--ui-text-primary); }
.ui-evidence-link__marker { color: var(--ui-warning); }
.ui-evidence-link.is-unverified { border-color: var(--ui-warning); }
</style>
