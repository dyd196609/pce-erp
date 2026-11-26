<template>
  <main class="supplier-settlement-page">
    <section class="table-card">
      <div class="toolbar-title">
        <div v-if="!embeddedInCommonShell">
          <p class="eyebrow">V1.14.2.8.4.7 · SCM</p>
          <h2 data-acceptance-id="page-internal-subject-title"><PceBusinessNameConsumer page-code="supplier-settlement" /></h2>
          <p class="page-note">
            本页用于查看供应商结算对象，承接应付核对后的结算确认；采购对账已拆分为独立只读页面。
            本页不付款、不写总账、不核销、不生成银行流水。
          </p>
        </div>
        <div class="toolbar-actions">
          <el-button type="success" plain @click="copyDiagnostics">复制诊断数据</el-button>
        </div>
      </div>
      <PceBusinessActionBar
        current-module="supplier-settlement"
        :current-status="supplierSettlementBusinessStatus"
        :selected-rows="selectedRows"
        :show-unavailable="true"
        @execute="executeRegistryAction"
      />

      <section v-if="contextResolution.contextualMode" class="source-context-panel" data-acceptance-id="supplier-settlement-source-context">
        <strong>供应商结算来源上下文</strong>
        <span>来源上下文状态：{{ contextResolution.status }}</span>
        <span class="semantic-compatibility-alias">页面来源状态：{{ contextResolution.status }}</span>
        <span>来源采购应付核对编号：{{ resolvedSourceContext.sourcePayableCheckNo || '-' }}</span>
        <span>来源采购应付核对状态：{{ resolvedSourceContext.sourceStatus || '-' }}</span>
        <span>来源采购应付预备编号：{{ resolvedSourceContext.sourcePayablePrepareNo || '-' }}</span>
        <span>来源采购订单编号：{{ resolvedSourceContext.purchaseOrderNo || '-' }}</span>
        <span>供应商编号：{{ resolvedSourceContext.supplierId || '-' }}</span>
        <span>供应商名称：{{ resolvedSourceContext.supplierName || '-' }}</span>
        <span>来源应付金额：{{ formatAmount(resolvedSourceContext.payableAmount) }}</span>
        <span>来源核对金额：{{ formatAmount(resolvedSourceContext.checkedAmount) }}</span>
        <span>差异金额：{{ formatAmount(resolvedSourceContext.differenceAmount) }}</span>
      </section>

      <section v-if="contextResolution.contextualMode" class="source-context-panel target-context-panel" data-acceptance-id="supplier-settlement-target-context">
        <strong>目标供应商结算</strong>
        <span>目标供应商结算编号：{{ targetSettlement?.settlementNo || '-' }}</span>
        <span>供应商结算对象是否存在：{{ targetSettlement ? '是' : '否' }}</span>
        <span>供应商结算状态：{{ targetSettlement?.settlementStatus || '-' }}</span>
        <span>数量：{{ targetSettlement ? `${targetSettlement.settlementQuantity || 0}${targetSettlement.unit || ''}` : '-' }}</span>
        <span>金额：{{ targetSettlement ? formatAmount(targetSettlement.settlementAmount) : '-' }}</span>
      </section>

      <section v-if="contextResolution.contextualMode" class="source-context-panel pre-reconciliation-panel" data-acceptance-id="supplier-settlement-pre-reconciliation-status">
        <strong>采购对账前状态</strong>
        <span>供应商结算状态：{{ targetSettlement?.settlementStatus || '-' }}</span>
        <span>是否达到采购对账入口条件：{{ preReconciliationEligible ? '是' : '否' }}</span>
        <span>采购对账对象数量：{{ downstreamCounts.purchaseReconciliationObjectCount }}</span>
        <span>是否已经创建采购对账对象：{{ downstreamCounts.purchaseReconciliationObjectCount > 0 ? '是' : '否' }}</span>
        <span>付款对象数量：{{ downstreamCounts.paymentObjectCount }}</span>
        <span>是否已经创建付款对象：{{ downstreamCounts.paymentObjectCount > 0 ? '是' : '否' }}</span>
      </section>

      <section v-if="detailRecord" class="source-context-panel" data-acceptance-id="supplier-settlement-detail-record">
        <strong>供应商结算单：{{ detailRecord.settlementNo }}</strong>
        <span>来源应付核对：{{ detailRecord.sourcePayableCheckNo }}</span>
        <span>来源应付预备：{{ detailRecord.sourcePayablePrepareNo }}</span>
        <span>来源库存流水：{{ detailRecord.sourceInventoryTransactionNos?.join('、') || '-' }}</span>
        <span>来源采购订单：{{ detailRecord.sourcePurchaseOrderNo }}</span>
        <span>来源核价单：{{ detailRecord.sourcePriceApprovalNo }}</span>
        <span>供应商：{{ detailRecord.supplierName }}</span>
        <span>物料：{{ detailRecord.materialCode }} / {{ detailRecord.materialName }}</span>
        <span>数量：{{ detailRecord.settlementQuantity }}{{ detailRecord.unit }}</span>
        <span>结算金额：{{ formatAmount(detailRecord.settlementAmount) }}</span>
        <span>结算状态：{{ displayStatus(detailRecord.settlementStatus, '-') }}</span>
        <span>采购对账对象：未生成</span>
        <span>付款流程：未进入</span>
      </section>

      <el-alert
        v-if="contextResolution.status === 'existing_settlement'"
        data-acceptance-id="supplier-settlement-context-existing"
        title="已找到与当前采购应付核对来源匹配的供应商结算记录。"
        type="success"
        show-icon
        :closable="false"
      />
      <el-alert
        v-else-if="contextResolution.status === 'pending_source'"
        data-acceptance-id="supplier-settlement-context-pending"
        title="当前采购应付核对来源真实存在，但尚未形成供应商结算记录。"
        description="下方显示待结算来源记录；本页不会自动生成供应商结算单。"
        type="warning"
        show-icon
        :closable="false"
      />
      <el-alert
        v-else-if="['invalid_source', 'incomplete_source'].includes(contextResolution.status)"
        data-acceptance-id="supplier-settlement-context-invalid"
        :title="contextResolution.status === 'incomplete_source' ? '来源采购应付核对存在，但必要来源关系不完整。' : '未找到与当前采购应付核对记录匹配的来源数据。'"
        type="error"
        show-icon
        :closable="false"
      >
        <template #default>
          <ul class="context-mismatch-list">
            <li>传入的来源采购应付核对编号：{{ sourceContext.sourcePayableCheckNo || '-' }}</li>
            <li>传入的来源采购应付预备编号：{{ sourceContext.sourcePayablePrepareNo || '-' }}</li>
            <li>传入的采购订单号：{{ sourceContext.purchaseOrderNo || '-' }}</li>
            <li v-for="item in contextResolution.mismatchFields" :key="`${item.field}-${item.expected}-${item.actual}`">
              不匹配字段 {{ mismatchFieldLabel(item.field) }}：传入/期望 {{ item.expected || '-' }}，实际 {{ item.actual || '-' }}
            </li>
          </ul>
        </template>
      </el-alert>

      <StandardListToolbar
        page-id="supplier-settlement"
        table-id="supplier-settlement-main"
        v-model:quick-search="quickSearch"
        :advanced-visible="advancedFilterVisible"
        :result-count="rows.length"
        :selected-count="selectedRows.length"
        :active-filter-count="activeFilterCount"
        :sort-text="sortStateLabel"
        :export-disabled="rows.length === 0"
        @search="clearSelection"
        @toggle-advanced="advancedFilterVisible = !advancedFilterVisible"
        @clear-filters="clearFilters"
        @clear-sort="clearSort"
        @export-current="exportCurrentRows"
        @clear-selection="clearSelection"
      />

      <section v-show="advancedFilterVisible" class="advanced-filter-panel" data-acceptance-id="list-advanced-filter-panel" data-pce-filter-for="supplier-settlement-main">
        <label>供应商结算单号<PceResultFilterSelect v-model="filters.settlementNo" :rows="rows" :fields="['settlementNo']" /></label>
        <label>来源应付核对单号<PceResultFilterSelect v-model="filters.sourcePayableCheckNo" :rows="rows" :fields="['sourcePayableCheckNo']" /></label>
        <label>供应商<PceResultFilterSelect v-model="filters.supplierName" :rows="rows" :fields="['supplierName']" /></label>
        <label>采购订单号<PceResultFilterSelect v-model="filters.purchaseOrderNo" :rows="rows" :fields="['purchaseOrderNo']" /></label>
        <label>对账状态<el-select v-model="filters.reconciliationStatus" clearable placeholder="全部">
          <el-option label="金额一致" value="matched" />
          <el-option label="存在差异" value="amount_difference" />
          <el-option label="来源缺失" value="source_missing" />
        </el-select></label>
        <label>结算状态<el-select v-model="filters.settlementStatus" clearable placeholder="全部">
          <el-option label="草稿" value="draft" />
          <el-option label="对账中" value="reconciling" />
          <el-option label="已对账" value="reconciled" />
          <el-option label="差异待处理" value="difference_pending" />
          <el-option label="已关闭" value="closed" />
        </el-select></label>
        <label>下一步准备状态<PceResultFilterSelect v-model="filters.nextStepReadiness" :rows="rows" :fields="['nextStepReadiness']" /></label>
      </section>

      <BusinessTableScrollContainer
        class="pce-baseline-table-shell"
        acceptance-id="business-table-scroll-supplier-settlement-main"
        page-id="supplier-settlement"
        table-id="supplier-settlement-main"
        min-width="2600px"
      >
        <el-table
          ref="supplierSettlementTableRef"
          class="pce-baseline-table-shell global-sort-arrow"
          :data="rows"
          border
          stripe
          height="520"
          scrollbar-always-on
          row-key="id"
          @selection-change="handleSelectionChange"
          @sort-change="handleSortChange"
        >
          <el-table-column
            type="selection"
            width="52"
            fixed="left"
            :selectable="isSelectableSettlementRow"
            class-name="business-table-selection-column"
            label-class-name="business-table-selection-column"
          />
          <el-table-column
            type="index"
            label="序号"
            width="70"
            fixed="left"
            class-name="pce-fixed-index-column"
            label-class-name="pce-fixed-index-column"
          />
          <el-table-column
            prop="settlementNo"
            label="供应商结算单号"
            min-width="200"
            fixed="left"
            sortable="custom"
            class-name="pce-fixed-primary-no-column"
            label-class-name="pce-fixed-primary-no-column"
          >
            <template #default="{ row }">{{ row.isPendingSource ? '尚未生成' : displayNo(row.settlementNo) }}</template>
          </el-table-column>
          <el-table-column prop="sourcePayableCheckNo" label="来源采购应付核对单号" min-width="210" sortable="custom">
            <template #default="{ row }">{{ displayNo(row.sourcePayableCheckNo || row.sourceObjectNo) }}</template>
          </el-table-column>
          <el-table-column prop="supplierName" label="供应商" min-width="170" sortable="custom">
            <template #default="{ row }">{{ row.supplierName || '-' }}</template>
          </el-table-column>
          <el-table-column prop="purchaseOrderNo" label="采购订单号" min-width="170" sortable="custom">
            <template #default="{ row }">{{ displayNo(row.purchaseOrderNo) }}</template>
          </el-table-column>
          <el-table-column prop="settlementAmount" label="结算金额" width="130" sortable="custom">
            <template #default="{ row }">{{ formatAmount(row.settlementAmount) }}</template>
          </el-table-column>
          <el-table-column prop="differenceAmount" label="差异金额" width="120" sortable="custom">
            <template #default="{ row }">{{ formatAmount(row.differenceAmount) }}</template>
          </el-table-column>
          <el-table-column prop="reconciliationStatus" label="对账状态" width="150" sortable="custom">
            <template #default="{ row }">{{ displayStatus(row.reconciliationStatus, '待对账') }}</template>
          </el-table-column>
          <el-table-column prop="settlementStatus" label="结算状态" width="150" sortable="custom">
            <template #default="{ row }">{{ displayStatus(row.settlementStatus, '草稿') }}</template>
          </el-table-column>
          <el-table-column prop="nextStepReadiness" label="下一步准备状态" min-width="160">
            <template #default="{ row }">{{ displayReadiness(row.nextStepReadiness) }}</template>
          </el-table-column>
          <el-table-column
            prop="operation"
            label="操作"
            min-width="280"
            fixed="right"
            class-name="payment-fixed-action-column"
            label-class-name="payment-fixed-action-column"
          >
            <template #default="{ row }">
              <div v-if="row.isPendingSource" class="row-actions">
                <el-button
                  type="primary"
                  size="small"
                  :disabled="Boolean(createBlockedReason)"
                  :title="createBlockedReason"
                  data-acceptance-id="generate-supplier-settlement"
                  @click="generateSupplierSettlement"
                >{{ pceBusinessActionLabel('generate-supplier-settlement') }}</el-button>
                <small v-if="createBlockedReason" class="blocked-reason">{{ createBlockedReason }}</small>
                <el-button size="small" plain @click="goPayableCheck(row)">查看来源采购应付核对</el-button>
              </div>
              <div v-else class="row-actions">
                <el-button size="small" plain @click="goPayableCheck(row)">查看来源采购应付核对</el-button>
                <el-button size="small" plain data-acceptance-id="view-supplier-settlement" @click="viewSupplierSettlement(row)">查看供应商结算单</el-button>
                <el-button size="small" plain data-acceptance-id="enter-purchase-reconciliation" @click="goPurchaseReconciliation(row)">{{ pceBusinessActionLabel('enter-purchase-reconciliation') }}</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </BusinessTableScrollContainer>
    </section>
  </main>
</template>

<script setup>
import PceBusinessNameConsumer from '../components/PceBusinessNameConsumer.vue'
const { embeddedInCommonShell = false } = defineProps({
  embeddedInCommonShell: { type: Boolean, default: false },
})
import { computed, onMounted, reactive, ref } from 'vue'
import PceResultFilterSelect from '../components/PceResultFilterSelect.vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import BusinessTableScrollContainer from '../components/BusinessTableScrollContainer.vue'
import StandardListToolbar from '../components/StandardListToolbar.vue'
import PceBusinessActionBar from '../components/PceBusinessActionBar.vue'
import { pceBusinessActionLabel } from '../runtime/pceBusinessActionRegistry.js'
import { formalExecutionApi } from '@/api/formalExecution.js'
import { resolveSupplierSettlementContext } from '../scm/resolveSupplierSettlementContext.js'
import { formatBusinessNo, formatBusinessStatus } from '../runtime/businessDisplayValueFormatter.js'
import { buildPurchaseReconciliationRoute, buildSupplierSettlementDetailRoute } from '../scm/supplierSettlementNavigation.js'

const VERSION = 'V1.14.2.8.4.7'
const router = useRouter()
const route = useRoute()
const supplierSettlementTableRef = ref(null)
const selectedRows = ref([])
const quickSearch = ref('')
const advancedFilterVisible = ref(false)
const sortState = ref({ prop: '', order: '' })
const filters = reactive({
  settlementNo: '',
  sourcePayableCheckNo: '',
  supplierName: '',
  purchaseOrderNo: '',
  reconciliationStatus: '',
  settlementStatus: '',
  nextStepReadiness: '',
})
const latestActionResult = ref(null)
const sourceContext = computed(() => ({
  sourcePayableCheckNo: String(route.query.sourcePayableCheckNo || ''),
  sourcePayablePrepareNo: String(route.query.sourcePayablePrepareNo || ''),
  purchaseOrderNo: String(route.query.purchaseOrderNo || ''),
  supplierId: String(route.query.supplierId || ''),
  supplierName: String(route.query.supplierName || ''),
  sourceStatus: String(route.query.sourceStatus || ''),
}))
const settlementRows = ref([])
const payableCheckRows = ref([])
onMounted(async () => {
  const response = await formalExecutionApi.payableCheckFacts()
  if (!response?.success) {
    settlementRows.value = []
    payableCheckRows.value = []
    ElMessage.error(response?.error?.message || '正式供应商结算事实读取失败')
    return
  }
  settlementRows.value = (response.data?.supplierSettlements || []).map((row) => ({
    ...row,
    formalAuthority: true,
    authoritySource: 'reconciliation.SupplierSettlementAuthorityRecord',
  }))
  payableCheckRows.value = (response.data?.payableChecks || []).map((row) => ({
    ...row,
    formalAuthority: true,
    authoritySource: 'reconciliation.PayableCheckAuthorityRecord',
  }))
})
const contextResolution = computed(() => resolveSupplierSettlementContext({
  query: sourceContext.value,
  payableChecks: payableCheckRows.value,
  supplierSettlements: settlementRows.value,
}))
const resolvedSourceContext = computed(() => {
  const source = contextResolution.value.sourceRecord || {}
  return {
    sourcePayableCheckNo: source.payableCheckNo || sourceContext.value.sourcePayableCheckNo,
    sourcePayablePrepareNo: source.sourcePayablePrepareNo || sourceContext.value.sourcePayablePrepareNo,
    purchaseOrderNo: source.sourcePurchaseOrderNo || source.purchaseOrderNo || sourceContext.value.purchaseOrderNo,
    supplierId: source.supplierId || sourceContext.value.supplierId,
    supplierName: source.supplierName || sourceContext.value.supplierName,
    sourceStatus: source.checkStatus || source.status || sourceContext.value.sourceStatus,
    payableAmount: Number(source.totalPayableAmount || 0),
    checkedAmount: Number(source.totalCheckedAmount || 0),
    differenceAmount: Number(source.amountDifference || 0),
  }
})
const createBlockedReason = computed(() => {
  if (contextResolution.value.status !== 'pending_source') return ''
  return '正式供应商结算仅允许通过服务端受控业务动作创建。'
})
const detailRecord = computed(() => settlementRows.value.find((row) => row.settlementNo === String(route.query.settlementNo || '')) || null)
const navigationSettlement = computed(() => selectedRows.value.length === 1 ? selectedRows.value[0] : contextResolution.value.settlementRecords[0] || detailRecord.value)
const targetSettlement = computed(() => contextResolution.value.settlementRecords[0] || detailRecord.value || null)
const supplierSettlementBusinessStatus = computed(() => (
  navigationSettlement.value?.settlementStatus
    || resolvedSourceContext.value.sourceStatus
    || (contextResolution.value.status === 'pending_source' ? 'source_ready' : '')
))

const downstreamCounts = computed(() => ({
  purchaseReconciliationObjectCount: 0,
  paymentObjectCount: 0,
}))
const preReconciliationEligible = computed(() => contextResolution.value.status === 'existing_settlement'
  && targetSettlement.value?.settlementStatus === 'reconciling'
  && downstreamCounts.value.purchaseReconciliationObjectCount === 0
  && downstreamCounts.value.paymentObjectCount === 0)
const rows = computed(() => {
  const list = contextResolution.value.displayRows.filter(matchRow)
  const { prop, order } = sortState.value
  if (!prop || !order) return list
  const factor = order === 'descending' ? -1 : 1
  return [...list].sort((a, b) => compareValue(a[prop], b[prop]) * factor)
})
const activeFilterCount = computed(() => Object.values(filters).filter((item) => String(item || '').trim()).length + (quickSearch.value.trim() ? 1 : 0))
const sortStateLabel = computed(() => {
  if (!sortState.value.prop || !sortState.value.order) return '默认业务顺序'
  return `${sortState.value.prop} ${sortState.value.order === 'ascending' ? '升序' : '降序'}`
})

const readinessTextMap = {
  ready_for_invoice_prepare: '可进入采购发票准备',
  ready: '可进入下一步',
  not_ready: '未准备好',
  blocked: '已阻断',
  closed: '已关闭',
}

const contextFieldTextMap = {
  sourcePayableCheckNo: '来源采购应付核对编号',
  sourcePayablePrepareNo: '来源采购应付预备编号',
  purchaseOrderNo: '采购订单号',
  supplierId: '供应商编号',
  supplierName: '供应商',
  sourceStatus: '来源状态',
  'settlement.purchaseOrderNo': '结算记录采购订单号',
  'settlement.supplierId': '结算记录供应商编号',
  'settlement.supplierName': '结算记录供应商',
  supplierSettlement: '供应商结算来源关系',
}

function displayNo(value) {
  return formatBusinessNo(value)
}

function displayStatus(value, fallback) {
  return formatBusinessStatus(value, fallback)
}

function displayReadiness(value) {
  return readinessTextMap[value] || formatBusinessStatus(value, '未准备好')
}

function mismatchFieldLabel(field) {
  return contextFieldTextMap[field] || field || '未知字段'
}

function isSelectableSettlementRow(row) {
  return !row?.isPendingSource && !row?.formalAuthority
}

function formatAmount(value) {
  const amount = Number(value)
  return Number.isFinite(amount) ? amount.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '0.00'
}

function handleSelectionChange(selection) {
  selectedRows.value = selection
}

function handleSortChange({ prop, order }) {
  sortState.value = { prop: prop || '', order: order || '' }
  clearSelection()
}

function clearSelection() {
  supplierSettlementTableRef.value?.clearSelection?.()
  selectedRows.value = []
}

function clearSort() {
  sortState.value = { prop: '', order: '' }
  supplierSettlementTableRef.value?.clearSort?.()
}

function clearFilters() {
  quickSearch.value = ''
  Object.keys(filters).forEach((key) => {
    filters[key] = ''
  })
  clearSelection()
}

function matchText(row, values) {
  const keyword = String(values || '').trim().toLowerCase()
  if (!keyword) return true
  return [
    row.settlementNo,
    row.sourcePayableCheckNo,
    row.sourceObjectNo,
    row.supplierName,
    row.purchaseOrderNo,
    displayStatus(row.reconciliationStatus, '待对账'),
    displayStatus(row.settlementStatus, '草稿'),
    displayReadiness(row.nextStepReadiness),
  ].some((item) => String(item || '').toLowerCase().includes(keyword))
}

function includeField(value, keyword) {
  const text = String(keyword || '').trim().toLowerCase()
  if (!text) return true
  return String(value || '').toLowerCase().includes(text)
}

function matchRow(row) {
  if (!matchText(row, quickSearch.value)) return false
  if (!includeField(row.settlementNo, filters.settlementNo)) return false
  if (!includeField(row.sourcePayableCheckNo || row.sourceObjectNo, filters.sourcePayableCheckNo)) return false
  if (!includeField(row.supplierName, filters.supplierName)) return false
  if (!includeField(row.purchaseOrderNo, filters.purchaseOrderNo)) return false
  if (filters.reconciliationStatus && row.reconciliationStatus !== filters.reconciliationStatus) return false
  if (filters.settlementStatus && row.settlementStatus !== filters.settlementStatus) return false
  if (!includeField(row.nextStepReadiness, filters.nextStepReadiness)) return false
  return true
}

function compareValue(a, b) {
  const leftNumber = Number(a)
  const rightNumber = Number(b)
  if (Number.isFinite(leftNumber) && Number.isFinite(rightNumber)) return leftNumber - rightNumber
  return String(a || '').localeCompare(String(b || ''), 'zh-CN')
}

function goPayableCheck(row) {
  router.push({ path: '/finance/payable-checks', query: { sourcePayableCheckNo: row.sourcePayableCheckNo || row.sourceObjectNo || '' } })
}

function goInvoicePrepare(row) {
  router.push({ path: '/finance/purchase-invoice-prepares', query: { sourceSettlementNo: row.settlementNo || '' } })
}

function generateSupplierSettlement() {
  latestActionResult.value = { ok: false, code: 'FORMAL_SERVER_ACTION_REQUIRED' }
  ElMessage.warning('正式供应商结算仅允许通过服务端受控业务动作创建。')
}

function executeRegistryAction(action) {
  if (action.actionId === 'generate-supplier-settlement') {
    generateSupplierSettlement()
  }
}

function viewSupplierSettlement(row) {
  router.push(buildSupplierSettlementDetailRoute(row, sourceContext.value))
}

function goPurchaseReconciliation(row) {
  if (!row?.id || !row?.settlementNo) return
  router.push(buildPurchaseReconciliationRoute(row))
}

function csvEscape(value) {
  return `"${String(value ?? '').replaceAll('"', '""')}"`
}

function exportCurrentRows() {
  const headers = ['供应商结算单号', '来源采购应付核对单号', '供应商', '采购订单号', '结算金额', '差异金额', '对账状态', '结算状态', '下一步准备状态']
  const csv = [headers.join(',')]
    .concat(rows.value.map((row) => [
      row.settlementNo,
      row.sourcePayableCheckNo || row.sourceObjectNo,
      row.supplierName,
      row.purchaseOrderNo,
      row.settlementAmount,
      row.differenceAmount,
      displayStatus(row.reconciliationStatus, '待对账'),
      displayStatus(row.settlementStatus, '草稿'),
      displayReadiness(row.nextStepReadiness),
    ].map(csvEscape).join(',')))
    .join('\n')
  const blob = new Blob([`\ufeff${csv}`], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = 'supplier-settlements.csv'
  link.click()
  URL.revokeObjectURL(link.href)
}

async function copyDiagnostics() {
  const diagnostics = {
    page: 'SupplierSettlementPage',
    version: VERSION,
    resultCount: rows.value.length,
    selectedCount: selectedRows.value.length,
    filterState: { quickSearch: quickSearch.value, ...filters },
    sortState: { ...sortState.value },
    exportEnabled: true,
    sortableColumns: ['settlementNo', 'sourcePayableCheckNo', 'supplierName', 'purchaseOrderNo', 'settlementAmount', 'differenceAmount', 'reconciliationStatus', 'settlementStatus'],
    sortArrowStyle: 'no-tail-bold-arrow',
    sortArrowShape: 'upright-triangle',
    readyForInvoicePrepareCount: rows.value.filter((row) => row.nextStepReadiness === 'ready_for_invoice_prepare').length,
    closedCount: rows.value.filter((row) => row.settlementStatus === 'closed').length,
    tableBaseline: {
      selectionColumn: true,
      indexColumn: true,
      primaryBusinessNoFixedLeft: true,
      operationColumnFixedRight: true,
      scrollOwner: 'ElementPlusTableInnerScrollbar',
    },
    navigationReachability: {
      sourcePayableCheckRoute: '/finance/payable-checks',
      purchaseReconciliationRoute: '/scm/purchase-reconciliations',
      invoicePrepareRoute: '/finance/purchase-invoice-prepares',
      pageRoute: '/scm/supplier-settlements',
    },
    sourceContext: { ...sourceContext.value },
    supplierSettlementContext: {
      status: contextResolution.value.status,
      contextualMode: contextResolution.value.contextualMode,
      mismatchFields: contextResolution.value.mismatchFields,
      sourcePayableCheckNo: resolvedSourceContext.value.sourcePayableCheckNo,
      displayedSettlementNos: contextResolution.value.settlementRecords.map((row) => row.settlementNo).filter(Boolean),
      pendingSourceDisplayed: contextResolution.value.status === 'pending_source',
      latestActionResult: latestActionResult.value,
    },
    protectionFlags: {
      writeBusinessDataScope: 'read_only_supplier_settlement_page_display',
      modifyPurchaseOrder: false,
      modifyReceipt: false,
      modifyInspection: false,
      modifyInventory: false,
      modifyPayablePrepareAmount: false,
      modifyPayment: false,
      writeLedger: false,
      writeOffPayment: false,
      generateBankFlow: false,
    },
    timestamp: new Date().toISOString(),
  }
  await navigator.clipboard.writeText(JSON.stringify(diagnostics, null, 2))
  ElMessage.success('诊断数据已复制')
}
</script>

<style scoped>
.supplier-settlement-page {
  display: grid;
  gap: 16px;
  max-width: 100%;
  overflow-x: hidden;
}

.source-context-panel {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 18px;
  align-items: center;
  padding: 10px 12px;
  border-left: 3px solid #2563eb;
  background: #eff6ff;
  color: #1e3a8a;
}

.semantic-compatibility-alias {
  display: none;
}

.context-mismatch-list {
  display: grid;
  gap: 4px;
  margin: 8px 0 0;
  padding-left: 20px;
}

.table-card {
  display: grid;
  gap: 14px;
}

.toolbar-title {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.toolbar-title h2,
.toolbar-title p {
  margin: 0;
}

.page-note {
  margin-top: 6px;
  color: #475569;
  font-size: 13px;
  line-height: 1.6;
}

.eyebrow {
  color: #2563eb;
  font-size: 13px;
  font-weight: 800;
}

.toolbar-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  justify-content: flex-end;
}

.row-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
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
</style>
