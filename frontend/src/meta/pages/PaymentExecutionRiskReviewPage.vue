<template>
  <main class="payment-risk-review-page">
    <header class="page-header">
      <section>
        <p class="eyebrow">V1.12.9 真实付款风险评审</p>
        <h1>{{ detail ? '真实付款风险评审详情' : '真实付款风险评审' }}</h1>
        <p>本页只评审真实付款前的风险，不执行真实付款，不连接银行，不生成银行流水，不生成财务凭证，不写总账。</p>
        <p class="finance-current-module-badge">当前操作模块：真实付款风险评审</p>
      </section>
      <nav class="page-tabs finance-flow-nav" aria-label="财务前置流程导航">
        <span class="finance-nav-title">财务前置流程导航</span>
        <router-link class="finance-nav-button" to="/finance/payable-prepares">应付预备</router-link>
        <router-link class="finance-nav-button" to="/finance/payable-checks">应付核对</router-link>
        <router-link class="finance-nav-button" to="/finance/invoice-prepares">发票预备</router-link>
        <router-link class="finance-nav-button" to="/finance/ap-drafts">应付账款草稿</router-link>
        <router-link class="finance-nav-button" to="/finance/payment-drafts">供应商付款草稿</router-link>
        <router-link class="finance-nav-button" to="/finance/payment-prepares">正式付款单预备</router-link>
        <router-link class="finance-nav-button" to="/finance/payment-order-drafts">正式付款单草稿</router-link>
        <router-link class="finance-nav-button finance-nav-button-active" to="/finance/payment-risk-reviews">真实付款风险评审<span class="finance-current-tag">当前</span></router-link>
      </nav>
    </header>

    <el-alert v-if="message" :title="message" :type="messageType" show-icon :closable="false" />

    <section v-if="detail" class="operation-shell">
      <section class="plain-flow-guide">
        <strong>真实付款风险评审流程：正式付款单草稿 -> 真实付款风险评审 -> 后续真实付款模块</strong>
        <div class="plain-flow-grid">
          <span><b>当前步骤</b>真实付款前风险识别。</span>
          <span><b>本页只做</b>检查付款资料、模拟银行信息、来源链路、重复付款和财务边界。</span>
          <span><b>下一步做什么</b>评审通过后，后续真实付款模块仍需独立审批。</span>
          <span><b>本页不会做</b>不真实付款、不连接银行、不生成流水、不生成凭证、不写总账、不做核销。</span>
        </div>
      </section>

      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>{{ detail.riskReviewNo }}</h2>
              <span>{{ detail.sourcePaymentOrderDraftNo || '-' }} / {{ detail.supplierName || '-' }}</span>
            </div>
            <div class="button-row">
              <el-button @click="router.push('/finance/payment-risk-reviews')">返回列表</el-button>
              <el-button @click="router.push(`/finance/payment-order-draft/${detail.sourcePaymentOrderDraftId}`)">查看正式付款单草稿</el-button>
              <el-button type="primary" @click="rerunReview(detail)">重新评审</el-button>
              <el-button v-if="canManualPass(detail)" type="success" @click="markPassed(detail)">标记评审通过</el-button>
              <el-button v-if="canManualBlock(detail)" type="warning" @click="markBlocked(detail)">标记评审阻断</el-button>
              <el-button v-if="canCancelRiskReview(detail)" type="danger" @click="cancelReview(detail)">取消风险评审</el-button>
            </div>
          </div>
        </template>
        <div class="info-grid">
          <article v-for="item in detailFields" :key="item.label">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </article>
        </div>
        <el-alert
          v-if="detail.riskReviewStatus === 'passed'"
          title="当前状态：评审通过。该状态表示本评审已通过，但本页仍未执行真实付款。"
          type="success"
          show-icon
          :closable="false"
        />
      </el-card>

      <el-card shadow="never">
        <template #header><h2>风险检查项</h2></template>
        <el-table :data="detail.reviewItems || []" border stripe height="430">
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="label" label="检查项" min-width="180" />
          <el-table-column prop="result" label="结果" width="120">
            <template #default="{ row }"><el-tag :type="reviewItemType(row)">{{ reviewItemLabel(row) }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="severity" label="级别" width="110">
            <template #default="{ row }">{{ severityLabel(row.severity) }}</template>
          </el-table-column>
          <el-table-column prop="message" label="说明 / 阻断原因" min-width="280" />
          <el-table-column prop="suggestion" label="处理建议" min-width="320" fixed="right" />
        </el-table>
      </el-card>
    </section>

    <section v-else class="operation-shell">
      <section class="plain-flow-guide">
        <strong>真实付款风险评审流程：正式付款单草稿 -> 真实付款风险评审 -> 后续真实付款模块</strong>
        <div class="plain-flow-grid">
          <span><b>本页不会做</b>不执行真实付款、不连接银行、不生成银行流水。</span>
          <span><b>本页不会做</b>不生成财务凭证、不写总账、不做付款核销。</span>
          <span><b>本页只做</b>识别付款资料、模拟银行信息、来源链路和重复付款风险。</span>
          <span><b>模拟数据</b>只要检测到模拟银行信息，风险评审必须阻断。</span>
        </div>
      </section>

      <section class="plain-flow-guide">
        <strong>风险评审状态与操作说明</strong>
        <div class="plain-flow-grid">
          <span><b>评审通过</b>可进入后续真实付款模块，但不是已付款。</span>
          <span><b>评审阻断</b>必须处理阻断原因后重新评审。</span>
          <span><b>有警告</b>可人工确认后通过，但需保留风险说明。</span>
          <span><b>已取消</b>需重新发起评审。</span>
          <span><b>查看详情</b>查看风险评审明细。</span>
          <span><b>重新评审</b>重新执行风险规则。</span>
          <span><b>取消风险评审</b>取消当前评审记录，需要重新发起。</span>
        </div>
      </section>

      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>来源正式付款单草稿</h2>
              <span>仅展示 paymentReady / 可进入真实付款的正式付款单草稿。</span>
            </div>
            <div class="button-row">
              <el-button type="primary" @click="refresh">刷新来源</el-button>
              <el-button @click="router.push('/finance/payment-order-drafts')">查看正式付款单草稿</el-button>
            </div>
          </div>
        </template>
        <div class="batch-bar">
          <span>已选择 {{ selectedSourceRows.length }} 条</span>
          <span class="sort-help">{{ sourceSortText }}</span>
          <el-button size="small" @click="resetSourceSorting">清除排序</el-button>
          <el-button size="small" @click="clearSourceSelection">清空选择</el-button>
          <span class="batch-action-title">当前模块操作（只生成风险评审）</span>
          <span class="batch-action-tip">以下按钮只评审风险，不执行真实付款、不连接银行、不生成凭证。</span>
          <el-button size="small" type="primary" :disabled="!sourceIds.length" @click="runBatchSourceReview">批量执行风险评审</el-button>
        </div>
        <BatchResult v-if="sourceBatchResult" :result="sourceBatchResult" :type="sourceBatchResultType" @close="sourceBatchResult = null" />
        <el-table ref="sourceTableRef" :data="sortedSourceRows" border stripe height="470" @selection-change="handleSourceSelectionChange" @sort-change="handleSourceSortChange">
          <el-table-column type="selection" width="48" fixed="left" />
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="paymentOrderDraftNo" label="正式付款单草稿号" min-width="180" sortable="custom" />
          <el-table-column prop="sourcePaymentPrepareNo" label="来源付款预备" min-width="170" sortable="custom" />
          <el-table-column prop="sourcePaymentDraftNo" label="来源供应商付款草稿" min-width="180" />
          <el-table-column prop="supplierName" label="供应商" min-width="150" sortable="custom" />
          <el-table-column prop="paymentAccount" label="付款账户" min-width="150" />
          <el-table-column prop="supplierBankAccount" label="收款账户" min-width="170" />
          <el-table-column prop="confirmedPayAmount" label="确认付款金额" width="140" sortable="custom" />
          <el-table-column prop="paymentOrderStatus" label="付款状态" width="150" sortable="custom">
            <template #default="{ row }"><el-tag :type="paymentOrderStatusType(row.paymentOrderStatus)">{{ paymentOrderStatusLabel(row.paymentOrderStatus) }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="voucherStatus" label="凭证状态" width="130">
            <template #default="{ row }">{{ voucherStatusLabel(row.voucherStatus) }}</template>
          </el-table-column>
          <el-table-column prop="bankInfoMocked" label="模拟银行信息" width="140">
            <template #default="{ row }"><el-tag :type="row.bankInfoMocked ? 'danger' : 'success'">{{ row.bankInfoMocked ? '是' : '否' }}</el-tag></template>
          </el-table-column>
          <el-table-column label="是否可评审" width="120">
            <template #default="{ row }"><el-tag :type="row.canRunRiskReview ? 'success' : 'info'">{{ row.canRunRiskReview ? '可评审' : '不可评审' }}</el-tag></template>
          </el-table-column>
          <el-table-column label="操作" fixed="right" :width="sourceActionColumnWidth">
            <template #default="{ row }">
              <div class="app-action-cell">
                <el-button size="small" class="app-action-button-md" type="primary" @click="runSourceReview(row)">执行风险评审</el-button>
                <el-button size="small" class="app-action-button-lg" @click="router.push(`/finance/payment-order-draft/${row.id}`)">查看付款单草稿</el-button>
                <el-button v-if="row.riskReviewId" size="small" class="app-action-button-md" type="success" @click="router.push(`/finance/payment-risk-review/${row.riskReviewId}`)">查看评审</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>风险评审结果列表</h2></template>
        <div class="batch-bar">
          <span>已选择 {{ selectedReviewRows.length }} 条</span>
          <span class="sort-help">{{ reviewSortText }}</span>
          <el-button size="small" @click="resetReviewSorting">清除排序</el-button>
          <el-button size="small" @click="clearReviewSelection">清空选择</el-button>
          <span class="batch-action-title">当前模块操作（评审记录）</span>
          <span class="batch-action-tip">可批量重新评审或取消评审；不支持批量真实付款、银行支付或生成凭证。</span>
          <el-button size="small" type="primary" :disabled="!reviewIds.length" @click="runBatchReviewAgain">批量重新评审</el-button>
          <el-button size="small" type="danger" :disabled="!reviewIds.length" @click="runBatchCancelReview">批量取消风险评审</el-button>
        </div>
        <BatchResult v-if="reviewBatchResult" :result="reviewBatchResult" :type="reviewBatchResultType" @close="reviewBatchResult = null" />
        <el-table ref="reviewTableRef" :data="sortedReviewRows" border stripe height="470" @selection-change="handleReviewSelectionChange" @sort-change="handleReviewSortChange">
          <el-table-column type="selection" width="48" fixed="left" />
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="riskReviewNo" label="风险评审编号" min-width="170" sortable="custom" />
          <el-table-column prop="sourcePaymentOrderDraftNo" label="来源付款单草稿" min-width="180" sortable="custom" />
          <el-table-column prop="supplierName" label="供应商" min-width="150" sortable="custom" />
          <el-table-column prop="confirmedPayAmount" label="付款金额" width="130" sortable="custom" />
          <el-table-column prop="riskLevel" label="风险等级" width="130" sortable="custom">
            <template #default="{ row }"><el-tag :type="riskLevelType(row.riskLevel)">{{ riskLevelLabel(row.riskLevel) }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="riskReviewStatus" label="评审状态" width="130" sortable="custom">
            <template #default="{ row }"><el-tag :type="riskReviewStatusType(row.riskReviewStatus)">{{ riskReviewStatusLabel(row.riskReviewStatus) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="阻断原因" min-width="260">
            <template #default="{ row }">{{ reasonText(row.blockingReasons) }}</template>
          </el-table-column>
          <el-table-column label="操作" fixed="right" :width="reviewActionColumnWidth">
            <template #default="{ row }">
              <div class="app-action-cell">
                <el-button size="small" class="app-action-button-sm" @click="router.push(`/finance/payment-risk-review/${row.id}`)">查看详情</el-button>
                <el-button size="small" class="app-action-button-md" type="primary" @click="rerunReview(row)">重新评审</el-button>
                <el-button v-if="canManualPass(row)" size="small" class="app-action-button-md" type="success" @click="markPassed(row)">标记通过</el-button>
                <el-button v-if="canManualBlock(row)" size="small" class="app-action-button-md" type="warning" @click="markBlocked(row)">标记阻断</el-button>
                <el-button v-if="canCancelRiskReview(row)" size="small" class="app-action-button-lg" type="danger" @click="cancelReview(row)">取消风险评审</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </section>
  </main>
</template>

<script setup>
import { computed, defineComponent, h, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  batchCancelPaymentExecutionRiskReviews,
  batchRerunPaymentExecutionRiskReviews,
  batchRunPaymentExecutionRiskReviews,
  cancelPaymentExecutionRiskReview,
  getPaymentExecutionRiskReviewById,
  getPaymentRiskReviewSources,
  listPaymentExecutionRiskReviews,
  markPaymentExecutionRiskReviewBlocked,
  markPaymentExecutionRiskReviewPassed,
  rerunPaymentExecutionRiskReview,
  runPaymentExecutionRiskReview,
} from '../finance/paymentExecutionRiskReviewStore.js'
import { getActionColumnWidthForRows } from '../runtime/tableActionColumnEngine.js'
import { sortRecords } from '../runtime/tableSortEngine.js'

const BatchResult = defineComponent({
  props: { result: { type: Object, required: true }, type: { type: String, default: 'success' } },
  emits: ['close'],
  setup(props, { emit }) {
    return () => h('div', { class: ['batch-result', props.type] }, [
      h('button', { type: 'button', onClick: () => emit('close') }, '关闭'),
      h('strong', '批量风险评审完成'),
      h('span', `已选择：${props.result.total} 条`),
      h('span', `通过：${props.result.successCount} 条`),
      props.result.alreadyDoneCount ? h('span', `已达成：${props.result.alreadyDoneCount} 条`) : null,
      h('span', `警告：${props.result.warningCount} 条`),
      h('span', `阻断：${props.result.blockedCount} 条`),
      h('span', `失败：${props.result.failedCount} 条`),
      props.result.failedReason?.length ? h('ol', props.result.failedReason.map((reason) => h('li', { key: reason }, reason))) : null,
      props.result.nextSuggestion ? h('span', `下一步建议：${props.result.nextSuggestion}`) : null,
    ])
  },
})

const route = useRoute()
const router = useRouter()
const sourceRows = ref([])
const reviewRows = ref([])
const selectedSourceRows = ref([])
const selectedReviewRows = ref([])
const sourceSortState = ref({ key: '', direction: 'asc' })
const reviewSortState = ref({ key: '', direction: 'asc' })
const sourceTableRef = ref(null)
const reviewTableRef = ref(null)
const message = ref('')
const messageType = ref('success')
const sourceBatchResult = ref(null)
const sourceBatchResultType = ref('success')
const reviewBatchResult = ref(null)
const reviewBatchResultType = ref('success')

const detail = computed(() => route.params.id ? getPaymentExecutionRiskReviewById(route.params.id) : null)
const sourceIds = computed(() => selectedSourceRows.value.map((row) => row.id).filter(Boolean))
const reviewIds = computed(() => selectedReviewRows.value.map((row) => row.id).filter(Boolean))
const sourceSortColumns = [
  { key: 'paymentOrderDraftNo', sortType: 'string' },
  { key: 'sourcePaymentPrepareNo', sortType: 'string' },
  { key: 'supplierName', sortType: 'string' },
  { key: 'confirmedPayAmount', sortType: 'amount' },
  { key: 'paymentOrderStatus', sortType: 'status' },
]
const reviewSortColumns = [
  { key: 'riskReviewNo', sortType: 'string' },
  { key: 'sourcePaymentOrderDraftNo', sortType: 'string' },
  { key: 'supplierName', sortType: 'string' },
  { key: 'confirmedPayAmount', sortType: 'amount' },
  { key: 'riskLevel', sortType: 'status' },
  { key: 'riskReviewStatus', sortType: 'status' },
]
const sortedSourceRows = computed(() => sortRecords(sourceRows.value, sourceSortState.value, sourceSortColumns))
const sortedReviewRows = computed(() => sortRecords(reviewRows.value, reviewSortState.value, reviewSortColumns))
const sourceActionColumnWidth = computed(() => getActionColumnWidthForRows(sortedSourceRows.value, sourceRowActions, ['执行风险评审', '查看付款单草稿']))
const reviewActionColumnWidth = computed(() => getActionColumnWidthForRows(sortedReviewRows.value, reviewRowActions, ['查看详情', '重新评审', '标记通过', '标记阻断', '取消风险评审']))
const sourceSortText = computed(() => currentSortText(sourceSortState.value, {
  paymentOrderDraftNo: '正式付款单草稿号',
  sourcePaymentPrepareNo: '来源付款预备',
  supplierName: '供应商',
  confirmedPayAmount: '确认付款金额',
  paymentOrderStatus: '付款状态',
}))
const reviewSortText = computed(() => currentSortText(reviewSortState.value, {
  riskReviewNo: '风险评审编号',
  sourcePaymentOrderDraftNo: '来源付款单草稿',
  supplierName: '供应商',
  confirmedPayAmount: '付款金额',
  riskLevel: '风险等级',
  riskReviewStatus: '评审状态',
}))
const detailFields = computed(() => detail.value ? [
  { label: '风险评审编号', value: detail.value.riskReviewNo },
  { label: '来源付款单草稿', value: detail.value.sourcePaymentOrderDraftNo || '-' },
  { label: '来源付款预备', value: detail.value.sourcePaymentPrepareNo || '-' },
  { label: '来源供应商付款草稿', value: detail.value.sourcePaymentDraftNo || '-' },
  { label: '来源应付草稿', value: detail.value.sourceApDraftNo || '-' },
  { label: '来源发票预备', value: detail.value.sourceInvoicePrepareNo || '-' },
  { label: '来源应付核对', value: detail.value.sourcePayableCheckNo || '-' },
  { label: '来源采购订单', value: detail.value.sourcePurchaseOrderNo || '-' },
  { label: '供应商', value: detail.value.supplierName || '-' },
  { label: '付款银行', value: detail.value.paymentBankName || '-' },
  { label: '付款账户', value: detail.value.paymentAccount || '-' },
  { label: '付款账户名称', value: detail.value.paymentAccountName || '-' },
  { label: '供应商开户行', value: detail.value.supplierBankName || '-' },
  { label: '供应商收款账号', value: detail.value.supplierBankAccount || '-' },
  { label: '供应商账户名称', value: detail.value.supplierBankAccountName || '-' },
  { label: '付款金额', value: detail.value.confirmedPayAmount },
  { label: '未付款金额', value: detail.value.unpaidAmount },
  { label: '检查使用付款金额', value: detail.value.checkPayAmount ?? detail.value.confirmedPayAmount },
  { label: '检查使用未付款金额', value: detail.value.checkUnpaidAmount ?? detail.value.unpaidAmount },
  { label: '风险等级', value: riskLevelLabel(detail.value.riskLevel) },
  { label: '评审状态', value: riskReviewStatusLabel(detail.value.riskReviewStatus) },
  { label: '阻断项', value: reasonText(detail.value.blockingReasons) },
  { label: '警告项', value: reasonText(detail.value.warningReasons) },
  { label: '处理建议', value: detail.value.nextSuggestion || '-' },
] : [])

function refresh() {
  const sources = getPaymentRiskReviewSources()
  sourceRows.value = route.query.sourceId ? sources.filter((row) => String(row.id) === String(route.query.sourceId)) : sources
  reviewRows.value = listPaymentExecutionRiskReviews()
}

function notify(text, type = 'success') {
  message.value = text
  messageType.value = type
  window.clearTimeout(notify.timer)
  notify.timer = window.setTimeout(() => { message.value = '' }, 2400)
}

function currentSortText(state = {}, labels = {}) {
  if (!state.key) return '排序：点击表格表头字段可升序/降序排序；点击“清除排序”恢复默认顺序。'
  return `当前排序：${labels[state.key] || state.key} / ${state.direction === 'desc' ? '降序' : '升序'}`
}

function handleSourceSelectionChange(rows) { selectedSourceRows.value = rows || [] }
function handleReviewSelectionChange(rows) { selectedReviewRows.value = rows || [] }
function clearSourceSelection() { selectedSourceRows.value = []; sourceTableRef.value?.clearSelection?.() }
function clearReviewSelection() { selectedReviewRows.value = []; reviewTableRef.value?.clearSelection?.() }
function handleSourceSortChange({ prop, order }) { sourceSortState.value = { key: prop || '', direction: order === 'descending' ? 'desc' : 'asc' }; clearSourceSelection() }
function handleReviewSortChange({ prop, order }) { reviewSortState.value = { key: prop || '', direction: order === 'descending' ? 'desc' : 'asc' }; clearReviewSelection() }
function resetSourceSorting() { sourceSortState.value = { key: '', direction: 'asc' }; clearSourceSelection() }
function resetReviewSorting() { reviewSortState.value = { key: '', direction: 'asc' }; clearReviewSelection() }
function sourceRowActions(row = {}) { return ['执行风险评审', '查看付款单草稿', { label: '查看评审', visible: Boolean(row.riskReviewId) }] }
function reviewRowActions(row = {}) {
  return [
    '查看详情',
    '重新评审',
    { label: '标记通过', visible: canManualPass(row) },
    { label: '标记阻断', visible: canManualBlock(row) },
    { label: '取消风险评审', visible: canCancelRiskReview(row) },
  ]
}
function batchType(result = {}) {
  return result.failedCount
    ? (result.successCount || result.alreadyDoneCount || result.warningCount || result.blockedCount ? 'warning' : 'error')
    : (result.blockedCount ? 'warning' : 'success')
}
function showSourceBatchResult(result) { refresh(); clearSourceSelection(); sourceBatchResult.value = result; sourceBatchResultType.value = batchType(result) }
function showReviewBatchResult(result) { refresh(); clearReviewSelection(); reviewBatchResult.value = result; reviewBatchResultType.value = batchType(result) }
function runBatchSourceReview() { if (!sourceIds.value.length) return notify('请先选择可评审的正式付款单草稿。', 'warning'); showSourceBatchResult(batchRunPaymentExecutionRiskReviews(sourceIds.value)) }
function runBatchReviewAgain() { if (!reviewIds.value.length) return notify('请先选择风险评审记录。', 'warning'); showReviewBatchResult(batchRerunPaymentExecutionRiskReviews(reviewIds.value)) }
function runBatchCancelReview() { if (!reviewIds.value.length) return notify('请先选择风险评审记录。', 'warning'); showReviewBatchResult(batchCancelPaymentExecutionRiskReviews(reviewIds.value)) }

function handleOutcome(outcome, successText) {
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  notify(successText)
}

function runSourceReview(row) {
  const outcome = runPaymentExecutionRiskReview(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  router.push(`/finance/payment-risk-review/${outcome.review.id}`)
}
function rerunReview(row) { handleOutcome(rerunPaymentExecutionRiskReview(row.id), '已重新执行真实付款风险评审。') }
function markPassed(row) {
  const outcome = markPaymentExecutionRiskReviewPassed(row.id)
  if (outcome.alreadyDone) return handleOutcome(outcome, '该风险评审已通过，无需重复标记。')
  handleOutcome(outcome, '已标记风险评审通过；后续真实付款仍需独立审批。')
}
function markBlocked(row) { handleOutcome(markPaymentExecutionRiskReviewBlocked(row.id), '已标记风险评审阻断。') }
function cancelReview(row) { handleOutcome(cancelPaymentExecutionRiskReview(row.id), '已取消风险评审。') }

function canManualPass(row = {}) {
  return ['blocked', 'warning'].includes(row.riskReviewStatus)
}

function canManualBlock(row = {}) {
  return row.riskReviewStatus === 'warning'
}

function canCancelRiskReview(row = {}) {
  return ['pending', 'reviewing', 'blocked'].includes(row.riskReviewStatus)
}

function reasonText(reasons = []) {
  return Array.isArray(reasons) && reasons.length ? reasons.join('；') : '-'
}
function paymentOrderStatusLabel(status) {
  return { draft: '草稿', checking: '执行确认中', confirmed: '付款执行已确认', paymentReady: '可进入真实付款', cancelled: '取消', closed: '关闭' }[status] || status || '-'
}
function paymentOrderStatusType(status) {
  return { draft: 'info', checking: 'primary', confirmed: 'success', paymentReady: 'warning', cancelled: 'info', closed: 'info' }[status] || 'info'
}
function voucherStatusLabel(status) {
  return { notGenerated: '未生成凭证', voucherReady: '可生成凭证', generated: '已生成凭证' }[status] || status || '-'
}
function riskReviewStatusLabel(status) {
  return { pending: '待评审', reviewing: '评审中', passed: '评审通过', blocked: '评审阻断', warning: '有警告', cancelled: '已取消' }[status] || status || '-'
}
function riskReviewStatusType(status) {
  return { pending: 'info', reviewing: 'primary', passed: 'success', blocked: 'danger', warning: 'warning', cancelled: 'info' }[status] || 'info'
}
function riskLevelLabel(level) {
  return { low: '低风险', medium: '中风险', high: '高风险', blocked: '阻断' }[level] || level || '-'
}
function riskLevelType(level) {
  return { low: 'success', medium: 'warning', high: 'danger', blocked: 'danger' }[level] || 'info'
}
function severityLabel(severity) {
  return { info: '提示', warning: '警告', error: '阻断' }[severity] || severity || '-'
}
function reviewItemLabel(row = {}) {
  if (row.result === 'blocked') return '阻断'
  if (row.result === 'warning') return '警告'
  return '通过'
}
function reviewItemType(row = {}) {
  if (row.result === 'blocked') return 'danger'
  if (row.result === 'warning') return 'warning'
  return 'success'
}

watch(() => route.fullPath, refresh, { immediate: true })
</script>

<style scoped>
.payment-risk-review-page { display: flex; flex-direction: column; gap: 16px; min-height: 100%; padding: 22px; background: #f5f7fb; color: #172033; }
.page-header, .card-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.page-header p { margin: 6px 0 0; color: #475467; line-height: 1.5; }
.eyebrow, .card-header span, .info-grid span { color: #64748b; font-size: 13px; }
h1, h2 { margin: 0; }
.page-tabs, .button-row, .batch-bar { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.finance-flow-nav { align-items: stretch; border: 1px solid #dbeafe; border-radius: 8px; padding: 10px; background: #f8fbff; }
.finance-nav-title { display: flex; align-items: center; color: #475467; font-size: 13px; font-weight: 700; margin-right: 4px; }
.finance-nav-button { border: 1px solid #bfdbfe; border-radius: 6px; padding: 8px 12px; background: #fff; color: #1d4ed8; font-weight: 700; text-decoration: none; white-space: nowrap; }
.finance-nav-button-active { border-color: #0f766e; background: #0f766e; color: #fff; box-shadow: 0 6px 14px rgba(15, 118, 110, 0.18); }
.finance-current-tag { display: inline-flex; align-items: center; margin-left: 6px; border-radius: 999px; padding: 2px 7px; background: rgba(255, 255, 255, 0.22); color: inherit; font-size: 12px; }
.finance-current-module-badge { display: inline-flex; width: fit-content; border: 1px solid #99f6e4; border-radius: 999px; padding: 5px 10px; background: #ecfdf5; color: #0f766e !important; font-weight: 800; }
.operation-shell { display: flex; flex-direction: column; gap: 16px; }
.plain-flow-guide { display: grid; gap: 10px; border: 1px solid #a7f3d0; border-radius: 8px; padding: 14px; background: #ecfdf5; color: #064e3b; line-height: 1.6; }
.plain-flow-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
.plain-flow-grid span { display: grid; gap: 4px; border: 1px solid rgba(6, 78, 59, 0.14); border-radius: 8px; padding: 10px; background: #fff; }
.info-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; margin-top: 14px; }
.info-grid article { border: 1px solid #dbe3ef; border-radius: 8px; padding: 12px; background: #fff; }
.info-grid strong { display: block; margin-top: 4px; }
.batch-bar { border: 1px solid #dbe3ef; border-radius: 8px; padding: 10px; margin-bottom: 12px; background: #f8fafc; }
.button-row .el-button, .batch-bar .el-button { min-width: 96px; white-space: nowrap; }
.button-row .el-button--small, .batch-bar .el-button--small { min-width: 86px; }
.button-row .el-button--primary, .button-row .el-button--success, .button-row .el-button--warning,
.batch-bar .el-button--primary, .batch-bar .el-button--success, .batch-bar .el-button--warning { min-width: 132px; }
.button-row .el-button--danger, .batch-bar .el-button--danger { min-width: 86px; }
.sort-help { color: #64748b; font-size: 13px; }
.batch-result { position: relative; display: grid; gap: 6px; margin-bottom: 12px; border-radius: 8px; padding: 12px; background: #ecfdf5; color: #065f46; }
.batch-result.warning { background: #fffbeb; color: #92400e; }
.batch-result.error { background: #fef2f2; color: #991b1b; }
.batch-result button { position: absolute; top: 8px; right: 8px; border: 0; background: transparent; color: inherit; cursor: pointer; }
@media (max-width: 900px) {
  .page-header { align-items: flex-start; flex-direction: column; }
  .plain-flow-grid { grid-template-columns: 1fr; }
}
</style>
