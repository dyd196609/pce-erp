<template>
  <strong
    class="pce-business-status"
    data-pce-status-presentation="business-label-only"
    :data-status-source="source"
    :title="resolvedTitle"
  >
    {{ visibleLabel }}
  </strong>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  statusCode: { type: String, default: '' },
  statusLabel: { type: String, default: '' },
  source: { type: String, default: 'server' },
})

const visibleLabel = computed(() => (
  String(props.statusLabel || '').trim() || '业务状态未提供'
))
const resolvedTitle = computed(() => (
  props.statusCode && !props.statusLabel
    ? '技术状态已隐藏，等待服务端业务标签'
    : visibleLabel.value
))
</script>

<style scoped>
.pce-business-status {
  color: #0f3d75;
  font-weight: 800;
  white-space: nowrap;
}
</style>
