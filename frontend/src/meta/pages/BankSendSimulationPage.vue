<template>
  <main class="page" data-acceptance-id="bank-send-simulation-content">
    <section class="card stage">
      <Heading title="银行发送执行模拟" note="模拟成功 ≠ 银行已发送" />
      <p><strong>当前阶段：</strong>银行发送执行模拟阶段</p>
      <p><strong>允许：</strong>✓ 执行模拟　✓ 查看模拟结果　✓ 查看失败原因</p>
      <p><strong>禁止：</strong>× 真实发送银行　× 调用银行接口　× 执行付款　× 扣减资金　× 创建流水　× 写总账</p>
    </section>

    <section class="card" data-acceptance-id="bank-send-simulation-server-facts">
      <Heading title="服务端持久事实" note="API、页面、Diagnostic、StrictFacts 与 AcceptanceFacts 使用同一服务端事实" />
      <div class="grid">
        <Fact label="事实加载状态" :value="loadStatus" />
        <Fact label="事实来源" value="服务端" />
        <Fact label="模拟数量" :value="facts.simulationCount" />
        <Fact label="模拟成功" :value="facts.successCount" />
        <Fact label="模拟失败" :value="facts.failedCount" />
      </div>
      <p v-if="failed" class="error">银行发送执行模拟事实读取失败</p>
    </section>

    <section class="card" data-acceptance-id="bank-send-simulation-list">
      <Heading title="模拟执行列表" note="仅展示中文业务状态，不代表真实银行发送" />
      <PceEnterpriseListTable
        ref="tableRef"
        :contract="enterpriseListContract"
        page-id="bank-send-simulation"
        table-id="bank-send-simulations-main"
        :rows="rows"
        :table-rows="filteredRows"
        :filter-schema="filterSchema"
        :filters="filters"
        :quick-search="quickSearch"
        :advanced-visible="advancedVisible"
        :selected-count="selectedRows.length"
        :active-filter-count="activeFilterCount"
        :sort-text="sortText"
        primary-field="simulationNo"
        primary-label="模拟编号"
        :primary-width="310"
        min-width="1320px"
        scroll-acceptance-id="bank-send-simulations-horizontal-scroll"
        :action-width="240"
        @update:quick-search="quickSearch = $event"
        @search="appliedSearch = quickSearch"
        @toggle-advanced="advancedVisible = !advancedVisible"
        @clear-filters="clearFilters"
        @clear-sort="clearSort"
        @export-current="exportCurrent"
        @clear-selection="clearSelection"
        @update-filter="(field, value) => filters[field] = value"
        @selection-change="handleSelectionChange"
        @sort-change="handleSort"
      >
        <template #columns>
          <el-table-column prop="bankSendRequestNo" label="来源发送请求" width="300" />
          <el-table-column prop="statusLabel" label="当前状态" width="160">
            <template #default="{ row }">
              <PceBusinessStatus :status-code="row.status" :status-label="row.statusLabel" :source="serverFactSource" />
            </template>
          </el-table-column>
          <el-table-column prop="simulationResult" label="模拟结果" width="160" />
          <el-table-column prop="currentStateSource" label="状态来源" width="120" />
        </template>
        <template #actions="{ row }">
          <el-button size="small" plain @click="viewResult(row)">{{ resultActionLabel }}</el-button>
          <el-button v-if="row.recovery" size="small" plain @click="viewRecovery(row)">{{ recoveryActionLabel }}</el-button>
        </template>
      </PceEnterpriseListTable>
    </section>

    <section class="card" data-acceptance-id="bank-send-simulation-checks">
      <Heading title="模拟检查结果" note="所有检查均由服务端生成" />
      <div class="grid">
        <Fact label="授权" :value="check('authorizationReadyForExecution')" />
        <Fact label="请求" :value="check('requestHashConsistent')" />
        <Fact label="金额" :value="check('paymentAmountConsistent')" />
        <Fact label="账户" :value="check('beneficiaryAccountConsistent')" />
        <Fact label="报文" :value="check('messageDigestConsistent')" />
        <Fact label="接口模拟环境" :value="check('simulatedBankInterfaceAvailable', '正常')" />
      </div>
      <p class="notice">模拟成功只说明执行前条件通过，银行报文仍未发送。</p>
    </section>

    <section class="card" data-acceptance-id="bank-send-simulation-recovery">
      <Heading title="失败恢复" note="失败后只记录恢复过程，不自动重试、不自动发送" />
      <div class="grid">
        <Fact label="失败原因" :value="failedSimulation?.failureReason || '无'" />
        <Fact label="恢复状态" :value="failedSimulation?.recovery?.recoveryStatusLabel || '无需恢复'" />
        <Fact label="审计记录" :value="failedSimulation?.recovery?.auditEvents?.length || failedSimulation?.auditEvents?.length || 0" />
      </div>
    </section>

    <PceBusinessActionBar
      current-module="bank-send-simulation"
      :current-status="current?.status || 'simulation_success'"
      :current-status-label="current?.statusLabel || '模拟成功'"
      :selected-rows="selectedRows.length ? selectedRows : current ? [current] : []"
      :eligibility="true"
      :include-action-ids="[
        'create-bank-send-execution-simulation',
        'view-bank-send-execution-simulation-result',
        'view-bank-send-execution-recovery',
      ]"
      @execute="handleAction"
    />

    <section class="card boundary" data-acceptance-id="bank-send-simulation-boundary">
      <Heading title="执行边界保护" note="本页面没有真实发送能力" />
      <p>允许：✓ 执行模拟　✓ 查看模拟结果　✓ 查看失败原因</p>
      <p>禁止：× 真实发送银行　× 调用银行接口　× 执行付款　× 扣减资金　× 创建流水　× 写总账</p>
      <div class="grid">
        <Fact label="银行报文发送" :value="facts.bankMessageSentCount" />
        <Fact label="付款执行" :value="facts.paymentExecutionCount" />
        <Fact label="资金扣减" :value="facts.fundsDebitCount" />
        <Fact label="银行流水" :value="facts.bankTransactionCount" />
        <Fact label="业务推进写入" :value="facts.businessProgressWriteCount" />
      </div>
    </section>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="720px">
      <pre>{{ JSON.stringify(dialogRow, null, 2) }}</pre>
    </el-dialog>
  </main>
</template>

<script setup>
import { computed, h, inject, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { bankSendSimulationApi } from '@/api/bankSendSimulation.js'
import PceBusinessActionBar from '@/meta/components/PceBusinessActionBar.vue'
import PceBusinessStatus from '@/meta/components/PceBusinessStatus.vue'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import { PAGE_OBSERVABILITY_ACTIONS_KEY } from '@/meta/runtime/pageObservabilityActions.js'
import { pceBusinessActionLabel } from '@/meta/runtime/pceBusinessActionRegistry.js'
import {
  createPceEnterpriseListContract,
  usePceEnterpriseListRuntime,
} from '@/meta/runtime/pceEnterpriseListContract.js'
import {
  BANK_SEND_SIMULATION_FILTER_SCHEMA,
  BANK_SEND_SIMULATION_VERSION,
  createBankSendSimulationPageFacts,
} from '@/meta/runtime/bankSendSimulationRuntime.js'
import { factLoadFailureFromError } from '@/meta/runtime/pceFactLoadContract.js'

const rows = ref([])
const serverFactSource = 'server'
const resultActionLabel = pceBusinessActionLabel('view-bank-send-execution-simulation-result')
const recoveryActionLabel = pceBusinessActionLabel('view-bank-send-execution-recovery')
const current = ref(null)
const facts = reactive({})
const factLoadFacts = ref(null)
const strictServerFacts = ref({})
const acceptanceFacts = ref({})
const observability = inject(PAGE_OBSERVABILITY_ACTIONS_KEY, null)
const dialogVisible = ref(false)
const dialogTitle = ref('')
const dialogRow = ref(null)
const failed = computed(() => factLoadFacts.value?.factLoadStatus === 'read_failed')
const failedSimulation = computed(() => rows.value.find(row => row.status === 'simulation_failed') || null)
const loadStatus = computed(() => failed.value ? '读取失败' : factLoadFacts.value?.factLoadStatus === 'success' ? '加载成功' : '加载中')
const enterpriseListContract = createPceEnterpriseListContract({
  pageCode: 'bank-send-simulation', pageType: 'list',
  title: '银行发送执行模拟', moduleCode: 'FIN_BANK_SEND_SIMULATION',
})
const filterSchema = BANK_SEND_SIMULATION_FILTER_SCHEMA
const {
  selectedRows, quickSearch, appliedSearch, advancedVisible, filters, tableRef,
  activeFilterCount, sortText, filteredRows, clearFilters, clearSort,
  clearSelection, handleSort, exportCurrent,
} = usePceEnterpriseListRuntime({
  rows, filterSchema, pageCode: 'bank-send-simulation',
  searchFields: ['simulationNo', 'bankSendRequestNo', 'statusLabel'],
  exportFileName: 'bank-send-simulations.csv',
  exportColumns: [
    { field: 'simulationNo', label: '模拟编号' },
    { field: 'bankSendRequestNo', label: '来源发送请求' },
    { field: 'statusLabel', label: '银行发送模拟状态' },
    { field: 'simulationResult', label: '模拟结果' },
  ],
})
const Heading = (_, { attrs }) => h('div', { class: 'heading' }, [h('h2', attrs.title), h('p', attrs.note)])
const Fact = (_, { attrs }) => h('article', { class: 'fact' }, [h('span', attrs.label), h('strong', String(attrs.value ?? '-'))])
function handleSelectionChange(selection) {
  selectedRows.value = selection
  if (selection.length === 1) current.value = selection[0]
}
function check(field, success = '一致') {
  return current.value?.checks?.[field] === true ? success : '未通过'
}
function viewResult(row) {
  current.value = row
  dialogTitle.value = '模拟执行结果'
  dialogRow.value = row
  dialogVisible.value = true
}
function viewRecovery(row) {
  current.value = row
  dialogTitle.value = '失败恢复记录'
  dialogRow.value = row.recovery
  dialogVisible.value = true
}
function handleAction(action) {
  if (action.actionId === 'view-bank-send-execution-simulation-result' && current.value) {
    viewResult(current.value)
  } else if (action.actionId === 'view-bank-send-execution-recovery' && current.value?.recovery) {
    viewRecovery(current.value)
  } else {
    ElMessage.info('创建执行模拟仅在隔离测试角色与服务端幂等门禁下开放')
  }
}
async function refresh() {
  try {
    const loaded = createBankSendSimulationPageFacts(await bankSendSimulationApi.list())
    rows.value = loaded.rows
    current.value = rows.value.find(row => row.status === 'simulation_success') || rows.value[0] || null
    Object.assign(facts, loaded.facts)
    factLoadFacts.value = loaded.factLoadFacts
    strictServerFacts.value = loaded.strictServerFacts
    acceptanceFacts.value = loaded.acceptanceFacts
    publish()
  } catch (error) {
    factLoadFacts.value = factLoadFailureFromError(
      error, '/api/finance/bank-send-simulations/', factLoadFacts.value,
    )
    rows.value = []
    publish()
    ElMessage.error('银行发送执行模拟事实读取失败')
  }
}
function diagnostics() {
  return {
    version: BANK_SEND_SIMULATION_VERSION,
    canonicalName: '银行发送执行模拟',
    moduleCode: 'FIN_BANK_SEND_SIMULATION',
    pageFactOwner: 'FIN_BANK_SEND_SIMULATION',
    pageFactOwnerGuard: 'page_fact_owner_unique',
    factSource: 'server',
    ...factLoadFacts.value,
    simulationFacts: { ...facts },
    acceptanceFacts: acceptanceFacts.value,
    diagnosticFacts: acceptanceFacts.value,
    strictFacts: acceptanceFacts.value,
    strictServerFacts: strictServerFacts.value,
    resultCount: facts.simulationCount ?? null,
    bankMessageSendWriteCount: 0,
    paymentExecutionWriteCount: 0,
    businessProgressWriteCount: 0,
  }
}
function publish() {
  window.__PCE_BUSINESS_PAGE_ACCEPTANCE__ = {
    ...diagnostics(),
    pageAssertions: [
      { regionTitle: '模拟执行列表', actualValue: current.value?.statusLabel || '', passed: Boolean(current.value) },
      { regionTitle: '模拟检查结果', actualValue: '模拟成功 ≠ 银行已发送', passed: true },
      { regionTitle: '失败恢复', actualValue: '不自动重试', passed: true },
      { regionTitle: '执行边界保护', actualValue: '0/0/0/0', passed: !facts.bankMessageSentCount && !facts.paymentExecutionCount && !facts.fundsDebitCount && !facts.bankTransactionCount },
    ],
  }
}
const provider = { factOwner: 'FIN_BANK_SEND_SIMULATION', refresh, buildDiagnostics: diagnostics }
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
.notice { color: #92400e; font-weight: 700; }
.error { color: #b42318; font-weight: 700; }
pre { max-height: 520px; overflow: auto; white-space: pre-wrap; }
</style>
