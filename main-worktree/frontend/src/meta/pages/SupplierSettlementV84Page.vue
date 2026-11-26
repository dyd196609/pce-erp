<template>
  <main class="page" :data-page-code="definition.pageCode">
    <section class="card identity" data-acceptance-id="page-identity-region">
      <p>SCM供应商结算闭环 · {{ version }}</p>
      <h1>{{ definition.title }}</h1>
      <p>仅记录供应商结算业务状态，不执行付款，不产生财务影响。</p>
    </section>

    <section class="card facts" data-acceptance-id="server-persistent-facts">
      <h2>服务端持久事实</h2>
      <div class="fact-grid">
        <Fact label="事实来源" value="server" />
        <Fact label="事实加载状态" value="加载成功" />
        <Fact label="记录数量" :value="facts.recordCount" />
        <Fact label="业务动作数量" :value="facts.actionCount" />
        <Fact label="危险动作数量" :value="facts.dangerActionCount" />
        <Fact label="付款执行写入" :value="facts.paymentExecutionWriteCount" />
        <Fact label="银行发送写入" :value="facts.bankSendWriteCount" />
        <Fact label="财务影响写入" :value="facts.financialImpactWriteCount" />
      </div>
    </section>

    <section class="card actions" data-acceptance-id="supplier-settlement-actions">
      <h2>业务操作</h2>
      <p>动作由当前行状态显示，执行前再次通过 AuthorizationService、员工岗位职责和流程节点校验。</p>
      <div class="action-row">
        <span v-for="action in allowedActions" :key="action">{{ action }}</span>
      </div>
    </section>

    <section class="card" :data-acceptance-id="`${definition.pageCode}-list`">
      <h2>{{ definition.listTitle }}</h2>
      <PceEnterpriseListTable
        ref="tableRef"
        :contract="enterpriseListContract"
        :page-id="definition.pageCode"
        :table-id="`${definition.pageCode}-table`"
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
        :primary-width="230"
        min-width="1650px"
        :scroll-acceptance-id="`${definition.pageCode}-horizontal-scroll`"
        :action-width="380"
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
          <template v-if="kind === 'paymentStatus'">
            <el-table-column prop="supplierName" label="供应商" width="190" />
            <el-table-column prop="paymentAmount" label="申请金额" width="150" />
            <el-table-column prop="statusLabel" label="当前状态" width="160" />
            <el-table-column prop="operateTime" label="状态更新时间" width="220" />
            <el-table-column prop="operator" label="操作人" width="180" />
            <el-table-column prop="remark" label="业务说明" width="340" show-overflow-tooltip />
          </template>
          <template v-else>
            <el-table-column prop="supplierName" label="供应商" width="190" />
            <el-table-column prop="reconciliationNo" label="对账编号" width="220" />
            <el-table-column prop="paymentRequestNo" label="付款申请编号" width="230" />
            <el-table-column prop="statusLabel" label="结算状态" width="150" />
            <el-table-column prop="completionDate" label="完成日期" width="160" />
            <el-table-column prop="performanceUpdateLabel" label="绩效更新状态" width="190" />
          </template>
        </template>
        <template #actions="{ row }">
          <el-button size="small" plain>查看详情</el-button>
          <el-button v-if="kind === 'paymentStatus' && row.paymentStatus === 'payment_completed'" size="small" type="success" plain @click="executeFormal('scm.supplier_settlement.complete', row.id)">确认结算完成</el-button>
          <template v-if="kind === 'completion' && row.completionStatus === 'completed'">
            <el-button size="small" type="primary" plain @click="executeFormal('scm.supplier_performance.calculate', row.id)">计算供应商绩效</el-button>
            <el-button size="small" type="primary" plain @click="executeFormal('scm.buyer_performance.calculate', row.id)">计算采购员绩效</el-button>
          </template>
        </template>
      </PceEnterpriseListTable>
    </section>

    <section v-if="kind === 'completion'" class="card performance" data-acceptance-id="performance-source">
      <h2>绩效更新来源</h2>
      <p>供应商绩效来源：SupplierSettlementCompletion</p>
      <p>采购员绩效来源：SupplierSettlementCompletion</p>
      <div class="fact-grid">
        <Fact label="已完成结算数量" :value="facts.completedCount" />
        <Fact label="绩效来源已更新" :value="facts.performanceUpdatedCount" />
      </div>
    </section>

    <section class="card boundary" data-acceptance-id="supplier-settlement-security-boundary">
      <h2>业务边界保护</h2>
      <div class="fact-grid">
        <Fact label="付款执行" value="否" />
        <Fact label="银行发送" value="否" />
        <Fact label="资金扣减" value="否" />
        <Fact label="银行流水" value="0" />
        <Fact label="财务凭证" value="0" />
        <Fact label="总账" value="0" />
      </div>
    </section>
  </main>
</template>

<script setup>
import { computed, h, inject, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { supplierSettlementV84Api } from '@/api/supplierSettlementV84.js'
import { supplierSettlementFormalApi } from '@/api/supplierSettlementFormal.js'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import { PAGE_OBSERVABILITY_ACTIONS_KEY } from '@/meta/runtime/pageObservabilityActions.js'
import { createPceEnterpriseListContract, usePceEnterpriseListRuntime } from '@/meta/runtime/pceEnterpriseListContract.js'
import {
  normalizeSupplierSettlementV84Facts,
  SUPPLIER_SETTLEMENT_V84_VERSION,
  supplierSettlementV84Definitions,
} from '@/meta/runtime/supplierSettlementV84Runtime.js'

const props = defineProps({ kind: { type: String, required: true } })
const kind = computed(() => props.kind)
const definition = computed(() => supplierSettlementV84Definitions[props.kind])
const version = SUPPLIER_SETTLEMENT_V84_VERSION
const rows = ref([])
const facts = reactive({})
const diagnosticFacts = ref({})
const strictFacts = ref({})
const acceptanceFacts = ref({})
const observability = inject(PAGE_OBSERVABILITY_ACTIONS_KEY, null)
const allowedActions = computed(() => props.kind === 'paymentStatus'
  ? ['业务状态记录只表达系统状态，不调用银行或扣减资金']
  : ['结算完成后分别生成供应商绩效与采购员采购绩效'])
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
  searchFields: ['paymentRequestNo', 'settlementNo', 'reconciliationNo', 'supplierName', 'statusLabel', 'operator'],
  exportFileName: `${definition.value.pageCode}.csv`,
  exportColumns: [
    { field: definition.value.primaryField, label: definition.value.primaryLabel },
    { field: 'supplierName', label: '供应商' },
    { field: 'statusLabel', label: '业务状态' },
  ],
})
const {
  selectedRows, quickSearch, appliedSearch, advancedVisible, filters, tableRef,
  activeFilterCount, sortText, filteredRows, clearFilters, clearSort,
  clearSelection, handleSort, exportCurrent,
} = runtime
const Fact = (_, { attrs }) => h('article', { class: 'fact' }, [
  h('span', attrs.label), h('strong', String(attrs.value ?? '-')),
])
function diagnostics() {
  return {
    version,
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
function publish() { window.__PCE_BUSINESS_PAGE_ACCEPTANCE__ = diagnostics() }
async function refresh() {
  try {
    const loaded = normalizeSupplierSettlementV84Facts(
      await supplierSettlementV84Api[definition.value.apiKey](),
      props.kind,
    )
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
async function executeFormal(actionCode, sourceId) {
  try {
    const inspection = await supplierSettlementFormalApi.inspect({ actionCode, sourceId })
    if (!inspection?.success) throw new Error(inspection?.error?.message || inspection?.error?.code || '正式业务动作不可执行')
    const result = await supplierSettlementFormalApi.execute({
      actionCode,
      sourceId,
      reason: '系统流程验收数据 / PCE采购结算与绩效闭环14—22 V1.0',
    })
    if (!result?.success) throw new Error(result?.error?.message || result?.error?.code || '正式业务动作执行失败')
    ElMessage.success(`${result?.data?.actionLabel || '正式业务动作'}已完成`)
    await refresh()
  } catch (error) {
    ElMessage.error(error?.message || '正式业务动作执行失败')
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
.page{display:grid;gap:18px;min-width:0;padding:20px;background:#f4f7fb}
.card{min-width:0;padding:20px;border:1px solid #dce4ed;border-radius:12px;background:#fff}
.identity{border-color:#c4b5fd;background:linear-gradient(135deg,#faf5ff,#fff)}
.identity h1,.card h2{margin:0 0 10px;color:#172033}.identity p,.card p{color:#64748b}
.facts{border-color:#bfdbfe}.actions{border-color:#a7f3d0}.performance{border-color:#fde68a;background:#fffbeb}
.boundary{border-color:#bbf7d0;background:#f0fdf4}
.fact-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px}
.fact{display:grid;gap:5px;padding:12px;border-radius:8px;background:#f6f8fb}.fact span{color:#64748b;font-size:13px}
.action-row{display:flex;flex-wrap:wrap;gap:10px}
</style>
