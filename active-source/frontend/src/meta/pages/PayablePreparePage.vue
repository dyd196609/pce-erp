<template>
  <main class="payable-page">
    <section v-if="detailRecord" class="table-card payable-prepare-detail" data-pce-section="payable-prepare-detail">
      <div class="toolbar-title">
        <div>
          <p class="eyebrow">V1.14.2.8.4.7.32 · Finance</p>
          <h2 data-testid="payable-prepare-detail-title">{{ pageName.pageTitle }}</h2>
        </div>
        <router-link class="flow-link-button" to="/finance/payable-prepares">返回采购应付预备列表</router-link>
      </div>
      <dl class="detail-grid">
        <div><dt>应付预备编号</dt><dd data-testid="payable-prepare-detail-no">{{ detailRecord.payablePrepareNo }}</dd></div>
        <div><dt>状态</dt><dd data-testid="payable-prepare-detail-status">{{ displayValue(detailRecord.payableStatus) }}</dd></div>
        <div><dt>来源库存流水</dt><dd data-testid="payable-prepare-detail-transaction-no">{{ detailRecord.sourceInventoryTransactionNo }}</dd></div>
        <div><dt>来源流水类型</dt><dd data-testid="payable-prepare-detail-transaction-type">{{ detailRecord.sourceInventoryTransactionType }}</dd></div>
        <div><dt>来源仓库任务</dt><dd data-testid="payable-prepare-detail-warehouse-task-no">{{ detailRecord.sourceWarehouseTaskNo }}</dd></div>
        <div><dt>来源检验单</dt><dd data-testid="payable-prepare-detail-inspection-no">{{ detailRecord.sourceInspectionNo }}</dd></div>
        <div><dt>来源采购收货</dt><dd data-testid="payable-prepare-detail-receive-no">{{ detailRecord.sourceReceiveNo }}</dd></div>
        <div><dt>来源采购订单</dt><dd data-testid="payable-prepare-detail-order-no">{{ detailRecord.sourcePurchaseOrderNo }}</dd></div>
        <div><dt>来源核价单</dt><dd data-testid="payable-prepare-detail-price-approval-no">{{ detailRecord.sourcePriceApprovalNo }}</dd></div>
        <div><dt>供应商</dt><dd data-testid="payable-prepare-detail-supplier">{{ detailRecord.supplierName }}</dd></div>
        <div><dt>物料</dt><dd data-testid="payable-prepare-detail-material">{{ detailLine.materialCode }} / {{ detailLine.materialName }}</dd></div>
        <div><dt>应付数量</dt><dd data-testid="payable-prepare-detail-quantity">{{ detailRecord.totalPayableQty }} {{ detailLine.unit }}</dd></div>
        <div><dt>应付单价</dt><dd data-testid="payable-prepare-detail-price">{{ detailLine.payablePrice }}</dd></div>
        <div><dt>应付金额</dt><dd data-testid="payable-prepare-detail-amount">{{ detailRecord.totalPayableAmount }}</dd></div>
      </dl>
      <div class="detail-actions">
        <el-button
          v-if="!detailPayableCheck"
          type="primary"
          data-testid="create-payable-check-from-detail"
          @click="createPayableCheckAndOpen(detailRecord)"
        >{{ pceBusinessActionLabel('generate-payable-check-from-prepare') }}</el-button>
        <el-button
          v-else
          type="primary"
          plain
          data-testid="open-payable-check-from-detail"
          @click="openPayableCheck(detailPayableCheck)"
        >{{ pceBusinessActionLabel('enter-payable-check') }}</el-button>
      </div>
    </section>
    <section class="table-card">
      <div class="toolbar-title">
        <div v-if="!embeddedInCommonShell">
          <p class="eyebrow">V1.14.2.8.3 · Finance</p>
          <h2 data-acceptance-id="page-internal-subject-title">{{ pageName.pageTitle }}</h2>
        </div>
        <span>当前结果 {{ filteredSortedRows.length }} 条</span>
      </div>

      <div class="business-flow-action-toolbar" data-acceptance-id="business-flow-action-toolbar">
        <PceBusinessActionBar
          current-module="payable-prepare"
          :selected-rows="selectedRows"
          :show-unavailable="selectedRows.length === 0"
          @execute="executeRegistryAction"
        />
        <div class="business-flow-secondary-actions" data-acceptance-id="business-flow-secondary-actions">
          <strong>辅助操作</strong>
          <el-button type="primary" plain @click="exportCurrentRows">导出当前结果</el-button>
        </div>
      </div>

      <section v-if="latestActionResult" class="action-result" data-testid="payable-prepare-action-result">
        <strong>生成结果</strong>
        <span data-testid="payable-prepare-action-status">{{ latestActionResult.status }}</span>
        <span data-testid="payable-prepare-action-no">{{ latestActionResult.payablePrepareNo }}</span>
        <span data-testid="payable-prepare-action-source-no">{{ latestActionResult.sourceInventoryTransactionNo }}</span>
      </section>

      <StandardListToolbar
        page-id="payable-prepare"
        table-id="payable-prepare-main"
        v-model:quick-search="quickSearch"
        :advanced-visible="advancedFilterVisible"
        :result-count="filteredSortedRows.length"
        :selected-count="selectedRows.length"
        :active-filter-count="activeFilterCount"
        :sort-text="sortStateLabel"
        :export-disabled="filteredSortedRows.length === 0"
        @search="clearSelection"
        @toggle-advanced="advancedFilterVisible = !advancedFilterVisible"
        @clear-filters="clearFilters"
        @clear-sort="clearSort"
        @export-current="exportCurrentRows"
        @clear-selection="clearSelection"
      />

      <section v-show="advancedFilterVisible" class="advanced-filter-panel" data-acceptance-id="list-advanced-filter-panel" data-pce-filter-for="payable-prepare-main">
        <label>来源库存流水编号<PceResultFilterSelect v-model="filters.sourceInventoryTransactionNo" :rows="rows" :fields="['sourceInventoryTransactionNo']" /></label>
        <label>应付预备单号<PceResultFilterSelect v-model="filters.payablePrepareNo" :rows="rows" :fields="['payablePrepareNo']" /></label>
        <label>来源采购订单号<PceResultFilterSelect v-model="filters.sourcePurchaseOrderNo" :rows="rows" :fields="['sourcePurchaseOrderNo']" /></label>
        <label>供应商<PceResultFilterSelect v-model="filters.supplierName" :rows="rows" :fields="['supplierName']" /></label>
        <label>状态<PceResultFilterSelect v-model="filters.payableStatus" :rows="rows" :fields="['payableStatus']" /></label>
        <label>来源回写状态<PceResultFilterSelect v-model="filters.flowWritebackStatus" :rows="rows" :fields="['flowWritebackStatus']" /></label>
      </section>

      <BusinessTableScrollContainer
        class="pce-baseline-table-shell"
        acceptance-id="business-table-scroll-payable-prepare-main"
        page-id="payable-prepare"
        table-id="payable-prepare-main"
        min-width="2600px"
      >
        <el-table
          ref="tableRef"
          class="global-sort-arrow"
          :data="filteredSortedRows"
          border
          stripe
          height="520"
          style="width: 100%"
          scrollbar-always-on
          @selection-change="handleSelectionChange"
          @sort-change="handleSortChange"
        >
          <el-table-column
            type="selection"
            width="48"
            fixed="left"
            class-name="business-table-selection-column"
            header-class-name="business-table-selection-column"
          />
          <el-table-column type="index" label="序号" width="64" fixed="left" class-name="pce-fixed-index-column" header-class-name="pce-fixed-index-column" />
          <el-table-column prop="sourceInventoryTransactionNo" label="来源库存流水编号" min-width="190" fixed="left" sortable="custom" />
          <el-table-column prop="payablePrepareNo" label="应付预备单号" min-width="180" fixed="left" sortable="custom" class-name="pce-fixed-primary-no-column" header-class-name="pce-fixed-primary-no-column" />
          <el-table-column prop="sourceInventoryTransactionType" label="来源流水类型" min-width="170" sortable="custom" />
          <el-table-column prop="sourceWarehouseTaskNo" label="来源仓库任务" min-width="170" sortable="custom" />
          <el-table-column prop="sourcePurchaseOrderNo" label="来源采购订单号" min-width="160" sortable="custom" />
          <el-table-column prop="sourceReceiveNo" label="来源收货单号" min-width="150" sortable="custom" />
          <el-table-column prop="sourceInspectionNo" label="来源检验单号" min-width="150" sortable="custom" />
          <el-table-column prop="supplierName" label="供应商" min-width="160" sortable="custom" />
          <el-table-column prop="totalPayableQty" label="应付预备数量" width="130" sortable="custom" />
          <el-table-column prop="totalPayableAmount" label="应付预备金额" width="140" sortable="custom" />
          <el-table-column prop="payableStatus" label="应付预备状态" width="130" sortable="custom">
            <template #default="{ row }">{{ displayValue(row.payableStatus) }}</template>
          </el-table-column>
          <el-table-column prop="downstreamObjectNo" label="下游对象编号" min-width="170">
            <template #default="{ row }">{{ displayNo(row.downstreamObjectNo) }}</template>
          </el-table-column>
          <el-table-column prop="flowWritebackStatus" label="来源回写状态" min-width="150">
            <template #default="{ row }">{{ displayValue(row.flowWritebackStatus) }}</template>
          </el-table-column>
          <el-table-column label="操作" fixed="right" min-width="310" class-name="payment-fixed-action-column" header-class-name="payment-fixed-action-column">
            <template #default="{ row }">
              <div class="row-actions">
                <el-button size="small" plain @click="goInventory(row)">查看来源库存流水</el-button>
                <el-button
                  v-if="!row.payablePrepareGenerated"
                  size="small"
                  type="primary"
                  data-testid="create-payable-prepare-row"
                  @click="handleCreateRow(row)"
                >{{ pceBusinessActionLabel('generate-payable-prepare') }}</el-button>
                <el-button
                  v-else
                  size="small"
                  type="primary"
                  plain
                  data-testid="view-payable-prepare-row"
                  @click="goPayablePrepare(row)"
                >查看采购应付预备</el-button>
                <el-button
                  v-if="row.payablePrepareGenerated && !row.payableCheckGenerated"
                  size="small"
                  type="primary"
                  data-testid="create-payable-check-row"
                  @click="createPayableCheckAndOpen(row)"
                >{{ pceBusinessActionLabel('generate-payable-check-from-prepare') }}</el-button>
                <el-button
                  v-if="row.payableCheckGenerated"
                  size="small"
                  type="primary"
                  plain
                  data-testid="open-payable-check-row"
                  @click="openPayableCheck(row.payableCheck)"
                >{{ pceBusinessActionLabel('enter-payable-check') }}</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </BusinessTableScrollContainer>
    </section>
  </main>
</template>

<script setup>
const { embeddedInCommonShell = false } = defineProps({
  embeddedInCommonShell: { type: Boolean, default: false },
})
import { computed, reactive, ref } from 'vue'
import PceResultFilterSelect from '../components/PceResultFilterSelect.vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import BusinessTableScrollContainer from '../components/BusinessTableScrollContainer.vue'
import StandardListToolbar from '../components/StandardListToolbar.vue'
import PceBusinessActionBar from '../components/PceBusinessActionBar.vue'
import { pceBusinessActionLabel } from '../runtime/pceBusinessActionRegistry.js'
import {
  batchCreatePayablePrepareFromInventoryTransactions,
  createPayablePrepareFromInventoryTransaction,
  getPayablePrepareByInventoryTransaction,
  getPayablePrepareSourcesFromInventory,
  listPayablePrepares,
} from '../finance/payablePrepareStore.js'
import {
  createPayableCheckFromPayablePrepare,
  listPayableChecks,
} from '../finance/payableCheckStore.js'
import { formatBusinessNo, formatBusinessStatus } from '../runtime/businessDisplayValueFormatter.js'
import { resolvePageNameConsumption } from '../governance/pageNameConsumer.js'

const router = useRouter()
const route = useRoute()
const pageName = resolvePageNameConsumption({ pageCode: 'payable-prepare', route: '/finance/payable-prepares' })
const tableRef = ref(null)
const rows = ref(buildRows())
const selectedRows = ref([])
const latestActionResult = ref(null)
const quickSearch = ref('')
const advancedFilterVisible = ref(false)
const sortState = ref({ prop: '', order: '' })
const filters = reactive({
  sourceInventoryTransactionNo: '',
  payablePrepareNo: '',
  sourcePurchaseOrderNo: '',
  supplierName: '',
  payableStatus: '',
  flowWritebackStatus: '',
})
const detailRecord = computed(() => {
  const id = String(route.params.id || '')
  return id ? listPayablePrepares().find((item) => String(item.id) === id) || null : null
})
const detailLine = computed(() => detailRecord.value?.lines?.[0] || {})
const detailPayableCheck = computed(() => listPayableChecks().find((item) => String(item.sourcePayablePrepareId) === String(detailRecord.value?.id || '')) || null)
const filteredRows = computed(() => rows.value.filter(matchRow))
const filteredSortedRows = computed(() => {
  const list = [...filteredRows.value]
  const { prop, order } = sortState.value
  if (!prop || !order) return list
  const factor = order === 'descending' ? -1 : 1
  return list.sort((a, b) => compareValue(a[prop], b[prop]) * factor)
})
const activeFilterCount = computed(() => Object.values(filters).filter((item) => String(item || '').trim()).length + (quickSearch.value.trim() ? 1 : 0))
const sortStateLabel = computed(() => {
  if (!sortState.value.prop || !sortState.value.order) return '默认业务顺序'
  return `${sortState.value.prop} ${sortState.value.order === 'ascending' ? '升序' : '降序'}`
})

const primaryActionDisabled = computed(() => selectedRows.value.length === 0 || selectedRows.value.every((row) => row.payablePrepareGenerated))
const primaryActionDisabledReason = computed(() => (
  selectedRows.value.length === 0
    ? '请选择一条采购应付预备来源记录后再执行。'
    : primaryActionDisabled.value
      ? '所选来源库存流水已生成采购应付预备，不能重复生成。'
      : '已选择记录，可执行本页业务流程动作。'
))

function buildRows() {
  const checksByPrepareId = new Map(listPayableChecks().map((item) => [String(item.sourcePayablePrepareId), item]))
  const sources = getPayablePrepareSourcesFromInventory()
  const linkedIds = new Set()
  const sourceRows = sources.map((source) => {
    const target = getPayablePrepareByInventoryTransaction(source)
    if (target?.id) linkedIds.add(target.id)
    return {
      ...source,
      ...(target || {}),
      rowType: 'inventoryTransactionSource',
      sourceInventoryTransactionId: source.id,
      sourceInventoryTransactionIds: [source.id],
      sourceInventoryTransactionNo: source.transactionNo,
      sourceInventoryTransactionType: source.transactionType,
      sourceWarehouseTaskId: source.sourceWarehouseTaskId || '',
      sourceWarehouseTaskNo: source.sourceWarehouseTaskNo || '',
      payablePrepareGenerated: Boolean(target),
      payableCheckGenerated: Boolean(target?.id && checksByPrepareId.has(String(target.id))),
      payableCheck: target?.id ? checksByPrepareId.get(String(target.id)) || null : null,
      payablePrepareNo: target?.payablePrepareNo || '',
      payableStatus: target?.payableStatus || 'notPrepared',
    }
  })
  const orphanTargets = listPayablePrepares().filter((item) => !linkedIds.has(item.id)).map((item) => ({
    ...item,
    rowType: 'payablePrepare',
    payablePrepareGenerated: true,
    payableCheckGenerated: checksByPrepareId.has(String(item.id)),
    payableCheck: checksByPrepareId.get(String(item.id)) || null,
  }))
  return [...sourceRows, ...orphanTargets]
}

function refreshRows() {
  rows.value = buildRows()
}

function handleSelectionChange(selection) {
  selectedRows.value = selection
}

function handleSortChange({ prop, order }) {
  sortState.value = { prop: prop || '', order: order || '' }
  clearSelection()
}

function clearSelection() {
  tableRef.value?.clearSelection?.()
  selectedRows.value = []
}

function clearSort() {
  sortState.value = { prop: '', order: '' }
  tableRef.value?.clearSort?.()
}

function clearFilters() {
  quickSearch.value = ''
  Object.keys(filters).forEach((key) => { filters[key] = '' })
  clearSelection()
}

function displayValue(value) {
  return formatBusinessStatus(value, '未执行')
}

function displayNo(value) {
  return formatBusinessNo(value)
}

function resolveSourceInventoryIds() {
  return selectedRows.value
    .filter((row) => !row.payablePrepareGenerated)
    .flatMap((row) => row.sourceInventoryTransactionIds || row.sourceInventoryTransactionId || [])
    .filter(Boolean)
}

function handleCreateSelected() {
  const [sourceId] = resolveSourceInventoryIds()
  if (!sourceId) {
    ElMessage.warning('当前选择记录缺少来源库存流水，不能执行。')
    return
  }
  const result = createPayablePrepareFromInventoryTransaction(sourceId)
  latestActionResult.value = result
  refreshRows()
  clearSelection()
  if (result?.status === 'already_exists') ElMessage.warning(`该来源流水已存在采购应付预备：${result.payablePrepareNo}`)
  else if (result?.success) ElMessage.success(`已生成采购应付预备：${result.payablePrepareNo}`)
  else ElMessage.warning(result?.error || '当前功能尚未接入，不能执行。')
}

function handleCreateRow(row) {
  selectedRows.value = [row]
  handleCreateSelected()
}

function handleBatchCreateSelected() {
  const sourceIds = resolveSourceInventoryIds()
  if (!sourceIds.length) {
    ElMessage.warning('当前选择记录缺少来源库存流水，不能执行。')
    return
  }
  const result = batchCreatePayablePrepareFromInventoryTransactions(sourceIds)
  refreshRows()
  clearSelection()
  ElMessage.success(`批量处理完成：成功 ${result.successCount} 条，失败 ${result.failedCount} 条。`)
}

function executeRegistryAction(action) {
  if (action.actionId === 'generate-payable-prepare') {
    handleCreateSelected()
    return
  }
  if (action.actionId === 'batch-generate-payable-prepare') {
    handleBatchCreateSelected()
  }
}

function openPayableCheck(check) {
  if (!check?.id) {
    ElMessage.warning('未找到采购应付核对记录。')
    return
  }
  router.push({ path: `/finance/payable-check/${check.id}` })
}

function createPayableCheckAndOpen(prepare) {
  const prepareId = prepare?.id || prepare?.sourcePayablePrepareId
  if (!prepareId) {
    ElMessage.warning('当前记录缺少采购应付预备标识，不能生成采购应付核对。')
    return
  }
  const result = createPayableCheckFromPayablePrepare(prepareId)
  refreshRows()
  if (!result?.ok) {
    ElMessage.warning(result?.error || '生成采购应付核对失败。')
    return
  }
  if (result.status === 'already_exists') ElMessage.warning(`采购应付核对已存在：${result.payableCheckNo}`)
  else ElMessage.success(`已生成采购应付核对：${result.payableCheckNo}`)
  openPayableCheck(result.record)
}

function includeField(value, keyword) {
  const text = String(keyword || '').trim().toLowerCase()
  if (!text) return true
  return String(value || '').toLowerCase().includes(text)
}

function matchRow(row) {
  const q = quickSearch.value.trim().toLowerCase()
  if (q && ![
    row.payablePrepareNo,
    row.sourceInventoryTransactionNo,
    row.sourceInventoryTransactionType,
    row.sourceWarehouseTaskNo,
    row.sourcePurchaseOrderNo,
    row.sourceReceiveNo,
    row.sourceInspectionNo,
    row.supplierName,
    displayValue(row.payableStatus),
    row.downstreamObjectNo,
  ].join(' ').toLowerCase().includes(q)) return false
  if (!includeField(row.payablePrepareNo, filters.payablePrepareNo)) return false
  if (!includeField(row.sourceInventoryTransactionNo, filters.sourceInventoryTransactionNo)) return false
  if (!includeField(row.sourcePurchaseOrderNo, filters.sourcePurchaseOrderNo)) return false
  if (!includeField(row.supplierName, filters.supplierName)) return false
  if (!includeField(row.payableStatus, filters.payableStatus)) return false
  if (!includeField(row.flowWritebackStatus, filters.flowWritebackStatus)) return false
  return true
}

function compareValue(a, b) {
  const leftNumber = Number(a)
  const rightNumber = Number(b)
  if (Number.isFinite(leftNumber) && Number.isFinite(rightNumber)) return leftNumber - rightNumber
  return String(a || '').localeCompare(String(b || ''), 'zh-CN')
}

function goInventory(row) {
  router.push({ path: `/wms/inventory-transaction/${row.sourceInventoryTransactionId}` })
}

function goPayablePrepare(row) {
  router.push({ path: `/finance/payable-prepare/${row.id}` })
}

function exportCurrentRows() {
  const csv = ['应付预备单号,来源采购订单号,供应商,应付预备金额,状态']
    .concat(filteredSortedRows.value.map((row) => [
      row.payablePrepareNo,
      row.sourcePurchaseOrderNo,
      row.supplierName,
      row.totalPayableAmount,
      row.payableStatus,
    ].map((item) => `"${String(item ?? '').replaceAll('"', '""')}"`).join(',')))
    .join('\n')
  const blob = new Blob([`\ufeff${csv}`], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = 'payable-prepares.csv'
  link.click()
  URL.revokeObjectURL(link.href)
}
</script>

<style scoped>
.payable-page {
  display: grid;
  gap: 16px;
  max-width: 100%;
  overflow-x: hidden;
}

.table-card {
  display: grid;
  gap: 14px;
}

.toolbar-title,
.business-flow-action-toolbar {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.toolbar-title h2,
.toolbar-title p {
  margin: 0;
}

.eyebrow {
  color: #2563eb;
  font-size: 13px;
  font-weight: 800;
}

.business-flow-primary-actions,
.business-flow-secondary-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.business-flow-primary-actions small {
  flex-basis: 100%;
  color: #b45309;
  font-weight: 700;
}

.flow-link-button {
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  padding: 0 12px;
  border: 1px solid #2563eb;
  border-radius: 6px;
  color: #2563eb;
  font-weight: 700;
  text-decoration: none;
}

.advanced-filter-panel {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 10px;
  padding: 10px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}

.advanced-filter-panel label {
  display: grid;
  gap: 5px;
  color: #334155;
  font-size: 12px;
  font-weight: 800;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 10px;
  margin: 0;
}

.detail-grid div,
.action-result {
  padding: 10px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #eff6ff;
}

.detail-grid dt {
  color: #64748b;
  font-size: 12px;
}

.detail-grid dd {
  margin: 4px 0 0;
  font-weight: 700;
}

.action-result {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.row-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
</style>
