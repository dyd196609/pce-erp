<template>
  <div
    v-show="visible"
    class="pce-enterprise-advanced-filter pce-unified-advanced-filter"
    data-acceptance-id="list-advanced-filter-panel"
    :data-pce-filter-for="tableId"
    :data-pce-filter-acceptance-id="acceptanceId"
    data-pce-enterprise-filter-version="V1.1"
    :data-pce-filter-layout-version="layoutVersion"
    :data-pce-filter-control-height="layoutMetrics.controlHeight"
    :data-pce-filter-control-min-width="layoutMetrics.controlMinWidth"
  >
    <section class="pce-filter-layout-row" data-pce-filter-row="query">
      <h3 class="pce-filter-layout-row-title">查询条件</h3>
      <div class="pce-filter-layout-grid">
        <PceAdvancedFilterField v-for="field in layoutRows.query" :key="field.field"
          :model-value="modelValue[field.field]" :field="field" :rows="rows"
          @update:model-value="$emit('update-filter', field.field, $event)" />
      </div>
    </section>
    <section class="pce-filter-layout-row" data-pce-filter-row="range">
      <h3 class="pce-filter-layout-row-title">范围条件</h3>
      <div class="pce-filter-layout-grid">
        <PceAdvancedFilterField v-for="field in layoutRows.range" :key="field.field"
          :model-value="modelValue[field.field]" :field="field" :rows="rows"
          @update:model-value="$emit('update-filter', field.field, $event)" />
        <span v-if="!layoutRows.range.length" class="pce-filter-layout-empty">当前页面无范围条件</span>
      </div>
    </section>
    <section class="pce-filter-layout-row" data-pce-filter-row="actions">
      <h3 class="pce-filter-layout-row-title">操作按钮</h3>
      <div class="pce-filter-layout-actions">
        <el-button @click="$emit('clear-filters')">清空条件</el-button>
        <el-button @click="$emit('clear-sort')">重置排序</el-button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import PceAdvancedFilterField from './PceAdvancedFilterField.vue'
import { normalizeListFilterSchema } from '@/meta/runtime/listFilterRuntime.js'
import {
  buildAdvancedFilterLayoutRows,
  PCE_ADVANCED_FILTER_LAYOUT_METRICS,
  PCE_ADVANCED_FILTER_LAYOUT_VERSION,
} from '@/meta/runtime/pceAdvancedFilterLayoutRuntime.js'

const props = defineProps({
  visible: { type: Boolean, default: false },
  schema: { type: Array, default: () => [] },
  modelValue: { type: Object, required: true },
  rows: { type: Array, default: () => [] },
  acceptanceId: { type: String, required: true },
  tableId: { type: String, required: true },
})
const normalizedSchema = computed(() => normalizeListFilterSchema(props.schema))
const layoutRows = computed(() => buildAdvancedFilterLayoutRows(normalizedSchema.value))
const layoutVersion = PCE_ADVANCED_FILTER_LAYOUT_VERSION
const layoutMetrics = PCE_ADVANCED_FILTER_LAYOUT_METRICS

defineEmits(['update-filter', 'clear-filters', 'clear-sort'])
</script>
