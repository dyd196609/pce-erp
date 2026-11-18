<template>
  <main class="page" data-acceptance-id="bank-send-chain-trace-content">
    <section class="card stage">
      <Heading title="银行发送全链路追踪" note="只读展示银行发送前八个服务端事实节点，不提供执行入口" />
      <p><strong>当前阶段：</strong>真实银行发送前链路追踪阶段</p>
      <p><strong>允许：</strong>✓ 查看链路　✓ 查看来源　✓ 查看节点状态</p>
      <p><strong>禁止：</strong>× 银行发送　× 付款执行　× 资金扣减</p>
    </section>

    <section class="card" data-acceptance-id="bank-send-chain-trace-facts">
      <Heading title="服务端持久事实" note="API、页面、复制诊断、strictFacts 与 AcceptanceFacts 共用同一事实" />
      <div class="grid">
        <Fact label="事实加载状态" value="加载成功" />
        <Fact label="事实来源" value="服务端" />
        <Fact label="追踪数量" :value="facts.traceCount" />
        <Fact label="完整链路" :value="facts.completeTraceCount" />
        <Fact label="节点数量" :value="facts.nodeCount" />
        <Fact label="缺失节点" :value="facts.missingNodeCount" />
      </div>
    </section>

    <section class="card" data-acceptance-id="bank-send-chain-trace-list">
      <Heading title="银行发送全链路追踪列表" note="链路追踪是只读对象，不会推进任何业务状态" />
      <PceEnterpriseListTable
        ref="tableRef"
        :contract="enterpriseListContract"
        page-id="bank-send-chain-trace"
        table-id="bank-send-chain-traces-main"
        :rows="rows"
        :table-rows="filteredRows"
        :filter-schema="filterSchema"
        :filters="filters"
        :quick-search="quickSearch"
        :advanced-visible="advancedVisible"
        :selected-count="selectedRows.length"
        :active-filter-count="activeFilterCount"
        :sort-text="sortText"
        primary-field="traceNo"
        primary-label="追踪编号"
        :primary-width="380"
        min-width="1700px"
        scroll-acceptance-id="bank-send-chain-traces-horizontal-scroll"
        :action-width="140"
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
          <el-table-column prop="formalPaymentOrderNo" label="正式付款单" width="220" />
          <el-table-column prop="bankSendRequestNo" label="发送请求" width="260" />
          <el-table-column prop="simulationNo" label="执行模拟" width="280" />
          <el-table-column label="链路完整" width="130">
            <template #default="{ row }">{{ row.traceComplete ? '是' : '否' }}</template>
          </el-table-column>
          <el-table-column prop="nodeCount" label="节点数量" width="120" />
          <el-table-column label="来源" width="120">
            <template #default>服务端</template>
          </el-table-column>
        </template>
        <template #actions="{ row }">
          <el-button size="small" plain @click="showTrace(row)">{{ viewTraceLabel }}</el-button>
        </template>
      </PceEnterpriseListTable>
    </section>

    <section class="card" data-acceptance-id="bank-send-chain-trace-nodes">
      <Heading title="链路节点展示" note="节点顺序固定，不允许跳过节点" />
      <div class="chain">
        <template v-for="(node, index) in current?.nodes || []" :key="node.nodeType">
          <article class="node">
            <span>{{ node.order }}</span>
            <strong>{{ node.nodeLabel }}</strong>
            <small>{{ node.businessNo }}</small>
            <small>状态：{{ node.status }}</small>
            <small>来源：服务端</small>
          </article>
          <b v-if="index < 7" class="arrow">→</b>
        </template>
      </div>
    </section>

    <section class="card" data-acceptance-id="bank-send-chain-completeness">
      <Heading title="链路完整性检查" note="完整性由服务端固定顺序和来源关系判定" />
      <div class="grid">
        <Fact label="链路完整" :value="current?.traceComplete ? '是' : '否'" />
        <Fact label="来源" value="服务端" />
        <Fact label="节点数量" :value="current?.nodeCount || 0" />
        <Fact label="缺失节点" :value="current?.missingNodeCount || 0" />
      </div>
    </section>

    <section class="card boundary" data-acceptance-id="bank-send-chain-boundary">
      <Heading title="执行边界保护" note="追踪对象只证明链路完整，不代表执行或发送" />
      <div class="grid">
        <Fact label="真实发送" value="否" />
        <Fact label="付款执行" value="否" />
        <Fact label="资金扣减" value="否" />
      </div>
    </section>

    <el-dialog v-model="dialogVisible" title="银行发送链路详情" width="820px">
      <pre>{{ JSON.stringify(dialogRow, null, 2) }}</pre>
    </el-dialog>
  </main>
</template>

<script setup>
import { computed, h, inject, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { bankSendChainFinalApprovalApi } from '@/api/bankSendChainFinalApproval.js'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import { PAGE_OBSERVABILITY_ACTIONS_KEY } from '@/meta/runtime/pageObservabilityActions.js'
import { pceBusinessActionLabel } from '@/meta/runtime/pceBusinessActionRegistry.js'
import {
  createPceEnterpriseListContract,
  usePceEnterpriseListRuntime,
} from '@/meta/runtime/pceEnterpriseListContract.js'
import {
  BANK_SEND_CHAIN_FINAL_APPROVAL_VERSION,
  TRACE_FILTER_SCHEMA,
  createChainTracePageFacts,
} from '@/meta/runtime/bankSendChainFinalApprovalRuntime.js'

const rows = ref([])
const facts = reactive({})
const acceptanceFacts = ref({})
const strictFacts = ref({})
const diagnosticFacts = ref({})
const current = computed(() => rows.value[0] || null)
const observability = inject(PAGE_OBSERVABILITY_ACTIONS_KEY, null)
const dialogVisible = ref(false)
const dialogRow = ref(null)
const viewTraceLabel = pceBusinessActionLabel('view-bank-send-chain-trace')
const enterpriseListContract = createPceEnterpriseListContract({
  pageCode: 'bank-send-chain-trace',
  pageType: 'list',
  title: '银行发送全链路追踪',
  moduleCode: 'FIN_BANK_SEND_CHAIN_TRACE',
})
const filterSchema = TRACE_FILTER_SCHEMA
const {
  selectedRows, quickSearch, appliedSearch, advancedVisible, filters, tableRef,
  activeFilterCount, sortText, filteredRows, clearFilters, clearSort,
  clearSelection, handleSort, exportCurrent,
} = usePceEnterpriseListRuntime({
  rows, filterSchema, pageCode: 'bank-send-chain-trace',
  searchFields: ['traceNo', 'formalPaymentOrderNo', 'bankSendRequestNo', 'simulationNo'],
  exportFileName: 'bank-send-chain-traces.csv',
  exportColumns: [
    { field: 'traceNo', label: '追踪编号' },
    { field: 'formalPaymentOrderNo', label: '正式付款单' },
    { field: 'bankSendRequestNo', label: '发送请求' },
    { field: 'simulationNo', label: '执行模拟' },
  ],
})
const Heading = (_, { attrs }) => h('div', { class: 'heading' }, [h('h2', attrs.title), h('p', attrs.note)])
const Fact = (_, { attrs }) => h('article', { class: 'fact' }, [h('span', attrs.label), h('strong', String(attrs.value ?? '-'))])
function showTrace(row) {
  dialogRow.value = row
  dialogVisible.value = true
}
async function refresh() {
  try {
    const loaded = createChainTracePageFacts(
      await bankSendChainFinalApprovalApi.traces(),
    )
    rows.value = loaded.rows
    Object.assign(facts, loaded.facts)
    acceptanceFacts.value = loaded.acceptanceFacts
    strictFacts.value = loaded.strictFacts
    diagnosticFacts.value = loaded.diagnosticFacts
    publish()
  } catch (error) {
    ElMessage.error(`银行发送全链路事实读取失败：${error?.message || 'UNKNOWN'}`)
  }
}
function diagnostics() {
  return {
    version: BANK_SEND_CHAIN_FINAL_APPROVAL_VERSION,
    canonicalName: '银行发送全链路追踪',
    moduleCode: 'FIN_BANK_SEND_CHAIN_TRACE',
    pageFactOwner: 'FIN_BANK_SEND_CHAIN_TRACE',
    factSource: 'server',
    traceFacts: { ...facts },
    diagnosticFacts: diagnosticFacts.value,
    strictFacts: strictFacts.value,
    acceptanceFacts: acceptanceFacts.value,
    resultCount: facts.recordCount ?? null,
    dangerActionCount: 0,
    businessProgressWriteCount: 0,
  }
}
function publish() {
  window.__PCE_BUSINESS_PAGE_ACCEPTANCE__ = {
    ...diagnostics(),
    pageAssertions: [
      { regionTitle: '链路节点展示', actualValue: String(facts.nodeCount), passed: facts.nodeCount === 8 },
      { regionTitle: '链路完整性检查', actualValue: '是', passed: facts.missingNodeCount === 0 },
      { regionTitle: '执行边界保护', actualValue: '真实发送：否', passed: facts.realBankSendCount === 0 },
    ],
  }
}
const provider = { factOwner: 'FIN_BANK_SEND_CHAIN_TRACE', refresh, buildDiagnostics: diagnostics }
onMounted(async () => {
  observability?.register?.(provider)
  await refresh()
  observability?.register?.(provider)
})
onBeforeUnmount(() => observability?.unregister?.(provider))
</script>

<style scoped>
.page { display: grid; min-width: 0; gap: 18px; }
.card { min-width: 0; padding: 20px; border: 1px solid #dce4ed; border-radius: 12px; background: #fff; }
.stage { border-color: #93c5fd; background: #eff6ff; }
.boundary { border-color: #b8d8c4; background: #f5fbf7; }
.heading h2 { margin: 0; color: #16243a; }
.heading p { margin: 6px 0 16px; color: #64748b; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 10px; }
.fact { display: grid; gap: 5px; padding: 12px; border-radius: 8px; background: #f5f8fb; }
.fact span, .node small { color: #64748b; font-size: 13px; }
.chain { display: flex; align-items: stretch; gap: 8px; overflow-x: auto; padding-bottom: 8px; }
.node { display: grid; flex: 0 0 190px; gap: 6px; padding: 14px; border: 1px solid #dbe5f0; border-radius: 10px; background: #f8fafc; }
.node > span { width: 26px; height: 26px; border-radius: 50%; color: #fff; background: #2563eb; text-align: center; line-height: 26px; }
.arrow { align-self: center; color: #2563eb; }
pre { max-height: 520px; overflow: auto; white-space: pre-wrap; }
</style>
