<template>
  <main class="payment-request-page" data-acceptance-id="payment-request-page">
    <header v-if="!embeddedInCommonShell" class="page-header">
      <div>
        <p class="eyebrow">当前版本：{{ VERSION }}</p>
        <h1>{{ pageName.pageTitle }}</h1>
      </div>
    </header>

    <section class="business-card capacity-card" data-acceptance-id="payment-request-capacity">
      <div class="section-heading">
        <h3>付款申请金丝雀群测试容量</h3>
        <strong :class="capacity.passed ? 'passed' : 'blocked'">
          {{ capacity.passed ? '容量门禁：通过' : '容量门禁：阻断' }}
        </strong>
      </div>
      <div class="facts">
        <Fact label="成功链数量" :value="capacity.passThroughLineageCount" />
        <Fact label="阻断场景数量" :value="capacity.blockedScenarioCount" />
        <Fact label="正式付款申请数量" :value="capacity.formalPaymentRequestCount" />
        <Fact label="下游可继承数量" :value="capacity.downstreamEligibleSourceCount" />
        <Fact label="已消费数量" :value="capacity.nextStageConsumedCount" />
        <Fact label="未消费数量" :value="capacity.unconsumedAvailableCount" />
        <Fact label="下一模块" value="付款指令准备" />
        <Fact label="当前状态来源" value="server" />
      </div>
      <p class="ctrl-f">Ctrl+F：付款申请金丝雀群测试容量</p>
    </section>

    <section class="business-card" data-acceptance-id="payment-request-scenarios">
      <div class="section-heading"><h3>金丝雀业务场景</h3><strong>A—Z 成功链与阻断场景隔离</strong></div>
      <BusinessTableScrollContainer acceptance-id="business-table-scroll-payment-request-scenarios" min-width="1200px">
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

    <section class="business-card" data-acceptance-id="payment-request-source">
      <div class="section-heading"><h3>付款申请来源</h3><strong>sourceDocumentType=paymentRequestPrepare</strong></div>
      <div class="facts">
        <Fact label="付款申请准备编号" :value="current?.sourcePaymentRequestPrepareNo" />
        <Fact label="应付确认准备编号" :value="current?.sourcePayableConfirmationPrepareNo" />
        <Fact label="AP草稿编号" :value="current?.sourceApDraftNo" />
        <Fact label="供应商" :value="current?.supplierName" />
        <Fact label="法人" :value="current?.legalEntityName" />
        <Fact label="账簿" :value="current?.ledgerBookId" />
        <Fact label="币种" :value="current?.currency" />
        <Fact label="付款金额" :value="current?.paymentAmount" />
        <Fact label="计划付款日期" :value="current?.plannedPaymentDate" />
        <Fact label="来源版本" :value="current?.sourcePrepareVersion" />
        <Fact label="来源资格" value="ready_for_payment_request" />
      </div>
      <p class="ctrl-f">Ctrl+F：付款申请来源</p>
    </section>

    <section class="business-card" data-acceptance-id="payment-request-information">
      <div class="section-heading"><h3>付款申请信息</h3><strong>正式服务端持久化对象</strong></div>
      <div class="facts">
        <Fact label="付款申请编号" :value="current?.requestNo" />
        <Fact label="申请人" :value="current?.applicantName" />
        <Fact label="申请部门" :value="current?.applicantDepartmentId || '-'" />
        <Fact label="申请原因" :value="current?.applicationReason" />
        <Fact label="付款用途" :value="current?.paymentPurpose" />
        <Fact label="付款摘要" :value="current?.paymentSummary" />
        <Fact label="付款金额" :value="current?.paymentAmount" />
        <Fact label="币种" :value="current?.currency" />
        <Fact label="付款方式" :value="current?.paymentMethodCode" />
        <Fact label="计划付款日期" :value="current?.plannedPaymentDate" />
        <Fact label="状态" :value="current?.status" />
      </div>
    </section>

    <section class="business-card" data-acceptance-id="payment-request-submission-readiness">
      <div class="section-heading"><h3>提交准备检查</h3><strong>服务端重新读取全部来源与 Provider</strong></div>
      <div class="facts">
        <Fact label="来源状态" value="prepared" />
        <Fact label="付款资料状态" value="complete" />
        <Fact label="校验状态" value="已通过" />
        <Fact label="付款冻结" :value="current?.eligibility?.paymentHold ?? false" />
        <Fact label="审批策略" :value="current?.approvalPolicyId" />
        <Fact label="审批路线" :value="`${current?.totalApprovalSteps || 0} 步`" />
        <Fact label="职责分离" value="已通过" />
        <Fact label="提交资格" :value="current?.submissionReadiness" />
        <Fact label="阻断原因" :value="current?.eligibility?.blockingReasons?.join(', ') || '无'" />
      </div>
    </section>

    <section class="business-card" data-acceptance-id="payment-request-approval-route">
      <div class="section-heading"><h3>审批路线</h3><strong>审批状态：{{ current?.approvalStatus }}</strong></div>
      <BusinessTableScrollContainer acceptance-id="business-table-scroll-payment-request-route" min-width="900px">
        <el-table :data="current?.approvalRoute || []" border stripe>
          <el-table-column prop="stepNo" label="审批步骤" width="130" />
          <el-table-column prop="roleCode" label="审批角色" min-width="240" />
          <el-table-column prop="minimumApprovals" label="最低批准人数" width="150" />
          <el-table-column label="顺序或并行方式" width="170">
            <template #default="{ row }">{{ row.allowParallel ? '并行' : '顺序' }}</template>
          </el-table-column>
        </el-table>
      </BusinessTableScrollContainer>
      <p class="ctrl-f">Ctrl+F：审批路线</p>
    </section>

    <section class="business-card" data-acceptance-id="payment-request-current-tasks">
      <div class="section-heading"><h3>当前审批任务</h3><strong>服务端任务顺序</strong></div>
      <BusinessTableScrollContainer acceptance-id="business-table-scroll-payment-request-tasks" min-width="900px">
        <el-table :data="current?.approvalTasks || []" border stripe>
          <el-table-column prop="taskNo" label="任务编号" min-width="240" />
          <el-table-column prop="stepNo" label="步骤" width="100" />
          <el-table-column prop="requiredRoleCode" label="要求角色" min-width="240" />
          <el-table-column prop="status" label="当前状态" width="130"><template #default="{ row }">{{ display(row.status) }}</template></el-table-column>
          <el-table-column label="当前用户可操作" width="160"><template #default>否（只读演示）</template></el-table-column>
        </el-table>
      </BusinessTableScrollContainer>
    </section>

    <section class="business-card" data-acceptance-id="payment-request-approval-history">
      <div class="section-heading"><h3>审批历史</h3><strong>不可变审批决定</strong></div>
      <BusinessTableScrollContainer acceptance-id="business-table-scroll-payment-request-history" min-width="1100px">
        <el-table :data="current?.approvalHistory || []" border stripe>
          <el-table-column prop="actorName" label="审批人" min-width="220" />
          <el-table-column prop="decision" label="审批决定" width="130" />
          <el-table-column prop="createdAt" label="审批时间" min-width="210" />
          <el-table-column prop="comment" label="审批意见" min-width="260" />
          <el-table-column prop="stepNo" label="步骤" width="100" />
          <el-table-column prop="taskNo" label="任务编号" min-width="230" />
        </el-table>
      </BusinessTableScrollContainer>
      <p class="ctrl-f">Ctrl+F：审批历史</p>
    </section>

    <section class="business-card eligibility-card" data-acceptance-id="payment-instruction-prepare-eligibility">
      <div class="section-heading"><h3>付款指令准备资格</h3><strong>{{ current?.eligibility?.nextStepReadiness }}</strong></div>
      <div class="facts">
        <Fact label="status" :value="current?.eligibility?.status" />
        <Fact label="approvalStatus" :value="current?.eligibility?.approvalStatus" />
        <Fact label="approvalResultCode" :value="current?.eligibility?.approvalResultCode" />
        <Fact label="completedApprovalSteps" :value="current?.eligibility?.completedApprovalSteps" />
        <Fact label="totalApprovalSteps" :value="current?.eligibility?.totalApprovalSteps" />
        <Fact label="paymentHold" :value="current?.eligibility?.paymentHold" />
        <Fact label="sourceCurrent" :value="current?.eligibility?.sourceCurrent" />
        <Fact label="nextStepReadiness" :value="current?.eligibility?.nextStepReadiness" />
        <Fact label="eligible" :value="current?.eligibility?.eligible" />
        <Fact label="blockingReasons" :value="current?.eligibility?.blockingReasons?.join(', ') || '无'" />
      </div>
      <PceBusinessActionBar
        current-module="payment-request"
        :current-status="current?.status || ''"
        :selected-rows="selectedRows.length ? selectedRows : (current ? [current] : [])"
        :eligibility="current?.eligibility?.eligible ?? null"
        :before-navigate="revalidatePaymentInstructionPrepareEligibility"
        :show-unavailable="true"
      />
      <div
        class="facts"
        data-acceptance-id="payment-request-action-server-revalidation"
      >
        <Fact
          label="动作前服务端复核"
          :value="businessActionRevalidation.status"
        />
        <Fact
          label="服务端复核对象数"
          :value="businessActionRevalidation.verifiedCount"
        />
        <Fact
          label="服务端资格结论"
          :value="businessActionRevalidation.nextStepReadiness"
        />
        <Fact
          label="业务写请求"
          :value="businessActionRevalidation.businessWriteRequestCount"
        />
      </div>
    </section>

    <section class="business-card" data-acceptance-id="payment-request-audit">
      <div class="section-heading"><h3>版本、幂等与审计</h3><strong>currentStateSource=server</strong></div>
      <div class="facts">
        <Fact label="对象版本" :value="current?.version" />
        <Fact label="状态转换数量" :value="current?.statusTransitionCount" />
        <Fact label="状态机事实一致" :value="current?.stateMachineConsistent" />
        <Fact label="幂等状态" :value="current?.idempotencyStatus" />
        <Fact label="编号状态" :value="current?.numberReservationStatus" />
        <Fact label="事务状态" :value="current?.transactionStatus" />
        <Fact label="审计状态" :value="current?.auditStatus" />
      </div>
    </section>

    <section class="business-card" data-acceptance-id="payment-request-list-region">
      <div class="section-heading"><h3>付款申请列表</h3><strong>正式对象数量={{ rows.length }}</strong></div>
      <StandardListToolbar
        page-id="payment-request"
        table-id="payment-request-main"
        v-model:quick-search="quickSearch"
        :advanced-visible="advancedVisible"
        :result-count="filteredRows.length"
        :selected-count="selectedRows.length"
        :active-filter-count="activeFilterCount"
        sort-text="付款申请编号升序"
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
        data-pce-filter-for="payment-request-main"
      >
        <label>付款申请编号<PceResultFilterSelect v-model="advancedFilters.requestNo" :rows="rows" :fields="['requestNo']" /></label>
        <label>来源付款申请准备<PceResultFilterSelect v-model="advancedFilters.sourcePaymentRequestPrepareNo" :rows="rows" :fields="['sourcePaymentRequestPrepareNo']" /></label>
        <label>供应商<PceResultFilterSelect v-model="advancedFilters.supplierName" :rows="rows" :fields="['supplierName']" /></label>
        <label>业务状态<PceResultFilterSelect v-model="advancedFilters.status" :rows="rows" :fields="['status']" /></label>
        <label>审批状态<PceResultFilterSelect v-model="advancedFilters.approvalStatus" :rows="rows" :fields="['approvalStatus']" /></label>
        <label>币种<PceResultFilterSelect v-model="advancedFilters.currency" :rows="rows" :fields="['currency']" /></label>
      </div>
      <BusinessTableScrollContainer acceptance-id="business-table-scroll-payment-request-main" min-width="1500px">
        <el-table ref="tableRef" :data="filteredRows" border stripe scrollbar-always-on @selection-change="selectedRows = $event" @row-click="selectDetail">
          <el-table-column type="selection" width="55" fixed="left" />
          <el-table-column type="index" label="序号" width="64" fixed="left" class-name="pce-fixed-index-column" header-class-name="pce-fixed-index-column" />
          <el-table-column prop="requestNo" label="付款申请编号" min-width="210" fixed="left" />
          <el-table-column prop="sourcePaymentRequestPrepareNo" label="来源付款申请准备" min-width="220" />
          <el-table-column prop="supplierName" label="供应商" min-width="180" />
          <el-table-column prop="legalEntityName" label="法人" min-width="180" />
          <el-table-column prop="currency" label="币种" width="90" />
          <el-table-column prop="paymentAmount" label="付款金额" width="140" />
          <el-table-column prop="plannedPaymentDate" label="计划付款日期" width="150" />
          <el-table-column prop="approvalStatus" label="审批状态" width="130"><template #default="{ row }">{{ display(row.approvalStatus) }}</template></el-table-column>
          <el-table-column prop="status" label="付款申请状态" width="120"><template #default="{ row }">{{ display(row.status) }}</template></el-table-column>
          <el-table-column label="操作" width="220" fixed="right">
            <template #default="{ row }"><el-button size="small" plain @click.stop="selectDetail(row)">查看付款申请</el-button></template>
          </el-table-column>
        </el-table>
      </BusinessTableScrollContainer>
      <p class="ctrl-f">Ctrl+F：{{ rows[0]?.requestNo || '付款申请编号' }}</p>
    </section>

    <section class="business-card boundary-card" data-acceptance-id="payment-request-process-boundary">
      <div class="section-heading"><h3>业务流程与后续边界</h3><strong>仅导航，不创建付款指令准备</strong></div>
      <div class="facts">
        <Fact label="当前模块" value="付款申请" />
        <Fact label="前置模块" value="付款申请准备" />
        <Fact label="下一模块" value="付款指令准备" />
        <Fact label="付款指令准备数量" :value="downstream.paymentInstructionPrepares || 0" />
      </div>
    </section>

    <section class="business-card boundary-card" data-acceptance-id="payment-request-zero-boundary">
      <div class="section-heading"><h3>下游零对象保护</h3><strong>paymentInstructionPrepareCreated=false</strong></div>
      <div class="facts">
        <Fact label="付款指令准备" :value="downstream.paymentInstructionPrepares || 0" />
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
import { paymentRequestApi } from '@/api/paymentRequest.js'
import { PAYMENT_REQUEST_VERSION } from '@/meta/runtime/paymentRequestRuntime.js'
import { displayPceFilterValue } from '@/meta/runtime/pceAdvancedFilterContract.js'
import { PAGE_OBSERVABILITY_ACTIONS_KEY } from '@/meta/runtime/pageObservabilityActions.js'
import { resolvePageNameConsumption } from '@/meta/governance/pageNameConsumer.js'
import { stateMachineFactsFromServer } from '@/meta/runtime/pceStateMachineFactContract.js'
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

defineProps({ embeddedInCommonShell: { type: Boolean, default: false } })
const VERSION = PAYMENT_REQUEST_VERSION
const FACT_LOAD_API_URL = '/api/finance/payment-requests/'
const display = displayPceFilterValue
const router = useRouter()
const pageName = resolvePageNameConsumption({ pageCode: 'payment-request', route: '/finance/payment-requests' })
const rows = ref([])
const current = ref(null)
const scenarioOverview = ref([])
const quickSearch = ref('')
const advancedVisible = ref(false)
const advancedFilters = reactive({
  requestNo: '',
  sourcePaymentRequestPrepareNo: '',
  supplierName: '',
  status: '',
  approvalStatus: '',
  currency: '',
})
const activeFilterCount = computed(() => (
  Number(Boolean(quickSearch.value.trim()))
  + Object.values(advancedFilters).filter(value => String(value || '').trim()).length
))
const selectedRows = ref([])
const tableRef = ref(null)
const capacity = reactive({})
const downstream = reactive({})
const factLoadFacts = ref(null)
const businessActionRevalidation = reactive({
  status: 'not_started',
  verifiedCount: 0,
  nextStepReadiness: 'not_started',
  serverDerived: false,
  businessWriteRequestCount: 0,
})
const observabilityActions = inject(PAGE_OBSERVABILITY_ACTIONS_KEY, null)
const Fact = defineComponent({
  props: { label: { type: String, required: true }, value: { type: [String, Number, Boolean], default: '-' } },
  setup: props => () => h('div', { class: 'fact' }, [h('span', props.label), h('strong', String(props.value ?? '-'))]),
})
const unwrap = response => response?.data?.data || response?.data || {}
const filteredRows = computed(() => {
  const q = quickSearch.value.trim().toLowerCase()
  return rows.value.filter((row) => {
    if (q && !JSON.stringify(row).toLowerCase().includes(q)) return false
    if (advancedFilters.requestNo && row.requestNo !== advancedFilters.requestNo) return false
    if (advancedFilters.sourcePaymentRequestPrepareNo && row.sourcePaymentRequestPrepareNo !== advancedFilters.sourcePaymentRequestPrepareNo) return false
    if (advancedFilters.supplierName && row.supplierName !== advancedFilters.supplierName) return false
    if (advancedFilters.status && row.status !== advancedFilters.status) return false
    if (advancedFilters.approvalStatus && row.approvalStatus !== advancedFilters.approvalStatus) return false
    if (advancedFilters.currency && row.currency !== advancedFilters.currency) return false
    return true
  })
})
async function refresh() {
  try {
    const loaded = readPceFactLoadEnvelope(
      await paymentRequestApi.list(),
      FACT_LOAD_API_URL,
    )
    factLoadFacts.value = loaded.factLoadFacts
    const data = loaded.data
    rows.value = (data.results || []).map((row) => ({
      ...row,
      ...stateMachineFactsFromServer(row, `payment-request-list:${row.requestNo}`),
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
    ElMessage.error(error?.message || '付款申请服务端读取失败')
  }
}
async function selectDetail(row) {
  const detail = unwrap(await paymentRequestApi.detail(row.id))
  current.value = {
    ...detail,
    ...stateMachineFactsFromServer(detail, `payment-request-detail:${detail.requestNo}`),
  }
}
async function revalidatePaymentInstructionPrepareEligibility(action) {
  const targets = action.selectedRows || []
  businessActionRevalidation.status = 'checking'
  businessActionRevalidation.verifiedCount = 0
  businessActionRevalidation.nextStepReadiness = 'checking'
  businessActionRevalidation.serverDerived = false
  try {
    const results = await Promise.all(targets.map(async (row) => (
      unwrap(await paymentRequestApi.eligibility(row.id))
    )))
    const passed = (
      results.length === targets.length
      && results.length > 0
      && results.every(item => (
        item.serverDerived === true
        && item.eligible === true
        && item.nextStepReadiness
          === 'ready_for_payment_instruction_prepare'
      ))
    )
    businessActionRevalidation.status = passed ? 'passed' : 'blocked'
    businessActionRevalidation.verifiedCount = results.length
    businessActionRevalidation.nextStepReadiness = passed
      ? 'ready_for_payment_instruction_prepare'
      : 'blocked'
    businessActionRevalidation.serverDerived = results.every(
      item => item.serverDerived === true,
    )
    if (!passed) {
      ElMessage({
        type: 'error',
        showClose: true,
        message: '服务端重新校验未通过，不能进入付款指令准备。',
      })
    }
    return passed
  } catch (error) {
    businessActionRevalidation.status = 'failed'
    businessActionRevalidation.nextStepReadiness = 'blocked'
    businessActionRevalidation.serverDerived = false
    ElMessage({
      type: 'error',
      showClose: true,
      message: error?.message || '付款指令准备资格服务端复核失败。',
    })
    return false
  }
}
function clearSelection() { tableRef.value?.clearSelection?.(); selectedRows.value = [] }
function clearSort() { tableRef.value?.clearSort?.(); clearSelection() }
function clearFilters() {
  quickSearch.value = ''
  Object.keys(advancedFilters).forEach(key => { advancedFilters[key] = '' })
  clearSelection()
}
function exportCurrent() {
  const fields = ['requestNo', 'sourcePaymentRequestPrepareNo', 'supplierName', 'currency', 'paymentAmount', 'approvalStatus', 'status']
  const csv = [fields.join(','), ...filteredRows.value.map(row => fields.map(field => `"${String(row[field] ?? '').replaceAll('"', '""')}"`).join(','))].join('\n')
  const link = document.createElement('a')
  link.href = URL.createObjectURL(new Blob([`\ufeff${csv}`], { type: 'text/csv;charset=utf-8;' }))
  link.download = 'payment-requests.csv'
  link.click()
  URL.revokeObjectURL(link.href)
}
function navigateNext() {
  router.push({ path: '/finance/payment-order-prepares', query: { sourcePaymentRequestNo: current.value?.requestNo, navigationOnly: 'true' } })
}
function buildDiagnostics() {
  const row = current.value || null
  const stateMachineFacts = row
    ? stateMachineFactsFromServer(row, `payment-request-diagnostic:${row.requestNo}`)
    : null
  return {
    version: VERSION,
    canonicalName: '付款申请',
    fullUrl: window.location.href,
    currentStateSource: 'server',
    ...factLoadFacts.value,
    factLoadFacts: factLoadFacts.value,
    resultCount: factLoadResultCount(factLoadFacts.value, rows.value.length),
    passed: factLoadPassed(factLoadFacts.value, Boolean(stateMachineFacts)),
    currentObject: row,
    formalRows: rows.value,
    stateMachineFacts,
    strictFacts: {
      currentStateSource: 'server',
      ...factLoadFacts.value,
      factLoadFacts: factLoadFacts.value,
      resultCount: factLoadResultCount(factLoadFacts.value, rows.value.length),
      passed: factLoadPassed(factLoadFacts.value, Boolean(stateMachineFacts)),
      formalObjectCount: factLoadResultCount(factLoadFacts.value, rows.value.length),
      ...(stateMachineFacts
        ? {
            status: row.status,
            eligibility: row.eligibility,
            ...stateMachineFacts,
          }
        : {}),
    },
    capacity: !factLoadFacts.value
      || factLoadFacts.value.factLoadStatus === 'read_failed'
      ? null
      : { ...capacity },
    downstreamCounts: { ...downstream },
    businessActionRevalidation: { ...businessActionRevalidation },
  }
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
.business-card { display: grid; gap: 14px; padding: 18px; border: 1px solid #dbe3ef; border-radius: 12px; background: #fff; }
.business-card h3, .business-card p { margin: 0; }
.capacity-card { border-color: #86efac; background: linear-gradient(135deg, #f0fdf4, #fff); }
.eligibility-card { border-color: #93c5fd; background: linear-gradient(135deg, #eff6ff, #fff); }
.boundary-card { border-color: #fdba74; background: #fffaf0; }
.facts { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; }
.advanced-filter-panel { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; padding: 10px; border: 1px solid #e2e8f0; border-radius: 8px; background: #f8fafc; }
.advanced-filter-panel label { display: grid; gap: 5px; color: #334155; font-size: 12px; font-weight: 800; }
:deep(.fact) { display: grid; gap: 5px; padding: 11px; border-radius: 8px; background: #f8fafc; }
:deep(.fact span) { color: #64748b; font-size: 12px; }
:deep(.fact strong) { color: #0f172a; overflow-wrap: anywhere; }
.passed { color: #15803d; }.blocked { color: #b45309; }.ctrl-f { color: #2563eb; font-size: 13px; font-weight: 800; }
</style>
