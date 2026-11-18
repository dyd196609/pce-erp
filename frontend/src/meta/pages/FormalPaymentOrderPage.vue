<template>
  <main class="formal-order-page" data-acceptance-id="formal-payment-order-business-content">
    <el-alert v-if="pageFacts?.factLoadStatus === 'read_failed'" type="error" title="服务端资料读取失败，数量未知；请检查登录身份后刷新。" :description="pageFacts.errorMessage" :closable="false" show-icon />
    <section class="business-card" data-acceptance-id="formal-payment-order-capacity">
      <Heading title="持久金丝雀容量" :note="pageFacts?.factLoadStatus === 'read_failed' ? '读取失败，数量未知' : `成功=${capacity.formalPaymentOrderCount} / 阻断=${capacity.blockedScenarioCount}`" />
      <div class="facts">
        <Fact label="风险评审来源" :value="capacity.sourceRiskReviewCount" />
        <Fact label="正式付款单" :value="capacity.formalPaymentOrderCount" />
        <Fact label="已准备" :value="capacity.preparedCount" />
        <Fact label="审批通过" :value="capacity.approvedCount" />
        <Fact label="已冻结" :value="capacity.frozenCount" />
        <Fact label="银行发送资格通过" :value="capacity.bankSendEligibleCount" />
        <Fact label="已消费" :value="capacity.nextStageConsumedCount" />
        <Fact label="阻断场景" :value="capacity.blockedScenarioCount" />
      </div>
      <p class="ctrl-f">Ctrl+F：持久金丝雀容量</p>
    </section>

    <section class="business-card" data-acceptance-id="formal-payment-order-object">
      <Heading title="正式付款单对象" :note="display(current?.status)" />
      <div class="facts">
        <Fact label="正式付款单编号" :value="current?.orderNo" />
        <Fact label="来源风险评审编号" :value="current?.sourceRiskReviewNo" />
        <Fact label="状态" :value="display(current?.status)" />
        <Fact label="供应商" :value="current?.supplierName" />
        <Fact label="币种" :value="current?.currency" />
        <Fact label="金额" :value="current?.amount" />
        <Fact label="计划执行日期" :value="current?.plannedExecutionDate" />
        <Fact label="当前状态来源" value="服务端" />
      </div>
      <p class="ctrl-f">Ctrl+F：正式付款单编号</p>
    </section>

    <section class="business-card" data-acceptance-id="formal-payment-order-approval-status">
      <Heading title="审批状态" note="复用共享 workflow_runtime，状态由服务端控制" />
      <div class="facts">
        <Fact label="审批状态" :value="display(current?.approvalStatus)" />
        <Fact label="状态机一致" :value="current?.stateMachineConsistent" />
        <Fact label="状态转换记录" :value="current?.statusTransitionCount" />
        <Fact label="流程实例编号" :value="current?.workflowInstance?.instanceNo" />
        <Fact label="当前审批节点" :value="current?.workflowInstance?.currentStep" />
        <Fact label="审批节点总数" :value="current?.workflowInstance?.totalSteps" />
        <Fact label="流程版本" :value="current?.workflowInstance?.version" />
        <Fact label="当前状态来源" value="服务端" />
      </div>
      <p class="ctrl-f">Ctrl+F：审批状态</p>
    </section>

    <section class="business-card" data-acceptance-id="formal-payment-order-approval-history">
      <Heading title="审批历史" :note="`审批节点=${current?.approvalHistory?.length || 0}`" />
      <el-table :data="current?.approvalHistory || []" border stripe>
        <el-table-column prop="stepNo" label="节点" width="90" />
        <el-table-column prop="taskNo" label="审批任务" min-width="240" />
        <el-table-column label="审批角色" min-width="170"><template #default="{ row }">{{ display(row.roleCode) }}</template></el-table-column>
        <el-table-column prop="actorName" label="审批人" min-width="180" />
        <el-table-column label="结论" width="120"><template #default="{ row }">{{ display(row.decision) }}</template></el-table-column>
        <el-table-column prop="createdAt" label="审批时间" min-width="220" />
      </el-table>
      <p class="ctrl-f">Ctrl+F：审批历史</p>
    </section>

    <section class="business-card" data-acceptance-id="formal-payment-order-freeze-status">
      <Heading title="执行冻结状态" note="冻结哈希保护金额、币种、账户、路线和执行日期" />
      <div class="facts">
        <Fact label="冻结状态" :value="display(current?.freezeStatus)" />
        <Fact label="冻结哈希" :value="current?.freezeHash" />
        <Fact label="冻结金额" :value="current?.freezeSnapshot?.amount" />
        <Fact label="冻结币种" :value="current?.freezeSnapshot?.currency" />
        <Fact label="付款账户" :value="current?.freezeSnapshot?.payerAccount" />
        <Fact label="收款账户" :value="current?.freezeSnapshot?.payeeAccount" />
        <Fact label="银行路线" :value="current?.freezeSnapshot?.bankRoute" />
        <Fact label="执行日期" :value="current?.freezeSnapshot?.executionDate" />
      </div>
      <p class="ctrl-f">Ctrl+F：执行冻结状态</p>
    </section>

    <section class="business-card" data-acceptance-id="formal-payment-order-bank-send-eligibility">
      <Heading title="银行发送资格" note="只计算资格；本版本不创建发送任务或银行报文" />
      <div class="facts">
        <Fact label="允许银行发送" :value="current?.bankSendEligibility?.readyForBankSend" />
        <Fact label="状态机事实一致" :value="current?.bankSendEligibility?.stateMachinePassed" />
        <Fact label="风险通过" :value="current?.bankSendEligibility?.riskPassed" />
        <Fact label="审批完成" :value="current?.bankSendEligibility?.approvalPassed" />
        <Fact label="冻结完成" :value="current?.bankSendEligibility?.freezePassed" />
        <Fact label="资金正常" :value="current?.bankSendEligibility?.fundsPassed" />
        <Fact label="银行能力正常" :value="current?.bankSendEligibility?.bankPassed" />
        <Fact label="签署能力正常" :value="current?.bankSendEligibility?.signaturePassed" />
        <Fact label="职责分离有效" :value="current?.bankSendEligibility?.segregationPassed" />
        <Fact label="银行发送任务" :value="current?.bankSendEligibility?.bankSendTaskCount" />
        <Fact label="银行报文" :value="current?.bankSendEligibility?.bankMessageCount" />
      </div>
      <p class="ctrl-f">Ctrl+F：银行发送资格</p>
    </section>

    <section class="business-card" data-acceptance-id="formal-payment-order-data">
      <Heading title="付款单资料" note="来自服务端持久化对象与不可变来源快照" />
      <div class="facts">
        <Fact label="法人" :value="current?.legalEntity" />
        <Fact label="账簿" :value="current?.ledgerBook" />
        <Fact label="来源草稿编号" :value="current?.sourcePaymentOrderDraftNo" />
        <Fact label="来源评审版本" :value="current?.sourceRiskReviewVersion" />
        <Fact label="风险规则版本" :value="current?.sourceRiskRuleVersion" />
        <Fact label="来源哈希" :value="shortHash(current?.sourceSnapshot?.sourceHash)" />
      </div>
      <p class="ctrl-f">Ctrl+F：付款单资料</p>
    </section>

    <section class="business-card" data-acceptance-id="formal-payment-order-evidence">
      <Heading title="资金与银行证据" note="全部由服务端 Provider 读取并持久化" />
      <div class="facts">
        <Fact label="资金证据" :value="evidenceState(current?.evidence?.funds)" />
        <Fact label="银行接口证据" :value="evidenceState(current?.evidence?.bankInterface)" />
        <Fact label="账户证据" :value="evidenceState(current?.evidence?.account)" />
        <Fact label="风险评审证据" :value="evidenceState(current?.evidence?.riskReview)" />
        <Fact label="职责分离证据" :value="evidenceState(current?.evidence?.segregation)" />
        <Fact label="证据哈希" :value="shortHash(current?.evidence?.evidenceHash)" />
      </div>
      <p class="ctrl-f">Ctrl+F：资金与银行证据</p>
    </section>

    <section class="business-card" data-acceptance-id="formal-payment-order-preview">
      <Heading title="正式付款单预览" note="只读预览，不执行银行发送或付款" />
      <div class="facts">
        <Fact label="只读" :value="current?.preview?.readonly" />
        <Fact label="已签署" :value="current?.preview?.signed" />
        <Fact label="已发送" :value="current?.preview?.sent" />
        <Fact label="已执行" :value="current?.preview?.executed" />
      </div>
      <p class="ctrl-f">Ctrl+F：正式付款单预览</p>
    </section>

    <section class="business-card" data-acceptance-id="formal-payment-order-audit">
      <Heading title="版本、幂等、审计" note="服务端事务提交后的当前事实" />
      <div class="facts">
        <Fact label="业务对象版本" :value="current?.version" />
        <Fact label="幂等状态" :value="display(current?.idempotencyStatus)" />
        <Fact label="编号状态" :value="display(current?.numberReservationStatus)" />
        <Fact label="事务状态" :value="display(current?.transactionStatus)" />
        <Fact label="审计状态" :value="display(current?.auditStatus)" />
        <Fact label="当前状态来源" value="服务端" />
      </div>
      <p class="ctrl-f">Ctrl+F：版本、幂等、审计</p>
    </section>

    <section class="business-card" data-acceptance-id="formal-payment-order-list-region">
      <Heading title="正式付款单标准列表" :note="`正式对象数量=${rows.length}`" />
      <StandardListToolbar
        page-id="formal-payment-order"
        table-id="formal-payment-orders-main"
        v-model:quick-search="quickSearch"
        placeholder="搜索正式付款单、风险评审、供应商或状态"
        :advanced-visible="advancedVisible"
        :result-count="filteredRows.length"
        :selected-count="selectedRows.length"
        :active-filter-count="activeFilterCount"
        :sort-text="sortText"
        @search="noop"
        @toggle-advanced="advancedVisible = !advancedVisible"
        @clear-filters="clearFilters"
        @clear-sort="clearSort"
        @export-current="exportOrders"
        @clear-selection="clearSelection"
      />
      <div
        v-show="advancedVisible"
        class="filter-grid list-advanced-filter-panel"
        data-acceptance-id="formal-payment-order-advanced-filter"
        data-pce-filter-for="formal-payment-orders-main"
      >
        <PceAdvancedFilterField
          v-for="field in filterSchema"
          :key="field.field"
          :field="field"
          :rows="rows"
          :model-value="filters[field.field]"
          @update:model-value="filters[field.field] = $event"
        />
      </div>
      <BusinessTableScrollContainer
        acceptance-id="business-table-scroll-formal-payment-orders-main"
        page-id="formal-payment-order"
        table-id="formal-payment-orders-main"
        min-width="1900px"
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
          @sort-change="updateSort"
        >
          <el-table-column type="selection" width="55" fixed="left" class-name="business-table-selection-column" />
          <el-table-column type="index" label="序号" width="65" fixed="left" class-name="pce-fixed-index-column" />
          <el-table-column prop="orderNo" label="正式付款单编号" width="220" fixed="left" sortable="custom" class-name="pce-fixed-primary-no-column" />
          <el-table-column prop="sourceRiskReviewNo" label="来源风险评审编号" width="220" />
          <el-table-column prop="supplierName" label="供应商" width="210" />
          <el-table-column prop="legalEntity" label="法人" width="180" />
          <el-table-column prop="ledgerBook" label="账簿" width="150" />
          <el-table-column prop="currency" label="币种" width="90" />
          <el-table-column prop="amount" label="付款金额" width="140" />
          <el-table-column prop="plannedExecutionDate" label="计划执行日期" width="150" />
          <el-table-column label="正式付款单状态" width="120"><template #default="{ row }">{{ display(row.status) }}</template></el-table-column>
          <el-table-column label="风险状态" width="120"><template #default="{ row }">{{ display(row.riskStatus) }}</template></el-table-column>
          <el-table-column label="风险等级" width="110"><template #default="{ row }">{{ display(row.riskLevel) }}</template></el-table-column>
          <el-table-column label="审批状态" width="130"><template #default="{ row }">{{ display(row.approvalStatus) }}</template></el-table-column>
          <el-table-column label="冻结状态" width="130"><template #default="{ row }">{{ display(row.freezeStatus) }}</template></el-table-column>
          <el-table-column label="银行发送资格" width="140"><template #default="{ row }">{{ display(row.bankSendEligibility?.readyForBankSend) }}</template></el-table-column>
          <el-table-column label="编号状态" width="120"><template #default="{ row }">{{ display(row.numberReservationStatus) }}</template></el-table-column>
          <el-table-column label="事务状态" width="120"><template #default="{ row }">{{ display(row.transactionStatus) }}</template></el-table-column>
          <el-table-column label="操作" width="690" fixed="right" class-name="payment-fixed-action-column">
            <template #default="{ row }">
              <div class="row-actions" data-acceptance-id="formal-payment-order-row-actions">
                <el-button data-action-id="view-formal-payment-order" size="small" plain @click.stop="viewFormalPaymentOrder(row)">查看正式付款单</el-button>
                <el-button data-action-id="view-source-risk-review" size="small" plain @click.stop="viewSourceRiskReview(row)">查看来源真实付款风险评审</el-button>
                <el-button data-action-id="copy-business-number" size="small" plain @click.stop="copyBusinessNumber(row)">复制业务编号</el-button>
                <el-button data-action-id="view-approval-history" size="small" plain @click.stop="viewApprovalHistory(row)">查看审批历史</el-button>
                <el-button v-if="row.businessActions?.canSubmit" data-action-id="submit-formal-payment-order" size="small" type="primary" @click.stop="submitApproval(row)">提交审批</el-button>
                <el-button v-if="row.businessActions?.canApprove" data-action-id="approve-formal-payment-order" size="small" type="success" @click.stop="approveCurrentTask(row)">审批</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </BusinessTableScrollContainer>
      <p class="ctrl-f">Ctrl+F：正式付款单标准列表</p>
    </section>

    <section class="business-card" data-acceptance-id="formal-payment-order-source">
      <Heading title="真实付款风险评审来源" note="唯一来源：服务端 PaymentRiskReview 权威对象" />
      <StandardListToolbar
        page-id="formal-payment-order"
        table-id="formal-payment-orders-source"
        v-model:quick-search="sourceSearch"
        placeholder="搜索风险评审编号、草稿编号或供应商"
        :advanced-visible="false"
        :result-count="filteredSources.length"
        :selected-count="0"
        :active-filter-count="0"
        sort-text="未排序"
        @search="noop"
        @toggle-advanced="noop"
        @clear-filters="sourceSearch = ''"
        @clear-sort="noop"
        @export-current="exportSources"
        @clear-selection="noop"
      />
      <BusinessTableScrollContainer
        acceptance-id="business-table-scroll-formal-payment-orders-source"
        page-id="formal-payment-order"
        table-id="formal-payment-orders-source"
        min-width="1300px"
      >
        <el-table :data="filteredSources" border stripe height="330" scrollbar-always-on row-key="id">
          <el-table-column type="index" label="序号" width="70" fixed="left" class-name="pce-fixed-index-column" />
          <el-table-column prop="reviewNo" label="风险评审编号" width="220" fixed="left" class-name="pce-fixed-primary-no-column" />
          <el-table-column prop="sourcePaymentOrderDraftNo" label="来源正式付款单草稿" width="230" />
          <el-table-column prop="supplierName" label="供应商" width="220" />
          <el-table-column prop="currency" label="币种" width="90" />
          <el-table-column prop="amount" label="付款金额" width="150" />
          <el-table-column label="评审状态" width="130"><template #default="{ row }">{{ display(row.status) }}</template></el-table-column>
          <el-table-column label="风险等级" width="110"><template #default="{ row }">{{ display(row.riskLevel) }}</template></el-table-column>
          <el-table-column label="操作" width="150" fixed="right" class-name="payment-fixed-action-column">
            <template #default="{ row }">
              <router-link class="source-link" :to="`/finance/payment-risk-review/${row.id}`">查看来源风险评审</router-link>
            </template>
          </el-table-column>
        </el-table>
      </BusinessTableScrollContainer>
      <p class="ctrl-f">Ctrl+F：真实付款风险评审来源</p>
    </section>

    <section class="business-card" data-acceptance-id="formal-payment-order-zero-boundary">
      <Heading title="下游零对象保护" note="本版本停止在银行发送前最终门禁" />
      <div class="facts">
        <Fact v-for="(value, key) in downstream" :key="key" :label="downstreamLabel(key)" :value="value" />
      </div>
      <p class="boundary-note">未生成银行报文、未发送银行、未执行付款、未生成凭证、未核销、未写总账、未过账。</p>
      <p class="ctrl-f">Ctrl+F：下游零对象保护</p>
    </section>
  </main>
</template>

<script setup>
import { computed, defineComponent, h, inject, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { formalPaymentOrderApi } from '@/api/formalPaymentOrder.js'
import {
  FORMAL_PAYMENT_ORDER_FILTER_SCHEMA,
  FORMAL_PAYMENT_ORDER_MODULE,
  FORMAL_PAYMENT_ORDER_VERSION,
  createFormalPaymentOrderPageFacts,
  formalPaymentOrderDisplayValue,
} from '@/meta/runtime/formalPaymentOrderRuntime.js'
import { assertStatusTransitionCountMatchesHistory } from '@/meta/runtime/pceStateMachineFactContract.js'
import { PAGE_OBSERVABILITY_ACTIONS_KEY } from '@/meta/runtime/pageObservabilityActions.js'
import { factLoadFailureFromError } from '@/meta/runtime/pceFactLoadContract.js'
import BusinessTableScrollContainer from '../components/BusinessTableScrollContainer.vue'
import PceAdvancedFilterField from '../components/PceAdvancedFilterField.vue'
import StandardListToolbar from '../components/StandardListToolbar.vue'

defineProps({ embeddedInCommonShell: { type: Boolean, default: false } })
const rows = ref([])
const sources = ref([])
const current = ref(null)
const pageFacts = ref(null)
const quickSearch = ref('')
const sourceSearch = ref('')
const advancedVisible = ref(false)
const selectedRows = ref([])
const tableRef = ref(null)
const sortState = reactive({ prop: '', order: '' })
const router = useRouter()
const filterSchema = FORMAL_PAYMENT_ORDER_FILTER_SCHEMA
const filters = reactive(Object.fromEntries(filterSchema.map(field => [field.field, ''])))
const capacity = computed(() => pageFacts.value?.capacity || {})
const downstream = computed(() => pageFacts.value?.downstreamCounts || {})
const activeFilterCount = computed(() => Object.values(filters).filter(value => String(value || '').trim()).length)
const sortText = computed(() => !sortState.prop || !sortState.order
  ? '未排序'
  : `正式付款单编号${sortState.order === 'descending' ? '降序' : '升序'}`)
const observability = inject(PAGE_OBSERVABILITY_ACTIONS_KEY, null)
const display = formalPaymentOrderDisplayValue
const noop = () => {}

const filteredSources = computed(() => {
  const keyword = sourceSearch.value.trim().toLowerCase()
  return sources.value.filter(row => (
    !keyword || [
      row.reviewNo,
      row.sourcePaymentOrderDraftNo,
      row.supplierName,
    ].join(' ').toLowerCase().includes(keyword)
  ))
})

const filteredRows = computed(() => {
  const keyword = quickSearch.value.trim().toLowerCase()
  const values = rows.value.filter(row => {
    const searchable = [
      row.orderNo,
      row.sourceRiskReviewNo,
      row.supplierName,
      row.legalEntity,
      row.ledgerBook,
      row.scenarioCode,
      row.status,
    ].join(' ').toLowerCase()
    const amount = Number(row.amount || 0)
    return (!keyword || searchable.includes(keyword))
      && (!filters.orderNo || row.orderNo.includes(String(filters.orderNo).trim()))
      && (!filters.sourceRiskReviewNo || row.sourceRiskReviewNo.includes(String(filters.sourceRiskReviewNo).trim()))
      && (!filters.supplierName || row.supplierName === filters.supplierName)
      && (!filters.legalEntity || row.legalEntity === filters.legalEntity)
      && (!filters.ledgerBook || row.ledgerBook === filters.ledgerBook)
      && (!filters.currency || row.currency === filters.currency)
      && (!filters.status || row.status === filters.status)
      && (!filters.riskStatus || row.riskStatus === filters.riskStatus)
      && (!filters.riskLevel || row.riskLevel === filters.riskLevel)
      && (!filters.amountMin || amount >= Number(filters.amountMin))
      && (!filters.amountMax || amount <= Number(filters.amountMax))
      && (!filters.executionDateFrom || row.plannedExecutionDate >= filters.executionDateFrom)
      && (!filters.executionDateTo || row.plannedExecutionDate <= filters.executionDateTo)
      && (!filters.scenarioCode || row.scenarioCode === filters.scenarioCode)
  })
  if (!sortState.prop || !sortState.order) return values
  const direction = sortState.order === 'descending' ? -1 : 1
  return [...values].sort((left, right) => String(left?.[sortState.prop] ?? '').localeCompare(
    String(right?.[sortState.prop] ?? ''),
    'zh-Hans-CN',
    { numeric: true },
  ) * direction)
})

function selectDetail(row) { current.value = row }
async function viewFormalPaymentOrder(row) {
  selectDetail(row)
  await nextTick()
  document.querySelector('[data-acceptance-id="formal-payment-order-object"]')?.scrollIntoView({
    behavior: 'smooth',
    block: 'start',
  })
}
function viewSourceRiskReview(row) {
  router.push(`/finance/payment-risk-review/${row.sourceRiskReviewId}`)
}
async function viewApprovalHistory(row) {
  selectDetail(row)
  await nextTick()
  document.querySelector('[data-acceptance-id="formal-payment-order-approval-history"]')?.scrollIntoView({
    behavior: 'smooth',
    block: 'start',
  })
}
function actionKey(prefix, row) {
  const entropy = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${row.id}`
  return `${prefix}-${row.orderNo}-${entropy}`
}
async function submitApproval(row) {
  await formalPaymentOrderApi.submit(row.id, {
    idempotencyKey: actionKey('FPO-SUBMIT', row),
    expectedVersion: row.version,
    explicitUserAction: true,
  })
  await refresh()
}
async function approveCurrentTask(row) {
  const task = (row.approvalTasks || []).find(item => item.status === 'pending')
  if (!task) return
  await formalPaymentOrderApi.approve(row.id, {
    taskId: task.id,
    idempotencyKey: actionKey('FPO-APPROVE', row),
    expectedOrderVersion: row.version,
    expectedWorkflowVersion: row.workflowInstance?.version,
    expectedTaskVersion: task.version,
    explicitUserAction: true,
    comment: '页面受控审批',
  })
  await refresh()
}
async function copyBusinessNumber(row) {
  await navigator.clipboard.writeText(row.orderNo)
}
function evidenceState(value) { return value && Object.keys(value).length ? '已持久化' : '缺失' }
function shortHash(value) { return value ? `${String(value).slice(0, 12)}…` : '-' }
function clearFilters() {
  quickSearch.value = ''
  Object.keys(filters).forEach(key => { filters[key] = '' })
}
function clearSort() {
  Object.assign(sortState, { prop: '', order: '' })
  tableRef.value?.clearSort()
}
function updateSort({ prop = '', order = '' } = {}) { Object.assign(sortState, { prop, order: order || '' }) }
function clearSelection() {
  tableRef.value?.clearSelection()
  selectedRows.value = []
}
function exportCsv(name, values, projector) {
  const payload = values.map(projector)
  const keys = Object.keys(payload[0] || {})
  const csv = [keys, ...payload.map(row => keys.map(key => row[key]))]
    .map(line => line.map(value => `"${String(value ?? '').replaceAll('"', '""')}"`).join(',')).join('\r\n')
  const link = document.createElement('a')
  link.href = URL.createObjectURL(new Blob([`\ufeff${csv}`], { type: 'text/csv;charset=utf-8' }))
  link.download = name
  link.click()
  URL.revokeObjectURL(link.href)
}
function exportSources() {
  exportCsv('formal-payment-order-sources.csv', filteredSources.value, row => ({
    riskReviewNo: row.reviewNo,
    sourcePaymentOrderDraftNo: row.sourcePaymentOrderDraftNo,
    supplierName: row.supplierName,
    status: display(row.status),
  }))
}
function exportOrders() {
  exportCsv('formal-payment-orders.csv', filteredRows.value, row => ({
    orderNo: row.orderNo,
    sourceRiskReviewNo: row.sourceRiskReviewNo,
    supplierName: row.supplierName,
    currency: row.currency,
    amount: row.amount,
    status: display(row.status),
  }))
}
function downstreamLabel(key) {
  return {
    bankMessages: '银行报文',
    bankSendTasks: '银行发送任务',
    paymentExecutions: '付款执行',
    paymentVouchers: '付款凭证',
    writeoffs: '核销',
    ledgerEntries: '总账',
    postings: '过账',
    bankTransactions: '银行流水',
  }[key] || key
}
async function refresh() {
  try {
    const response = await formalPaymentOrderApi.list()
    const facts = createFormalPaymentOrderPageFacts(response)
    pageFacts.value = facts
    rows.value = facts.rows
    sources.value = facts.sources
    const selectedNo = current.value?.orderNo
    current.value = rows.value.find(row => row.orderNo === selectedNo) || rows.value[0] || null
  } catch (error) {
    const failed = factLoadFailureFromError(
      error,
      '/api/finance/formal-payment-orders/',
      pageFacts.value?.factLoadFacts,
    )
    pageFacts.value = createFormalPaymentOrderPageFacts({
      data: { factLoadFacts: failed },
    })
    rows.value = []
    sources.value = []
    current.value = null
  }
}
function buildDiagnostics() {
  const facts = pageFacts.value
  if (!facts) throw new Error('fact_load_not_completed')
  const currentFacts = current.value
  if (currentFacts) {
    assertStatusTransitionCountMatchesHistory(
      currentFacts,
      'formal-payment-order:diagnostic',
    )
    assertStatusTransitionCountMatchesHistory(
      facts.strictServerFacts,
      'formal-payment-order:diagnostic:strictServerFacts',
    )
  }
  return {
    version: FORMAL_PAYMENT_ORDER_VERSION,
    pageCode: FORMAL_PAYMENT_ORDER_MODULE.pageCode,
    moduleCode: FORMAL_PAYMENT_ORDER_MODULE.moduleCode,
    canonicalName: FORMAL_PAYMENT_ORDER_MODULE.canonicalName,
    tenantId: facts.tenantId,
    canaryBatchId: facts.canaryBatchId,
    currentStateSource: 'server',
    ...facts.factLoadFacts,
    factLoadFacts: facts.factLoadFacts,
    passed: facts.passed,
    sourceRiskReviewCount: facts.capacity.sourceRiskReviewCount,
    formalPaymentOrderCount: facts.capacity.formalPaymentOrderCount,
    preparedCount: facts.capacity.preparedCount,
    approvedCount: facts.capacity.approvedCount,
    frozenCount: facts.capacity.frozenCount,
    bankSendEligibleCount: facts.capacity.bankSendEligibleCount,
    blockedScenarioCount: facts.capacity.blockedScenarioCount,
    nextStageConsumedCount: facts.capacity.nextStageConsumedCount,
    resultCount: facts.resultCount,
    currentObject: current.value,
    selectedObject: current.value,
    scenarioCode: current.value?.scenarioCode || '',
    sourceScenarioCode: current.value?.sourceScenarioCode || '',
    scenarioCodes: facts.rows.map(row => row.scenarioCode),
    sourceObjects: facts.sourceObjects,
    fundEvidence: current.value?.evidence?.funds || {},
    bankEvidence: current.value?.evidence?.bankInterface || {},
    eligibility: current.value?.eligibility || {},
    approvalStatus: current.value?.approvalStatus || 'not_started',
    statusTransitionHistory: currentFacts?.statusTransitionHistory,
    statusTransitionCount: currentFacts?.statusTransitionCount,
    stateMachineConsistent: current.value?.stateMachineConsistent === true,
    workflowInstance: current.value?.workflowInstance || {},
    approvalHistory: current.value?.approvalHistory || [],
    freezeStatus: current.value?.freezeStatus || 'not_frozen',
    freezeHash: current.value?.freezeHash || '',
    bankSendEligibility: current.value?.bankSendEligibility || {},
    executionGateFacts: current.value?.executionGateFacts || {},
    downstreamCounts: facts.downstreamCounts,
    strictServerFacts: facts.strictServerFacts,
  }
}
onMounted(async () => {
  await refresh()
  observability?.register({ refresh, buildDiagnostics })
})
onBeforeUnmount(() => observability?.unregister())

const Heading = defineComponent({
  props: { title: String, note: String },
  setup: props => () => h('header', { class: 'card-heading' }, [
    h('h2', props.title),
    props.note ? h('span', props.note) : null,
  ]),
})
const Fact = defineComponent({
  props: { label: String, value: [String, Number, Boolean, Array] },
  setup: props => () => h('div', { class: 'fact' }, [
    h('span', props.label),
    h('strong', display(props.value)),
  ]),
})
</script>

<style scoped>
.formal-order-page { display: grid; gap: 16px; min-width: 0; }
.business-card { border: 1px solid #dbe3ec; border-radius: 12px; padding: 16px; background: #fff; min-width: 0; }
.card-heading { display: flex; justify-content: space-between; gap: 16px; align-items: center; margin-bottom: 14px; }
.card-heading h2 { margin: 0; color: #0f172a; font-size: 18px; }
.card-heading span { color: #475569; font-size: 13px; }
.facts { display: grid; grid-template-columns: repeat(auto-fit, minmax(205px, 1fr)); gap: 10px; }
.fact { display: grid; gap: 5px; padding: 10px; border: 1px solid #e2e8f0; border-radius: 8px; min-width: 0; }
.fact span { color: #64748b; font-size: 13px; }
.fact strong { color: #0f172a; overflow-wrap: anywhere; }
.filter-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; padding: 12px; border: 1px solid #dfe6ee; background: #f8fafc; }
.ctrl-f { margin: 12px 0 0; color: #64748b; font-size: 12px; }
.boundary-note { color: #9f1239; font-weight: 700; }
.source-link { color: #1d4ed8; text-decoration: none; font-weight: 700; }
.row-actions { display: flex; align-items: center; gap: 8px; white-space: nowrap; }
</style>
