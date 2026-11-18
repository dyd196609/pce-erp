<template>
  <main class="bank-send-execution-gate-page" data-acceptance-id="bank-send-execution-gate-content">
    <section class="business-card" data-acceptance-id="execution-gate-server-facts">
      <Heading title="服务端持久事实" note="API、页面、复制诊断与 strictFacts 共用服务端事实" />
      <div class="fact-grid">
        <Fact label="事实加载状态" :value="factLoadStatusLabel" />
        <Fact label="事实来源" value="服务端" />
        <Fact label="API" :value="factLoadFacts?.apiUrl" />
        <Fact label="租户" :value="factLoadFacts?.tenantId" />
        <Fact label="批次" :value="factLoadFacts?.batchId" />
      </div>
      <p v-if="factLoadFailed" class="fact-load-error">银行发送执行授权事实读取失败</p>
    </section>

    <section class="business-card" data-acceptance-id="execution-gate-list">
      <Heading title="银行发送执行授权列表" note="中文业务状态优先展示；技术状态保留在服务端诊断" />
      <div class="fact-grid">
        <Fact label="授权数量" :value="capacity.gateCount" />
        <Fact label="待最终授权审核" :value="capacity.pendingReviewCount" />
        <Fact label="授权审核通过" :value="capacity.approvedCount" />
        <Fact label="执行前就绪" :value="capacity.readyForExecutionCount" />
      </div>
      <StandardListToolbar
        v-if="!factLoadFailed"
        page-id="bank-send-execution-gate"
        table-id="bank-send-execution-gates-main"
        :quick-search="quickSearch"
        :advanced-visible="advancedVisible"
        :result-count="filteredRows.length"
        :selected-count="selectedRows.length"
        :active-filter-count="activeFilterCount"
        :sort-text="sortText"
        @update:quick-search="quickSearch = $event"
        @search="appliedSearch = quickSearch"
        @toggle-advanced="advancedVisible = !advancedVisible"
        @clear-filters="clearFilters"
        @clear-sort="clearSort"
        @export-current="exportCurrent"
        @clear-selection="clearSelection"
      />
      <div v-if="advancedVisible" class="advanced-filter-grid">
        <PceAdvancedFilterField
          v-for="field in filterSchema"
          :key="field.field"
          v-model="filters[field.field]"
          :field="field"
          :rows="rows"
        />
      </div>
      <BusinessTableScrollContainer
        v-if="!factLoadFailed"
        acceptance-id="bank-send-execution-gates-horizontal-scroll"
        page-id="bank-send-execution-gate"
        table-id="bank-send-execution-gates-main"
        min-width="1100px"
      >
        <el-table
          ref="tableRef"
          :data="filteredRows"
          row-key="id"
          data-acceptance-id="bank-send-execution-gates-main"
          @selection-change="selectedRows = $event"
          @sort-change="handleSort"
        >
          <el-table-column type="selection" fixed="left" width="54" />
          <el-table-column type="index" fixed="left" label="序号" width="64" />
          <el-table-column prop="gateNo" label="授权编号" width="240" sortable />
          <el-table-column prop="bankSendTaskNo" label="来源银行发送任务" width="220" />
          <el-table-column prop="formalPaymentOrderNo" label="来源正式付款单" width="220" />
          <el-table-column prop="statusLabel" label="当前状态" width="170" />
          <el-table-column prop="currentStateSource" label="状态来源" width="120" />
          <el-table-column fixed="right" label="操作" width="110">
            <template #default="{ row }">
              <el-button size="small" plain @click="currentGate = row">查看</el-button>
            </template>
          </el-table-column>
        </el-table>
      </BusinessTableScrollContainer>
      <p>Ctrl+F：执行前就绪</p>
    </section>

    <section class="business-card" data-acceptance-id="execution-gate-canary">
      <Heading title="银行发送执行授权容量" note="独立测试数据库金丝雀池" />
      <div class="fact-grid">
        <Fact label="正常授权池" :value="canary.normalPoolCount" />
        <Fact label="阻断授权池" :value="canary.blockedPoolCount" />
        <Fact label="备用授权池" :value="canary.reservePoolCount" />
        <Fact label="已创建授权" :value="canary.createdGateCount" />
      </div>
    </section>

    <PceBusinessActionBar
      current-module="bank-send-execution-gate"
      :current-status="currentGate?.status || currentSource?.status || ''"
      :selected-rows="currentGate ? [currentGate] : currentSource ? [currentSource] : []"
      :eligibility="currentSource?.authorizationEligibility?.eligible === true"
      :include-action-ids="[
        'view-bank-send-execution-gate',
        'view-bank-send-execution-gate-conditions',
        'submit-bank-send-final-authorization-review',
      ]"
      @execute="handleAction"
    />

    <section id="execution-gate-checks" class="business-card" data-acceptance-id="execution-gate-checks">
      <Heading title="最终授权检查" note="创建授权时由服务端重新验证全部条件" />
      <div class="fact-grid">
        <Fact label="正式付款单冻结" :value="check('formalPaymentOrderFreezeConsistent', '是')" />
        <Fact label="审批" :value="check('approvalApproved', '通过')" />
        <Fact label="风险评审" :value="check('riskReviewPassed', '通过')" />
        <Fact label="资金" :value="check('fundsAvailable', '可用')" />
        <Fact label="职责分离" :value="check('segregationOfDutiesPassed', '通过')" />
        <Fact label="接口" :value="check('bankInterfaceAvailable', '可用')" />
        <Fact label="报文hash" :value="check('messagePreviewHashConsistent', '一致')" />
      </div>
    </section>

    <section class="business-card zero-boundary" data-acceptance-id="execution-gate-boundary">
      <Heading title="执行边界保护" note="本版本只建设最终授权门禁，不进入银行发送执行" />
      <p>允许：✓ 最终授权审核　✓ 查看授权记录</p>
      <p>禁止：× 发送银行　× 执行付款　× 扣减资金　× 创建流水　× 写总账</p>
      <div class="fact-grid">
        <Fact label="银行发送" :value="false" />
        <Fact label="付款执行" :value="false" />
        <Fact label="资金扣减" :value="false" />
        <Fact label="银行流水" :value="downstream.bankTransactions" />
        <Fact label="总账" :value="downstream.ledgerEntries" />
      </div>
      <p>Ctrl+F：执行边界保护</p>
    </section>
  </main>
</template>

<script setup>
import { computed, h, inject, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { bankSendExecutionGateApi } from '@/api/bankSendExecutionGate.js'
import BusinessTableScrollContainer from '@/meta/components/BusinessTableScrollContainer.vue'
import PceAdvancedFilterField from '@/meta/components/PceAdvancedFilterField.vue'
import PceBusinessActionBar from '@/meta/components/PceBusinessActionBar.vue'
import StandardListToolbar from '@/meta/components/StandardListToolbar.vue'
import { PAGE_OBSERVABILITY_ACTIONS_KEY } from '@/meta/runtime/pageObservabilityActions.js'
import {
  BANK_SEND_EXECUTION_GATE_VERSION,
  BANK_SEND_EXECUTION_GATE_FILTER_SCHEMA,
  createBankSendExecutionGatePageFacts,
  executionGateDisplayValue,
} from '@/meta/runtime/bankSendExecutionGateRuntime.js'
import { factLoadFailureFromError, factLoadPassed, factLoadResultCount } from '@/meta/runtime/pceFactLoadContract.js'

const API_URL = '/api/finance/bank-send-execution-gates/'
const rows = ref([])
const selectedRows = ref([])
const quickSearch = ref('')
const appliedSearch = ref('')
const advancedVisible = ref(false)
const tableRef = ref(null)
const sortState = reactive({ prop: '', order: '' })
const filterSchema = BANK_SEND_EXECUTION_GATE_FILTER_SCHEMA
const filters = reactive(Object.fromEntries(filterSchema.map(field => [field.field, ''])))
const sources = ref([])
const currentGate = ref(null)
const facts = reactive({})
const capacity = reactive({})
const canary = reactive({})
const downstream = reactive({})
const writeIntentFacts = reactive({})
const strictServerFacts = ref({})
const factLoadFacts = ref(null)
const observability = inject(PAGE_OBSERVABILITY_ACTIONS_KEY, null)
const currentSource = computed(() => sources.value.find(row => !row.targetExists) || sources.value[0] || null)
const factLoadFailed = computed(() => factLoadFacts.value?.factLoadStatus === 'read_failed')
const factLoadStatusLabel = computed(() => factLoadFailed.value ? '读取失败' : factLoadFacts.value?.factLoadStatus === 'success' ? '加载成功' : '加载中')
const activeFilterCount = computed(() => Object.values(filters).filter(value => value !== '').length)
const sortText = computed(() => sortState.prop ? `${sortState.prop} ${sortState.order === 'descending' ? '降序' : '升序'}` : '默认业务顺序')
const filteredRows = computed(() => {
  const keyword = appliedSearch.value.trim().toLowerCase()
  let result = rows.value.filter(row => {
    if (keyword && ![
      row.gateNo, row.bankSendTaskNo, row.formalPaymentOrderNo, row.statusLabel,
    ].some(value => String(value || '').toLowerCase().includes(keyword))) return false
    return filterSchema.every(field => {
      const expected = filters[field.field]
      return expected === '' || String(row[field.field] ?? '') === String(expected)
    })
  })
  if (sortState.prop && sortState.order) {
    const direction = sortState.order === 'descending' ? -1 : 1
    result = [...result].sort((left, right) => (
      String(left[sortState.prop] ?? '').localeCompare(
        String(right[sortState.prop] ?? ''),
        'zh-CN',
        { numeric: true },
      ) * direction
    ))
  }
  return result
})
const Heading = (_, { attrs }) => h('div', { class: 'section-heading' }, [h('div', {}, [h('h2', {}, attrs.title), h('p', {}, attrs.note)])])
const Fact = (_, { attrs }) => h('article', { class: 'fact-item' }, [h('span', {}, attrs.label), h('strong', {}, executionGateDisplayValue(attrs.value))])

function check(field, passedLabel) {
  const checks = currentGate.value?.authorizationChecks || currentSource.value?.authorizationEligibility
  return checks?.[field] === true ? passedLabel : '未通过'
}

function clearFilters() {
  quickSearch.value = ''
  appliedSearch.value = ''
  for (const field of filterSchema) filters[field.field] = ''
}

function clearSort() {
  Object.assign(sortState, { prop: '', order: '' })
  tableRef.value?.clearSort()
}

function clearSelection() {
  selectedRows.value = []
  tableRef.value?.clearSelection()
}

function handleSort({ prop, order }) {
  sortState.prop = prop || ''
  sortState.order = order || ''
}

function exportCurrent() {
  const csv = [
    ['授权编号', '来源银行发送任务', '来源正式付款单', '业务状态'],
    ...filteredRows.value.map(row => [
      row.gateNo, row.bankSendTaskNo, row.formalPaymentOrderNo, row.statusLabel,
    ]),
  ].map(line => line.map(value => `"${String(value ?? '').replace(/"/g, '""')}"`).join(',')).join('\n')
  const url = URL.createObjectURL(new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8' }))
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = 'bank-send-execution-gates.csv'
  anchor.click()
  URL.revokeObjectURL(url)
}

async function refresh() {
  try {
    const loaded = createBankSendExecutionGatePageFacts(await bankSendExecutionGateApi.list())
    factLoadFacts.value = loaded.factLoadFacts
    rows.value = loaded.rows
    sources.value = loaded.sources
    currentGate.value = rows.value[0] || null
    Object.assign(facts, loaded.facts)
    Object.assign(capacity, loaded.capacity)
    Object.assign(canary, loaded.canaryPoolFacts)
    Object.assign(downstream, loaded.downstreamCounts)
    Object.assign(writeIntentFacts, loaded.writeIntentFacts)
    strictServerFacts.value = loaded.strictServerFacts
    publishAcceptance()
  } catch (error) {
    const failed = factLoadFailureFromError(error, API_URL, factLoadFacts.value)
    factLoadFacts.value = failed
    rows.value = []
    strictServerFacts.value = {
      ...failed,
      factLoadFacts: failed,
      pageCode: 'bank-send-execution-gate',
      moduleCode: 'FIN_BANK_SEND_EXECUTION_GATE',
      pageFactOwner: 'FIN_BANK_SEND_EXECUTION_GATE',
      pageFactOwnerGuard: 'page_fact_owner_unique',
      currentStateSource: 'server',
      resultCount: null,
      passed: false,
      rows: [],
    }
    publishAcceptance()
    ElMessage.error('银行发送执行授权事实读取失败')
  }
}

async function handleAction(action) {
  if (action.actionId === 'view-bank-send-execution-gate-conditions') {
    document.getElementById('execution-gate-checks')?.scrollIntoView({ behavior: 'smooth' })
    return
  }
  if (action.actionId !== 'submit-bank-send-final-authorization-review') return
  const source = currentSource.value
  if (!source) return ElMessage.warning('没有可授权的银行发送任务')
  const response = await bankSendExecutionGateApi.createFromTask(source.id, {
    idempotencyKey: `V60-GATE-${source.taskNo}`,
    expectedSourceVersion: source.version,
    explicitUserAction: true,
  })
  const result = response?.data?.result ? response.data : response
  if (result?.result !== 'passed') return ElMessage.error(result?.error?.message || '最终授权失败')
  ElMessage.success('最终授权审核完成；未发送银行')
  await refresh()
}

function buildDiagnostics() {
  return {
    version: BANK_SEND_EXECUTION_GATE_VERSION,
    canonicalName: '银行发送执行授权',
    moduleCode: 'FIN_BANK_SEND_EXECUTION_GATE',
    pageFactOwner: 'FIN_BANK_SEND_EXECUTION_GATE',
    pageFactOwnerGuard: 'page_fact_owner_unique',
    currentStateSource: 'server',
    ...factLoadFacts.value,
    factLoadFacts: factLoadFacts.value,
    resultCount: factLoadResultCount(factLoadFacts.value, facts.gateCount),
    passed: factLoadPassed(factLoadFacts.value, facts.passed === true),
    currentObject: currentGate.value,
    bankSendExecutionGateFacts: { ...facts },
    canaryPoolFacts: { ...canary },
    downstreamCounts: { ...downstream },
    writeIntentFacts: { ...writeIntentFacts },
    strictServerFacts: strictServerFacts.value,
    bankSendExecutionCount: 0,
    bankMessageSentCount: 0,
    paymentExecutionCount: 0,
  }
}

function publishAcceptance() {
  window.__PCE_BUSINESS_PAGE_ACCEPTANCE__ = {
    ...buildDiagnostics(),
    pageAssertions: [
      { regionTitle: '银行发送执行授权列表', expectedValue: '执行前就绪', actualValue: currentGate.value?.statusLabel || '', ctrlF: '执行前就绪', passed: currentGate.value?.statusLabel === '执行前就绪' },
      { regionTitle: '最终授权检查', expectedValue: '全部通过', actualValue: currentGate.value?.authorizationChecks?.eligible === true ? '全部通过' : '未通过', ctrlF: '最终授权检查', passed: currentGate.value?.authorizationChecks?.eligible === true },
      { regionTitle: '执行边界保护', expectedValue: '0/0/0', actualValue: `${facts.bankSendExecutionCount}/${facts.paymentExecutionCount}/${downstream.bankTransactions}`, ctrlF: '执行边界保护', passed: facts.bankSendExecutionCount === 0 && facts.paymentExecutionCount === 0 && downstream.bankTransactions === 0 },
    ],
  }
}

const provider = { factOwner: 'FIN_BANK_SEND_EXECUTION_GATE', refresh, buildDiagnostics }
onMounted(async () => {
  observability?.register?.(provider)
  await refresh()
  observability?.register?.(provider)
  publishAcceptance()
})
onBeforeUnmount(() => observability?.unregister?.(provider))
</script>

<style scoped>
.bank-send-execution-gate-page { display: grid; gap: 18px; }
.business-card { padding: 20px; border: 1px solid #dce4ed; border-radius: 12px; background: #fff; }
.section-heading h2 { margin: 0; color: #16243a; }
.section-heading p { margin: 6px 0 16px; color: #64748b; }
.fact-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 10px; margin: 12px 0; }
.fact-item { display: grid; gap: 5px; padding: 12px; border-radius: 8px; background: #f5f8fb; }
.fact-item span { color: #64748b; font-size: 13px; }
.gate-table { width: 100%; border-collapse: collapse; }
.gate-table th, .gate-table td { padding: 12px; border-bottom: 1px solid #e5eaf0; text-align: left; }
.zero-boundary { border-color: #b8d8c4; background: #f5fbf7; }
.fact-load-error { color: #b42318; font-weight: 700; }
</style>
