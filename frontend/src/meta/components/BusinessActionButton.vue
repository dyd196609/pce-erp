<template>
  <router-link
    v-if="action?.handlerType === 'route' && action.targetRoutePath && isEnabled"
    class="business-action-button"
    :to="action.targetRoutePath"
  >
    {{ action.actionName }}
  </router-link>
  <button
    v-else
    class="business-action-button"
    type="button"
    :disabled="!isEnabled"
    :title="disabledReason"
    @click="$emit('execute', action)"
  >
    {{ action?.actionName || '未命名操作' }}
  </button>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  action: {
    type: Object,
    default: null,
  },
})

defineEmits(['execute'])

const isEnabled = computed(() => props.action?.enabledWhen === 'always' || props.action?.enabledWhen === 'route_available')
const disabledReason = computed(() => props.action?.disabledReason || '该操作当前不可用')
</script>

<style scoped>
.business-action-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 32px;
  padding: 0 12px;
  border: 1px solid #2563eb;
  border-radius: 6px;
  background: #2563eb;
  color: #ffffff;
  font-size: 13px;
  font-weight: 700;
  text-decoration: none;
}

.business-action-button:disabled {
  border-color: #cbd5e1;
  background: #e2e8f0;
  color: #64748b;
  cursor: not-allowed;
}
</style>
