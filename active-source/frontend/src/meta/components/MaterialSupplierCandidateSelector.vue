<template>
  <section class="material-supplier-selector" data-context-type="MaterialSupplierCandidateContext"
    :data-material-code="materialCode" data-source="Supplier Master" data-allow-free-text="false">
    <SupplierCandidateSelector :model-value="modelValue" @update:model-value="emit('update:modelValue', $event)" />
  </section>
</template>

<script setup>
import SupplierCandidateSelector from '@/meta/components/SupplierCandidateSelector.vue'

defineProps({
  materialCode: { type: String, required: true },
  modelValue: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue'])
</script>

<style scoped>
.material-supplier-selector{min-width:0}
</style>
