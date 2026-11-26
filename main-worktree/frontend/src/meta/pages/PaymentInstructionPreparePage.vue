<template>
  <main class="payment-instruction-prepare-page" data-acceptance-id="payment-instruction-prepare-page">
    <header v-if="!embeddedInCommonShell" class="page-header">
      <div><p class="eyebrow">当前版本：{{ VERSION }}</p><h1>{{ pageName.pageTitle }}</h1></div>
    </header>

    <section class="business-card" data-acceptance-id="payment-instruction-prepare-action">
      <Heading title="当前业务动作说明" note="固化已审批付款申请，校验支付路由，仅生成只读银行指令预览" />
      <div class="facts">
        <Fact label="当前模块" value="付款指令准备" />
        <Fact label="唯一直接来源" value="paymentRequest" />
        <Fact label="允许终态" value="prepared" />
        <Fact label="生产灰度" value="false" />
      </div>
    </section>

    <section class="business-card" data-acceptance-id="payment-instruction-readonly-actions">
      <Heading title="只读查看入口" note="仅定位当前服务端事实，不触发业务写入" />
      <div class="readonly-action-list">
        <el-button @click="scrollToRegion('payment-instruction-prepare-source')">查看来源付款申请</el-button>
        <el-button @click="scrollToRegion('payment-instruction-route')">查看支付路由</el-button>
        <el-button @click="scrollToRegion('payment-instruction-data')">查看指令资料</el-button>
        <el-button @click="scrollToRegion('payment-instruction-preview')">查看银行指令预览</el-button>
        <el-button @click="scrollToRegion('payment-instruction-validation')">查看校验结果</el-button>
      </div>
    </section>

    <section class="business-card capacity-card" data-acceptance-id="payment-instruction-prepare-capacity">
      <Heading title="付款指令准备金丝雀群测试容量" :note="capacity.passed ? '容量门禁：通过' : '容量门禁：阻断'" />
      <div class="facts">
        <Fact label="成功链数量" :value="capacity.passThroughLineageCount" />
        <Fact label="阻断场景数量" :value="capacity.blockedScenarioCount" />
        <Fact label="正式对象数量" :value="capacity.formalPaymentInstructionPrepareCount" />
        <Fact label="下游可继承数量" :value="capacity.downstreamEligibleSourceCount" />
        <Fact label="已消费数量" :value="capacity.nextStageConsumedCount" />
        <Fact label="未消费数量" :value="capacity.unconsumedAvailableCount" />
        <Fact label="下一模块" :value="capacity.nextCanonicalName" />
        <Fact label="当前状态来源" value="server" />
      </div>
      <p class="ctrl-f">Ctrl+F：付款指令准备金丝雀群测试容量</p>
    </section>

    <section class="business-card" data-acceptance-id="payment-instruction-prepare-scenarios">
      <Heading title="金丝雀业务场景" note="A—Z 成功链与独立阻断场景隔离" />
      <BusinessTableScrollContainer acceptance-id="business-table-scroll-payment-instruction-scenarios" min-width="1100px">
        <el-table :data="scenarioOverview" border stripe height="300" scrollbar-always-on>
          <el-table-column prop="scenarioCode" label="场景编码" min-width="250" fixed="left" />
          <el-table-column prop="scenarioClass" label="场景类型" width="140" />
          <el-table-column prop="scenarioRole" label="场景目的" min-width="220" />
          <el-table-column prop="currentObjectNo" label="当前对象" min-width="210" />
          <el-table-column prop="currentStatus" label="当前状态" width="130"><template #default="{ row }">{{ display(row.currentStatus) }}</template></el-table-column>
          <el-table-column prop="blockingRuleCode" label="阻断规则" min-width="250" />
        </el-table>
      </BusinessTableScrollContainer>
    </section>

    <section class="business-card" data-acceptance-id="payment-instruction-prepare-source">
      <Heading title="付款指令准备来源" note="服务端付款申请 Repository" />
      <div class="facts">
        <Fact label="付款申请编号" :value="current?.sourcePaymentRequestNo" />
        <Fact label="付款申请准备编号" :value="current?.sourcePaymentRequestPrepareNo" />
        <Fact label="供应商" :value="current?.supplierName" />
        <Fact label="法人" :value="current?.legalEntityName" />
        <Fact label="账簿" :value="current?.ledgerBookId" />
        <Fact label="币种" :value="current?.currency" />
        <Fact label="付款金额" :value="current?.paymentAmount" />
        <Fact label="计划付款日期" :value="current?.plannedExecutionDate" />
        <Fact label="申请状态" value="approved" />
        <Fact label="审批状态" value="approved" />
        <Fact label="审批证据版本" :value="current?.sourcePaymentRequestVersion" />
        <Fact label="来源资格" value="ready_for_payment_instruction_prepare" />
      </div>
      <p class="ctrl-f">Ctrl+F：付款指令准备来源</p>
    </section>

    <section class="business-card" data-acceptance-id="payment-instruction-route">
      <Heading title="支付路由资料" note="服务端 PaymentRouteProvider 权威选择" />
      <div class="facts">
        <Fact label="路由编号" :value="current?.route?.routeCode" />
        <Fact label="支付方式" :value="current?.route?.paymentMethodCode" />
        <Fact label="付款银行" :value="current?.route?.payerBankCode" />
        <Fact label="收款银行" :value="current?.route?.payeeBankCode" />
        <Fact label="币种" :value="current?.route?.currency" />
        <Fact label="金额范围" :value="routeAmountRange" />
        <Fact label="路由状态" :value="current?.route?.active" />
        <Fact label="优先级" :value="current?.route?.priority" />
      </div>
      <p class="ctrl-f">Ctrl+F：支付路由资料</p>
    </section>

    <section class="business-card" data-acceptance-id="payment-instruction-bank-interface">
      <Heading title="银行接口能力" note="服务端 BankInterfaceProvider 权威读取" />
      <div class="facts">
        <Fact label="接口配置编号" :value="current?.bankInterface?.interfaceProfileId" />
        <Fact label="支付渠道" :value="current?.bankInterface?.channelCode" />
        <Fact label="报文格式" :value="current?.bankInterface?.messageFormat" />
        <Fact label="支持币种" :value="current?.bankInterface?.supportedCurrencies?.join(', ')" />
        <Fact label="支持付款方式" :value="current?.bankInterface?.supportedPaymentMethods?.join(', ')" />
        <Fact label="连接状态" :value="current?.bankInterface?.connectionStatus" />
        <Fact label="支付能力状态" :value="current?.bankInterface?.paymentEnabled" />
      </div>
      <p class="ctrl-f">Ctrl+F：银行接口能力</p>
    </section>

    <section class="business-card" data-acceptance-id="payment-instruction-data">
      <Heading title="指令资料" note="不可变版本化快照" />
      <div class="facts">
        <Fact label="计划执行日期" :value="current?.instructionData?.plannedExecutionDate" />
        <Fact label="计划执行时间" :value="current?.instructionData?.plannedExecutionTime" />
        <Fact label="付款金额" :value="current?.paymentAmount" />
        <Fact label="币种" :value="current?.currency" />
        <Fact label="付款用途" :value="current?.instructionData?.paymentPurpose" />
        <Fact label="付款摘要" :value="current?.instructionData?.paymentSummary" />
        <Fact label="优先级" :value="current?.priority" />
        <Fact label="付款参考号" :value="current?.instructionData?.instructionReference" />
        <Fact label="资料版本" :value="current?.currentInstructionDataVersion" />
      </div>
      <p class="ctrl-f">Ctrl+F：指令资料</p>
    </section>

    <section class="business-card preview-card" data-acceptance-id="payment-instruction-preview">
      <Heading title="银行指令预览" note="只读预览；未发送银行；未创建正式付款指令" />
      <div class="facts">
        <Fact label="付款人" :value="current?.preview?.debtorName" />
        <Fact label="付款账户脱敏号" :value="current?.preview?.debtorAccountMasked" />
        <Fact label="收款人" :value="current?.preview?.creditorName" />
        <Fact label="收款账户脱敏号" :value="current?.preview?.creditorAccountMasked" />
        <Fact label="金额" :value="current?.preview?.amount" />
        <Fact label="币种" :value="current?.preview?.currency" />
        <Fact label="路由" :value="current?.preview?.routeCode" />
        <Fact label="渠道" :value="current?.preview?.channelCode" />
        <Fact label="执行日期" :value="current?.preview?.executionDate" />
        <Fact label="预览哈希" :value="current?.preview?.previewHash" />
      </div>
      <p class="ctrl-f">Ctrl+F：只读预览</p>
    </section>

    <section class="business-card" data-acceptance-id="payment-instruction-validation">
      <Heading title="校验结果" :note="current?.validation?.resultCode || 'not_validated'" />
      <div class="facts">
        <Fact label="校验状态" :value="current?.validationStatus" />
        <Fact label="校验结果编码" :value="current?.validationResultCode" />
        <Fact label="规则数量" :value="current?.validation?.ruleCount" />
        <Fact label="通过数量" :value="current?.validation?.passedCount" />
        <Fact label="阻断数量" :value="current?.validation?.blockedCount" />
        <Fact label="问题数量" :value="current?.validation?.issueCount" />
      </div>
      <p class="ctrl-f">Ctrl+F：校验结果</p>
    </section>

    <section class="business-card" data-acceptance-id="payment-instruction-validation-issues">
      <Heading title="校验问题清单" note="问题维度持久化，不扩展生命周期状态" />
      <BusinessTableScrollContainer acceptance-id="business-table-scroll-payment-instruction-issues" min-width="1000px">
        <el-table :data="current?.validation?.issues || []" border stripe>
          <el-table-column prop="ruleCode" label="规则编码" min-width="240" />
          <el-table-column prop="dimension" label="维度" min-width="150" />
          <el-table-column prop="expected" label="期望" min-width="220" />
          <el-table-column prop="actual" label="实际" min-width="220" />
          <el-table-column prop="message" label="说明" min-width="240" />
        </el-table>
      </BusinessTableScrollContainer>
    </section>

    <section class="business-card eligibility-card" data-acceptance-id="payment-order-prepare-eligibility">
      <Heading title="下一模块资格" :note="current?.eligibility?.nextStepReadiness || 'blocked'" />
      <div class="facts">
        <Fact v-for="field in eligibilityFields" :key="field" :label="field" :value="formatValue(current?.eligibility?.[field])" />
      </div>
      <PceBusinessActionBar
        current-module="payment-instruction-prepare"
        :current-status="current?.status || ''"
        :selected-rows="selectedRows.length ? selectedRows : (current ? [current] : [])"
        :eligibility="current?.eligibility?.eligible ?? null"
        :show-unavailable="true"
      />
      <p class="ctrl-f">Ctrl+F：下一模块资格</p>
    </section>

    <section class="business-card" data-acceptance-id="payment-instruction-audit">
      <Heading title="版本、幂等与审计" note="currentStateSource=server" />
      <div class="facts">
        <Fact label="当前版本" :value="VERSION" />
        <Fact label="页面框架版本" value="V1.14.2.8.4.3" />
        <Fact label="业务动作框架版本" value="V1.14.2.7.2.1" />
        <Fact label="对象版本" :value="current?.version" />
        <Fact label="状态转换数量" :value="current?.statusTransitionCount" />
        <Fact label="状态机事实一致" :value="current?.stateMachineConsistent" />
        <Fact label="幂等状态" :value="current?.idempotencyStatus" />
        <Fact label="编号状态" :value="current?.numberReservationStatus" />
        <Fact label="事务状态" :value="current?.transactionStatus" />
        <Fact label="审计状态" :value="current?.auditStatus" />
      </div>
      <p class="ctrl-f">Ctrl+F：版本、幂等与审计</p>
    </section>

    <section class="business-card" data-acceptance-id="payment-instruction-toolbar-region">
      <Heading title="标准工具栏" note="普通租户仅提供只读动作" />
      <StandardListToolbar
        page-id="payment-instruction-prepare"
        table-id="payment-instruction-prepare-main"
        v-model:quick-search="quickSearch"
        :advanced-visible="advancedVisible"
        :result-count="filteredRows.length"
        :selected-count="selectedRows.length"
        :active-filter-count="activeFilterCount"
        sort-text="付款指令准备编号升序"
        @search="clearSelection"
        @toggle-advanced="advancedVisible = !advancedVisible"
        @clear-filters="clearFilters"
        @clear-sort="clearSort"
        @export-current="exportCurrent"
        @clear-selection="clearSelection"
      />
      <div
        v-show="advancedVisible"
        class="advanced-filter-panel"
        data-acceptance-id="list-advanced-filter-panel"
        data-pce-filter-for="payment-instruction-prepare-main"
      >
        <label>付款指令准备编号<PceResultFilterSelect v-model="advancedFilters.prepareNo" :rows="rows" :fields="['prepareNo']" /></label>
        <label>来源付款申请<PceResultFilterSelect v-model="advancedFilters.sourcePaymentRequestNo" :rows="rows" :fields="['sourcePaymentRequestNo']" /></label>
        <label>供应商<PceResultFilterSelect v-model="advancedFilters.supplierName" :rows="rows" :fields="['supplierName']" /></label>
        <label>状态<PceResultFilterSelect v-model="advancedFilters.status" :rows="rows" :fields="['status']" /></label>
        <label>校验状态<PceResultFilterSelect v-model="advancedFilters.validationStatus" :rows="rows" :fields="['validationStatus']" /></label>
        <label>币种<PceResultFilterSelect v-model="advancedFilters.currency" :rows="rows" :fields="['currency']" /></label>
        <label>计划执行日期
          <el-date-picker v-model="advancedFilters.dateRange" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期" />
        </label>
      </div>
    </section>

    <section class="business-card" data-acceptance-id="payment-instruction-list-region">
      <Heading title="付款指令准备正式列表" :note="`正式对象数量=${rows.length}`" />
      <BusinessTableScrollContainer acceptance-id="business-table-scroll-payment-instruction-prepare-main" page-id="payment-instruction-prepare" table-id="payment-instruction-prepare-main" min-width="2100px">
        <el-table ref="tableRef" :data="filteredRows" border stripe scrollbar-always-on @selection-change="selectedRows = $event" @row-click="selectDetail">
          <el-table-column type="selection" width="55" fixed="left" class-name="business-table-selection-column" header-class-name="business-table-selection-column" />
          <el-table-column type="index" label="序号" width="64" fixed="left" class-name="pce-fixed-index-column" header-class-name="pce-fixed-index-column" />
          <el-table-column prop="prepareNo" label="付款指令准备编号" min-width="210" fixed="left" />
          <el-table-column prop="sourcePaymentRequestNo" label="来源付款申请" min-width="210" />
          <el-table-column prop="supplierName" label="供应商" min-width="180" />
          <el-table-column prop="payerBankAccountId" label="付款银行账户" min-width="190" />
          <el-table-column prop="payeeBankAccountId" label="收款银行账户" min-width="190" />
          <el-table-column prop="currency" label="币种" width="90" />
          <el-table-column prop="paymentAmount" label="付款金额" width="140" />
          <el-table-column prop="plannedExecutionDate" label="计划执行日期" width="150" />
          <el-table-column prop="paymentRouteId" label="支付路由" min-width="180" />
          <el-table-column prop="validationStatus" label="校验状态" width="120"><template #default="{ row }">{{ display(row.validationStatus) }}</template></el-table-column>
          <el-table-column prop="status" label="业务状态" width="110"><template #default="{ row }">{{ display(row.status) }}</template></el-table-column>
          <el-table-column label="操作" width="150" fixed="right"><template #default="{ row }"><el-button size="small" plain @click.stop="selectDetail(row)">查看</el-button></template></el-table-column>
        </el-table>
      </BusinessTableScrollContainer>
      <p class="ctrl-f">Ctrl+F：{{ rows[0]?.prepareNo || '付款指令准备编号' }}</p>
    </section>

    <section class="business-card boundary-card" data-acceptance-id="payment-instruction-process-boundary">
      <Heading title="业务流程与后续边界" note="下一步按钮仅导航，不创建下游对象" />
      <div class="facts">
        <Fact label="上一步" value="付款申请" />
        <Fact label="当前页面" value="付款指令准备" />
        <Fact label="下一步" :value="capacity.nextCanonicalName" />
        <Fact label="下一模块编码" :value="capacity.nextModuleCode" />
        <Fact label="下一模块路由" :value="capacity.nextRoute" />
      </div>
    </section>

    <section class="business-card boundary-card" data-acceptance-id="payment-instruction-zero-boundary">
      <Heading title="下游零对象保护" note="未创建正式付款指令、未执行付款、未发送银行" />
      <div class="facts">
        <Fact v-for="(value, key) in downstream" :key="key" :label="key" :value="value" />
      </div>
      <p class="ctrl-f">Ctrl+F：下游零对象保护</p>
    </section>
  </main>
</template>

<script setup>
import { computed, defineComponent, h, inject, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { paymentInstructionPrepareApi } from '@/api/paymentInstructionPrepare.js'
import { PAYMENT_INSTRUCTION_PREPARE_VERSION } from '@/meta/runtime/paymentInstructionPrepareRuntime.js'
import { PAGE_OBSERVABILITY_ACTIONS_KEY } from '@/meta/runtime/pageObservabilityActions.js'
import { resolvePageNameConsumption } from '@/meta/governance/pageNameConsumer.js'
import { stateMachineFactsFromServer } from '@/meta/runtime/pceStateMachineFactContract.js'
import { displayPceFilterValue } from '@/meta/runtime/pceAdvancedFilterContract.js'
import {
  factLoadFailureFromError,
  factLoadPassed,
  factLoadResultCount,
  readPceFactLoadEnvelope,
} from '@/meta/runtime/pceFactLoadContract.js'
import BusinessTableScrollContainer from '../components/BusinessTableScrollContainer.vue'
import PceResultFilterSelect from '../components/PceResultFilterSelect.vue'
import StandardListToolbar from '../components/StandardListToolbar.vue'
import PceBusinessActionBar from '../components/PceBusinessActionBar.vue'
import {
  createAcceptanceFacts,
  summarizeAcceptanceActions,
} from '../acceptance/acceptanceObservabilityContract.js'
import { getPceBusinessActionContract } from '../runtime/pceBusinessActionRegistry.js'

defineProps({ embeddedInCommonShell: { type: Boolean, default: false } })
const VERSION = PAYMENT_INSTRUCTION_PREPARE_VERSION
const FACT_LOAD_API_URL = '/api/finance/payment-instruction-prepares/'
const display = displayPceFilterValue
const router = useRouter()
const pageName = resolvePageNameConsumption({ pageCode: 'payment-instruction-prepare', route: '/finance/payment-order-prepares' })
const rows = ref([])
const factLoadFacts = ref(null)
const current = ref(null)
const scenarioOverview = ref([])
const quickSearch = ref('')
const advancedVisible = ref(false)
const advancedFilters = reactive({
  prepareNo: '',
  sourcePaymentRequestNo: '',
  supplierName: '',
  status: '',
  validationStatus: '',
  currency: '',
  dateRange: [],
})
const activeFilterCount = computed(() => (
  Number(Boolean(quickSearch.value.trim()))
  + Object.values(advancedFilters).filter(value => (
    Array.isArray(value) ? value.length > 0 : Boolean(String(value || '').trim())
  )).length
))
const selectedRows = ref([])
const tableRef = ref(null)
const capacity = reactive({})
const downstream = reactive({})
const serverMeta = reactive({
  canonicalName: '付款指令准备',
  currentStateSource: 'server',
  tenantId: '',
  canaryBatchId: '',
})
const observabilityActions = inject(PAGE_OBSERVABILITY_ACTIONS_KEY, null)
const Fact = defineComponent({
  props: { label: { type: String, required: true }, value: { type: [String, Number, Boolean], default: '-' } },
  setup: props => () => h('div', { class: 'fact' }, [h('span', props.label), h('strong', String(props.value ?? '-'))]),
})
const Heading = defineComponent({
  props: { title: { type: String, required: true }, note: { type: String, default: '' } },
  setup: props => () => h('div', { class: 'section-heading' }, [h('h3', props.title), h('strong', props.note)]),
})
const eligibilityFields = [
  'status', 'instructionDataStatus', 'validationStatus', 'routeValid',
  'bankInterfaceAvailable', 'businessDayValid', 'cutoffValid',
  'singleLimitPassed', 'dailyLimitPassed', 'paymentHold',
  'duplicatePaymentRisk', 'nextStepReadiness', 'eligible', 'blockingReasons',
]
const unwrap = response => response?.data?.data || response?.data || {}
const routeAmountRange = computed(() => current.value?.route ? `${current.value.route.amountMin} - ${current.value.route.amountMax}` : '-')
const filteredRows = computed(() => {
  const q = quickSearch.value.trim().toLowerCase()
  return rows.value.filter((row) => {
    if (q && !JSON.stringify(row).toLowerCase().includes(q)) return false
    if (advancedFilters.prepareNo && row.prepareNo !== advancedFilters.prepareNo) return false
    if (advancedFilters.sourcePaymentRequestNo && row.sourcePaymentRequestNo !== advancedFilters.sourcePaymentRequestNo) return false
    if (advancedFilters.supplierName && row.supplierName !== advancedFilters.supplierName) return false
    if (advancedFilters.status && row.status !== advancedFilters.status) return false
    if (advancedFilters.validationStatus && row.validationStatus !== advancedFilters.validationStatus) return false
    if (advancedFilters.currency && row.currency !== advancedFilters.currency) return false
    if (advancedFilters.dateRange?.length === 2) {
      const date = String(row.plannedExecutionDate || '')
      if (date < advancedFilters.dateRange[0] || date > advancedFilters.dateRange[1]) return false
    }
    return true
  })
})
function formatValue(value) {
  return Array.isArray(value) ? (value.join(', ') || '无') : value
}
async function refresh() {
  try {
    const loaded = readPceFactLoadEnvelope(
      await paymentInstructionPrepareApi.list(),
      FACT_LOAD_API_URL,
    )
    factLoadFacts.value = loaded.factLoadFacts
    const envelope = loaded.payload
    const data = loaded.data
    serverMeta.canonicalName = envelope.canonicalName || '付款指令准备'
    serverMeta.currentStateSource = envelope.currentStateSource || 'server'
    serverMeta.tenantId = data.tenantId || ''
    serverMeta.canaryBatchId = data.canaryBatchId || data.capacity?.canaryBatchId || ''
    rows.value = (data.results || []).map((row) => ({
      ...row,
      ...stateMachineFactsFromServer(row, `payment-instruction-prepare-list:${row.prepareNo}`),
    }))
    scenarioOverview.value = data.scenarioOverview || []
    Object.assign(capacity, data.capacity || {})
    Object.assign(downstream, data.downstreamCounts || {})
    if (rows.value.length) await selectDetail(rows.value[0])
  } catch (error) {
    factLoadFacts.value = factLoadFailureFromError(
      error,
      FACT_LOAD_API_URL,
      factLoadFacts.value,
    )
    ElMessage.error(error?.message || '付款指令准备服务端读取失败')
  }
}
async function selectDetail(row) {
  const detail = unwrap(await paymentInstructionPrepareApi.detail(row.id))
  current.value = {
    ...detail,
    ...stateMachineFactsFromServer(detail, `payment-instruction-prepare-detail:${detail.prepareNo}`),
  }
}
function clearSelection() { tableRef.value?.clearSelection?.(); selectedRows.value = [] }
function clearSort() { tableRef.value?.clearSort?.(); clearSelection() }
function clearFilters() {
  quickSearch.value = ''
  Object.keys(advancedFilters).forEach(key => {
    advancedFilters[key] = key === 'dateRange' ? [] : ''
  })
  clearSelection()
}
function exportCurrent() {
  const fields = ['prepareNo', 'sourcePaymentRequestNo', 'supplierName', 'currency', 'paymentAmount', 'validationStatus', 'status']
  const csv = [fields.join(','), ...filteredRows.value.map(row => fields.map(field => `"${String(row[field] ?? '').replaceAll('"', '""')}"`).join(','))].join('\n')
  const link = document.createElement('a')
  link.href = URL.createObjectURL(new Blob([`\ufeff${csv}`], { type: 'text/csv;charset=utf-8;' }))
  link.download = 'payment-instruction-prepares.csv'
  link.click()
  URL.revokeObjectURL(link.href)
}
function navigateNext() {
  router.push({ path: capacity.nextRoute || '/finance/payment-prepares', query: { navigationOnly: 'true', sourcePaymentInstructionPrepareNo: current.value?.prepareNo } })
}
function scrollToRegion(acceptanceId) {
  document.querySelector(`[data-acceptance-id="${acceptanceId}"]`)?.scrollIntoView({
    behavior: 'smooth',
    block: 'start',
  })
}
function buildDiagnostics() {
  const row = current.value || {}
  const stateMachineFacts = current.value
    ? stateMachineFactsFromServer(
        row,
        `payment-instruction-prepare-diagnostic:${row.prepareNo}`,
      )
    : null
  const actionInventory = summarizeAcceptanceActions(
    getPceBusinessActionContract('payment-instruction-prepare')?.actions || [],
  )
  const acceptanceFacts = createAcceptanceFacts({
    pageCode: 'FIN_PAYMENT_INSTRUCTION_PREPARE',
    factSource: 'server',
    recordCount: capacity.formalPaymentInstructionPrepareCount,
    selectedCount: selectedRows.value.length,
    ...actionInventory,
    businessProgressWriteCount: 0,
    downstreamObjectCount: capacity.nextStageConsumedCount,
    fieldSources: {
      recordCount: 'server.capacity.formalPaymentInstructionPrepareCount',
      downstreamObjectCount: 'server.capacity.nextStageConsumedCount',
      actions: 'PCE Business Action Registry',
    },
  })
  return {
    version: VERSION,
    canonicalName: serverMeta.canonicalName,
    fullUrl: window.location.href,
    currentStateSource: serverMeta.currentStateSource,
    ...factLoadFacts.value,
    factLoadFacts: factLoadFacts.value,
    resultCount: factLoadResultCount(factLoadFacts.value, rows.value.length),
    passed: factLoadPassed(factLoadFacts.value, Boolean(stateMachineFacts)),
    stateMachineFacts,
    strictFacts: {
      currentStateSource: 'server',
      ...factLoadFacts.value,
      factLoadFacts: factLoadFacts.value,
      resultCount: factLoadResultCount(factLoadFacts.value, rows.value.length),
      passed: factLoadPassed(factLoadFacts.value, Boolean(stateMachineFacts)),
      ...(stateMachineFacts ? { status: row.status, ...stateMachineFacts } : {}),
    },
    tenantId: serverMeta.tenantId,
    canaryBatchId: serverMeta.canaryBatchId,
    selectedScenarioCode: row.scenarioCode || '',
    process: {
      previousModuleCode: 'payment_request',
      currentModuleCode: 'payment_instruction_prepare',
      nextModuleCode: capacity.nextModuleCode,
      nextCanonicalName: capacity.nextCanonicalName,
      nextRoute: capacity.nextRoute,
    },
    capacity: {
      passThroughLineageCount: capacity.passThroughLineageCount,
      blockedScenarioCount: capacity.blockedScenarioCount,
      formalPaymentInstructionPrepareCount: capacity.formalPaymentInstructionPrepareCount,
      downstreamEligibleSourceCount: capacity.downstreamEligibleSourceCount,
      nextStageConsumedCount: capacity.nextStageConsumedCount,
      unconsumedAvailableCount: capacity.unconsumedAvailableCount,
    },
    selectedObject: {
      prepareNo: row.prepareNo,
      sourcePaymentRequestNo: row.sourcePaymentRequestNo,
      status: row.status,
      instructionDataStatus: row.instructionDataStatus,
      validationStatus: row.validationStatus,
      validationResultCode: row.validationResultCode,
      validationIssueCount: row.validationIssueCount,
      currentInstructionDataVersion: row.currentInstructionDataVersion,
      currentValidationVersion: row.currentValidationVersion,
      ...stateMachineFacts,
    },
    paymentRoute: {
      routeId: row.route?.routeId,
      routeCode: row.route?.routeCode,
      routeStatus: row.route?.routeStatus,
      routeAuthorityVersion: row.route?.authorityVersion,
    },
    bankInterface: {
      interfaceProfileId: row.bankInterface?.interfaceProfileId,
      channelCode: row.bankInterface?.channelCode,
      connectionStatus: row.bankInterface?.connectionStatus,
      paymentEnabled: row.bankInterface?.paymentEnabled,
      authorityVersion: row.bankInterface?.authorityVersion,
    },
    accounts: {
      payerBankAccountMasked: row.preview?.debtorAccountMasked,
      payeeBankAccountMasked: row.preview?.creditorAccountMasked,
    },
    instruction: {
      plannedExecutionDate: row.instructionData?.plannedExecutionDate,
      plannedExecutionTime: row.instructionData?.plannedExecutionTime,
      currency: row.currency,
      paymentAmount: row.paymentAmount,
      priority: row.priority,
      instructionReference: row.instructionData?.instructionReference,
    },
    validation: {
      ruleCount: row.validation?.ruleCount,
      passedCount: row.validation?.passedCount,
      blockedCount: row.validation?.blockedCount,
      issueCount: row.validation?.issueCount,
      issues: row.validation?.issues || [],
    },
    eligibility: {
      eligible: row.eligibility?.eligible,
      nextStepReadiness: row.eligibility?.nextStepReadiness,
      blockingReasons: row.eligibility?.blockingReasons || [],
      serverRevalidationRequired: row.eligibility?.serverRevalidationRequired,
    },
    transaction: {
      idempotencyStatus: row.idempotencyStatus,
      numberReservationStatus: row.numberReservationStatus,
      transactionStatus: row.transactionStatus,
      auditStatus: row.auditStatus,
    },
    downstream: {
      nextModuleObjectCount: downstream.nextModuleObjects,
      formalPaymentInstructionCount: downstream.formalPaymentInstructions,
      paymentExecutionCount: downstream.paymentExecutions,
      paymentVoucherCount: downstream.paymentVouchers,
      writeoffCount: downstream.writeoffs,
      ledgerEntryCount: downstream.ledgerEntries,
      postingCount: downstream.postings,
      bankTransactionCount: downstream.bankTransactions,
    },
    acceptanceFacts,
  }
}
onMounted(async () => {
  observabilityActions?.register({ refresh, buildDiagnostics })
  await refresh()
})
onBeforeUnmount(() => observabilityActions?.unregister())
</script>

<style scoped>
.payment-instruction-prepare-page { display: grid; gap: 16px; max-width: 100%; overflow-x: hidden; }
.page-header, :deep(.section-heading) { display: flex; justify-content: space-between; gap: 12px; align-items: center; flex-wrap: wrap; }
.business-card { display: grid; gap: 14px; padding: 18px; border: 1px solid #dbe3ef; border-radius: 12px; background: #fff; }
.business-card h3, .business-card p { margin: 0; }
.capacity-card { border-color: #86efac; background: linear-gradient(135deg, #f0fdf4, #fff); }
.eligibility-card { border-color: #93c5fd; background: linear-gradient(135deg, #eff6ff, #fff); }
.preview-card { border-color: #c4b5fd; background: linear-gradient(135deg, #f5f3ff, #fff); }
.boundary-card { border-color: #fdba74; background: #fffaf0; }
.facts { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; }
.advanced-filter-panel { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; padding: 10px; border: 1px solid #e2e8f0; border-radius: 8px; background: #f8fafc; }
.advanced-filter-panel label { display: grid; gap: 5px; color: #334155; font-size: 12px; font-weight: 800; }
.readonly-action-list { display: flex; flex-wrap: wrap; gap: 10px; }
:deep(.fact) { display: grid; gap: 5px; padding: 11px; border-radius: 8px; background: #f8fafc; }
:deep(.fact span) { color: #64748b; font-size: 12px; }
:deep(.fact strong) { color: #0f172a; overflow-wrap: anywhere; }
.ctrl-f { color: #2563eb; font-size: 13px; font-weight: 800; }
</style>
