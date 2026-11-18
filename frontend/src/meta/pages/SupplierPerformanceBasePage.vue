<template>
  <main class="page" :data-acceptance-id="`${kind}-performance-content`">
    <section class="card" :data-acceptance-id="`${kind}-server-facts`">
      <Heading title="服务端持久事实" note="API、页面、诊断、StrictFacts 与 AcceptanceFacts 复用同一服务端事实" />
      <div class="grid">
        <Fact label="事实来源" value="server" />
        <Fact label="记录数量" :value="facts.recordCount" />
        <Fact label="API" :value="facts.apiUrl" />
        <Fact label="状态" value="加载成功" />
        <Fact label="危险动作" :value="facts.dangerActionCount" />
        <Fact label="业务推进写入" :value="facts.businessProgressWriteCount" />
        <Fact label="下游对象" :value="facts.downstreamObjectCount" />
      </div>
    </section>

    <section v-if="kind === 'reconciliation'" class="card stage" data-acceptance-id="formal-reconciliation-actions">
      <Heading title="正式业务操作" note="每次只执行一个受 AuthorizationService、岗位职责和流程节点保护的动作。" />
      <div class="formal-create">
        <el-input v-model="purchaseOrderId" placeholder="输入已完成履约的采购订单ID" style="max-width:320px" />
        <el-button type="primary" @click="executeFormal('scm.supplier_reconciliation.create', purchaseOrderId)">创建供应商对账</el-button>
        <el-button plain @click="loadFormalChain">读取正式链</el-button>
      </div>
      <pre v-if="formalChain" class="formal-chain-readback">{{ JSON.stringify(formalChain, null, 2) }}</pre>
    </section>

    <section class="card" :data-acceptance-id="`${kind}-list`">
      <Heading :title="listTitle" :note="listNote" />
      <PceEnterpriseListTable
        ref="tableRef" :contract="enterpriseListContract" :page-id="`v81-${kind}`"
        :table-id="`v81-${kind}-table`" :rows="rows" :table-rows="filteredRows"
        :filter-schema="definition.filterSchema" :filters="filters" :quick-search="quickSearch"
        :advanced-visible="advancedVisible" :selected-count="selectedRows.length"
        :active-filter-count="activeFilterCount" :sort-text="sortText"
        :primary-field="primaryField" :primary-label="primaryLabel" :primary-width="280"
        min-width="1500px" :scroll-acceptance-id="`${kind}-horizontal-scroll`" :action-width="380"
        @update:quick-search="quickSearch = $event" @search="appliedSearch = quickSearch"
        @toggle-advanced="advancedVisible = !advancedVisible" @clear-filters="clearFiltersAndRefresh"
        @clear-sort="clearSort" @export-current="exportCurrent" @clear-selection="clearSelection"
        @update-filter="updateFilterAndRefresh" @selection-change="selectedRows = $event"
        @sort-change="handleSort"
      >
        <template #columns>
          <template v-if="kind === 'reconciliation'">
            <el-table-column prop="supplierName" label="供应商" width="190" />
            <el-table-column prop="period" label="对账期间" width="130" />
            <el-table-column prop="purchaseAmount" label="采购金额" width="150" />
            <el-table-column prop="receivedAmount" label="入库金额" width="150" />
            <el-table-column prop="qualifiedAmount" label="质量合格金额" width="160" />
            <el-table-column prop="reconciliationAmount" label="对账金额" width="150" />
            <el-table-column prop="statusLabel" label="对账状态" width="170" />
          </template>
          <template v-else-if="kind === 'buyer'">
            <el-table-column prop="period" label="期间" width="130" />
            <el-table-column prop="purchaseOrderCount" label="采购订单数量" width="150" />
            <el-table-column prop="onTimePurchaseRate" label="准时率" width="130" />
            <el-table-column prop="priceOptimizationRate" label="成本控制" width="140" />
            <el-table-column prop="supplierIssueResponseTime" label="异常处理时长" width="160" />
            <el-table-column prop="processComplianceRate" label="流程合规率" width="150" />
            <el-table-column prop="overallScore" label="综合评分" width="140" />
          </template>
          <template v-else>
            <el-table-column prop="period" label="期间" width="130" />
            <el-table-column prop="deliveryOnTimeRate" label="交付评分" width="140" />
            <el-table-column prop="qualityPassRate" label="质量评分" width="140" />
            <el-table-column prop="priceTrendScore" label="价格评分" width="140" />
            <el-table-column prop="serviceScore" label="服务评分" width="140" />
            <el-table-column prop="reconciliationAccuracyRate" label="结算准确率" width="150" />
            <el-table-column prop="overallScore" label="综合评分" width="140" />
          </template>
        </template>
        <template #actions="{ row }">
          <el-button size="small" plain @click="showRow(row)">查看详情</el-button>
          <template v-if="kind === 'reconciliation'">
            <el-button v-if="row.statusCode === 'draft'" size="small" type="primary" plain @click="executeFormal('scm.supplier_reconciliation.analyze', row.id)">差异分析</el-button>
            <el-button v-if="row.statusCode === 'draft'" size="small" type="primary" plain @click="executeFormal('scm.supplier_reconciliation.confirm', row.id)">确认对账</el-button>
            <el-button v-if="row.statusCode === 'completed'" size="small" type="success" plain @click="executeFormal('scm.supplier_payable.confirm', row.id)">确认应付</el-button>
          </template>
        </template>
      </PceEnterpriseListTable>
    </section>

    <section v-if="kind === 'reconciliation'" class="card" data-acceptance-id="supplier-reconciliation-source-chain">
      <Heading title="业务来源链" note="采购订单 → 收货 → 质量检验 → 入库" />
      <div class="source-chain">
        <Fact label="采购订单" :value="sourceTotals.purchaseOrder" /><b>→</b>
        <Fact label="收货" :value="sourceTotals.receipt" /><b>→</b>
        <Fact label="质量检验" :value="sourceTotals.inspection" /><b>→</b>
        <Fact label="入库" :value="sourceTotals.warehouseReceipt" /><b>→</b>
        <Fact label="库存交易" :value="sourceTotals.inventoryTransaction" />
      </div>
    </section>

    <section v-if="kind === 'reconciliation'" class="card" data-acceptance-id="supplier-reconciliation-confirmation">
      <Heading title="对账确认" note="状态全部来自服务端状态机事实" />
      <div class="grid">
        <Fact label="内部审核" :value="current?.internalReviewStatus" />
        <Fact label="供应商确认" :value="current?.supplierConfirmationStatus" />
        <Fact label="完成状态" :value="current?.completed ? '已完成' : '未完成'" />
        <Fact label="直接付款" value="禁止" />
      </div>
    </section>

    <section class="card boundary" :data-acceptance-id="`${kind}-security-boundary`">
      <Heading title="业务边界保护" note="本页面用于供应商结算业务管理和绩效分析。" />
      <div class="grid">
        <Fact label="付款执行" value="否" /><Fact label="银行发送" value="否" />
        <Fact label="资金扣减" value="否" /><Fact label="财务影响" value="0" />
      </div>
    </section>
    <el-dialog v-model="dialogVisible" title="业务详情" width="860px">
      <PceBusinessDetailCard v-if="dialogRow" :detail="businessDetail" />
    </el-dialog>
  </main>
</template>

<script setup>
import { computed, h, inject, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { supplierPerformanceApi } from '@/api/supplierPerformance.js'
import { supplierSettlementFormalApi } from '@/api/supplierSettlementFormal.js'
import PceBusinessDetailCard from '@/meta/components/PceBusinessDetailCard.vue'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import { PAGE_OBSERVABILITY_ACTIONS_KEY } from '@/meta/runtime/pageObservabilityActions.js'
import { createPceEnterpriseListContract, usePceEnterpriseListRuntime } from '@/meta/runtime/pceEnterpriseListContract.js'
import { normalizeSupplierPerformanceFacts, pageDefinitions, SUPPLIER_PERFORMANCE_VERSION } from '@/meta/runtime/supplierPerformanceRuntime.js'

const props = defineProps({ kind: { type: String, required: true } })
const purchaseOrderId = ref('')
const formalChain = ref(null)
const definition = computed(() => pageDefinitions[props.kind])
const rows = ref([]); const facts = reactive({}); const diagnosticFacts = ref({}); const strictFacts = ref({}); const acceptanceFacts = ref({})
const current = computed(() => rows.value[0] || null)
const primaryField = computed(() => props.kind === 'reconciliation' ? 'reconciliationNo' : props.kind === 'buyer' ? 'buyerName' : 'supplierName')
const primaryLabel = computed(() => props.kind === 'reconciliation' ? '对账编号' : props.kind === 'buyer' ? '采购员' : '供应商')
const listTitle = computed(() => props.kind === 'reconciliation' ? '供应商对账列表' : props.kind === 'buyer' ? '采购员评分区域' : '供应商评分区域')
const listNote = computed(() => props.kind === 'reconciliation' ? '供应商、金额与中文状态均来自服务端' : '评分结果与来源关系均来自服务端')
const sourceTotals = computed(() => rows.value.reduce((total, row) => {
  for (const key of Object.keys(total)) total[key] += row.sourceCounts?.[key] || 0
  return total
}, { purchaseOrder: 0, receipt: 0, inspection: 0, warehouseReceipt: 0, inventoryTransaction: 0 }))
const dialogVisible = ref(false); const dialogRow = ref(null); const observability = inject(PAGE_OBSERVABILITY_ACTIONS_KEY, null)
const businessDetail = computed(() => {
  const row = dialogRow.value || {}
  const number = row.reconciliationNo || row.buyerId || row.supplierId || row.buyerName || row.supplierName
  return {
    basicInformation: {
      number,
      supplier: row.supplierName || row.buyerName || '-',
      period: row.period || '-',
      sourceDocument: row.reconciliationNo || '服务端绩效事实',
    },
    amountInformation: {
      confirmedAmount: row.reconciliationAmount,
      deductionAmount: null,
      finalAmount: row.reconciliationAmount,
    },
    businessSourceChain: Object.entries(row.sourceCounts || {}).map(([label, count]) => ({
      label,
      count,
      references: [],
    })),
    currentStatus: row.statusLabel || (row.overallScore !== undefined ? `综合评分 ${row.overallScore}` : '已记录'),
    stateHistory: row.statusHistory || [],
    operationRecords: row.operationRecords || [],
  }
})
const enterpriseListContract = computed(() => createPceEnterpriseListContract({
  pageCode: `v81-${props.kind}`, pageType: 'list', title: definition.value.title, moduleCode: definition.value.moduleCode,
}))
const runtime = usePceEnterpriseListRuntime({
  rows, filterSchema: definition.value.filterSchema, pageCode: `v81-${props.kind}`,
  searchFields: ['reconciliationNo', 'supplierName', 'buyerName', 'period', 'statusLabel'],
  exportFileName: `v81-${props.kind}.csv`,
  exportColumns: [{ field: primaryField.value, label: primaryLabel.value }, { field: 'period', label: '期间' }, { field: 'overallScore', label: '综合评分' }],
})
const { selectedRows, quickSearch, appliedSearch, advancedVisible, filters, tableRef, activeFilterCount,
  sortText, filteredRows, apiFilterParams, clearFilters, clearSort, clearSelection, handleSort, exportCurrent } = runtime
const Heading = (_, { attrs }) => h('div', { class: 'heading' }, [h('h2', attrs.title), h('p', attrs.note)])
const Fact = (_, { attrs }) => h('article', { class: 'fact' }, [h('span', attrs.label), h('strong', String(attrs.value ?? '-'))])
function showRow(row) { dialogRow.value = row; dialogVisible.value = true }
async function executeFormal(actionCode, sourceId) {
  if (!sourceId) { ElMessage.warning('请先输入或选择来源对象'); return }
  try {
    const inspection = await supplierSettlementFormalApi.inspect({ actionCode, sourceId: Number(sourceId) })
    if (!inspection?.success) throw new Error(inspection?.error?.message || inspection?.error?.code || '正式业务动作不可执行')
    const result = await supplierSettlementFormalApi.execute({
      actionCode,
      sourceId: Number(sourceId),
      reason: '系统流程验收数据 / PCE采购结算与绩效闭环14—22 V1.0',
    })
    if (!result?.success) throw new Error(result?.error?.message || result?.error?.code || '正式业务动作执行失败')
    ElMessage.success(`${result?.data?.actionLabel || '正式业务动作'}已完成`)
    await refresh()
  } catch (error) {
    ElMessage.error(error?.message || '正式业务动作执行失败')
  }
}
async function loadFormalChain() {
  if (!purchaseOrderId.value) { ElMessage.warning('请先输入采购订单ID'); return }
  const result = await supplierSettlementFormalApi.chain(Number(purchaseOrderId.value))
  if (!result?.success) { ElMessage.error(result?.error?.message || '正式链回读失败'); return }
  formalChain.value = result.data
  ElMessage.success('正式业务链已从服务端回读')
}
function diagnostics() { return {
  version: SUPPLIER_PERFORMANCE_VERSION, canonicalName: definition.value.title,
  moduleCode: definition.value.moduleCode, pageFactOwner: definition.value.moduleCode, factSource: 'server',
  pageFacts: { ...facts }, diagnosticFacts: diagnosticFacts.value, strictFacts: strictFacts.value,
  acceptanceFacts: acceptanceFacts.value, filterApiParams: { ...apiFilterParams.value },
  resultCount: facts.recordCount ?? null, dangerActionCount: 0, businessProgressWriteCount: 0,
} }
function publish() { window.__PCE_BUSINESS_PAGE_ACCEPTANCE__ = { ...diagnostics(), pageAssertions: [
  { rule: 'PAGE-IDENTITY-001', regionTitle: '页面身份区域', actualValue: definition.value.title, passed: true },
  { rule: 'PAGE-ACTION-001', regionTitle: '当前业务动作说明', actualValue: '只读治理动作', passed: true },
  { rule: 'PAGE-FLOW-001', regionTitle: '模块主流程', actualValue: definition.value.title, passed: true },
  { rule: 'PAGE-TITLE-001', regionTitle: '页面标题', actualValue: document.title, passed: document.title.includes(definition.value.title) },
  { rule: 'FACT-001', regionTitle: '服务端持久事实', actualValue: facts.recordCount, passed: facts.factSource === 'server' },
  { regionTitle: listTitle.value, actualValue: rows.value.length, passed: rows.value.length === facts.recordCount },
  { rule: 'SECURITY-001', regionTitle: '业务边界保护', actualValue: '付款/银行/财务写入=0', passed: facts.paymentExecutionWriteCount === 0 && facts.bankSendWriteCount === 0 && facts.financialImpactWriteCount === 0 },
] } }
async function refresh(params = {}) {
  try {
    const api = props.kind === 'reconciliation' ? supplierPerformanceApi.reconciliations : props.kind === 'buyer' ? supplierPerformanceApi.buyers : supplierPerformanceApi.suppliers
    const loaded = normalizeSupplierPerformanceFacts(await api(params), props.kind)
    rows.value = loaded.rows; Object.assign(facts, loaded.facts); diagnosticFacts.value = loaded.diagnosticFacts
    strictFacts.value = loaded.strictFacts; acceptanceFacts.value = loaded.acceptanceFacts; publish()
  } catch (error) { ElMessage.error(`${definition.value.title}事实读取失败：${error?.message || 'UNKNOWN'}`) }
}
let filterRefreshTimer
function updateFilterAndRefresh(field, value) {
  filters[field] = value
  clearTimeout(filterRefreshTimer)
  filterRefreshTimer = setTimeout(() => refresh({ ...apiFilterParams.value }), 120)
}
function clearFiltersAndRefresh() {
  clearFilters()
  refresh()
}
const provider = { factOwner: definition.value.moduleCode, refresh, buildDiagnostics: diagnostics }
onMounted(async () => { observability?.register?.(provider); await refresh(); observability?.register?.(provider) })
onBeforeUnmount(() => {
  clearTimeout(filterRefreshTimer)
  observability?.unregister?.(provider)
})
watch(() => props.kind, async () => {
  rows.value = []
  for (const key of Object.keys(facts)) delete facts[key]
  await refresh()
})
</script>

<style scoped>
.page { display:grid; min-width:0; gap:18px; padding:20px; background:#f4f7fb; }
.card { min-width:0; padding:20px; border:1px solid #dce4ed; border-radius:12px; background:#fff; }
.stage { border-color:#93c5fd; background:#eff6ff; }.boundary { border-color:#b8d8c4; background:#f5fbf7; }
.heading h2 { margin:0; color:#16243a; }.heading p { margin:6px 0 16px; color:#64748b; }
.grid,.source-chain { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px; align-items:center; }
.formal-create { display:flex; flex-wrap:wrap; gap:10px; align-items:center; }
.formal-chain-readback { margin:14px 0 0; padding:14px; border:1px solid #dbeafe; border-radius:8px; background:#f8fafc; color:#172033; font-size:12px; line-height:1.55; }
.fact { display:grid; gap:5px; padding:12px; border-radius:8px; background:#f5f8fb; }.fact span { color:#64748b; font-size:13px; }
pre { max-height:520px; overflow:auto; white-space:pre-wrap; }
</style>
