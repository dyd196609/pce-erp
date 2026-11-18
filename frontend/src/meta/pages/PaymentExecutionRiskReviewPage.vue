<template>
  <main class="risk-page" data-acceptance-id="payment-risk-review-business-content">
    <section class="business-card" data-acceptance-id="payment-risk-review-capacity">
      <Heading title="持久金丝雀容量" :note="`成功=${capacity.passedCount} / 阻断场景=${capacity.blockedScenarioCount}`" />
      <div class="facts">
        <Fact label="风险评审来源数量" :value="capacity.sourceDraftCount" />
        <Fact label="风险评审对象数量" :value="capacity.riskReviewCount" />
        <Fact label="已通过数量" :value="capacity.passedCount" />
        <Fact label="已阻断对象数量" :value="capacity.blockedCount" />
        <Fact label="阻断场景数量" :value="capacity.blockedScenarioCount" />
        <Fact label="下一阶段已消费数量" :value="capacity.nextStageConsumedCount" />
      </div>
      <p class="ctrl-f">Ctrl+F：持久金丝雀容量</p>
    </section>

    <section class="business-card" data-acceptance-id="payment-risk-review-source">
      <Heading title="真实付款风险评审来源" note="唯一来源：服务端正式付款单草稿" />
      <StandardListToolbar
        page-id="payment-risk-review"
        table-id="payment-risk-reviews-source"
        v-model:quick-search="sourceSearch"
        placeholder="搜索来源草稿编号或供应商"
        :advanced-visible="sourceAdvancedVisible"
        :result-count="filteredSources.length"
        :selected-count="0"
        :active-filter-count="sourceActiveFilterCount"
        :sort-text="sourceSortText"
        @search="noop"
        @toggle-advanced="sourceAdvancedVisible = !sourceAdvancedVisible"
        @clear-filters="clearSourceFilters"
        @clear-sort="clearSourceSort"
        @export-current="exportRows('payment-risk-review-sources.csv', filteredSources)"
        @clear-selection="noop"
      />
      <div
        v-show="sourceAdvancedVisible"
        class="filter-grid list-advanced-filter-panel"
        data-acceptance-id="source-list-advanced-filter"
        data-pce-filter-for="payment-risk-reviews-source"
      >
        <label data-filter-key="sourceNo">
          <span>正式付款单草稿编号</span>
          <el-input v-model="sourceFilters.sourceNo" clearable />
        </label>
        <label data-filter-key="supplierName">
          <span>供应商</span>
          <PceResultFilterSelect v-model="sourceFilters.supplierName" :rows="rows" :fields="['supplierName']" />
        </label>
      </div>
      <BusinessTableScrollContainer
        acceptance-id="business-table-scroll-payment-risk-reviews-source"
        page-id="payment-risk-review"
        table-id="payment-risk-reviews-source"
        min-width="1200px"
      >
        <el-table
          ref="sourceTableRef"
          :data="filteredSources"
          border
          stripe
          height="330"
          scrollbar-always-on
          row-key="id"
          @sort-change="updateSourceSort"
        >
          <el-table-column type="index" label="序号" width="70" fixed="left" class-name="pce-fixed-index-column" />
          <el-table-column prop="sourcePaymentOrderDraftNo" label="正式付款单草稿编号" width="230" fixed="left" sortable="custom" class-name="pce-fixed-primary-no-column" />
          <el-table-column prop="supplierName" label="供应商" width="220" />
          <el-table-column prop="currency" label="币种" width="90" />
          <el-table-column prop="paymentAmount" label="付款金额" width="150" />
          <el-table-column prop="plannedExecutionDate" label="计划付款日期" width="160" />
          <el-table-column label="来源状态" width="130"><template #default>已复核</template></el-table-column>
          <el-table-column label="操作" width="110" fixed="right" class-name="payment-fixed-action-column">
            <template #default="{ row }"><el-button size="small" plain @click="selectDetail(row)">查看评审</el-button></template>
          </el-table-column>
        </el-table>
      </BusinessTableScrollContainer>
      <p class="ctrl-f">Ctrl+F：真实付款风险评审来源</p>
    </section>

    <section class="business-card" data-acceptance-id="payment-risk-review-object">
      <Heading title="真实付款风险评审对象" :note="display(current?.status)" />
      <div class="facts">
        <Fact label="风险评审编号" :value="current?.reviewNo" />
        <Fact label="来源正式付款单草稿编号" :value="current?.sourcePaymentOrderDraftNo" />
        <Fact label="评审状态" :value="display(current?.status)" />
        <Fact label="风险等级" :value="display(current?.riskLevel)" />
        <Fact label="风险结果" :value="display(current?.riskResult)" />
        <Fact label="供应商" :value="current?.supplierName" />
        <Fact label="付款金额" :value="current?.paymentAmount" />
        <Fact label="问题数量" :value="current?.issueCount" />
      </div>
      <p class="ctrl-f">Ctrl+F：{{ current?.reviewNo || '风险评审编号' }}</p>
    </section>

    <section class="business-card" data-acceptance-id="payment-risk-review-rules">
      <Heading title="风险规则执行结果" :note="display(current?.ruleExecution?.status)" />
      <div class="facts">
        <Fact label="规则版本" :value="current?.ruleExecution?.ruleVersion" />
        <Fact label="规则数量" :value="current?.ruleExecution?.ruleCount" />
        <Fact label="通过数量" :value="current?.ruleExecution?.passedCount" />
        <Fact label="阻断数量" :value="current?.ruleExecution?.blockedCount" />
        <Fact label="执行失败数量" :value="current?.ruleExecution?.failedCount" />
      </div>
      <p class="ctrl-f">Ctrl+F：风险规则执行结果</p>
    </section>

    <section class="business-card" data-acceptance-id="payment-risk-review-issues">
      <Heading title="风险问题清单" :note="`问题=${current?.riskIssues?.length || 0}`" />
      <BusinessTableScrollContainer acceptance-id="business-table-scroll-payment-risk-review-issues" min-width="1000px">
        <el-table :data="current?.riskIssues || []" border stripe>
          <el-table-column prop="riskCode" label="风险编码" min-width="210" />
          <el-table-column prop="riskLevel" label="风险等级" min-width="120" />
          <el-table-column prop="description" label="说明" min-width="240" />
          <el-table-column prop="expected" label="期望值" min-width="160" />
          <el-table-column prop="actual" label="实际值" min-width="160" />
          <template #empty><span>当前无风险问题</span></template>
        </el-table>
      </BusinessTableScrollContainer>
      <p class="ctrl-f">Ctrl+F：风险问题清单</p>
    </section>

    <section class="business-card" data-acceptance-id="payment-risk-review-eligibility">
      <Heading title="真实付款风险评审资格" :note="display(current?.eligibility?.nextStepReadiness)" />
      <div class="facts">
        <Fact label="评审状态" :value="display(current?.eligibility?.status)" />
        <Fact label="风险结果" :value="display(current?.eligibility?.riskResult)" />
        <Fact label="风险等级" :value="display(current?.eligibility?.riskLevel)" />
        <Fact label="下一步骤放行状态" :value="display(current?.eligibility?.nextStepReadiness)" />
        <Fact label="是否允许进入下一模块" :value="display(current?.eligibility?.eligible)" />
        <Fact label="阻断原因" :value="display(current?.eligibility?.blockingReasons)" />
      </div>
      <p class="boundary-note">当前仅形成导航资格，不创建正式付款单。</p>
      <p class="ctrl-f">Ctrl+F：真实付款风险评审资格</p>
    </section>

    <section class="business-card" data-acceptance-id="payment-risk-review-audit">
      <Heading title="版本、幂等与审计" note="全部来自服务端当前状态" />
      <div class="facts">
        <Fact label="业务对象版本" :value="current?.version" />
        <Fact label="评审版本" :value="current?.reviewVersion" />
        <Fact label="幂等状态" :value="display(current?.idempotencyStatus)" />
        <Fact label="事务状态" :value="display(current?.transactionStatus)" />
        <Fact label="审计状态" :value="display(current?.auditStatus)" />
        <Fact label="当前状态来源" value="服务端" />
      </div>
      <p class="ctrl-f">Ctrl+F：版本、幂等与审计</p>
    </section>

    <section class="business-card" data-acceptance-id="payment-risk-review-list-region">
      <Heading title="真实付款风险评审标准列表" :note="`正式对象数量=${rows.length}`" />
      <StandardListToolbar
        page-id="payment-risk-review"
        table-id="payment-risk-reviews-main"
        v-model:quick-search="quickSearch"
        placeholder="搜索风险编号、来源草稿、供应商或状态"
        :advanced-visible="advancedVisible"
        :result-count="filteredRows.length"
        :selected-count="selectedRows.length"
        :active-filter-count="activeFilterCount"
        :sort-text="mainSortText"
        @search="noop"
        @toggle-advanced="advancedVisible = !advancedVisible"
        @clear-filters="clearFilters"
        @clear-sort="clearSort"
        @export-current="exportRows('payment-risk-reviews.csv', filteredRows)"
        @clear-selection="clearSelection"
      />
      <div v-show="advancedVisible" class="filter-grid list-advanced-filter-panel" data-pce-filter-for="payment-risk-reviews-main">
        <label data-filter-key="reviewNo"><span>风险评审编号</span><el-input v-model="filters.reviewNo" clearable /></label>
        <label data-filter-key="sourceNo"><span>来源草稿编号</span><el-input v-model="filters.sourceNo" clearable /></label>
        <label data-filter-key="supplierName"><span>供应商</span><PceResultFilterSelect v-model="filters.supplierName" :rows="rows" :fields="['supplierName']" /></label>
        <label data-filter-key="status"><span>评审状态</span><el-select v-model="filters.status" clearable><el-option label="已通过" value="passed" /><el-option label="已阻断" value="blocked" /></el-select></label>
        <label data-filter-key="riskLevel"><span>风险等级</span><el-select v-model="filters.riskLevel" clearable><el-option label="低" value="low" /><el-option label="中" value="medium" /><el-option label="高" value="high" /></el-select></label>
        <label data-filter-key="currency"><span>币种</span><PceResultFilterSelect v-model="filters.currency" :rows="rows" :fields="['currency']" /></label>
      </div>
      <BusinessTableScrollContainer
        acceptance-id="business-table-scroll-payment-risk-reviews-main"
        page-id="payment-risk-review"
        table-id="payment-risk-reviews-main"
        min-width="1800px"
      >
        <el-table
          ref="tableRef"
          :data="filteredRows"
          border
          stripe
          height="480"
          scrollbar-always-on
          row-key="id"
          data-acceptance-id="formal-list-table"
          @selection-change="selectedRows = $event"
          @row-click="selectDetail"
          @sort-change="updateMainSort"
        >
          <el-table-column type="selection" width="55" fixed="left" class-name="business-table-selection-column" />
          <el-table-column type="index" label="序号" width="65" fixed="left" class-name="pce-fixed-index-column" />
          <el-table-column prop="reviewNo" label="风险评审编号" width="220" fixed="left" sortable="custom" class-name="pce-fixed-primary-no-column" />
          <el-table-column prop="sourcePaymentOrderDraftNo" label="来源草稿编号" width="220" />
          <el-table-column prop="supplierName" label="供应商" width="210" />
          <el-table-column prop="currency" label="币种" width="90" />
          <el-table-column prop="paymentAmount" label="付款金额" width="140" />
          <el-table-column label="评审状态" width="130"><template #default="{ row }">{{ display(row.status) }}</template></el-table-column>
          <el-table-column label="风险等级" width="120"><template #default="{ row }">{{ display(row.riskLevel) }}</template></el-table-column>
          <el-table-column label="风险结果" width="130"><template #default="{ row }">{{ display(row.riskResult) }}</template></el-table-column>
          <el-table-column prop="issueCount" label="问题数量" width="110" />
          <el-table-column label="放行状态" width="210"><template #default="{ row }">{{ display(row.eligibility?.nextStepReadiness) }}</template></el-table-column>
          <el-table-column label="操作" width="100" fixed="right" class-name="payment-fixed-action-column">
            <template #default="{ row }"><el-button size="small" plain @click.stop="selectDetail(row)">查看</el-button></template>
          </el-table-column>
        </el-table>
      </BusinessTableScrollContainer>
      <p class="ctrl-f">Ctrl+F：真实付款风险评审标准列表</p>
    </section>

    <section class="business-card" data-acceptance-id="payment-risk-review-zero-boundary">
      <Heading title="下游零对象保护" note="本页不创建正式付款单或任何付款执行对象" />
      <div class="facts">
        <Fact v-for="(value, key) in downstream" :key="key" :label="downstreamLabel(key)" :value="value" />
      </div>
      <p class="ctrl-f">Ctrl+F：下游零对象保护</p>
    </section>
  </main>
</template>

<script setup>
import { computed, defineComponent, h, inject, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { paymentRiskReviewApi } from '@/api/paymentRiskReview.js'
import {
  PAYMENT_RISK_REVIEW_MODULE,
  PAYMENT_RISK_REVIEW_VERSION,
  createPaymentRiskReviewPageFacts,
  paymentRiskReviewDisplayValue,
} from '@/meta/runtime/paymentRiskReviewRuntime.js'
import { PAGE_OBSERVABILITY_ACTIONS_KEY } from '@/meta/runtime/pageObservabilityActions.js'
import BusinessTableScrollContainer from '../components/BusinessTableScrollContainer.vue'
import PceResultFilterSelect from '../components/PceResultFilterSelect.vue'
import StandardListToolbar from '../components/StandardListToolbar.vue'
import {
  createAcceptanceFacts,
  summarizeAcceptanceActions,
} from '../acceptance/acceptanceObservabilityContract.js'
import { getPceBusinessActionContract } from '../runtime/pceBusinessActionRegistry.js'

defineProps({ embeddedInCommonShell: { type: Boolean, default: false } })
const rows = ref([])
const current = ref(null)
const pageFacts = ref(createPaymentRiskReviewPageFacts())
const quickSearch = ref('')
const sourceSearch = ref('')
const sourceAdvancedVisible = ref(false)
const advancedVisible = ref(false)
const selectedRows = ref([])
const tableRef = ref(null)
const sourceTableRef = ref(null)
const mainSort = reactive({ prop: '', order: '' })
const sourceSort = reactive({ prop: '', order: '' })
const filters = reactive({ reviewNo: '', sourceNo: '', supplierName: '', status: '', riskLevel: '', currency: '' })
const sourceFilters = reactive({ sourceNo: '', supplierName: '' })
const capacity = computed(() => pageFacts.value.capacity)
const downstream = computed(() => pageFacts.value.downstreamCounts)
const activeFilterCount = computed(() => Object.values(filters).filter(value => String(value || '').trim()).length)
const sourceActiveFilterCount = computed(() => Object.values(sourceFilters).filter(value => String(value || '').trim()).length)
const mainSortText = computed(() => sortLabel(mainSort, '风险评审编号'))
const sourceSortText = computed(() => sortLabel(sourceSort, '来源草稿编号'))
const filteredRows = computed(() => {
  const keyword = quickSearch.value.trim().toLowerCase()
  const values = rows.value.filter(row => {
    const searchable = [row.reviewNo, row.sourcePaymentOrderDraftNo, row.supplierName, row.status, row.riskLevel].join(' ').toLowerCase()
    return (!keyword || searchable.includes(keyword))
      && (!filters.reviewNo || row.reviewNo.includes(filters.reviewNo.trim()))
      && (!filters.sourceNo || row.sourcePaymentOrderDraftNo.includes(filters.sourceNo.trim()))
      && (!filters.supplierName || row.supplierName.includes(filters.supplierName.trim()))
      && (!filters.status || row.status === filters.status)
      && (!filters.riskLevel || row.riskLevel === filters.riskLevel)
      && (!filters.currency || row.currency === filters.currency.trim())
  })
  return sortRows(values, mainSort)
})
const filteredSources = computed(() => {
  const keyword = sourceSearch.value.trim().toLowerCase()
  const values = rows.value.filter(row => (
    (!keyword || [row.sourcePaymentOrderDraftNo, row.supplierName].join(' ').toLowerCase().includes(keyword))
    && (!sourceFilters.sourceNo || row.sourcePaymentOrderDraftNo.includes(sourceFilters.sourceNo.trim()))
    && (!sourceFilters.supplierName || row.supplierName.includes(sourceFilters.supplierName.trim()))
  ))
  return sortRows(values, sourceSort)
})
const observability = inject(PAGE_OBSERVABILITY_ACTIONS_KEY, null)

const display = paymentRiskReviewDisplayValue
const noop = () => {}
function selectDetail(row) { current.value = row }
function clearFilters() {
  quickSearch.value = ''
  Object.assign(filters, { reviewNo: '', sourceNo: '', supplierName: '', status: '', riskLevel: '', currency: '' })
}
function clearSourceFilters() {
  sourceSearch.value = ''
  Object.assign(sourceFilters, { sourceNo: '', supplierName: '' })
}
function sortRows(values, state) {
  if (!state.prop || !state.order) return values
  const direction = state.order === 'descending' ? -1 : 1
  return [...values].sort((left, right) => String(left?.[state.prop] ?? '').localeCompare(
    String(right?.[state.prop] ?? ''),
    'zh-Hans-CN',
    { numeric: true },
  ) * direction)
}
function sortLabel(state, fallback) {
  if (!state.prop || !state.order) return '未排序'
  return `${fallback}${state.order === 'descending' ? '降序' : '升序'}`
}
function updateMainSort({ prop = '', order = '' } = {}) {
  Object.assign(mainSort, { prop, order: order || '' })
}
function updateSourceSort({ prop = '', order = '' } = {}) {
  Object.assign(sourceSort, { prop, order: order || '' })
}
function clearSort() {
  Object.assign(mainSort, { prop: '', order: '' })
  tableRef.value?.clearSort()
}
function clearSourceSort() {
  Object.assign(sourceSort, { prop: '', order: '' })
  sourceTableRef.value?.clearSort()
}
function clearSelection() {
  tableRef.value?.clearSelection()
  selectedRows.value = []
}
function exportRows(name, values) {
  const payload = values.map(row => ({
    riskReviewNo: row.reviewNo,
    sourcePaymentOrderDraftNo: row.sourcePaymentOrderDraftNo,
    supplierName: row.supplierName,
    currency: row.currency,
    paymentAmount: row.paymentAmount,
    status: display(row.status),
    riskLevel: display(row.riskLevel),
  }))
  const keys = Object.keys(payload[0] || {})
  const csv = [keys, ...payload.map(row => keys.map(key => row[key]))]
    .map(line => line.map(value => `"${String(value ?? '').replaceAll('"', '""')}"`).join(',')).join('\r\n')
  const link = document.createElement('a')
  link.href = URL.createObjectURL(new Blob([`\ufeff${csv}`], { type: 'text/csv;charset=utf-8' }))
  link.download = name
  link.click()
  URL.revokeObjectURL(link.href)
}
function downstreamLabel(key) {
  return {
    formalPaymentOrders: '正式付款单数量',
    formalPaymentInstructions: '正式付款指令数量',
    signingResults: '签署结果数量',
    bankMessages: '银行报文数量',
    paymentExecutions: '付款执行数量',
    paymentVouchers: '付款凭证数量',
    writeoffs: '核销数量',
    ledgerEntries: '总账数量',
    postings: '过账数量',
    bankTransactions: '银行流水数量',
  }[key] || key
}
async function refresh() {
  const response = await paymentRiskReviewApi.list()
  const facts = createPaymentRiskReviewPageFacts(response?.data || {})
  pageFacts.value = facts
  rows.value = facts.rows
  const selectedNo = current.value?.reviewNo
  current.value = rows.value.find(row => row.reviewNo === selectedNo) || rows.value[0] || null
}
function buildDiagnostics() {
  const facts = pageFacts.value
  const actionInventory = summarizeAcceptanceActions(
    getPceBusinessActionContract('payment-risk-review')?.actions || [],
  )
  const acceptanceFacts = createAcceptanceFacts({
    pageCode: PAYMENT_RISK_REVIEW_MODULE.moduleCode,
    factSource: 'server',
    recordCount: facts.capacity.riskReviewCount,
    selectedCount: selectedRows.value.length,
    ...actionInventory,
    businessProgressWriteCount: 0,
    downstreamObjectCount: facts.capacity.nextStageConsumedCount,
    fieldSources: {
      recordCount: 'server.capacity.riskReviewCount',
      downstreamObjectCount: 'server.capacity.nextStageConsumedCount',
      actions: 'PCE Business Action Registry',
    },
  })
  return {
    version: PAYMENT_RISK_REVIEW_VERSION,
    pageCode: PAYMENT_RISK_REVIEW_MODULE.pageCode,
    moduleCode: PAYMENT_RISK_REVIEW_MODULE.moduleCode,
    canonicalName: PAYMENT_RISK_REVIEW_MODULE.canonicalName,
    tenantId: facts.tenantId,
    canaryBatchId: facts.canaryBatchId,
    currentStateSource: 'server',
    sourceDraftCount: facts.capacity.sourceDraftCount,
    riskReviewCount: facts.capacity.riskReviewCount,
    passedCount: facts.capacity.passedCount,
    blockedCount: facts.capacity.blockedCount,
    blockedScenarioCount: facts.capacity.blockedScenarioCount,
    nextStageConsumedCount: facts.capacity.nextStageConsumedCount,
    resultCount: facts.resultCount,
    currentObject: current.value,
    selectedObject: current.value,
    sourceObjects: facts.sourceObjects,
    status: current.value?.status || '',
    riskRules: current.value?.ruleExecution || {},
    riskIssues: current.value?.riskIssues || [],
    eligibility: current.value?.eligibility || {},
    downstreamCounts: facts.downstreamCounts,
    strictServerFacts: facts.strictServerFacts,
    displayValues: {
      status: { rawValue: current.value?.status, displayValue: display(current.value?.status) },
      riskLevel: { rawValue: current.value?.riskLevel, displayValue: display(current.value?.riskLevel) },
      riskResult: { rawValue: current.value?.riskResult, displayValue: display(current.value?.riskResult) },
      nextStepReadiness: {
        rawValue: current.value?.eligibility?.nextStepReadiness,
        displayValue: display(current.value?.eligibility?.nextStepReadiness),
      },
    },
    acceptanceFacts,
  }
}
onMounted(async () => {
  await refresh()
  observability?.register({ refresh, buildDiagnostics })
})
onBeforeUnmount(() => observability?.unregister())

const Heading = defineComponent({
  props: { title: String, note: String },
  setup: props => () => h('header', { class: 'card-heading' }, [h('h2', props.title), props.note ? h('span', props.note) : null]),
})
const Fact = defineComponent({
  props: { label: String, value: [String, Number, Boolean, Array] },
  setup: props => () => h('div', { class: 'fact' }, [h('span', props.label), h('strong', display(props.value))]),
})
</script>

<style scoped>
.risk-page { display: grid; gap: 16px; min-width: 0; }
.business-card { display: grid; gap: 14px; min-width: 0; padding: 18px; border: 1px solid #d8e0ea; border-radius: 14px; background: #fff; box-shadow: 0 5px 16px rgba(30, 50, 75, .06); }
.card-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; border-bottom: 1px solid #edf1f5; padding-bottom: 10px; }
.card-heading h2 { margin: 0; color: #17324d; font-size: 19px; }
.card-heading span { color: #526579; font-size: 13px; }
.facts { display: grid; grid-template-columns: repeat(auto-fit, minmax(205px, 1fr)); gap: 10px; }
.fact { display: grid; gap: 5px; min-height: 68px; padding: 11px; border: 1px solid #e5eaf0; border-radius: 9px; background: #f8fafc; }
.fact span { color: #596b7d; font-size: 13px; }
.fact strong { color: #17324d; overflow-wrap: anywhere; }
.filter-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; padding: 12px; border: 1px solid #dfe6ee; background: #f8fafc; }
.filter-grid label { display: grid; gap: 6px; color: #465a70; font-size: 13px; }
.ctrl-f { margin: 0; color: #60758a; font-size: 12px; }
.boundary-note { margin: 0; padding: 10px 12px; border-left: 4px solid #c58b17; background: #fff8e8; color: #714e0b; }
</style>
