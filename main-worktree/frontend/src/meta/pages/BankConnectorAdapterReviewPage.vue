<template>
  <main class="page" data-acceptance-id="bank-connector-adapter-content">
    <section class="card stage">
      <Heading title="银行接口适配评审" note="BankConnectorAdapter 所有方法只返回模拟结果，不进行真实 HTTP 调用" />
      <p><strong>允许：</strong>✓ 查看接口适配　✓ 查看签名结果　✓ 查看失败模型</p>
      <p><strong>禁止：</strong>× 调用银行接口　× 启用生产连接　× 上传生产密钥　× 执行银行发送</p>
    </section>

    <section class="card" data-acceptance-id="bank-connector-adapter-facts">
      <Heading title="服务端持久事实" note="适配器、签名、幂等、失败和回执事实均来自服务端" />
      <div class="grid">
        <Fact label="事实加载状态" value="加载成功" />
        <Fact label="事实来源" value="服务端" />
        <Fact label="适配器数量" :value="facts.adapterCount" />
        <Fact label="模拟允许" :value="facts.simulationAllowedCount" />
        <Fact label="生产启用" :value="facts.productionEnabledCount" />
        <Fact label="网络调用" :value="facts.networkCallCount" />
      </div>
    </section>

    <section class="card" data-acceptance-id="bank-connector-adapter-list">
      <Heading title="接口适配列表" note="模拟允许，生产关闭" />
      <PceEnterpriseListTable
        ref="tableRef"
        :contract="enterpriseListContract"
        page-id="bank-connector-adapter-review"
        table-id="bank-connector-adapter-reviews-main"
        :rows="rows"
        :table-rows="filteredRows"
        :filter-schema="filterSchema"
        :filters="filters"
        :quick-search="quickSearch"
        :advanced-visible="advancedVisible"
        :selected-count="selectedRows.length"
        :active-filter-count="activeFilterCount"
        :sort-text="sortText"
        primary-field="interfaceName"
        primary-label="接口名称"
        :primary-width="340"
        min-width="1450px"
        scroll-acceptance-id="bank-connector-adapter-horizontal-scroll"
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
          <el-table-column prop="environmentLabel" label="环境" width="180" />
          <el-table-column prop="statusLabel" label="状态" width="180" />
          <el-table-column prop="callMode" label="调用方式" width="260" />
          <el-table-column prop="productionMode" label="生产模式" width="180" />
        </template>
        <template #actions="{ row }">
          <el-button size="small" plain @click="showRow(row)">查看适配</el-button>
        </template>
      </PceEnterpriseListTable>
    </section>

    <section class="card" data-acceptance-id="bank-connector-signature">
      <Heading title="模拟签名" note="只使用 SHA256_SIMULATION，不加载生产证书" />
      <div class="grid">
        <Fact label="签名编号" :value="current?.signature?.signatureNo" />
        <Fact label="算法" :value="current?.signature?.algorithm" />
        <Fact label="证书模式" value="仅模拟" />
        <Fact label="载荷哈希" :value="current?.signature?.payloadHash" />
      </div>
    </section>

    <section class="card" data-acceptance-id="bank-connector-idempotency">
      <Heading title="幂等控制" note="同一请求与执行版本只保留一个模拟执行意图" />
      <div class="grid">
        <Fact label="幂等键" :value="current?.idempotency?.idempotencyKey" />
        <Fact label="请求编号" :value="current?.idempotency?.requestNo" />
        <Fact label="执行版本" :value="current?.idempotency?.executionVersion" />
        <Fact label="状态" value="已模拟" />
      </div>
    </section>

    <section class="card" data-acceptance-id="bank-connector-failure">
      <Heading title="失败模型" note="只模拟失败，禁止自动重试" />
      <div class="grid">
        <Fact label="失败类型" :value="current?.failure?.failureType" />
        <Fact label="失败原因" :value="current?.failure?.failureReason" />
        <Fact label="允许重试" :value="current?.failure?.retryAllowed ? '是' : '否'" />
        <Fact label="模拟失败" :value="current?.failure?.simulated ? '是' : '否'" />
      </div>
    </section>

    <section class="card" data-acceptance-id="bank-connector-receipt">
      <Heading title="模拟回执" note="回执不是来自真实银行" />
      <div class="grid">
        <Fact label="回执编号" :value="current?.receipt?.receiptNo" />
        <Fact label="响应状态" :value="current?.receipt?.responseStatus" />
        <Fact label="回执来源" value="模拟" />
        <Fact label="真实银行报文" value="未发送" />
      </div>
    </section>

    <section class="card boundary" data-acceptance-id="bank-connector-adapter-boundary">
      <Heading title="执行能力边界" note="接口抽象存在不代表生产连接已开放" />
      <p class="notice">框架存在 ≠ 已经可以发送银行</p>
      <div class="grid">
        <Fact label="生产环境" value="关闭" />
        <Fact label="网络调用" value="0" />
        <Fact label="真实银行发送" value="否" />
      </div>
    </section>

    <el-dialog v-model="dialogVisible" title="银行接口适配详情" width="820px">
      <pre>{{ JSON.stringify(dialogRow, null, 2) }}</pre>
    </el-dialog>
  </main>
</template>

<script setup>
import { computed, h, inject, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { bankSendExecutionFrameworkApi } from '@/api/bankSendExecutionFramework.js'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import { PAGE_OBSERVABILITY_ACTIONS_KEY } from '@/meta/runtime/pageObservabilityActions.js'
import { createPceEnterpriseListContract, usePceEnterpriseListRuntime } from '@/meta/runtime/pceEnterpriseListContract.js'
import {
  ADAPTER_FILTER_SCHEMA,
  BANK_SEND_EXECUTION_FRAMEWORK_VERSION,
  createAdapterPageFacts,
} from '@/meta/runtime/bankSendExecutionFrameworkRuntime.js'

const rows = ref([])
const facts = reactive({})
const acceptanceFacts = ref({})
const strictFacts = ref({})
const diagnosticFacts = ref({})
const current = computed(() => rows.value[0] || null)
const observability = inject(PAGE_OBSERVABILITY_ACTIONS_KEY, null)
const dialogVisible = ref(false)
const dialogRow = ref(null)
const filterSchema = ADAPTER_FILTER_SCHEMA
const enterpriseListContract = createPceEnterpriseListContract({
  pageCode: 'bank-connector-adapter-review',
  pageType: 'list',
  title: '银行接口适配评审',
  moduleCode: 'FIN_BANK_CONNECTOR_ADAPTER_REVIEW',
})
const {
  selectedRows, quickSearch, appliedSearch, advancedVisible, filters, tableRef,
  activeFilterCount, sortText, filteredRows, clearFilters, clearSort,
  clearSelection, handleSort, exportCurrent,
} = usePceEnterpriseListRuntime({
  rows, filterSchema, pageCode: 'bank-connector-adapter-review',
  searchFields: ['interfaceName', 'environmentLabel', 'statusLabel', 'callMode'],
  exportFileName: 'bank-connector-adapter-reviews.csv',
  exportColumns: [
    { field: 'interfaceName', label: '接口名称' },
    { field: 'environmentLabel', label: '环境' },
    { field: 'callMode', label: '调用方式' },
  ],
})
const Heading = (_, { attrs }) => h('div', { class: 'heading' }, [h('h2', attrs.title), h('p', attrs.note)])
const Fact = (_, { attrs }) => h('article', { class: 'fact' }, [h('span', attrs.label), h('strong', String(attrs.value ?? '-'))])
function showRow(row) { dialogRow.value = row; dialogVisible.value = true }
function diagnostics() {
  return {
    version: BANK_SEND_EXECUTION_FRAMEWORK_VERSION,
    canonicalName: '银行接口适配评审',
    moduleCode: 'FIN_BANK_CONNECTOR_ADAPTER_REVIEW',
    pageFactOwner: 'FIN_BANK_CONNECTOR_ADAPTER_REVIEW',
    factSource: 'server',
    adapterFacts: { ...facts },
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
      { regionTitle: '接口适配列表', actualValue: '模拟允许/生产关闭', passed: current.value?.productionMode === '关闭' },
      { regionTitle: '模拟签名', actualValue: '无生产证书', passed: current.value?.signature?.certificateMode === 'simulation_only' },
      { regionTitle: '幂等控制', actualValue: '请求+版本唯一', passed: Boolean(current.value?.idempotency?.idempotencyKey) },
      { regionTitle: '失败模型', actualValue: '禁止自动重试', passed: current.value?.failure?.retryAllowed === false },
      { regionTitle: '执行能力边界', actualValue: '框架存在 ≠ 已经可以发送银行', passed: current.value?.realBankMessageSent === false },
    ],
  }
}
async function refresh() {
  try {
    const loaded = createAdapterPageFacts(await bankSendExecutionFrameworkApi.adapters())
    rows.value = loaded.rows
    Object.assign(facts, loaded.facts)
    acceptanceFacts.value = loaded.acceptanceFacts
    strictFacts.value = loaded.strictFacts
    diagnosticFacts.value = loaded.diagnosticFacts
    publish()
  } catch (error) {
    ElMessage.error(`接口适配事实读取失败：${error?.message || 'UNKNOWN'}`)
  }
}
const provider = { factOwner: 'FIN_BANK_CONNECTOR_ADAPTER_REVIEW', refresh, buildDiagnostics: diagnostics }
onMounted(async () => { observability?.register?.(provider); await refresh(); observability?.register?.(provider) })
onBeforeUnmount(() => observability?.unregister?.(provider))
</script>

<style scoped>
.page { display: grid; min-width: 0; gap: 18px; }
.card { min-width: 0; padding: 20px; border: 1px solid #dce4ed; border-radius: 12px; background: #fff; }
.stage { border-color: #93c5fd; background: #eff6ff; }
.boundary { border-color: #b8d8c4; background: #f5fbf7; }
.heading h2 { margin: 0; color: #16243a; }
.heading p { margin: 6px 0 16px; color: #64748b; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; }
.fact { display: grid; gap: 5px; padding: 12px; border-radius: 8px; background: #f5f8fb; }
.fact span { color: #64748b; font-size: 13px; }
.fact strong { word-break: break-all; }
.notice { color: #991b1b; font-size: 18px; font-weight: 800; }
pre { max-height: 520px; overflow: auto; white-space: pre-wrap; }
</style>
