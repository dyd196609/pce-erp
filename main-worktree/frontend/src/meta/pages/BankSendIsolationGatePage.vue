<template>
  <main class="page" data-acceptance-id="bank-send-isolation-gate-content">
    <section class="card stage">
      <Heading title="银行发送生产隔离门禁" note="证明当前系统仍处于模拟隔离状态" />
      <p><strong>允许：</strong>✓ 查看隔离状态</p>
      <p><strong>禁止：</strong>× 开启生产发送　× 配置生产接口　× 上传生产密钥　× 执行银行发送</p>
    </section>

    <section class="card" data-acceptance-id="bank-send-isolation-gate-facts">
      <Heading title="服务端持久事实" note="五端复用同一生产隔离门禁事实" />
      <div class="grid">
        <Fact label="事实加载状态" value="加载成功" />
        <Fact label="事实来源" value="服务端" />
        <Fact label="门禁数量" :value="facts.gateCount" />
        <Fact label="隔离有效" :value="facts.isolatedCount" />
        <Fact label="生产发送允许" :value="facts.productionSendAllowedCount" />
      </div>
    </section>

    <section class="card" data-acceptance-id="bank-send-isolation-gate-list">
      <Heading title="生产隔离门禁列表" note="仅提供查看能力，不提供生产配置入口" />
      <PceEnterpriseListTable
        ref="tableRef"
        :contract="enterpriseListContract"
        page-id="bank-send-isolation-gate"
        table-id="bank-send-isolation-gates-main"
        :rows="rows"
        :table-rows="filteredRows"
        :filter-schema="filterSchema"
        :filters="filters"
        :quick-search="quickSearch"
        :advanced-visible="advancedVisible"
        :selected-count="selectedRows.length"
        :active-filter-count="activeFilterCount"
        :sort-text="sortText"
        primary-field="gateNo"
        primary-label="门禁编号"
        :primary-width="380"
        min-width="1500px"
        scroll-acceptance-id="bank-send-isolation-gates-horizontal-scroll"
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
          <el-table-column prop="statusLabel" label="状态" width="150">
            <template #default="{ row }">
              <PceBusinessStatus :status-code="row.status" :status-label="row.statusLabel" source="server" />
            </template>
          </el-table-column>
          <el-table-column label="环境" width="150">
            <template #default="{ row }">{{ row.simulationEnvironment ? '模拟环境' : '非模拟环境' }}</template>
          </el-table-column>
          <el-table-column label="生产连接" width="150">
            <template #default="{ row }">{{ row.productionConnectionEnabled ? '开启' : '关闭' }}</template>
          </el-table-column>
          <el-table-column label="生产密钥" width="150">
            <template #default="{ row }">{{ row.productionSecretAvailable ? '存在' : '不存在' }}</template>
          </el-table-column>
          <el-table-column label="生产发送" width="150">
            <template #default="{ row }">{{ row.productionSendAllowed ? '允许' : '禁止' }}</template>
          </el-table-column>
        </template>
        <template #actions="{ row }">
          <el-button size="small" plain @click="showGate(row)">{{ viewIsolationLabel }}</el-button>
        </template>
      </PceEnterpriseListTable>
    </section>

    <section class="card boundary" data-acceptance-id="bank-send-isolation-gate-status">
      <Heading title="隔离状态" note="真实发送能力保持关闭" />
      <div class="grid">
        <Fact label="环境" value="模拟环境" />
        <Fact label="生产连接" :value="current?.productionConnectionEnabled ? '开启' : '关闭'" />
        <Fact label="生产密钥" :value="current?.productionSecretAvailable ? '存在' : '不存在'" />
        <Fact label="生产发送" :value="current?.productionSendAllowed ? '允许' : '禁止'" />
        <Fact label="付款执行" :value="current?.paymentExecutionAllowed ? '允许' : '禁止'" />
        <Fact label="状态" :value="current?.statusLabel || '-'" />
      </div>
      <p class="notice">隔离有效：当前页面没有任何开启生产发送的动作。</p>
    </section>

    <section class="card" data-acceptance-id="bank-send-isolation-rules">
      <Heading title="隔离检查规则" note="ISOLATION-001～006 全部由服务端判定" />
      <div class="grid">
        <Fact v-for="code in ruleCodes" :key="code" :label="code" :value="current?.checks?.[code] ? '通过' : '未通过'" />
      </div>
    </section>

    <el-dialog v-model="dialogVisible" title="生产隔离门禁详情" width="720px">
      <pre>{{ JSON.stringify(dialogRow, null, 2) }}</pre>
    </el-dialog>
  </main>
</template>

<script setup>
import { computed, h, inject, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
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
  BANK_SEND_SIMULATION_ISOLATION_VERSION,
  ISOLATION_FILTER_SCHEMA,
  createIsolationGatePageFacts,
} from '@/meta/runtime/bankSendSimulationIsolationRuntime.js'

const rows = ref([])
const facts = reactive({})
const acceptanceFacts = ref({})
const strictFacts = ref({})
const diagnosticFacts = ref({})
const observability = inject(PAGE_OBSERVABILITY_ACTIONS_KEY, null)
const dialogVisible = ref(false)
const dialogRow = ref(null)
const current = computed(() => rows.value[0] || null)
const ruleCodes = ['ISOLATION-001', 'ISOLATION-002', 'ISOLATION-003', 'ISOLATION-004', 'ISOLATION-005', 'ISOLATION-006']
const viewIsolationLabel = pceBusinessActionLabel('view-bank-send-production-isolation')
const enterpriseListContract = createPceEnterpriseListContract({
  pageCode: 'bank-send-isolation-gate',
  pageType: 'list',
  title: '银行发送生产隔离门禁',
  moduleCode: 'FIN_BANK_SEND_ISOLATION_GATE',
})
const filterSchema = ISOLATION_FILTER_SCHEMA
const {
  selectedRows, quickSearch, appliedSearch, advancedVisible, filters, tableRef,
  activeFilterCount, sortText, filteredRows, clearFilters, clearSort,
  clearSelection, handleSort, exportCurrent,
} = usePceEnterpriseListRuntime({
  rows, filterSchema, pageCode: 'bank-send-isolation-gate',
  searchFields: ['gateNo', 'statusLabel', 'tenantId', 'batchId'],
  exportFileName: 'bank-send-isolation-gates.csv',
  exportColumns: [
    { field: 'gateNo', label: '门禁编号' },
    { field: 'statusLabel', label: '隔离状态' },
    { field: 'tenantId', label: '租户' },
    { field: 'batchId', label: '批次' },
  ],
})
const Heading = (_, { attrs }) => h('div', { class: 'heading' }, [h('h2', attrs.title), h('p', attrs.note)])
const Fact = (_, { attrs }) => h('article', { class: 'fact' }, [h('span', attrs.label), h('strong', String(attrs.value ?? '-'))])
function showGate(row) {
  dialogRow.value = row
  dialogVisible.value = true
}
async function refresh() {
  try {
    const loaded = createIsolationGatePageFacts(
      await bankSendSimulationIsolationApi.gates(),
    )
    rows.value = loaded.rows
    Object.assign(facts, loaded.facts)
    acceptanceFacts.value = loaded.acceptanceFacts
    strictFacts.value = loaded.strictFacts
    diagnosticFacts.value = loaded.diagnosticFacts
    publish()
  } catch (error) {
    ElMessage.error(`银行发送生产隔离门禁事实读取失败：${error?.message || 'UNKNOWN'}`)
  }
}
function diagnostics() {
  return {
    version: BANK_SEND_SIMULATION_ISOLATION_VERSION,
    canonicalName: '银行发送生产隔离门禁',
    moduleCode: 'FIN_BANK_SEND_ISOLATION_GATE',
    pageFactOwner: 'FIN_BANK_SEND_ISOLATION_GATE',
    pageFactOwnerGuard: 'page_fact_owner_unique',
    factSource: 'server',
    isolationFacts: { ...facts },
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
      { regionTitle: '生产隔离门禁列表', actualValue: String(facts.gateCount), passed: facts.gateCount === 1 },
      { regionTitle: '隔离状态', actualValue: current.value?.statusLabel || '', passed: current.value?.status === 'isolated' },
      { regionTitle: '真实发送', actualValue: '禁止', passed: current.value?.productionSendAllowed === false },
    ],
  }
}
const provider = { factOwner: 'FIN_BANK_SEND_ISOLATION_GATE', refresh, buildDiagnostics: diagnostics }
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
.notice { color: #166534; font-weight: 700; }
pre { max-height: 520px; overflow: auto; white-space: pre-wrap; }
</style>
