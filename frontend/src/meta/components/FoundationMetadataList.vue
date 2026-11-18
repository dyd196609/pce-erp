<template>
  <section
    class="foundation-metadata-list"
    :data-pce-metadata-code="metadata.metadataCode"
    :data-pce-metadata-source="metadata.metadataSource"
    :data-pce-column-count="metadata.fields.length"
    :data-pce-page-kind="metadata.pageKind"
    :data-pce-action-policy="actionPolicy.join(',')"
    :data-provider-query-result-count="filteredRows.length"
    data-pce-filter-source="masterDataRegistry.filterSchema"
    data-pce-dropdown-runtime="listFilterRuntime"
  >
    <PceEnterpriseListTable
      ref="tableRef"
      :contract="contract"
      :page-id="metadata.pageCode"
      :table-id="`${metadata.pageCode}-table`"
      :rows="sourceRows"
      :table-rows="filteredRows"
      :filter-schema="metadata.filterSchema"
      :filters="filters"
      :quick-search="quickSearch"
      :advanced-visible="advancedVisible"
      :selected-count="selectedRows.length"
      :active-filter-count="activeFilterCount"
      :sort-text="sortText"
      :primary-field="metadata.primaryField"
      :primary-label="metadata.primaryLabel"
      :primary-width="180"
      :min-width="tableMinWidth"
      :show-action-column="showActionColumn"
      :action-contracts="actionContracts"
      :action-label-resolver="resolveActionLabel"
      :show-refresh="refreshable"
      :refreshing="refreshing"
      @update:quick-search="quickSearch = $event"
      @search="appliedSearch = quickSearch"
      @toggle-advanced="advancedVisible = !advancedVisible"
      @clear-filters="clearFilters"
      @clear-sort="clearSort"
      @export-current="exportCurrent"
      @clear-selection="clearSelection"
      @update-filter="updateFilter"
      @selection-change="selectedRows = $event"
      @sort-change="handleSort"
      @row-action="handleRowAction"
      @refresh="$emit('refresh')"
    >
      <template #columns>
        <el-table-column
          v-for="column in metadata.columns"
          :key="column.key"
          :prop="column.key"
          :label="column.label"
          :width="column.width || 150"
          sortable
          show-overflow-tooltip
        >
          <template #default="{ row }">
            <PceBusinessStatus
              v-if="column.statusField"
              :status-code="String(row[column.key] || '')"
              :status-label="statusLabel(row)"
              source="metadata-runtime"
            />
            <span v-else>{{ displayValue(row[column.key]) }}</span>
          </template>
        </el-table-column>
      </template>
    </PceEnterpriseListTable>
  </section>
</template>

<script setup>
import { computed, watch } from 'vue'
import PceBusinessStatus from './PceBusinessStatus.vue'
import PceEnterpriseListTable from './PceEnterpriseListTable.vue'
import {
  createPceEnterpriseListContract,
  usePceEnterpriseListRuntime,
} from '../runtime/pceEnterpriseListContract.js'
import { createSchemaActionContracts } from '../runtime/listActionColumnRuntime.js'
import { getActionColumnWidth } from '../runtime/tableActionColumnEngine.js'

const props = defineProps({
  metadata: { type: Object, required: true },
  rows: { type: Array, default: () => [] },
  showActions: { type: Boolean, default: true },
  canToggleStatus: { type: Boolean, default: true },
  statusLabelResolver: { type: Function, default: null },
  enabledResolver: { type: Function, default: null },
  refreshable: { type: Boolean, default: true },
  refreshing: { type: Boolean, default: false },
})

const emit = defineEmits(['view', 'edit', 'toggle-status', 'result-count-change', 'refresh'])

const sourceRows = computed(() => props.rows)
const actionPolicy = computed(() => Array.isArray(props.metadata.actionPolicy)
  ? props.metadata.actionPolicy : (props.metadata.pageKind === 'fact' ? ['view'] : ['view', 'edit']))
const effectiveActionPolicy = computed(() => actionPolicy.value.filter(action => (
  action !== 'toggle-status' || props.canToggleStatus
)))
const actionContracts = computed(() => createSchemaActionContracts(effectiveActionPolicy.value))
const showActionColumn = computed(() => props.showActions && actionContracts.value.length > 0)
const contract = createPceEnterpriseListContract({
  pageCode: props.metadata.pageCode,
  pageType: 'list',
  title: props.metadata.title,
  moduleCode: 'EMD',
})
const tableMinWidth = computed(() => `${Math.max(1200, 180 + props.metadata.columns.reduce(
  (total, column) => total + Number(column.width || 150),
  0,
) + (showActionColumn.value ? getActionColumnWidth(actionContracts.value) : 0))}px`)
const runtime = usePceEnterpriseListRuntime({
  rows: sourceRows,
  filterSchema: props.metadata.filterSchema,
  pageCode: props.metadata.pageCode,
  searchFields: props.metadata.searchFields,
  exportFileName: `${props.metadata.entityCode}.csv`,
  exportColumns: props.metadata.fields.map(column => ({ field: column.key, label: column.label })),
})
const {
  selectedRows,
  quickSearch,
  appliedSearch,
  advancedVisible,
  filters,
  tableRef,
  activeFilterCount,
  sortText,
  filteredRows,
  updateFilter,
  clearFilters,
  clearSort,
  clearSelection,
  handleSort,
  exportCurrent,
} = runtime

watch(filteredRows, rows => emit('result-count-change', rows.length), { immediate: true })

function resolveActionLabel(row, contract) {
  if (contract.actionCode === 'toggle-status') return enabled(row) ? '停用' : '启用'
  return contract.actionName
}

function handleRowAction(action, row) {
  if (action.actionCode === 'view') emit('view', row)
  else if (action.actionCode === 'edit') emit('edit', row)
  else if (action.actionCode === 'toggle-status') emit('toggle-status', row)
}

function displayValue(value) {
  if (value === undefined || value === null || value === '') return '-'
  if (typeof value === 'boolean') return value ? '是' : '否'
  return String(value)
}

function statusLabel(row) {
  if (props.statusLabelResolver) return props.statusLabelResolver(row)
  return String(row.statusLabel || row.status || '')
}

function enabled(row) {
  if (props.enabledResolver) return props.enabledResolver(row)
  return ['enabled', 'active'].includes(String(row.status || '').toLowerCase())
}
</script>

<style scoped>
.foundation-metadata-list { width: 100%; min-width: 0; max-width: 100%; }
</style>
