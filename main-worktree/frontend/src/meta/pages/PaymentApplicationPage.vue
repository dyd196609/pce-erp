<template>
  <main class="payment-request-page" data-acceptance-id="payment-request-prepare-page">
    <header class="page-header">
      <div v-if="!embeddedInCommonShell">
        <p class="eyebrow">当前版本：{{ VERSION }}</p>
        <h1 data-acceptance-id="page-business-title">
          <span data-acceptance-id="page-internal-subject-title"><PceBusinessNameConsumer page-code="payment-application" /></span>
        </h1>
        <p data-acceptance-id="page-breadcrumb-current-title">业务流程中心 / <strong>付款申请准备</strong></p>
        <p>唯一直接来源：应付确认准备；当前状态与付款申请资格均来自服务端。</p>
      </div>
      <div class="header-actions">
        <el-button plain @click="refresh">刷新</el-button>
        <el-button type="success" plain @click="copyDiagnostics">复制诊断数据</el-button>
        <el-button plain @click="router.push('/process-center')">返回业务流程中心</el-button>
      </div>
    </header>

    <section v-if="!embeddedInCommonShell" class="business-card process-navigation" data-acceptance-id="payment-request-process-navigation">
      <div class="section-heading">
        <h2>业务流程导航</h2>
        <strong>单一服务端正式读模型</strong>
      </div>
      <div class="facts">
        <Fact label="上一步" :value="RUNTIME.previousModule.name" />
        <Fact label="当前页面" :value="RUNTIME.currentModule.name" />
        <Fact label="下一步" :value="RUNTIME.nextModule.name" />
      </div>
      <div class="navigation-actions">
        <el-button plain :disabled="!current" @click="viewSource(current)">查看来源应付确认准备</el-button>
      </div>
      <p class="boundary">进入付款申请仅形成导航资格，不创建任何下游对象。</p>
      <p class="ctrl-f">Ctrl+F：业务流程导航</p>
    </section>

    <section class="business-card capacity-card" data-acceptance-id="payment-request-prepare-capacity">
      <div class="section-heading">
        <h3>付款申请准备金丝雀群测试容量</h3>
        <strong :class="capacity.passed ? 'passed' : 'blocked'">
          {{ capacity.passed ? '容量门禁：通过' : '容量门禁：阻断' }}
        </strong>
      </div>
      <div class="facts">
        <Fact label="成功链数量" :value="capacity.passThroughLineageCount" />
        <Fact label="阻断场景数量" :value="capacity.blockedScenarioCount" />
        <Fact label="正式对象数量" :value="capacity.formalPaymentRequestPrepareCount" />
        <Fact label="下游可继承数量" :value="capacity.downstreamEligibleSourceCount" />
        <Fact label="已消费数量" :value="capacity.nextStageConsumedCount" />
        <Fact label="未消费数量" :value="capacity.unconsumedAvailableCount" />
        <Fact label="下一模块" value="付款申请" />
        <Fact label="当前状态来源" value="server" />
      </div>
      <p class="ctrl-f">Ctrl+F：付款申请准备金丝雀群测试容量</p>
    </section>

    <section class="business-card" data-acceptance-id="payment-request-prepare-scenarios">
      <div class="section-heading">
        <div>
          <h3>金丝雀业务场景</h3>
          <p>成功链与独立阻断场景分开持久化；阻断场景不计入容量。</p>
        </div>
        <label class="scenario-filter">
          场景筛选
          <el-select v-model="scenarioFilter" @change="refresh">
            <el-option label="全部场景" value="all" />
            <el-option label="成功场景" value="success" />
            <el-option label="阻断场景" value="blocked" />
            <el-option
              v-for="item in scenarioOptions"
              :key="item.scenarioCode"
              :label="item.scenarioCode"
              :value="item.scenarioCode"
            />
          </el-select>
        </label>
      </div>
      <BusinessTableScrollContainer acceptance-id="business-table-scroll-payment-request-scenarios" min-width="1400px">
        <el-table :data="scenarioOverview" border stripe height="340" scrollbar-always-on>
          <el-table-column prop="scenarioCode" label="场景编码" width="270" fixed="left" />
          <el-table-column prop="scenarioClass" label="场景类型" width="130" />
          <el-table-column prop="scenarioRole" label="场景目的" min-width="240" />
          <el-table-column prop="currentObjectNo" label="当前对象编号" min-width="210" />
          <el-table-column prop="currentStatus" label="当前状态" width="130"><template #default="{ row }">{{ display(row.currentStatus) }}</template></el-table-column>
          <el-table-column prop="downstreamEligible" label="下游资格" width="130">
            <template #default="{ row }">{{ row.downstreamEligible ? '允许' : '阻断' }}</template>
          </el-table-column>
          <el-table-column prop="blockingRuleCode" label="阻断规则" min-width="240" />
          <el-table-column prop="blockingReason" label="阻断原因" min-width="240" />
        </el-table>
      </BusinessTableScrollContainer>
      <p class="ctrl-f">Ctrl+F：金丝雀业务场景</p>
    </section>

    <section class="business-card" data-acceptance-id="payment-request-prepare-source">
      <div class="section-heading">
        <h3>付款申请准备来源</h3>
        <strong>sourceDocumentType=payableConfirmationPrepare</strong>
      </div>
      <div class="facts">
        <Fact label="应付确认准备编号" :value="current?.sourcePayableConfirmationPrepareNo" />
        <Fact label="AP草稿编号" :value="current?.sourceApDraftNo" />
        <Fact label="供应商" :value="current?.supplierName" />
        <Fact label="法人" :value="current?.legalEntityName" />
        <Fact label="账簿" :value="current?.ledgerBookId" />
        <Fact label="币种" :value="current?.currency" />
        <Fact label="应付金额" :value="current?.payableAmount" />
        <Fact label="来源版本" :value="current?.sourceConfirmationVersion" />
        <Fact label="来源资格" value="ready_for_payment_request_prepare" />
      </div>
      <p class="ctrl-f">Ctrl+F：付款申请准备来源</p>
    </section>

    <section class="business-card" data-acceptance-id="payment-request-data">
      <div class="section-heading">
        <h3>付款资料采集</h3>
        <strong>服务端 Provider 权威读取；账号仅脱敏展示</strong>
      </div>
      <div class="facts">
        <Fact label="收款银行账户" :value="current?.paymentData?.payeeAccountNoMasked" />
        <Fact label="收款账户名称" :value="current?.paymentData?.payeeAccountName" />
        <Fact label="付款银行账户" :value="current?.paymentData?.payerAccountNoMasked" />
        <Fact label="付款账户名称" :value="current?.paymentData?.payerAccountName" />
        <Fact label="付款方式" :value="current?.paymentData?.paymentMethodCode" />
        <Fact label="计划付款日期" :value="current?.paymentData?.plannedPaymentDate" />
        <Fact label="付款金额" :value="current?.paymentData?.paymentAmount" />
        <Fact label="付款用途" :value="current?.paymentData?.paymentPurpose" />
        <Fact label="付款摘要" :value="current?.paymentData?.paymentSummary" />
        <Fact label="资料版本" :value="current?.currentPaymentDataVersion" />
      </div>
      <p class="ctrl-f">Ctrl+F：付款资料采集</p>
    </section>

    <section class="business-card" data-acceptance-id="payment-element-validation">
      <div class="section-heading">
        <h3>付款要素校验</h3>
        <strong>金额使用服务端 Decimal；日期、冻结与账户均服务端重读</strong>
      </div>
      <div class="facts">
        <Fact label="校验状态" :value="current?.validationStatus" />
        <Fact label="结果编码" :value="current?.validationResultCode" />
        <Fact label="规则数量" :value="current?.validation?.ruleCount" />
        <Fact label="通过数量" :value="current?.validation?.passedCount" />
        <Fact label="阻断数量" :value="current?.validation?.blockedCount" />
        <Fact label="问题数量" :value="current?.validation?.issueCount" />
      </div>
      <p class="ctrl-f">Ctrl+F：付款要素校验</p>
    </section>

    <section class="business-card" data-acceptance-id="payment-validation-issues">
      <div class="section-heading">
        <h3>校验问题清单</h3>
        <strong>{{ validationIssues.length ? '存在阻断问题' : '无阻断问题' }}</strong>
      </div>
      <el-table :data="validationIssues" border empty-text="当前校验无阻断问题">
        <el-table-column prop="ruleCode" label="规则编码" min-width="240" />
        <el-table-column prop="actual" label="实际值" min-width="180" />
        <el-table-column prop="expected" label="期望值" min-width="180" />
        <el-table-column prop="message" label="阻断原因" min-width="260" />
      </el-table>
      <p class="ctrl-f">Ctrl+F：校验问题清单</p>
    </section>

    <section class="business-card eligibility-card" data-acceptance-id="payment-request-eligibility">
      <div class="section-heading">
        <h3>付款申请资格</h3>
        <strong :class="current?.eligibility?.eligible ? 'passed' : 'blocked'">
          {{ current?.eligibility?.nextStepReadiness || 'blocked' }}
        </strong>
      </div>
      <div class="facts">
        <Fact label="status" :value="current?.status" />
        <Fact label="payment_data_status" :value="current?.paymentDataStatus" />
        <Fact label="validation_status" :value="current?.validationStatus" />
        <Fact label="issueCount" :value="current?.validationIssueCount" />
        <Fact label="paymentHold" :value="current?.eligibility?.paymentHold" />
        <Fact label="paymentAmount" :value="current?.paymentAmount" />
        <Fact label="sourcePayableAmount" :value="current?.payableAmount" />
        <Fact label="nextStepReadiness" :value="current?.eligibility?.nextStepReadiness" />
        <Fact label="eligible" :value="current?.eligibility?.eligible" />
        <Fact label="blockingReasons" :value="(current?.eligibility?.blockingReasons || []).join(',') || 'none'" />
      </div>
      <PceBusinessActionBar
        current-module="payment-request-prepare"
        :current-status="current?.status || ''"
        :selected-rows="selectedRows.length ? selectedRows : (current ? [current] : [])"
        :eligibility="current?.eligibility?.eligible ?? null"
        :show-unavailable="true"
      />
      <p class="boundary">该按钮仅导航，不创建付款申请。</p>
      <p class="ctrl-f">Ctrl+F：付款申请资格</p>
    </section>

    <section class="business-card" data-acceptance-id="payment-request-version-audit">
      <div class="section-heading">
        <h3>版本、幂等与审计</h3>
        <strong>currentStateSource=server</strong>
      </div>
      <div class="facts">
        <Fact label="页面版本" :value="VERSION" />
        <Fact label="对象版本" :value="current?.version" />
        <Fact label="状态转换数量" :value="current?.statusTransitionCount" />
        <Fact label="状态机事实一致" :value="current?.stateMachineConsistent" />
        <Fact label="幂等键" :value="current?.idempotencyKey" />
        <Fact label="编号状态" :value="current?.numberReservationStatus" />
        <Fact label="事务状态" :value="current?.transactionStatus" />
        <Fact label="审计状态" :value="current?.auditStatus" />
      </div>
      <p class="ctrl-f">Ctrl+F：版本、幂等与审计</p>
    </section>

    <section
      class="business-card"
      data-acceptance-id="payment-request-prepare-formal-list"
      data-search-alias="快速搜索"
      aria-label="搜索"
    >
      <div class="section-heading">
        <div>
          <h3>付款申请准备列表</h3>
          <p>只展示服务端正式领域表中的持久对象。</p>
        </div>
      </div>
      <div class="business-flow-action-toolbar" data-acceptance-id="business-flow-action-toolbar">
        <div class="business-flow-primary-actions" data-acceptance-id="business-flow-primary-actions">
          <strong>可信测试租户动作</strong>
          <el-button type="primary" disabled data-acceptance-id="business-flow-primary-action-button">测试租户生成付款申请准备</el-button>
          <el-button type="primary" plain disabled data-acceptance-id="business-flow-primary-action-button">测试租户保存付款资料</el-button>
          <el-button type="primary" plain disabled data-acceptance-id="business-flow-primary-action-button">测试租户执行付款要素校验</el-button>
          <small data-acceptance-id="business-flow-action-disabled-reason">当前 8 条正式对象均已 prepared，不允许重复写入。</small>
          <small data-acceptance-id="business-flow-selected-count">已选择 {{ selectedRows.length }} 条</small>
        </div>
        <div class="business-flow-secondary-actions" data-acceptance-id="business-flow-secondary-actions">
          <strong>辅助操作</strong>
          <el-button plain @click="exportCurrentRows">导出当前结果</el-button>
        </div>
      </div>
      <StandardListToolbar
        page-id="payment-application"
        table-id="payment-application-main"
        v-model:quick-search="quickSearch"
        :advanced-visible="advancedFilterVisible"
        :result-count="filteredRows.length"
        :selected-count="selectedRows.length"
        :active-filter-count="activeFilterCount"
        sort-text="默认业务顺序"
        :export-disabled="filteredRows.length === 0"
        @search="clearSelection"
        @toggle-advanced="advancedFilterVisible = !advancedFilterVisible"
        @clear-filters="clearFilters"
        @clear-sort="clearSort"
        @export-current="exportCurrentRows"
        @clear-selection="clearSelection"
      />
      <section
        v-show="advancedFilterVisible"
        class="advanced-filter-panel"
        data-acceptance-id="list-advanced-filter-panel"
        data-pce-filter-for="payment-application-main"
      >
        <label>准备编号<PceResultFilterSelect v-model="filters.prepareNo" :rows="rows" :fields="['prepareNo']" /></label>
        <label>来源应付确认<PceResultFilterSelect v-model="filters.sourcePayableConfirmationPrepareNo" :rows="rows" :fields="['sourcePayableConfirmationPrepareNo']" /></label>
        <label>AP草稿<PceResultFilterSelect v-model="filters.sourceApDraftNo" :rows="rows" :fields="['sourceApDraftNo']" /></label>
        <label>供应商<PceResultFilterSelect v-model="filters.supplierName" :rows="rows" :fields="['supplierName']" /></label>
        <label>状态<PceResultFilterSelect v-model="filters.status" :rows="rows" :fields="['status']" /></label>
        <label>资料状态<PceResultFilterSelect v-model="filters.paymentDataStatus" :rows="rows" :fields="['paymentDataStatus']" /></label>
        <label>校验状态<PceResultFilterSelect v-model="filters.validationStatus" :rows="rows" :fields="['validationStatus']" /></label>
        <label>币种<PceResultFilterSelect v-model="filters.currency" :rows="rows" :fields="['currency']" /></label>
        <label>场景编码<PceResultFilterSelect v-model="filters.scenarioCode" :rows="rows" :fields="['scenarioCode']" /></label>
      </section>
      <BusinessTableScrollContainer
        class="pce-baseline-table-shell"
        acceptance-id="business-table-scroll-payment-application-main"
        min-width="2600px"
      >
        <el-table
          ref="tableRef"
          v-loading="loading"
          class="global-sort-arrow"
          :data="filteredRows"
          border
          stripe
          height="560"
          style="width:100%"
          scrollbar-always-on
          @selection-change="selectedRows = $event"
        >
          <el-table-column type="selection" width="48" fixed="left" class-name="business-table-selection-column" header-class-name="business-table-selection-column" />
          <el-table-column type="index" label="序号" width="64" fixed="left" class-name="pce-fixed-index-column" header-class-name="pce-fixed-index-column" />
          <el-table-column prop="prepareNo" label="付款申请准备编号" min-width="210" fixed="left" sortable class-name="pce-fixed-primary-no-column" header-class-name="pce-fixed-primary-no-column" />
          <el-table-column prop="scenarioCode" label="场景编码" min-width="250" sortable />
          <el-table-column prop="sourcePayableConfirmationPrepareNo" label="来源应付确认准备" min-width="220" sortable />
          <el-table-column prop="sourceApDraftNo" label="来源AP草稿" min-width="190" sortable />
          <el-table-column prop="supplierName" label="供应商" min-width="180" sortable />
          <el-table-column prop="currency" label="币种" width="90" sortable />
          <el-table-column prop="payableAmount" label="应付金额" width="130" sortable />
          <el-table-column prop="paymentAmount" label="付款金额" width="130" sortable />
          <el-table-column prop="paymentDataStatus" label="资料状态" width="130" sortable><template #default="{ row }">{{ display(row.paymentDataStatus) }}</template></el-table-column>
          <el-table-column prop="validationStatus" label="校验状态" width="120" sortable><template #default="{ row }">{{ display(row.validationStatus) }}</template></el-table-column>
          <el-table-column prop="validationResultCode" label="校验结果" width="140" sortable />
          <el-table-column prop="status" label="准备状态" width="110" sortable><template #default="{ row }">{{ display(row.status) }}</template></el-table-column>
          <el-table-column label="付款申请资格" min-width="220">
            <template #default="{ row }">{{ display(row.eligibility?.nextStepReadiness || 'blocked') }}</template>
          </el-table-column>
          <el-table-column label="收款账号" min-width="180">
            <template #default="{ row }">{{ row.paymentData?.payeeAccountNoMasked || '-' }}</template>
          </el-table-column>
          <el-table-column label="付款账号" min-width="180">
            <template #default="{ row }">{{ row.paymentData?.payerAccountNoMasked || '-' }}</template>
          </el-table-column>
          <el-table-column label="操作" fixed="right" width="210" class-name="payment-fixed-action-column" header-class-name="payment-fixed-action-column">
            <template #default="{ row }">
              <div class="row-actions">
                <el-button size="small" plain @click="viewSource(row)">查看来源应付确认准备</el-button>
                <el-button size="small" plain @click="selectDetail(row)">查看付款资料</el-button>
                <el-button size="small" plain @click="selectDetail(row)">查看校验结果</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </BusinessTableScrollContainer>
      <p class="ctrl-f">Ctrl+F：{{ rows[0]?.prepareNo || '付款申请准备编号' }}</p>
    </section>

    <section class="business-card boundary-card" data-acceptance-id="payment-request-process-boundary">
      <div class="section-heading">
        <h3>业务流程与后续边界</h3>
        <strong>本版本仅允许导航</strong>
      </div>
      <div class="facts">
        <Fact label="当前模块" value="付款申请准备" />
        <Fact label="前置模块" value="应付确认准备" />
        <Fact label="下一模块" value="付款申请" />
        <Fact label="付款申请数量" :value="downstream.paymentRequests || 0" />
      </div>
      <p class="ctrl-f">Ctrl+F：业务流程与后续边界</p>
    </section>

    <section class="business-card boundary-card" data-acceptance-id="payment-request-zero-boundary">
      <div class="section-heading">
        <h3>下游零对象保护</h3>
        <strong>paymentRequestCreated=false</strong>
      </div>
      <div class="facts">
        <Fact label="付款申请" :value="downstream.paymentRequests || 0" />
        <Fact label="付款对象" :value="downstream.payments || 0" />
        <Fact label="付款指令" :value="downstream.paymentInstructions || 0" />
        <Fact label="付款凭证" :value="downstream.paymentVouchers || 0" />
        <Fact label="核销" :value="downstream.writeoffs || 0" />
        <Fact label="总账" :value="downstream.ledgerEntries || 0" />
        <Fact label="过账" :value="downstream.postings || 0" />
        <Fact label="银行流水" :value="downstream.bankTransactions || 0" />
      </div>
      <p class="ctrl-f">Ctrl+F：下游零对象保护</p>
    </section>
  </main>
</template>

<script setup>
import PceBusinessNameConsumer from '../components/PceBusinessNameConsumer.vue'
const { embeddedInCommonShell = false } = defineProps({
  embeddedInCommonShell: { type: Boolean, default: false },
})
import {
  computed,
  defineComponent,
  h,
  inject,
  onBeforeUnmount,
  onMounted,
  reactive,
  ref,
} from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { paymentRequestPrepareApi } from '@/api/paymentRequestPrepare.js'
import {
  PAYMENT_REQUEST_PREPARE_RUNTIME,
  PAYMENT_REQUEST_PREPARE_VERSION,
} from '@/meta/runtime/paymentRequestPrepareRuntime.js'
import { displayPceFilterValue } from '@/meta/runtime/pceAdvancedFilterContract.js'
import { PAGE_OBSERVABILITY_ACTIONS_KEY } from '@/meta/runtime/pageObservabilityActions.js'
import { stateMachineFactsFromServer } from '@/meta/runtime/pceStateMachineFactContract.js'
import BusinessTableScrollContainer from '../components/BusinessTableScrollContainer.vue'
import PceResultFilterSelect from '../components/PceResultFilterSelect.vue'
import StandardListToolbar from '../components/StandardListToolbar.vue'
import PceBusinessActionBar from '../components/PceBusinessActionBar.vue'
import {
  createAcceptanceFacts,
  summarizeAcceptanceActions,
} from '../acceptance/acceptanceObservabilityContract.js'
import { getPceBusinessActionContract } from '../runtime/pceBusinessActionRegistry.js'

const display = displayPceFilterValue

const RUNTIME = PAYMENT_REQUEST_PREPARE_RUNTIME
const VERSION = PAYMENT_REQUEST_PREPARE_VERSION
const router = useRouter()
const observabilityActions = inject(PAGE_OBSERVABILITY_ACTIONS_KEY, null)
const loading = ref(false)
const rows = ref([])
const scenarioOverview = ref([])
const scenarioOptions = ref([])
const scenarioFilter = ref('all')
const current = ref(null)
const validationIssues = ref([])
const quickSearch = ref('')
const advancedFilterVisible = ref(false)
const selectedRows = ref([])
const tableRef = ref(null)
const capacity = reactive({})
const downstream = reactive({})
const filters = reactive({
  prepareNo: '',
  sourcePayableConfirmationPrepareNo: '',
  sourceApDraftNo: '',
  supplierName: '',
  status: '',
  paymentDataStatus: '',
  validationStatus: '',
  currency: '',
  scenarioCode: '',
})

const Fact = defineComponent({
  props: {
    label: { type: String, required: true },
    value: { type: [String, Number, Boolean], default: '-' },
  },
  setup(props) {
    return () => h('div', { class: 'fact' }, [
      h('span', props.label),
      h('strong', String(props.value ?? '-')),
    ])
  },
})

function unwrap(response) {
  const envelope = response?.data || {}
  return envelope?.data || envelope
}

function queryForScenario() {
  if (['all', 'success', 'blocked'].includes(scenarioFilter.value)) {
    return { scenarioClass: scenarioFilter.value }
  }
  return { scenarioCode: scenarioFilter.value }
}

async function refresh() {
  loading.value = true
  try {
    const data = unwrap(await paymentRequestPrepareApi.list(queryForScenario()))
    rows.value = (data.results || []).map((row) => ({
      ...row,
      ...stateMachineFactsFromServer(row, `payment-request-prepare-list:${row.prepareNo}`),
    }))
    scenarioOverview.value = data.scenarioOverview || []
    if (!scenarioOptions.value.length || scenarioFilter.value === 'all') {
      scenarioOptions.value = [...(data.scenarioOverview || [])]
    }
    Object.assign(capacity, data.capacity || {})
    Object.assign(downstream, data.downstreamCounts || {})
    if (rows.value.length) selectDetail(rows.value[0])
    else {
      current.value = null
      validationIssues.value = []
    }
  } catch (error) {
    ElMessage.error(error?.message || '服务端付款申请准备读取失败')
  } finally {
    loading.value = false
  }
}

async function selectDetail(row) {
  try {
    const detail = unwrap(await paymentRequestPrepareApi.detail(row.id))
    current.value = {
      ...detail,
      ...stateMachineFactsFromServer(detail, `payment-request-prepare-detail:${detail.prepareNo}`),
    }
    validationIssues.value = current.value?.validation?.issues || []
  } catch (error) {
    ElMessage.error(error?.message || '服务端详情读取失败')
  }
}

const activeFilterCount = computed(() => (
  Object.values(filters).filter(Boolean).length + (quickSearch.value.trim() ? 1 : 0)
))
const filteredRows = computed(() => rows.value.filter((row) => {
  const q = quickSearch.value.trim().toLowerCase()
  if (q && !JSON.stringify(row).toLowerCase().includes(q)) return false
  return Object.entries(filters).every(([field, value]) => !value || row[field] === value)
}))

function clearSelection() {
  tableRef.value?.clearSelection?.()
  selectedRows.value = []
}
function clearSort() {
  tableRef.value?.clearSort?.()
  clearSelection()
}
function clearFilters() {
  quickSearch.value = ''
  Object.keys(filters).forEach((key) => { filters[key] = '' })
  clearSelection()
}
function viewSource(row) {
  router.push({
    path: '/finance/account-payable-confirms',
    query: { payableConfirmationPrepareNo: row.sourcePayableConfirmationPrepareNo },
  })
}
function navigateToPaymentRequest() {
  router.push({
    path: '/process-center',
    query: {
      targetModule: RUNTIME.nextModule.code,
      sourcePaymentRequestPrepareNo: current.value?.prepareNo || '',
      navigationOnly: 'true',
    },
  })
}
function exportCurrentRows() {
  const fields = [
    'prepareNo', 'scenarioCode', 'sourcePayableConfirmationPrepareNo',
    'sourceApDraftNo', 'supplierName', 'currency', 'payableAmount',
    'paymentAmount', 'paymentDataStatus', 'validationStatus', 'status',
  ]
  const csv = [fields.join(',')].concat(filteredRows.value.map((row) => fields
    .map((field) => `"${String(row[field] ?? '').replaceAll('"', '""')}"`).join(','))).join('\n')
  const blob = new Blob([`\ufeff${csv}`], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = 'payment-request-prepares.csv'
  link.click()
  URL.revokeObjectURL(link.href)
}
function buildDiagnostics() {
  const stateMachineFacts = current.value
    ? stateMachineFactsFromServer(
        current.value,
        `payment-request-prepare-diagnostic:${current.value.prepareNo}`,
      )
    : null
  const actionInventory = summarizeAcceptanceActions(
    getPceBusinessActionContract('payment-request-prepare')?.actions || [],
  )
  const acceptanceFacts = createAcceptanceFacts({
    pageCode: 'FIN_PAYMENT_APPLICATION',
    factSource: 'server',
    recordCount: capacity.formalPaymentRequestPrepareCount,
    selectedCount: selectedRows.value.length,
    ...actionInventory,
    businessProgressWriteCount: 0,
    downstreamObjectCount: capacity.nextStageConsumedCount,
    fieldSources: {
      recordCount: 'server.capacity.formalPaymentRequestPrepareCount',
      downstreamObjectCount: 'server.capacity.nextStageConsumedCount',
      actions: 'PCE Business Action Registry',
    },
  })
  return {
    version: VERSION,
    canonicalName: '付款申请准备',
    sourceDocumentType: 'payableConfirmationPrepare',
    currentStateSource: 'server',
    fullUrl: window.location.href,
    capacity,
    formalRows: rows.value,
    stateMachineFacts,
    strictFacts: stateMachineFacts
      ? {
          currentStateSource: 'server',
          formalObjectCount: rows.value.length,
          status: current.value.status,
          eligibility: current.value.eligibility,
          ...stateMachineFacts,
        }
      : null,
    scenarioOverview: scenarioOverview.value,
    downstream,
    paymentRequestCreated: false,
    acceptanceFacts,
  }
}
async function copyDiagnostics() {
  await navigator.clipboard.writeText(JSON.stringify(
    buildDiagnostics(),
    null,
    2,
  ))
  ElMessage.success(`${VERSION} 诊断数据已复制`)
}

onMounted(() => {
  observabilityActions?.register({ refresh, buildDiagnostics })
  refresh()
})
onBeforeUnmount(() => observabilityActions?.unregister())
</script>

<style scoped>
.payment-request-page { display: grid; gap: 16px; max-width: 100%; overflow-x: hidden; }
.page-header, .section-heading { display: flex; justify-content: space-between; gap: 12px; align-items: center; flex-wrap: wrap; }
.page-header h1, .page-header p, .business-card h2, .business-card h3, .business-card p { margin: 0; }
.header-actions, .navigation-actions, .business-flow-action-toolbar, .business-flow-primary-actions, .business-flow-secondary-actions, .row-actions { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.eyebrow, .ctrl-f { color: #2563eb; font-size: 13px; font-weight: 800; }
.business-card { display: grid; gap: 14px; padding: 18px; border: 1px solid #dbe3ef; border-radius: 12px; background: #fff; }
.capacity-card { border-color: #86efac; background: linear-gradient(135deg, #f0fdf4, #fff); }
.process-navigation { border-color: #93c5fd; background: linear-gradient(135deg, #eff6ff, #fff); }
.eligibility-card { border-color: #93c5fd; background: linear-gradient(135deg, #eff6ff, #fff); }
.boundary-card { border-color: #fdba74; background: #fffaf0; }
.facts { display: grid; grid-template-columns: repeat(auto-fit, minmax(215px, 1fr)); gap: 10px; }
:deep(.fact) { display: grid; gap: 5px; padding: 11px; border-radius: 8px; background: #f8fafc; }
:deep(.fact span) { color: #64748b; font-size: 12px; }
:deep(.fact strong) { color: #0f172a; overflow-wrap: anywhere; }
.scenario-filter { display: grid; gap: 5px; min-width: 280px; color: #334155; font-size: 12px; font-weight: 800; }
.business-flow-action-toolbar { justify-content: space-between; }
.business-flow-primary-actions small { flex-basis: 100%; color: #b45309; font-weight: 700; }
.advanced-filter-panel { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; padding: 10px; border: 1px solid #e2e8f0; border-radius: 8px; background: #f8fafc; }
.advanced-filter-panel label { display: grid; gap: 5px; color: #334155; font-size: 12px; font-weight: 800; }
.passed { color: #15803d; font-weight: 800; }
.blocked, .boundary { color: #b45309; font-weight: 800; }
</style>
