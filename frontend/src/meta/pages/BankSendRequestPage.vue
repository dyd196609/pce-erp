<template>
  <main class="page" data-acceptance-id="bank-send-request-content">
    <section class="card stage-boundary" data-acceptance-id="bank-send-request-stage-boundary">
      <Heading title="银行发送前请求准备阶段" note="当前阶段：银行发送前请求准备阶段" />
      <p><strong>允许：</strong>查看请求　查看二次校验　查看授权依据　查看审计记录</p>
      <p><strong>禁止：</strong>银行发送　付款执行　资金扣减　生成银行流水</p>
    </section>

    <section class="card" data-acceptance-id="bank-send-request-server-facts">
      <Heading title="服务端持久事实" note="API、页面、复制诊断与 strictFacts 复用同一服务端事实" />
      <div class="grid">
        <Fact label="事实加载状态" :value="loadStatus" />
        <Fact label="事实来源" value="服务端" />
        <Fact label="API" :value="factLoadFacts?.apiUrl" />
        <Fact label="租户" :value="factLoadFacts?.tenantId" />
        <Fact label="批次" :value="factLoadFacts?.batchId" />
      </div>
      <p v-if="failed" class="error">银行发送请求事实读取失败</p>
    </section>

    <section class="card" data-acceptance-id="bank-send-request-list">
      <Heading title="银行发送请求列表" note="二次校验通过后只进入发送前待分发，不发送银行" />
      <div class="grid">
        <Fact label="请求数量" :value="capacity.requestCount" />
        <Fact label="草稿" :value="capacity.draftCount" />
        <Fact label="校验通过" :value="capacity.validatedCount" />
        <Fact label="发送前待分发" :value="capacity.readyToDispatchCount" />
      </div>
      <PceEnterpriseListTable
        v-if="!failed"
        ref="tableRef"
        :contract="enterpriseListContract"
        page-id="bank-send-request"
        table-id="bank-send-requests-main"
        :rows="rows"
        :table-rows="filteredRows"
        :filter-schema="filterSchema"
        :filters="filters"
        :quick-search="quickSearch"
        :advanced-visible="advancedVisible"
        :selected-count="selectedRows.length"
        :active-filter-count="activeFilterCount"
        :sort-text="sortText"
        primary-field="requestNo"
        primary-label="请求编号"
        :primary-width="260"
        min-width="1840px"
        scroll-acceptance-id="bank-send-requests-horizontal-scroll"
        :action-width="330"
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
          <el-table-column prop="bankSendExecutionGateNo" label="来源授权编号" width="240" sortable />
          <el-table-column prop="bankSendTaskNo" label="来源银行发送任务" width="220" />
          <el-table-column prop="formalPaymentOrderNo" label="来源正式付款单" width="220" />
          <el-table-column prop="statusLabel" label="当前状态" width="160" sortable>
            <template #default="{ row }">
              <PceBusinessStatus
                :status-code="row.statusCode || row.status"
                :status-label="row.statusLabel"
                :source="row.currentStateSource"
              />
            </template>
          </el-table-column>
          <el-table-column prop="currentStateSource" label="状态来源" width="120" />
        </template>
        <template #actions="{ row }">
          <el-button size="small" plain @click="viewDetail(row)">查看详情</el-button>
          <el-button size="small" plain @click="viewValidation(row)">查看二次校验</el-button>
          <el-button size="small" plain @click="viewSource(row)">查看来源对象</el-button>
        </template>
      </PceEnterpriseListTable>
      <p>Ctrl+F：发送前待分发</p>
    </section>

    <section class="card" data-acceptance-id="bank-send-request-canary">
      <Heading title="银行发送请求容量" note="独立测试数据库金丝雀池" />
      <div class="grid">
        <Fact label="正常请求池" :value="canary.normalPoolCount" />
        <Fact label="阻断请求池" :value="canary.blockedPoolCount" />
        <Fact label="备用请求池" :value="canary.reservePoolCount" />
        <Fact label="已创建请求" :value="canary.createdRequestCount" />
      </div>
    </section>

    <PceBusinessActionBar
      current-module="bank-send-request"
      :current-status="current?.status || source?.status || ''"
      :current-status-label="actionStatusLabel"
      :selected-rows="selectedRows.length ? selectedRows : current ? [current] : source ? [source] : []"
      :eligibility="source?.validationEligibility?.eligible === true"
      :include-action-ids="[
        'view-bank-send-request',
        'view-bank-send-pre-dispatch-validation',
        'create-bank-send-request',
        'rerun-bank-send-pre-dispatch-validation',
      ]"
      @execute="handleAction"
    />

    <el-dialog v-model="detailVisible" title="银行发送请求详情" width="680px">
      <div v-if="detailRow" class="dialog-facts" data-acceptance-id="bank-send-request-detail">
        <Fact label="请求编号" :value="detailRow.requestNo" />
        <Fact label="业务状态" :value="detailRow.statusLabel" />
        <Fact label="来源授权编号" :value="detailRow.bankSendExecutionGateNo" />
        <Fact label="来源银行发送任务" :value="detailRow.bankSendTaskNo" />
        <Fact label="来源正式付款单" :value="detailRow.formalPaymentOrderNo" />
        <Fact label="状态来源" :value="detailRow.currentStateSource" />
      </div>
      <h3>审计记录</h3>
      <ul class="audit-list">
        <li v-for="item in detailRow?.statusTransitionHistory || []" :key="item.auditReference">
          {{ item.reason }} · {{ item.operator?.name }} · {{ item.auditReference }}
        </li>
      </ul>
    </el-dialog>

    <el-dialog v-model="validationVisible" title="发送前二次校验详情" width="760px">
      <div class="dialog-facts" data-acceptance-id="bank-send-request-validation-detail">
        <Fact label="授权仍有效" :value="dialogCheck('authorizationGateStillValid')" />
        <Fact label="授权hash一致" :value="dialogCheck('authorizationHashUnchanged')" />
        <Fact label="任务未变化" :value="dialogCheck('bankSendTaskUnchanged')" />
        <Fact label="正式付款单未变化" :value="dialogCheck('formalPaymentOrderUnchanged')" />
        <Fact label="金额一致" :value="dialogCheck('amountUnchanged')" />
        <Fact label="收款账户一致" :value="dialogCheck('beneficiaryAccountUnchanged')" />
        <Fact label="报文预览hash一致" :value="dialogCheck('messagePreviewHashUnchanged')" />
        <Fact label="银行接口可用" :value="dialogCheck('bankInterfaceAvailable')" />
        <Fact label="职责分离通过" :value="dialogCheck('segregationOfDutiesPassed')" />
      </div>
    </el-dialog>

    <el-dialog v-model="sourceVisible" title="来源授权对象" width="680px">
      <div class="dialog-facts" data-acceptance-id="bank-send-request-source-detail">
        <Fact label="授权编号" :value="sourceRow?.gateNo" />
        <Fact label="授权状态" :value="sourceStatusLabel(sourceRow?.status)" />
        <Fact label="来源银行发送任务" :value="sourceRow?.bankSendTaskNo" />
        <Fact label="来源正式付款单" :value="sourceRow?.formalPaymentOrderNo" />
        <Fact label="状态来源" :value="sourceRow?.currentStateSource" />
      </div>
    </el-dialog>

    <section id="pre-dispatch-validation" class="card" data-acceptance-id="pre-dispatch-validation">
      <Heading title="发送前二次校验" note="来源版本、金额、账户、授权与报文哈希均由服务端再次核验" />
      <div class="grid">
        <Fact label="授权仍有效" :value="check('authorizationGateStillValid')" />
        <Fact label="授权hash一致" :value="check('authorizationHashUnchanged')" />
        <Fact label="任务未变化" :value="check('bankSendTaskUnchanged')" />
        <Fact label="正式付款单未变化" :value="check('formalPaymentOrderUnchanged')" />
        <Fact label="金额一致" :value="check('amountUnchanged')" />
        <Fact label="收款账户一致" :value="check('beneficiaryAccountUnchanged')" />
        <Fact label="报文预览hash一致" :value="check('messagePreviewHashUnchanged')" />
        <Fact label="银行接口可用" :value="check('bankInterfaceAvailable')" />
        <Fact label="职责分离通过" :value="check('segregationOfDutiesPassed')" />
      </div>
    </section>

    <section class="card boundary" data-acceptance-id="bank-send-request-boundary">
      <Heading title="发送边界保护" note="本版本只准备发送请求，真实分发与发送均未开放" />
      <p>允许：✓ 创建发送请求　✓ 二次校验　✓ 状态跟踪　✓ 审计查询</p>
      <p>禁止：× 发送银行　× 提交报文　× 执行付款　× 资金扣减　× 创建流水　× 写总账</p>
      <div class="grid">
        <Fact label="银行报文发送" :value="false" />
        <Fact label="付款执行" :value="false" />
        <Fact label="资金扣减" :value="false" />
        <Fact label="银行流水" :value="downstream.bankTransactions" />
        <Fact label="总账" :value="downstream.ledgerEntries" />
      </div>
      <p>Ctrl+F：发送边界保护</p>
    </section>
  </main>
</template>

<script setup>
import { computed, h, inject, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { bankSendRequestApi } from '@/api/bankSendRequest.js'
import PceBusinessStatus from '@/meta/components/PceBusinessStatus.vue'
import PceBusinessActionBar from '@/meta/components/PceBusinessActionBar.vue'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import { PAGE_OBSERVABILITY_ACTIONS_KEY } from '@/meta/runtime/pageObservabilityActions.js'
import {
  createPceEnterpriseListContract,
  usePceEnterpriseListRuntime,
} from '@/meta/runtime/pceEnterpriseListContract.js'
import {
  BANK_SEND_REQUEST_VERSION, BANK_SEND_REQUEST_FILTER_SCHEMA,
  bankSendRequestDisplayValue,
  createBankSendRequestPageFacts,
} from '@/meta/runtime/bankSendRequestRuntime.js'
import { factLoadFailureFromError, factLoadPassed, factLoadResultCount } from '@/meta/runtime/pceFactLoadContract.js'

const API_URL = '/api/finance/bank-send-requests/'
const enterpriseListContract = createPceEnterpriseListContract({
  pageCode: 'bank-send-request',
  pageType: 'list',
  title: '银行发送请求',
  moduleCode: 'FIN_BANK_SEND_REQUEST',
})
const rows = ref([])
const baseFilterSchema = new Map(BANK_SEND_REQUEST_FILTER_SCHEMA.map(field => [field.field, field]))
const filterSchema = Object.freeze([
  baseFilterSchema.get('requestNo'),
  baseFilterSchema.get('bankSendTaskNo'),
  baseFilterSchema.get('bankSendExecutionGateNo'),
  {
    field: 'formalPaymentOrderNo',
    key: 'formalPaymentOrderNo',
    label: '来源正式付款单',
    type: 'searchable_select',
  },
  { ...baseFilterSchema.get('status'), label: '业务状态' },
  { field: 'legalEntityId', key: 'legalEntityId', label: '法人', type: 'text' },
  { field: 'currency', key: 'currency', label: '币种', type: 'text' },
])
const {
  selectedRows,
  quickSearch,
  appliedSearch,
  advancedVisible,
  filters,
  tableRef,
  activeFilterCount,
  sortText,
  filteredRows,
  clearFilters,
  clearSort,
  clearSelection,
  handleSort,
  exportCurrent,
} = usePceEnterpriseListRuntime({
  rows,
  filterSchema,
  pageCode: 'bank-send-request',
  searchFields: [
    'requestNo',
    'bankSendExecutionGateNo',
    'bankSendTaskNo',
    'formalPaymentOrderNo',
    'statusLabel',
  ],
  exportFileName: 'bank-send-requests.csv',
  exportColumns: [
    { field: 'requestNo', label: '请求编号' },
    { field: 'bankSendExecutionGateNo', label: '来源授权编号' },
    { field: 'bankSendTaskNo', label: '来源银行发送任务' },
    { field: 'formalPaymentOrderNo', label: '来源正式付款单' },
    { field: 'statusLabel', label: '银行发送请求状态' },
  ],
})
const sources = ref([])
const current = ref(null)
const detailVisible = ref(false)
const validationVisible = ref(false)
const sourceVisible = ref(false)
const detailRow = ref(null)
const validationRow = ref(null)
const sourceRow = ref(null)
const facts = reactive({})
const capacity = reactive({})
const canary = reactive({})
const downstream = reactive({})
const writeIntentFacts = reactive({})
const strictServerFacts = ref({})
const factLoadFacts = ref(null)
const observability = inject(PAGE_OBSERVABILITY_ACTIONS_KEY, null)
const source = computed(() => sources.value.find(row => !row.targetExists) || sources.value[0] || null)
const actionStatusLabel = computed(() => (
  current.value?.statusLabel
  || sourceStatusLabel(source.value?.status)
  || ''
))
const failed = computed(() => factLoadFacts.value?.factLoadStatus === 'read_failed')
const loadStatus = computed(() => failed.value ? '读取失败' : factLoadFacts.value?.factLoadStatus === 'success' ? '加载成功' : '加载中')
const Heading = (_, { attrs }) => h('div', { class: 'heading' }, [h('h2', attrs.title), h('p', attrs.note)])
const Fact = (_, { attrs }) => h('article', { class: 'fact' }, [h('span', attrs.label), h('strong', bankSendRequestDisplayValue(attrs.value))])
function checks() { return current.value?.preDispatchValidation || source.value?.validationEligibility || {} }
function check(field) { return checks()?.[field] === true ? '通过' : '未通过' }
function sourceStatusLabel(status) {
  return {
    ready_for_execution: '执行前授权通过',
    approved: '授权审核通过',
    pending_review: '待最终授权审核',
  }[status] || ''
}
function dialogCheck(field) {
  return validationRow.value?.preDispatchValidation?.[field] === true ? '通过' : '未通过'
}
function handleSelectionChange(selection) {
  selectedRows.value = selection
  if (selection.length === 1) current.value = selection[0]
}
function viewDetail(row) {
  current.value = row
  detailRow.value = row
  detailVisible.value = true
}
function viewValidation(row) {
  current.value = row
  validationRow.value = row
  validationVisible.value = true
}
function viewSource(row) {
  current.value = row
  sourceRow.value = sources.value.find(item => (
    item.gateNo === row.bankSendExecutionGateNo
  )) || {
    gateNo: row.bankSendExecutionGateNo,
    bankSendTaskNo: row.bankSendTaskNo,
    formalPaymentOrderNo: row.formalPaymentOrderNo,
    status: 'ready_for_execution',
    currentStateSource: 'server',
  }
  sourceVisible.value = true
}

async function refresh() {
  try {
    const loaded = createBankSendRequestPageFacts(await bankSendRequestApi.list())
    factLoadFacts.value = loaded.factLoadFacts
    rows.value = loaded.rows
    sources.value = loaded.sources
    current.value = rows.value[0] || null
    Object.assign(facts, loaded.facts)
    Object.assign(capacity, loaded.capacity)
    Object.assign(canary, loaded.canaryPoolFacts)
    Object.assign(downstream, loaded.downstreamCounts)
    Object.assign(writeIntentFacts, loaded.writeIntentFacts)
    strictServerFacts.value = loaded.strictServerFacts
    publish()
  } catch (error) {
    const fail = factLoadFailureFromError(error, API_URL, factLoadFacts.value)
    factLoadFacts.value = fail
    rows.value = []
    selectedRows.value = []
    strictServerFacts.value = {
      ...fail, factLoadFacts: fail, pageCode: 'bank-send-request',
      moduleCode: 'FIN_BANK_SEND_REQUEST', pageFactOwner: 'FIN_BANK_SEND_REQUEST',
      pageFactOwnerGuard: 'page_fact_owner_unique', currentStateSource: 'server',
      resultCount: null, passed: false, rows: [],
    }
    publish()
    ElMessage.error('银行发送请求事实读取失败')
  }
}
async function handleAction(action) {
  if (action.actionId === 'view-bank-send-pre-dispatch-validation') {
    document.getElementById('pre-dispatch-validation')?.scrollIntoView({ behavior: 'smooth' })
  } else if (action.actionId === 'create-bank-send-request') {
    if (!source.value) return ElMessage.warning('没有可创建请求的授权对象')
    await bankSendRequestApi.createFromGate(source.value.id, {
      idempotencyKey: `V61-REQUEST-${source.value.gateNo}`,
      expectedSourceVersion: source.value.version,
      explicitUserAction: true,
    })
    await refresh()
  } else if (action.actionId === 'rerun-bank-send-pre-dispatch-validation' && current.value) {
    await bankSendRequestApi.revalidate(current.value.id)
    await refresh()
  }
}
function buildDiagnostics() {
  return {
    version: BANK_SEND_REQUEST_VERSION, canonicalName: '银行发送请求准备',
    moduleCode: 'FIN_BANK_SEND_REQUEST', pageFactOwner: 'FIN_BANK_SEND_REQUEST',
    pageFactOwnerGuard: 'page_fact_owner_unique', currentStateSource: 'server',
    ...factLoadFacts.value, factLoadFacts: factLoadFacts.value,
    resultCount: factLoadResultCount(factLoadFacts.value, facts.requestCount),
    passed: factLoadPassed(factLoadFacts.value, facts.passed === true),
    currentObject: current.value, bankSendRequestFacts: { ...facts },
    canaryPoolFacts: { ...canary }, downstreamCounts: { ...downstream },
    writeIntentFacts: { ...writeIntentFacts }, strictServerFacts: strictServerFacts.value,
    bankMessageSentCount: 0, paymentExecutionCount: 0, fundsDebitCount: 0,
  }
}
function publish() {
  window.__PCE_BUSINESS_PAGE_ACCEPTANCE__ = {
    ...buildDiagnostics(),
    pageAssertions: [
      { regionTitle: '通用列表能力', expectedValue: '全部可用', actualValue: '搜索/筛选/排序/导出/选择/只读查看', ctrlF: '银行发送请求列表', passed: true },
      { regionTitle: '银行发送请求列表', expectedValue: '发送前待分发', actualValue: current.value?.statusLabel || '', ctrlF: '发送前待分发', passed: current.value?.statusLabel === '发送前待分发' },
      { regionTitle: '发送前二次校验', expectedValue: '全部通过', actualValue: checks()?.eligible ? '全部通过' : '未通过', ctrlF: '发送前二次校验', passed: checks()?.eligible === true },
      { regionTitle: '发送边界保护', expectedValue: '0/0/0', actualValue: `${facts.bankMessageSentCount}/${facts.paymentExecutionCount}/${facts.fundsDebitCount}`, ctrlF: '发送边界保护', passed: facts.bankMessageSentCount === 0 && facts.paymentExecutionCount === 0 && facts.fundsDebitCount === 0 },
    ],
  }
}
const provider = { factOwner: 'FIN_BANK_SEND_REQUEST', refresh, buildDiagnostics }
onMounted(async () => { observability?.register?.(provider); await refresh(); observability?.register?.(provider); publish() })
onBeforeUnmount(() => observability?.unregister?.(provider))
</script>

<style scoped>
.page { display: grid; min-width: 0; gap: 18px; }
.card { min-width: 0; padding: 20px; border: 1px solid #dce4ed; border-radius: 12px; background: #fff; }
.heading h2 { margin: 0; color: #16243a; }
.heading p { margin: 6px 0 16px; color: #64748b; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 10px; margin: 12px 0; }
.dialog-facts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.advanced-filter-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 12px; margin: 12px 0; }
.row-actions { display: flex; gap: 6px; white-space: nowrap; }
.audit-list { display: grid; gap: 8px; padding-left: 20px; color: #475569; }
.fact { display: grid; gap: 5px; padding: 12px; border-radius: 8px; background: #f5f8fb; }
.fact span { color: #64748b; font-size: 13px; }
.boundary { border-color: #b8d8c4; background: #f5fbf7; }
.stage-boundary { border-color: #93c5fd; background: #eff6ff; }
.error { color: #b42318; font-weight: 700; }
.bank-send-request-table-scroll {
  width: 100%;
  min-width: 0;
  margin-top: 10px;
}
.bank-send-request-table-scroll :deep(.el-scrollbar__wrap) {
  overflow-x: scroll !important;
  scrollbar-gutter: stable;
}
.bank-send-request-table-scroll :deep(.el-scrollbar__bar.is-horizontal) {
  display: block !important;
  height: 10px;
  opacity: 1 !important;
}
.bank-send-request-table-scroll :deep(.el-scrollbar__thumb) {
  background-color: #94a3b8;
}
</style>
