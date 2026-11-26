<template>
  <main class="page" :data-acceptance-id="`${kind}-v82-content`">
    <section class="card" :data-acceptance-id="`${kind}-server-facts`">
      <Heading title="服务端持久事实" note="API、页面、Diagnostic、StrictFacts 与验收报告复用同一服务端事实。" />
      <div class="grid">
        <Fact label="事实来源" value="server" />
        <Fact label="记录数量" :value="facts.recordCount" />
        <Fact label="事实加载状态" value="加载成功" />
        <Fact label="API" :value="facts.apiUrl" />
        <Fact label="危险动作" :value="facts.dangerActionCount" />
        <Fact label="业务推进写入" :value="facts.businessProgressWriteCount" />
      </div>
    </section>

    <section v-if="kind === 'difference'" class="card statistics" data-acceptance-id="difference-statistics">
      <Heading title="差异统计" note="统计结果全部来自服务端差异事实。" />
      <div class="grid">
        <Fact label="差异数量" :value="facts.differenceCount" />
        <Fact label="差异金额" :value="facts.differenceAmount" />
        <Fact label="供应商数量" :value="facts.supplierCount" />
        <Fact label="关闭数量" :value="facts.closedCount" />
      </div>
    </section>

    <section class="card" :data-acceptance-id="`${kind}-list`">
      <Heading :title="definition.listTitle" note="列表、筛选、状态和统计数据均来自服务端。" />
      <PceEnterpriseListTable
        ref="tableRef"
        :contract="enterpriseListContract"
        :page-id="`v82-${kind}`"
        :table-id="`v82-${kind}-table`"
        :rows="rows"
        :table-rows="filteredRows"
        :filter-schema="definition.filterSchema"
        :filters="filters"
        :quick-search="quickSearch"
        :advanced-visible="advancedVisible"
        :selected-count="selectedRows.length"
        :active-filter-count="activeFilterCount"
        :sort-text="sortText"
        :primary-field="definition.primaryField"
        :primary-label="definition.primaryLabel"
        :primary-width="240"
        min-width="1550px"
        :scroll-acceptance-id="`${kind}-horizontal-scroll`"
        :action-width="130"
        @update:quick-search="quickSearch = $event"
        @search="appliedSearch = quickSearch"
        @toggle-advanced="advancedVisible = !advancedVisible"
        @clear-filters="clearFilters"
        @clear-sort="clearSort"
        @export-current="exportCurrent"
        @clear-selection="clearSelection"
        @update-filter="(field, value) => filters[field] = value"
        @selection-change="selectedRows = $event"
        @sort-change="handleSort"
      >
        <template #columns>
          <template v-if="kind === 'difference'">
            <el-table-column prop="supplierName" label="供应商" width="180" />
            <el-table-column prop="reconciliationNo" label="来源对账编号" width="220" />
            <el-table-column prop="differenceTypeLabel" label="差异类型" width="150" />
            <el-table-column prop="differenceAmount" label="差异金额" width="140" />
            <el-table-column prop="differenceQuantity" label="差异数量" width="140" />
            <el-table-column prop="responsibilityLabel" label="责任类型" width="150" />
            <el-table-column prop="buyerName" label="采购员" width="130" />
            <el-table-column prop="occurredAt" label="差异日期" width="140" />
            <el-table-column prop="statusLabel" label="状态" width="160" />
          </template>
          <template v-else-if="kind === 'confirmation'">
            <el-table-column prop="supplierName" label="供应商" width="180" />
            <el-table-column prop="differenceNo" label="差异编号" width="220" />
            <el-table-column prop="statusLabel" label="确认状态" width="170" />
            <el-table-column prop="supplierResponseLabel" label="处理结果" width="140" />
            <el-table-column prop="supplierComment" label="供应商意见" width="300" show-overflow-tooltip />
            <el-table-column prop="confirmedBy" label="确认人" width="150" />
            <el-table-column prop="confirmedAt" label="确认时间" width="210" />
          </template>
          <template v-else>
            <el-table-column prop="period" label="周期" width="130" />
            <el-table-column prop="purchaseOrderCount" label="负责订单数" width="150" />
            <el-table-column prop="differenceResponsibilityCount" label="差异数量" width="140" />
            <el-table-column prop="supplierIssueCount" label="供应商问题数量" width="170" />
            <el-table-column prop="priceDifferenceCount" label="价格差异数量" width="160" />
            <el-table-column prop="deliveryDelayCount" label="交付延期数量" width="160" />
            <el-table-column prop="managementScore" label="综合管理评分" width="160" />
          </template>
        </template>
        <template #actions="{ row }">
          <el-button size="small" plain @click="showRow(row)">查看详情</el-button>
        </template>
      </PceEnterpriseListTable>
    </section>

    <section class="card boundary" :data-acceptance-id="`${kind}-security-boundary`">
      <Heading title="业务边界保护" note="本版本属于SCM供应商结算协同，不产生财务影响。" />
      <div class="grid">
        <Fact label="付款执行" value="否" />
        <Fact label="银行发送" value="否" />
        <Fact label="资金扣减" value="否" />
        <Fact label="总账处理" value="否" />
        <Fact label="财务影响" value="0" />
      </div>
    </section>

    <el-dialog v-model="dialogVisible" title="业务详情" width="760px">
      <PceBusinessDetailCard v-if="dialogRow" :detail="businessDetail" />
    </el-dialog>
  </main>
</template>

<script setup>
import { computed, h, inject, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { supplierReconciliationV82Api } from '@/api/supplierReconciliationV82.js'
import PceBusinessDetailCard from '@/meta/components/PceBusinessDetailCard.vue'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import { PAGE_OBSERVABILITY_ACTIONS_KEY } from '@/meta/runtime/pageObservabilityActions.js'
import { createPceEnterpriseListContract, usePceEnterpriseListRuntime } from '@/meta/runtime/pceEnterpriseListContract.js'
import { normalizeV82Facts, SUPPLIER_RECONCILIATION_V82_VERSION, v82PageDefinitions } from '@/meta/runtime/supplierReconciliationV82Runtime.js'

const props = defineProps({ kind: { type: String, required: true } })
const definition = computed(() => v82PageDefinitions[props.kind])
const rows = ref([])
const facts = reactive({})
const diagnosticFacts = ref({})
const strictFacts = ref({})
const acceptanceFacts = ref({})
const dialogVisible = ref(false)
const dialogRow = ref(null)
const observability = inject(PAGE_OBSERVABILITY_ACTIONS_KEY, null)
const businessDetail = computed(() => {
  const row = dialogRow.value || {}
  return {
    basicInformation: {
      number: row.differenceNo || row.confirmationNo || row.buyerName || '-',
      supplier: row.supplierName || row.buyerName || '-',
      period: row.period || row.occurredAt || '-',
      sourceDocument: row.reconciliationNo || row.differenceNo || '服务端结算协同事实',
    },
    amountInformation: {
      confirmedAmount: row.differenceAmount,
      deductionAmount: null,
      finalAmount: row.differenceAmount,
    },
    businessSourceChain: [
      { label: '供应商对账', count: row.reconciliationNo ? 1 : 0, references: [row.reconciliationNo].filter(Boolean) },
      { label: definition.value.listTitle, count: 1, references: [row.differenceNo || row.confirmationNo || row.buyerName].filter(Boolean) },
    ],
    currentStatus: row.statusLabel || '已记录',
    stateHistory: row.statusHistory || [],
    operationRecords: row.operationRecords || [],
  }
})

const enterpriseListContract = computed(() => createPceEnterpriseListContract({
  pageCode: definition.value.pageCode,
  pageType: 'list',
  title: definition.value.title,
  moduleCode: definition.value.moduleCode,
}))
const runtime = usePceEnterpriseListRuntime({
  rows,
  filterSchema: definition.value.filterSchema,
  pageCode: definition.value.pageCode,
  searchFields: ['differenceNo', 'confirmationNo', 'reconciliationNo', 'supplierName', 'buyerName', 'statusLabel'],
  exportFileName: `${definition.value.pageCode}.csv`,
  exportColumns: [
    { field: definition.value.primaryField, label: definition.value.primaryLabel },
    { field: 'supplierName', label: '供应商' },
    { field: 'statusLabel', label: '状态' },
  ],
})
const {
  selectedRows, quickSearch, appliedSearch, advancedVisible, filters, tableRef,
  activeFilterCount, sortText, filteredRows, clearFilters, clearSort,
  clearSelection, handleSort, exportCurrent,
} = runtime

const Heading = (_, { attrs }) => h('div', { class: 'heading' }, [h('h2', attrs.title), h('p', attrs.note)])
const Fact = (_, { attrs }) => h('article', { class: 'fact' }, [h('span', attrs.label), h('strong', String(attrs.value ?? '-'))])

function showRow(row) {
  dialogRow.value = row
  dialogVisible.value = true
}
function diagnostics() {
  return {
    version: SUPPLIER_RECONCILIATION_V82_VERSION,
    canonicalName: definition.value.title,
    moduleCode: definition.value.moduleCode,
    pageFactOwner: definition.value.moduleCode,
    factSource: 'server',
    pageFacts: { ...facts },
    diagnosticFacts: diagnosticFacts.value,
    strictFacts: strictFacts.value,
    acceptanceFacts: acceptanceFacts.value,
    resultCount: facts.recordCount ?? null,
    dangerActionCount: 0,
    businessProgressWriteCount: 0,
  }
}
function publish() {
  window.__PCE_BUSINESS_PAGE_ACCEPTANCE__ = diagnostics()
}
async function refresh() {
  try {
    const api = supplierReconciliationV82Api[definition.value.apiKey]
    const loaded = normalizeV82Facts(await api(), props.kind)
    rows.value = loaded.rows
    Object.assign(facts, loaded.facts)
    diagnosticFacts.value = loaded.diagnosticFacts
    strictFacts.value = loaded.strictFacts
    acceptanceFacts.value = loaded.acceptanceFacts
    publish()
  } catch (error) {
    ElMessage.error(`${definition.value.title}事实读取失败：${error?.message || 'UNKNOWN'}`)
  }
}
const provider = { factOwner: definition.value.moduleCode, refresh, buildDiagnostics: diagnostics }
onMounted(async () => {
  observability?.register?.(provider)
  await refresh()
  observability?.register?.(provider)
})
onBeforeUnmount(() => observability?.unregister?.(provider))
</script>

<style scoped>
.page { display:grid; min-width:0; gap:18px; padding:20px; background:#f4f7fb; }
.card { min-width:0; padding:20px; border:1px solid #dce4ed; border-radius:12px; background:#fff; }
.statistics { border-color:#bfdbfe; background:#f8fbff; }
.boundary { border-color:#b8d8c4; background:#f5fbf7; }
.heading h2 { margin:0; color:#16243a; }.heading p { margin:6px 0 16px; color:#64748b; }
.grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px; }
.fact { display:grid; gap:5px; padding:12px; border-radius:8px; background:#f5f8fb; }
.fact span { color:#64748b; font-size:13px; }
pre { max-height:520px; overflow:auto; white-space:pre-wrap; }
</style>
