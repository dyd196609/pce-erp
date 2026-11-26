<template>
  <el-select
    class="pce-result-filter-select"
    data-pce-rendered-control-type="select"
    :model-value="modelValue"
    filterable
    clearable
    :placeholder="placeholder"
    @update:model-value="$emit('update:modelValue', $event ?? '')"
  >
    <el-option v-for="option in options" :key="option.value" :label="option.label" :value="option.value" />
  </el-select>
</template>

<script setup>
import { computed } from 'vue'
import { displayPceFilterValue } from '@/meta/runtime/pceAdvancedFilterContract.js'

const props = defineProps({
  modelValue: { type: [String, Number, Boolean], default: '' },
  rows: { type: Array, default: () => [] },
  fields: { type: Array, default: () => [] },
  options: { type: Array, default: () => [] },
  placeholder: { type: String, default: '请选择或搜索' },
})

defineEmits(['update:modelValue'])

const options = computed(() => {
  const values = [
    ...props.options,
    ...props.rows.flatMap((row) => props.fields.map((field) => row?.[field])),
  ]
  if (props.modelValue !== '' && props.modelValue != null) values.push(props.modelValue)
  return [...new Set(values.map((value) => String(value ?? '').trim()).filter(Boolean))]
    .map(value => ({ value, label: displayPceFilterValue(value) }))
})
</script>
