<template>
  <main class="page" data-acceptance-id="bank-send-simulation-audit-content">
    <section class="card stage">
      <Heading title="银行发送模拟审计" note="模拟审计不是发送审计，未进入银行发送" />
      <p><strong>当前阶段：</strong>银行发送模拟结果审计阶段</p>
      <p><strong>允许：</strong>✓ 查看模拟审计　✓ 查看模拟链路　✓ 查看隔离状态</p>
      <p><strong>禁止：</strong>× 开启生产发送　× 配置生产接口　× 上传生产密钥　× 执行银行发送</p>
    </section>

    <section class="card" data-acceptance-id="bank-send-simulation-audit-facts">
      <Heading title="服务端持久事实" note="API、Page、Diagnostic、StrictFacts、AcceptanceFacts 使用同一服务端事实" />
      <div class="grid">
        <Fact label="事实加载状态" value="加载成功" />
        <Fact label="事实来源" value="服务端" />
        <Fact label="审计记录" :value="facts.recordCount" />
        <Fact label="模拟对象" :value="facts.simulationCount" />
        <Fact label="完成审计" :value="facts.completedAuditCount" />
        <Fact label="失败审计" :value="facts.failedAuditCount" />
        <Fact label="恢复审计" :value="facts.recoveredAuditCount" />
      </div>
    </section>

    <section class="card" data-acceptance-id="bank-send-simulation-audit-list">
      <Heading title="模拟审计列表" note="全过程独立审计，可按模拟编号追溯" />
      <PceEnterpriseListTable
        ref="tableRef"
        :contract="enterpriseListContract"
        page-id="bank-send-simulation-audit"
        table-id="bank-send-simulation-audits-main"
        :rows="rows"
        :table-rows="filteredRows"
        :filter-schema="filterSchema"
        :filters="filters"
        :quick-search="quickSearch"
        :advanced-visible="advancedVisible"
        :selected-count="selectedRows.length"
        :active-filter-count="activeFilterCount"
        :sort-text="sortText"
        primary-field="auditNo"
        primary-label="审计编号"
        :primary-width="360"
        min-width="1680px"
        scroll-acceptance-id="bank-send-simulation-audits-horizontal-scroll"
        :action-width="150"
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
          <el-table-column prop="simulationNo" label="模拟编号" width="330" />
          <el-table-column prop="auditTypeLabel" label="审计类型" width="150">
            <template #default="{ row }">
              <PceBusinessStatus :status-code="row.auditType" :status-label="row.auditTypeLabel" source="server" />
            </template>
          </el-table-column>
          <el-table-column prop="operator" label="操作人" width="180" />
          <el-table-column prop="timestamp" label="时间" width="220" />
          <el-table-column prop="reason" label="原因" min-width="360" />
        </template>
        <template #actions="{ row }">
          <el-button size="small" plain @click="showAudit(row)">{{ viewAuditLabel }}</el-button>
        </template>
      </PceEnterpriseListTable>
    </section>

    <section class="card" data-acceptance-id="bank-send-simulation-audit-chain">
      <Heading title="模拟链路" note="链路终点是模拟结果，不是银行发送" />
      <div class="chain">
        <strong>银行发送请求</strong><span>→</span>
        <strong>执行授权</strong><span>→</span>
        <strong>模拟执行</strong><span>→</span>
        <strong>模拟结果</strong>
      </div>
      <p class="notice">未进入银行发送。</p>
    </section>

    <section class="card boundary" data-acceptance-id="bank-send-simulation-audit-isolation">
      <Heading title="隔离状态" note="隔离事实来自服务端生产隔离门禁" />
      <div class="grid">
        <Fact label="模拟环境" :value="gate?.simulationEnvironment ? '是' : '否'" />
        <Fact label="生产接口" :value="gate?.productionConnectionEnabled ? '已启用' : '未启用'" />
        <Fact label="生产密钥" :value="gate?.productionSecretAvailable ? '存在' : '不存在'" />
        <Fact label="真实发送" :value="gate?.productionSendAllowed ? '允许' : '禁止'" />
      </div>
    </section>

    <el-dialog v-model="dialogVisible" title="模拟审计详情" width="720px">
      <pre>{{ JSON.stringify(dialogRow, null, 2) }}</pre>
    </el-dialog>
  </main>
</template>

<script setup>
import { h, inject, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { bankSendSimulationIsolationApi } from '@/api/bankSendSimulationIsolation.js'
import PceBusinessStatus from '@/meta/components/PceBusinessStatus.vue'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import { PAGE_OBSERVABILITY_ACTIONS_KEY } from '@/meta/runtime/pageObservabilityActions.js'
import { pceBusinessActionLabel } from '@/meta/runtime/pceBusinessActionRegistry.js'
import {
  createPceEnterpriseListContract,
  usePceEnterpriseListRuntime,
} from '@/meta/runtime/pceEnterpriseListContract.js'
import {
  AUDIT_FILTER_SCHEMA,
  BANK_SEND_SIMULATION_ISOLATION_VERSION,
  createIsolationGatePageFacts,
  createSimulationAuditPageFacts,
} from '@/meta/runtime/bankSendSimulationIsolationRuntime.js'

const rows = ref([])
const gate = ref(null)
const facts = reactive({})
const acceptanceFacts = ref({})
const strictFacts = ref({})
const diagnosticFacts = ref({})
const observability = inject(PAGE_OBSERVABILITY_ACTIONS_KEY, null)
const dialogVisible = ref(false)
const dialogRow = ref(null)
const viewAuditLabel = pceBusinessActionLabel('view-bank-send-simulation-audit')
const enterpriseListContract = createPceEnterpriseListContract({
  pageCode: 'bank-send-simulation-audit',
  pageType: 'list',
  title: '银行发送模拟审计',
  moduleCode: 'FIN_BANK_SEND_SIMULATION_AUDIT',
})
const filterSchema = AUDIT_FILTER_SCHEMA
const {
  selectedRows, quickSearch, appliedSearch, advancedVisible, filters, tableRef,
  activeFilterCount, sortText, filteredRows, clearFilters, clearSort,
  clearSelection, handleSort, exportCurrent,
} = usePceEnterpriseListRuntime({
  rows, filterSchema, pageCode: 'bank-send-simulation-audit',
  searchFields: ['auditNo', 'simulationNo', 'auditTypeLabel', 'operator', 'reason'],
  exportFileName: 'bank-send-simulation-audits.csv',
  exportColumns: [
    { field: 'auditNo', label: '审计编号' },
    { field: 'simulationNo', label: '模拟编号' },
    { field: 'auditTypeLabel', label: '审计类型' },
    { field: 'operator', label: '操作人' },
    { field: 'timestamp', label: '时间' },
    { field: 'reason', label: '原因' },
  ],
})
const Heading = (_, { attrs }) => h('div', { class: 'heading' }, [h('h2', attrs.title), h('p', attrs.note)])
const Fact = (_, { attrs }) => h('article', { class: 'fact' }, [h('span', attrs.label), h('strong', String(attrs.value ?? '-'))])
function showAudit(row) {
  dialogRow.value = row
  dialogVisible.value = true
}
async function refresh() {
  try {
    const [auditPayload, gatePayload] = await Promise.all([
      bankSendSimulationIsolationApi.audits(),
      bankSendSimulationIsolationApi.gates(),
    ])
    const loaded = createSimulationAuditPageFacts(auditPayload)
    const gateLoaded = createIsolationGatePageFacts(gatePayload)
    rows.value = loaded.rows
    gate.value = gateLoaded.rows[0] || null
    Object.assign(facts, loaded.facts)
    acceptanceFacts.value = loaded.acceptanceFacts
    strictFacts.value = loaded.strictFacts
    diagnosticFacts.value = loaded.diagnosticFacts
    publish()
  } catch (error) {
    ElMessage.error(`银行发送模拟审计事实读取失败：${error?.message || 'UNKNOWN'}`)
  }
}
function diagnostics() {
  return {
    version: BANK_SEND_SIMULATION_ISOLATION_VERSION,
    canonicalName: '银行发送模拟审计',
    moduleCode: 'FIN_BANK_SEND_SIMULATION_AUDIT',
    pageFactOwner: 'FIN_BANK_SEND_SIMULATION_AUDIT',
    pageFactOwnerGuard: 'page_fact_owner_unique',
    factSource: 'server',
    auditFacts: { ...facts },
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
      { regionTitle: '模拟审计列表', actualValue: String(facts.recordCount), passed: facts.recordCount > 0 },
      { regionTitle: '模拟链路', actualValue: '未进入银行发送', passed: true },
      { regionTitle: '隔离状态', actualValue: '真实发送：禁止', passed: gate.value?.productionSendAllowed === false },
    ],
  }
}
const provider = { factOwner: 'FIN_BANK_SEND_SIMULATION_AUDIT', refresh, buildDiagnostics: diagnostics }
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
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 10px; margin: 12px 0; }
.fact { display: grid; gap: 5px; padding: 12px; border-radius: 8px; background: #f5f8fb; }
.fact span { color: #64748b; font-size: 13px; }
.chain { display: flex; flex-wrap: wrap; align-items: center; gap: 14px; padding: 16px; border-radius: 8px; background: #f5f8fb; }
.notice { color: #92400e; font-weight: 700; }
pre { max-height: 520px; overflow: auto; white-space: pre-wrap; }
</style>
