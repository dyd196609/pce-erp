<template>
  <BusinessTableScrollContainer
    class="pce-enterprise-table-scroll"
    :acceptance-id="scrollAcceptanceId || `${pageId}-horizontal-scroll`"
    :page-id="pageId"
    :table-id="tableId"
    :min-width="minWidth"
    :width-policy="widthPolicy"
  >
  <div
    class="pce-enterprise-list-table"
    data-pce-enterprise-list-runtime="V1.1"
    :data-pce-enterprise-list-contract="contract.contractVersion"
    :data-pce-page-code="contract.pageCode"
    :data-pce-module-code="contract.moduleCode"
    :data-acceptance-id="`${pageId}-enterprise-list-runtime`"
    data-pce-fixed-header="true"
    data-pce-internal-vertical-scroll="true"
    data-pce-pagination="true"
    data-pce-page-container-rule="LIST-RUNTIME-001"
    data-pce-list-container-runtime="V1.14.2.8.18.13.1"
    data-pce-unified-filter-schema="true"
    data-pce-default-action-column="true"
    data-pce-list-display-rule="LIST-DISPLAY-001"
    data-pce-technical-field-separation="TECH-FIELD-SEPARATION-001"
    data-pce-long-text-mode="ellipsis-tooltip-detail"
    :data-pce-row-density="rowDensity"
    data-pce-table-scroll-runtime="V1.14.2.8.18.13.3"
    :data-pce-action-column-runtime="actionWidthRuntime.runtimeCode"
    :data-pce-action-column-runtime-version="actionWidthRuntime.runtimeVersion"
    :data-pce-action-column-width="resolvedActionWidth"
    :data-pce-action-count="actionWidthRuntime.actionCount"
    :data-pce-action-density="actionWidthRuntime.density"
    :data-source-mode="dataSourceMode"
  >
    <StandardListToolbar
      :page-id="pageId"
      :table-id="tableId"
      :quick-search="quickSearch"
      :advanced-visible="advancedVisible"
      :result-count="tableRows.length"
      :selected-count="selectedCount"
      :active-filter-count="activeFilterCount"
      :sort-text="sortText"
      :show-refresh="showRefresh"
      :refreshing="refreshing"
      @update:quick-search="$emit('update:quickSearch', $event)"
      @search="$emit('search')"
      @toggle-advanced="$emit('toggle-advanced')"
      @clear-filters="$emit('clear-filters')"
      @clear-sort="clearSort"
      @export-current="requestExportCurrent"
      @clear-selection="clearSelection"
      @refresh="$emit('refresh')"
    />
    <div v-if="$slots['toolbar-extension']" class="pce-enterprise-toolbar-extension" data-pce-toolbar-extension="true">
      <slot name="toolbar-extension" />
    </div>
    <div class="pce-column-width-actions" data-pce-column-width-contract="PCE-COLUMN-WIDTH-PREFERENCE-V1">
      <el-button
        size="small"
        plain
        :disabled="!preferenceUserKey"
        :data-acceptance-id="`${tableId}-restore-default-widths`"
        @click="resetColumnWidths"
      >恢复默认列宽</el-button>
    </div>
    <PceEnterpriseAdvancedFilter
      :visible="advancedVisible"
      :schema="filterSchema"
      :model-value="filters"
      :rows="rows"
      :acceptance-id="`${pageId}-advanced-filter`"
      :table-id="tableId"
      @update-filter="(field, value) => $emit('update-filter', field, value)"
      @clear-filters="$emit('clear-filters')"
      @clear-sort="clearSort"
    />
    <div v-if="selectedCount" class="pce-enterprise-batch-filter" data-pce-batch-filter-runtime="V1.14.2.8.18.14">
      <span>已选择 {{ selectedCount }} 条</span>
      <el-select v-model="batchFilterField" placeholder="选择批量筛选字段" clearable>
        <el-option v-for="field in batchFilterRuntime.fields" :key="field.field"
          :label="field.label" :value="field.field" />
      </el-select>
      <el-button :disabled="!batchFilterField" @click="applyBatchFilter">按已选数据筛选</el-button>
    </div>
    <div class="pce-enterprise-table-viewport">
      <el-table
        ref="tableRef"
        :data="pagedRows"
        border
        :fit="false"
        :allow-drag-last-column="true"
        :row-key="resolveRowIdentity"
        :expand-row-keys="resolvedExpandRowKeys"
        :max-height="resolvedViewportMaxHeight"
        :data-acceptance-id="tableId"
        data-pce-list-scroll-owner="element-plus-table-body"
        @select="handleSingleRowSelection"
        @select-all="handleHeaderSelection"
        @sort-change="$emit('sort-change', $event)"
        @current-change="$emit('current-change', $event)"
        @expand-change="(row, expandedRows) => $emit('expand-change', row, expandedRows)"
        @header-dragend="handleHeaderDragend"
      >
        <el-table-column
          type="selection"
          column-key="__selection"
          :reserve-selection="reserveSelection"
          fixed="left"
          width="54"
          class-name="business-table-selection-column"
          label-class-name="business-table-selection-column"
          data-acceptance-id="row-selection-contract-column"
        />
        <el-table-column
          type="index"
          column-key="__index"
          fixed="left"
          :index="resolveRowIndex"
          label="序号"
          width="64"
          class-name="pce-fixed-index-column"
          label-class-name="pce-fixed-index-column"
        />
        <el-table-column
          :prop="primaryField"
          :column-key="`primary:${primaryField}`"
          fixed="left"
          :label="primaryLabel"
          :width="primaryWidth"
          sortable
          show-overflow-tooltip
          class-name="pce-fixed-primary-no-column"
          label-class-name="pce-fixed-primary-no-column"
        >
          <template #default="{ row }">
            <slot name="primary" :row="row">{{ row[primaryField] }}</slot>
          </template>
        </el-table-column>
        <slot name="columns" />
        <el-table-column
          v-if="showActionColumn"
          column-key="__actions"
          fixed="right"
          :label="actionLabel"
          :width="resolvedActionWidth"
          class-name="payment-fixed-action-column"
          label-class-name="payment-fixed-action-column"
        >
          <template #default="{ row }">
            <div
              class="pce-enterprise-row-actions"
              data-pce-action-source="Action Contract"
            >
              <slot v-if="$slots.actions" name="actions" :row="row" />
              <template v-else-if="actionsForRow(row).length">
                <el-button v-for="action in actionsForRow(row)" :key="action.actionCode" link
                  :type="action.buttonType || 'primary'"
                  :data-process-action="action.actionCode" :data-action-contract="action.actionCode"
                  :data-action-style="action.buttonType || 'primary'"
                  @click="$emit('row-action', action, row)">{{ action.label }}</el-button>
              </template>
              <span v-else class="pce-enterprise-no-action">暂无可用操作</span>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>
    <footer
      class="pce-enterprise-pagination"
      :data-acceptance-id="`${pageId}-pagination`"
      :data-pce-pagination-for="tableId"
      aria-label="企业列表分页"
    >
      <span data-acceptance-id="pagination-total">总记录数：<strong>{{ tableRows.length }}</strong></span>
      <span data-acceptance-id="pagination-current">当前页：<strong>{{ currentPage }}</strong> / {{ totalPages }}</span>
      <label>
        每页数量
        <select
          v-model.number="pageSize"
          data-acceptance-id="pagination-page-size"
          aria-label="每页数量"
        >
          <option v-for="size in resolvedPageSizes" :key="size" :value="size">{{ size }} 条/页</option>
        </select>
      </label>
      <button
        type="button"
        data-acceptance-id="pagination-previous"
        :disabled="currentPage <= 1"
        @click="currentPage -= 1"
      >上一页</button>
      <button
        type="button"
        data-acceptance-id="pagination-next"
        :disabled="currentPage >= totalPages"
        @click="currentPage += 1"
      >下一页</button>
    </footer>
  </div>
  </BusinessTableScrollContainer>
</template>

<script setup>
import { computed, inject, nextTick, onMounted, ref, watch } from 'vue'
import BusinessTableScrollContainer from './BusinessTableScrollContainer.vue'
import PceEnterpriseAdvancedFilter from './PceEnterpriseAdvancedFilter.vue'
import StandardListToolbar from './StandardListToolbar.vue'
import {
  assertPceEnterpriseListContract,
  paginatePceEnterpriseRows,
  PCE_ENTERPRISE_LIST_SHELL_DEFAULTS,
  PCE_ENTERPRISE_LIST_SHELL_KEY,
} from '../runtime/pceEnterpriseListContract.js'
import { createListActionColumnRuntime } from '../runtime/listActionColumnRuntime.js'
import { createBatchFilterRuntime } from '../runtime/batchFilterRuntime.js'
import { createActionColumnWidthRuntime, getActionColumnWidthForRows } from '../runtime/tableActionColumnEngine.js'
import {
  applyHeaderSelection,
  applySingleRowSelection,
  selectionContains,
} from '../runtime/baseDataRowSelectionContract.js'
import { createColumnWidthPreferenceRuntime } from '../runtime/columnWidthPreferences.js'

const props = defineProps({
  contract: {
    type: Object,
    required: true,
    validator(value) {
      try {
        assertPceEnterpriseListContract(value)
        return true
      } catch {
        return false
      }
    },
  },
  pageId: { type: String, required: true },
  tableId: { type: String, required: true },
  preferenceUserKey: { type: [String, Number], default: '' },
  rows: { type: Array, default: () => [] },
  tableRows: { type: Array, default: () => [] },
  rowKey: { type: String, default: 'id' },
  quickSearch: { type: String, default: '' },
  advancedVisible: { type: Boolean, default: false },
  filterSchema: { type: Array, default: () => [] },
  filters: { type: Object, required: true },
  selectedCount: { type: Number, default: 0 },
  reserveSelection: { type: Boolean, default: false },
  expandRowKeys: { type: Array, default: undefined },
  activeFilterCount: { type: Number, default: 0 },
  sortText: { type: String, default: '默认业务顺序' },
  minWidth: { type: [String, Number], default: '1480px' },
  widthPolicy: { type: String, default: 'normal' },
  scrollAcceptanceId: { type: String, default: '' },
  primaryField: { type: String, required: true },
  primaryLabel: { type: String, required: true },
  primaryWidth: { type: [String, Number], default: 220 },
  showActionColumn: { type: Boolean, default: true },
  actionLabel: { type: String, default: '操作' },
  actionWidth: { type: [String, Number], default: 96 },
  actionContracts: { type: [Array, Object], default: () => [] },
  actionStateField: { type: String, default: '' },
  actionLabelResolver: { type: Function, default: null },
  showRefresh: { type: Boolean, default: false },
  refreshing: { type: Boolean, default: false },
  viewportMaxHeight: { type: [String, Number], default: '' },
  defaultPageSize: { type: Number, default: 0 },
  pageSizes: { type: Array, default: () => [] },
  dataSourceMode: {
    type: String,
    default: 'production',
    validator: value => ['production', 'canary_acceptance'].includes(value),
  },
  rowDensity: {
    type: String,
    default: 'compact',
    validator: value => ['compact', 'comfortable'].includes(value),
  },
})

const emit = defineEmits([
  'update:quickSearch',
  'search',
  'toggle-advanced',
  'clear-filters',
  'clear-sort',
  'export-current',
  'clear-selection',
  'update-filter',
  'selection-change',
  'sort-change',
  'current-change',
  'expand-change',
  'row-action',
  'refresh',
])

const tableRef = ref(null)
let columnWidthRuntime = null
let columnWidthRuntimeSignature = ''
const shellDefaults = inject(PCE_ENTERPRISE_LIST_SHELL_KEY, PCE_ENTERPRISE_LIST_SHELL_DEFAULTS)
const resolvedViewportMaxHeight = computed(() => (
  props.viewportMaxHeight || shellDefaults.viewportMaxHeight
))
const resolvedPageSizes = computed(() => (
  props.pageSizes.length ? props.pageSizes : shellDefaults.pageSizes
))
const pageSize = ref(props.defaultPageSize || shellDefaults.defaultPageSize)
const currentPage = ref(1)
const internalSelectedRows = ref([])
const batchFilterField = ref('')
const batchFilterRuntime = computed(() => createBatchFilterRuntime({ schema: props.filterSchema }))
const paginationState = computed(() => paginatePceEnterpriseRows(
  props.tableRows,
  currentPage.value,
  pageSize.value,
))
const totalPages = computed(() => paginationState.value.totalPages)
const pagedRows = computed(() => paginationState.value.rows)
// Consumers retain raw business row keys; Element Plus consumes this wrapper's
// namespaced identities, consistently with its row-key callback.
const resolvedExpandRowKeys = computed(() => {
  if (!Array.isArray(props.expandRowKeys)) return undefined
  const requested = new Set(props.expandRowKeys.map(key => String(key)))
  return pagedRows.value.filter(row => {
    const configured = row?.[props.rowKey]
    return configured !== undefined && configured !== null && configured !== '' && requested.has(String(configured))
  }).map(resolveRowIdentity)
})
const actionRuntime = computed(() => createListActionColumnRuntime({ contracts: props.actionContracts,
  stateField: props.actionStateField, labelResolver: props.actionLabelResolver }))
const actionsForRow = row => actionRuntime.value.resolve(row)
const fallbackActions = computed(() => actionRuntime.value.contracts.map(contract => ({ label: contract.actionName })))
const resolvedActionWidth = computed(() => props.actionContracts && Object.keys(props.actionContracts).length
  ? getActionColumnWidthForRows(props.tableRows, actionsForRow, fallbackActions.value) : props.actionWidth)
const actionWidthRuntime = computed(() => createActionColumnWidthRuntime(
  props.actionContracts && Object.keys(props.actionContracts).length
    ? (props.tableRows.length ? actionsForRow(props.tableRows[0]) : fallbackActions.value)
    : [],
  { emptyWidth: Number(props.actionWidth) || 96 },
))

watch(() => props.tableRows, () => {
  currentPage.value = 1
}, { deep: false })

watch(pageSize, () => {
  currentPage.value = 1
})

watch(totalPages, value => {
  if (currentPage.value > value) currentPage.value = value
})

function ensureColumnWidthRuntime() {
  const signature = `${props.preferenceUserKey}|${props.pageId}|${props.tableId}`
  if (columnWidthRuntime && columnWidthRuntimeSignature === signature) return columnWidthRuntime
  columnWidthRuntimeSignature = signature
  columnWidthRuntime = createColumnWidthPreferenceRuntime({
    storage: globalThis.localStorage,
    userKey: props.preferenceUserKey,
    pageId: props.pageId,
    tableId: props.tableId,
  })
  return columnWidthRuntime
}

async function applyColumnWidths() {
  await nextTick()
  ensureColumnWidthRuntime().apply(tableRef.value)
}

function handleHeaderDragend(newWidth, oldWidth, column) {
  ensureColumnWidthRuntime().persist(newWidth, column)
  tableRef.value?.doLayout?.()
}

function resetColumnWidths() {
  ensureColumnWidthRuntime().reset(tableRef.value)
}

onMounted(applyColumnWidths)
watch(() => [props.preferenceUserKey, props.pageId, props.tableId], applyColumnWidths)

function resolveRowIndex(index) {
  return (currentPage.value - 1) * pageSize.value + index + 1
}

function resolveRowIdentity(row) {
  const configured = row?.[props.rowKey]
  if (configured !== undefined && configured !== null && configured !== '') {
    return `${props.rowKey}:${configured}`
  }
  const primary = row?.[props.primaryField]
  if (primary !== undefined && primary !== null && primary !== '') {
    return `${props.primaryField}:${primary}`
  }
  return row
}

function clearSort() {
  tableRef.value?.clearSort()
  emit('clear-sort')
}

function clearSelection() {
  tableRef.value?.clearSelection()
  internalSelectedRows.value = []
  emit('selection-change', [])
  emit('clear-selection')
}

function requestExportCurrent() {
  emit('export-current')
}

function toggleRowSelection(row, selected) {
  tableRef.value?.toggleRowSelection(row, selected)
  internalSelectedRows.value = applySingleRowSelection(internalSelectedRows.value, row, selected, resolveRowIdentity)
  emit('selection-change', internalSelectedRows.value)
}

function handleSingleRowSelection(rows, row) {
  const selected = selectionContains(rows, row, resolveRowIdentity)
  internalSelectedRows.value = applySingleRowSelection(internalSelectedRows.value, row, selected, resolveRowIdentity)
  emit('selection-change', internalSelectedRows.value)
}

function handleHeaderSelection(rows) {
  const selected = pagedRows.value.length > 0 && rows.length > 0
  internalSelectedRows.value = applyHeaderSelection(internalSelectedRows.value, pagedRows.value, selected, resolveRowIdentity)
  emit('selection-change', internalSelectedRows.value)
}

function applyBatchFilter() {
  const result = batchFilterRuntime.value.createFilter(internalSelectedRows.value, batchFilterField.value)
  emit('update-filter', result.field, result.values)
}

defineExpose({
  clearSort,
  clearSelection,
  toggleRowSelection,
  currentPage,
  pageSize,
  totalPages,
  applyColumnWidths,
  resetColumnWidths,
})
</script>

<style scoped>
.pce-enterprise-toolbar-extension {
  display: flex;
  justify-content: flex-end;
  padding: 0 14px 10px;
}

.pce-column-width-actions {
  display: flex;
  justify-content: flex-end;
  margin: 0 0 8px;
}
</style>

<style scoped>
.pce-enterprise-list-table {
  width: 100%;
  min-width: 0;
  max-width: 100%;
  overflow-x: hidden;
}

.pce-enterprise-table-scroll {
  width: 100%;
  min-width: 0;
  max-width: 100%;
}

.pce-enterprise-table-viewport { width: 100%; min-width: 0; max-width: 100%; margin-top: 10px; }

.pce-enterprise-table-scroll :deep(.el-scrollbar__wrap) {
  overflow-x: auto !important;
  overflow-y: auto !important;
  scrollbar-gutter: stable;
}

.pce-enterprise-table-scroll :deep(.el-table__header-wrapper),
.pce-enterprise-table-scroll :deep(th.el-table__cell) {
  position: sticky;
  top: 0;
  z-index: 5;
  background: #f8fafc;
}

.pce-enterprise-table-scroll :deep(.el-scrollbar__bar.is-horizontal) {
  display: block !important;
  height: 12px;
  bottom: 0;
  opacity: 1 !important;
}

.pce-enterprise-table-scroll :deep(.el-scrollbar__thumb) {
  background-color: #94a3b8;
}

.pce-enterprise-row-actions {
  display: flex;
  min-width: 0;
  gap: 6px;
  align-items: center;
  white-space: nowrap;
}

.pce-enterprise-row-actions :deep(.el-button + .el-button) {
  margin-left: 0;
}

.pce-enterprise-list-table[data-pce-row-density='compact'] :deep(.el-table__body td.el-table__cell) {
  height: 38px;
  padding: 4px 0;
}

.pce-enterprise-list-table[data-pce-row-density='compact'] :deep(.el-table__body .cell) {
  overflow: hidden;
  line-height: 22px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pce-enterprise-no-action { color: #94a3b8; font-size: 12px; }

.pce-enterprise-batch-filter {
  display: flex;
  min-width: 0;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin: 10px 0;
  padding: 10px 12px;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  background: #eff6ff;
}

.pce-enterprise-batch-filter :deep(.el-select) { width: 220px; }

.pce-enterprise-pagination {
  display: flex;
  min-width: 0;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  min-height: 44px;
  padding: 10px 2px 0;
  color: #334155;
  font-size: 13px;
}

.pce-enterprise-pagination label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.pce-enterprise-pagination select,
.pce-enterprise-pagination button {
  min-height: 32px;
  padding: 5px 10px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  background: #fff;
  color: #1e293b;
}

.pce-enterprise-pagination button:not(:disabled) {
  cursor: pointer;
}

.pce-enterprise-pagination button:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}
</style>
