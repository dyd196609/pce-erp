<template>
  <main class="payment-draft-page">
    <header class="page-header">
      <section>
        <p class="eyebrow">V1.12.6 付款申请预备</p>
        <h1>{{ detail ? '供应商付款草稿详情' : '供应商付款草稿' }}</h1>
        <p>本页根据应付账款草稿生成供应商付款草稿，只形成付款申请预备数据，不执行真实付款，不生成银行付款，不生成财务凭证。</p>
        <p class="finance-current-module-badge">当前操作模块：供应商付款草稿</p>
      </section>
      <nav class="page-tabs finance-flow-nav" aria-label="财务前置流程导航">
        <span class="finance-nav-title">财务前置流程导航</span>
        <router-link class="finance-nav-button" to="/finance/payable-prepares">应付预备</router-link>
        <router-link class="finance-nav-button" to="/finance/payable-checks">应付核对</router-link>
        <router-link class="finance-nav-button" to="/finance/invoice-prepares">发票预备</router-link>
        <router-link class="finance-nav-button" to="/finance/ap-drafts">应付账款草稿</router-link>
        <router-link class="finance-nav-button finance-nav-button-active" to="/finance/payment-drafts">供应商付款草稿 <span class="finance-current-tag">当前</span></router-link>
        <router-link class="finance-nav-button" to="/finance/payment-prepares">正式付款单预备</router-link>
      </nav>
    </header>

    <el-alert v-if="message" :title="message" :type="messageType" show-icon :closable="false" />

    <section v-if="detail" class="operation-shell">
      <section class="plain-flow-guide">
        <strong>供应商付款草稿流程：应付账款草稿 -> 生成付款草稿 -> 提交付款申请 -> 审批付款申请 -> 标记可付款 -> 后续正式付款</strong>
        <div class="plain-flow-grid">
          <span><b>当前步骤</b>准备供应商付款申请。</span>
          <span><b>本页要做</b>把已经确认的应付账款草稿整理成准备付款的申请草稿。</span>
          <span><b>下一步</b>提交付款申请，审批通过后进入后续正式付款。</span>
          <span><b>本页不会做</b>不真实付款、不生成银行付款、不生成财务凭证。</span>
        </div>
      </section>

      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>{{ detail.paymentDraftNo }}</h2>
              <span>{{ detail.sourceApDraftNo || '-' }} / {{ detail.supplierName || '-' }}</span>
            </div>
            <div class="button-row">
              <el-button @click="router.push('/finance/payment-drafts')">返回列表</el-button>
              <el-button @click="router.push(`/finance/ap-draft/${detail.sourceApDraftId}`)">查看应付账款草稿</el-button>
              <el-button v-if="detail.paymentDraftStatus === 'draft'" type="success" @click="submitDraft(detail)">提交付款申请</el-button>
              <el-button v-if="detail.paymentDraftStatus === 'submitted'" type="primary" @click="approveDraft(detail)">审批付款申请</el-button>
              <el-button v-if="detail.paymentDraftStatus === 'approved'" type="warning" @click="readyDraft(detail)">标记可付款</el-button>
              <el-button v-if="['approved', 'paymentReady'].includes(detail.paymentDraftStatus)" type="success" @click="openPaymentPrepareFromDraft(detail)">
                {{ detail.paymentPrepareGenerated ? '查看付款预备' : '进入付款预备' }}
              </el-button>
              <el-button v-if="['draft', 'submitted'].includes(detail.paymentDraftStatus)" type="danger" @click="cancelDraft(detail)">取消草稿</el-button>
            </div>
          </div>
        </template>
        <div class="info-grid">
          <article v-for="item in detailFields" :key="item.label">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </article>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>供应商付款草稿明细</h2></template>
        <el-table :data="detail.lines || []" border stripe height="520">
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="materialCode" label="物料编码" min-width="130" />
          <el-table-column prop="materialName" label="物料名称" min-width="160" />
          <el-table-column prop="spec" label="规格型号" min-width="120" />
          <el-table-column prop="unit" label="单位" width="90" />
          <el-table-column prop="payableAmount" label="应付金额" width="120" />
          <el-table-column prop="paidAmount" label="已付金额" width="120" />
          <el-table-column prop="unpaidAmount" label="未付金额" width="120" />
          <el-table-column prop="applyPayAmount" label="申请付款金额" width="140" />
          <el-table-column prop="sourcePurchaseOrderNo" label="采购订单" min-width="150" />
          <el-table-column prop="sourceReceiveNo" label="收货单" min-width="150" />
          <el-table-column prop="sourceInspectionNo" label="检验单" min-width="150" />
          <el-table-column prop="sourceInventoryTransactionNo" label="库存流水" min-width="150" />
          <el-table-column prop="rootRequestNo" label="原始请购单" min-width="150" />
          <el-table-column prop="remark" label="备注" min-width="180" />
        </el-table>
      </el-card>
    </section>

    <section v-else class="operation-shell">
      <section class="plain-flow-guide">
        <strong>供应商付款草稿流程：应付账款草稿 -> 生成付款草稿 -> 提交付款申请 -> 审批付款申请 -> 标记可付款 -> 后续正式付款</strong>
        <div class="plain-flow-grid">
          <span><b>当前步骤</b>准备供应商付款申请。</span>
          <span><b>本页要做</b>从 confirmed / paymentPending 应付账款草稿生成付款申请草稿。</span>
          <span><b>下一步</b>提交付款申请，审批通过后标记可付款。</span>
          <span><b>本页不会做</b>不真实付款、不生成银行付款、不生成财务凭证。</span>
        </div>
      </section>
      <section class="flow-guide">
        <strong>付款申请预备说明</strong>
        <span>本页只生成供应商付款草稿和付款申请预备数据；正式付款、银行支付、财务凭证和总账记录均不在本轮执行。</span>
      </section>

      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>来源应付账款草稿</h2>
              <span>来源为 confirmed / paymentPending 且未付款金额大于 0 的应付账款草稿。</span>
            </div>
            <div class="button-row">
              <el-button type="primary" @click="refresh">刷新来源</el-button>
              <el-button @click="router.push('/finance/ap-drafts')">查看应付账款草稿</el-button>
              <el-button type="success" @click="router.push('/finance/payment-prepares')">进入正式付款单预备</el-button>
            </div>
          </div>
        </template>
        <div class="batch-bar">
          <span>已选择 {{ selectedSourceRows.length }} 条</span>
          <span>可生成 {{ sourceBatchCounts.create }} 条</span>
          <span>跳过 {{ selectedSourceRows.length - sourceBatchCounts.create }} 条</span>
          <span class="sort-help">排序：点击表格表头字段可升序/降序排序；点击“清除排序”恢复默认顺序。</span>
          <span class="sort-help">{{ sourceSortText }}</span>
          <el-button size="small" @click="resetSourceSorting">清除排序</el-button>
          <el-button size="small" @click="clearSourceSelection">清空选择</el-button>
          <span class="batch-action-title">当前模块操作（立即生效）</span>
          <span class="batch-action-tip">以下按钮会立即修改所选记录状态，请确认选择无误后再执行。</span>
          <el-button size="small" type="success" :disabled="!sourceBatchCounts.create" @click="runBatchCreateDrafts">批量生成供应商付款草稿</el-button>
        </div>
        <BatchResult v-if="sourceBatchResult" :result="sourceBatchResult" :type="sourceBatchResultType" @close="sourceBatchResult = null" />
        <el-table ref="sourceTableRef" :data="sortedSourceRows" border stripe height="460" @selection-change="handleSourceSelectionChange" @sort-change="handleSourceSortChange">
          <el-table-column type="selection" width="48" fixed="left" :selectable="sourceSelectable" />
          <el-table-column type="expand" width="44" fixed="left">
            <template #default="{ row }">{{ row.sourceRejectReason || '可生成供应商付款草稿' }}</template>
          </el-table-column>
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="apDraftNo" label="应付账款草稿单号" min-width="170" sortable="custom" />
          <el-table-column prop="sourceInvoicePrepareNo" label="来源发票预备" min-width="170" sortable="custom" />
          <el-table-column prop="supplierName" label="供应商" min-width="150" sortable="custom" />
          <el-table-column prop="sourcePurchaseOrderNo" label="采购订单" min-width="150" sortable="custom" />
          <el-table-column prop="sourceReceiveNo" label="收货单" min-width="150" />
          <el-table-column prop="sourceInspectionNo" label="检验单" min-width="150" />
          <el-table-column prop="sourceInventoryTransactionNos" label="库存流水" min-width="150">
            <template #default="{ row }">{{ sourceInventoryText(row) }}</template>
          </el-table-column>
          <el-table-column prop="rootRequestNo" label="原始请购单" min-width="150" />
          <el-table-column prop="totalPayableAmount" label="应付金额" width="120" sortable="custom" />
          <el-table-column prop="paidAmount" label="已付金额" width="120" sortable="custom" />
          <el-table-column prop="unpaidAmount" label="未付金额" width="120" sortable="custom" />
          <el-table-column prop="apStatus" label="状态" width="150" sortable="custom">
            <template #default="{ row }"><el-tag :type="apStatusType(row.apStatus)">{{ apStatusLabel(row.apStatus) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="是否已生成付款草稿" width="160">
            <template #default="{ row }"><el-tag :type="row.paymentDraftGenerated ? 'success' : 'info'">{{ row.paymentDraftGeneratedText }}</el-tag></template>
          </el-table-column>
          <el-table-column label="操作" fixed="right" :width="getActionColumnWidth(['查看应付账款草稿', '生成付款草稿'])">
            <template #default="{ row }">
              <div class="app-action-cell">
                <el-button size="small" class="app-action-button-lg" @click="router.push(`/finance/ap-draft/${row.id}`)">查看应付账款草稿</el-button>
                <el-button v-if="!row.paymentDraftGenerated" size="small" class="app-action-button-md" type="success" :disabled="!row.canCreatePaymentDraft" @click="createDraft(row)">生成付款草稿</el-button>
                <el-button v-else size="small" class="app-action-button-lg" type="success" @click="viewPaymentDraftFromSource(row)">查看供应商付款草稿</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>供应商付款草稿列表</h2></template>
        <div class="batch-bar">
          <span>已选择 {{ selectedDraftRows.length }} 条</span>
          <span class="sort-help">排序：点击表格表头字段可升序/降序排序；点击“清除排序”恢复默认顺序。</span>
          <span class="sort-help">{{ draftSortText }}</span>
          <el-button size="small" @click="resetDraftSorting">清除排序</el-button>
          <el-button size="small" @click="clearDraftSelection">清空选择</el-button>
          <span class="batch-action-title">当前模块操作（立即生效）</span>
          <span class="batch-action-tip">以下按钮会立即修改所选记录状态，请确认选择无误后再执行。</span>
          <el-button size="small" type="success" :disabled="!selectedDraftRows.length" @click="runBatchSubmit">批量提交付款申请</el-button>
          <el-button size="small" type="primary" :disabled="!selectedDraftRows.length" @click="runBatchApprove">批量审批付款申请</el-button>
          <el-button size="small" type="warning" :disabled="!selectedDraftRows.length" @click="runBatchReady">批量标记可付款</el-button>
          <el-button size="small" type="danger" :disabled="!selectedDraftRows.length" @click="runBatchCancel">批量取消草稿</el-button>
        </div>
        <BatchResult v-if="draftBatchResult" :result="draftBatchResult" :type="draftBatchResultType" @close="draftBatchResult = null" />
        <el-table ref="draftTableRef" :data="sortedDraftRows" border stripe height="520" @selection-change="handleDraftSelectionChange" @sort-change="handleDraftSortChange">
          <el-table-column type="selection" width="48" fixed="left" />
          <el-table-column type="expand" width="44" fixed="left">
            <template #default="{ row }">来源：{{ row.sourceApDraftNo }}；本页不执行真实付款，不生成银行付款或财务凭证。</template>
          </el-table-column>
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="paymentDraftNo" label="付款草稿单号" min-width="170" sortable="custom" />
          <el-table-column prop="sourceApDraftNo" label="来源应付账款草稿" min-width="170" sortable="custom" />
          <el-table-column prop="supplierName" label="供应商" min-width="150" sortable="custom" />
          <el-table-column prop="applyPayAmount" label="申请付款金额" width="140" sortable="custom" />
          <el-table-column prop="expectedPayDate" label="预计付款日期" width="130" sortable="custom" />
          <el-table-column prop="paymentMethod" label="付款方式" width="130">
            <template #default="{ row }">{{ paymentMethodLabel(row.paymentMethod) }}</template>
          </el-table-column>
          <el-table-column prop="paymentDraftStatus" label="付款草稿状态" width="140" sortable="custom">
            <template #default="{ row }"><el-tag :type="paymentDraftStatusType(row.paymentDraftStatus)">{{ paymentDraftStatusLabel(row.paymentDraftStatus) }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="approvalStatus" label="审批状态" width="120">
            <template #default="{ row }">{{ approvalStatusLabel(row.approvalStatus) }}</template>
          </el-table-column>
          <el-table-column prop="paymentStatus" label="付款状态" width="120">
            <template #default="{ row }">{{ paymentStatusLabel(row.paymentStatus) }}</template>
          </el-table-column>
          <el-table-column prop="voucherStatus" label="凭证状态" width="130">
            <template #default="{ row }">{{ voucherStatusLabel(row.voucherStatus) }}</template>
          </el-table-column>
          <el-table-column label="操作" fixed="right" :width="draftActionColumnWidth">
            <template #default="{ row }">
              <div class="app-action-cell">
                <el-button size="small" class="app-action-button-sm" @click="router.push(`/finance/payment-draft/${row.id}`)">查看详情</el-button>
                <el-button v-if="row.paymentDraftStatus === 'draft'" size="small" class="app-action-button-md" type="success" @click="submitDraft(row)">提交付款申请</el-button>
                <el-button v-if="row.paymentDraftStatus === 'submitted'" size="small" class="app-action-button-md" type="primary" @click="approveDraft(row)">审批付款申请</el-button>
                <el-button v-if="row.paymentDraftStatus === 'approved'" size="small" class="app-action-button-md" type="warning" @click="readyDraft(row)">标记可付款</el-button>
                <el-button v-if="['approved', 'paymentReady'].includes(row.paymentDraftStatus)" size="small" class="app-action-button-md" type="success" @click="openPaymentPrepareFromDraft(row)">
                  {{ row.paymentPrepareGenerated ? '查看付款预备' : '进入付款预备' }}
                </el-button>
                <el-button v-if="['draft', 'submitted'].includes(row.paymentDraftStatus)" size="small" class="app-action-button-md" type="danger" @click="cancelDraft(row)">取消草稿</el-button>
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
  approvePaymentDraft,
  batchApprovePaymentDrafts,
  batchCancelPaymentDrafts,
  batchCreatePaymentDraftsFromApDrafts,
  batchMarkPaymentReady,
  batchSubmitPaymentDrafts,
  cancelPaymentDraft,
  createPaymentDraftFromApDraft,
  getPaymentDraftSourcesFromApDrafts,
  getSupplierPaymentDraftById,
  listSupplierPaymentDrafts,
  markPaymentReady,
  submitPaymentDraft,
} from '../finance/supplierPaymentDraftStore.js'
import { getActionColumnWidth, getActionColumnWidthForRows } from '../runtime/tableActionColumnEngine.js'
import { sortRecords } from '../runtime/tableSortEngine.js'

const BatchResult = defineComponent({
  props: { result: { type: Object, required: true }, type: { type: String, default: 'success' } },
  emits: ['close'],
  setup(props, { emit }) {
    return () => h('div', { class: ['batch-result', props.type] }, [
      h('button', { type: 'button', onClick: () => emit('close') }, '关闭'),
      h('strong', '批量操作完成'),
      h('span', `操作名称：${props.result.operationName}`),
      h('span', `已选择：${props.result.total} 条`),
      h('span', `成功：${props.result.successCount} 条`),
      h('span', `失败/跳过：${props.result.failedCount} 条`),
      props.result.failedReason?.length ? h('ol', props.result.failedReason.map((reason) => h('li', { key: reason }, reason))) : null,
      props.result.nextSuggestion ? h('span', `下一步建议：${props.result.nextSuggestion}`) : null,
    ])
  },
})

const route = useRoute()
const router = useRouter()
const sourceRows = ref([])
const draftRows = ref([])
const selectedSourceRows = ref([])
const selectedDraftRows = ref([])
const sourceSortState = ref({ key: '', direction: 'asc' })
const draftSortState = ref({ key: '', direction: 'asc' })
const sourceTableRef = ref(null)
const draftTableRef = ref(null)
const message = ref('')
const messageType = ref('success')
const sourceBatchResult = ref(null)
const sourceBatchResultType = ref('success')
const draftBatchResult = ref(null)
const draftBatchResultType = ref('success')

const detail = computed(() => route.params.id ? getSupplierPaymentDraftById(route.params.id) : null)
const sourceIds = computed(() => selectedSourceRows.value.map((row) => row.id).filter(Boolean))
const draftIds = computed(() => selectedDraftRows.value.map((row) => row.id).filter(Boolean))
const sourceSortColumns = [
  { key: 'apDraftNo', sortType: 'string' },
  { key: 'sourceInvoicePrepareNo', sortType: 'string' },
  { key: 'supplierName', sortType: 'string' },
  { key: 'sourcePurchaseOrderNo', sortType: 'string' },
  { key: 'totalPayableAmount', sortType: 'amount' },
  { key: 'paidAmount', sortType: 'amount' },
  { key: 'unpaidAmount', sortType: 'amount' },
  { key: 'apStatus', sortType: 'status' },
]
const draftSortColumns = [
  { key: 'paymentDraftNo', sortType: 'string' },
  { key: 'sourceApDraftNo', sortType: 'string' },
  { key: 'supplierName', sortType: 'string' },
  { key: 'applyPayAmount', sortType: 'amount' },
  { key: 'expectedPayDate', sortType: 'date' },
  { key: 'paymentDraftStatus', sortType: 'status' },
]
const sortedSourceRows = computed(() => sortRecords(sourceRows.value, sourceSortState.value, sourceSortColumns))
const sortedDraftRows = computed(() => sortRecords(draftRows.value, draftSortState.value, draftSortColumns))
const sourceBatchCounts = computed(() => ({ create: selectedSourceRows.value.filter((row) => row.canCreatePaymentDraft).length }))
const draftActionColumnWidth = computed(() => getActionColumnWidthForRows(sortedDraftRows.value, draftRowActions, ['查看详情']))
const sourceSortText = computed(() => currentSortText(sourceSortState.value, {
  apDraftNo: '应付账款草稿单号',
  sourceInvoicePrepareNo: '来源发票预备',
  supplierName: '供应商',
  sourcePurchaseOrderNo: '采购订单',
  totalPayableAmount: '应付金额',
  paidAmount: '已付金额',
  unpaidAmount: '未付金额',
  apStatus: '状态',
}))
const draftSortText = computed(() => currentSortText(draftSortState.value, {
  paymentDraftNo: '付款草稿单号',
  sourceApDraftNo: '来源应付账款草稿',
  supplierName: '供应商',
  applyPayAmount: '申请付款金额',
  expectedPayDate: '预计付款日期',
  paymentDraftStatus: '付款草稿状态',
}))
const detailFields = computed(() => detail.value ? [
  { label: '付款草稿单号', value: detail.value.paymentDraftNo },
  { label: '来源应付账款草稿', value: detail.value.sourceApDraftNo || '-' },
  { label: '来源发票预备', value: detail.value.sourceInvoicePrepareNo || '-' },
  { label: '来源应付核对', value: detail.value.sourcePayableCheckNo || '-' },
  { label: '来源应付预备', value: detail.value.sourcePayablePrepareNo || '-' },
  { label: '供应商', value: detail.value.supplierName || '-' },
  { label: '采购订单', value: detail.value.sourcePurchaseOrderNo || '-' },
  { label: '收货单', value: detail.value.sourceReceiveNo || '-' },
  { label: '检验单', value: detail.value.sourceInspectionNo || '-' },
  { label: '库存流水', value: sourceInventoryText(detail.value) },
  { label: '原始请购单', value: detail.value.rootRequestNo || '-' },
  { label: '应付金额', value: detail.value.totalPayableAmount },
  { label: '已付金额', value: detail.value.paidAmount },
  { label: '未付金额', value: detail.value.unpaidAmount },
  { label: '申请付款金额', value: detail.value.applyPayAmount },
  { label: '申请日期', value: detail.value.applyDate || '-' },
  { label: '预计付款日期', value: detail.value.expectedPayDate || '-' },
  { label: '到期日', value: detail.value.dueDate || '-' },
  { label: '付款方式', value: paymentMethodLabel(detail.value.paymentMethod) },
  { label: '付款账户', value: detail.value.paymentAccount || '-' },
  { label: '供应商开户行', value: detail.value.supplierBankName || '-' },
  { label: '供应商银行账号', value: detail.value.supplierBankAccount || '-' },
  { label: '审批状态', value: approvalStatusLabel(detail.value.approvalStatus) },
  { label: '付款状态', value: paymentStatusLabel(detail.value.paymentStatus) },
  { label: '凭证状态', value: voucherStatusLabel(detail.value.voucherStatus) },
  { label: '付款草稿状态', value: paymentDraftStatusLabel(detail.value.paymentDraftStatus) },
] : [])

function refresh() {
  sourceRows.value = getPaymentDraftSourcesFromApDrafts()
  draftRows.value = listSupplierPaymentDrafts()
}

function notify(text, type = 'success') {
  message.value = text
  messageType.value = type
  window.clearTimeout(notify.timer)
  notify.timer = window.setTimeout(() => { message.value = '' }, 2400)
}

function currentSortText(state = {}, labels = {}) {
  if (!state.key) return '当前排序：默认顺序'
  return `当前排序：${labels[state.key] || state.key} / ${state.direction === 'desc' ? '降序' : '升序'}`
}

function handleSourceSelectionChange(rows) { selectedSourceRows.value = rows || [] }
function handleDraftSelectionChange(rows) { selectedDraftRows.value = rows || [] }
function clearSourceSelection() { selectedSourceRows.value = []; sourceTableRef.value?.clearSelection?.() }
function clearDraftSelection() { selectedDraftRows.value = []; draftTableRef.value?.clearSelection?.() }
function sourceSelectable(row) { return row.canCreatePaymentDraft }

function draftRowActions(row = {}) {
  return [
    '查看详情',
    { label: '提交付款申请', visible: row.paymentDraftStatus === 'draft' },
    { label: '审批付款申请', visible: row.paymentDraftStatus === 'submitted' },
    { label: '标记可付款', visible: row.paymentDraftStatus === 'approved' },
    { label: row.paymentPrepareGenerated ? '查看付款预备' : '进入付款预备', visible: ['approved', 'paymentReady'].includes(row.paymentDraftStatus) },
    { label: '取消草稿', visible: ['draft', 'submitted'].includes(row.paymentDraftStatus) },
  ]
}

function handleSourceSortChange({ prop, order }) {
  sourceSortState.value = { key: prop || '', direction: order === 'descending' ? 'desc' : 'asc' }
  clearSourceSelection()
}

function handleDraftSortChange({ prop, order }) {
  draftSortState.value = { key: prop || '', direction: order === 'descending' ? 'desc' : 'asc' }
  clearDraftSelection()
}

function resetSourceSorting() { sourceSortState.value = { key: '', direction: 'asc' }; clearSourceSelection() }
function resetDraftSorting() { draftSortState.value = { key: '', direction: 'asc' }; clearDraftSelection() }

function nextBatchSuggestion(reasons = []) {
  const text = reasons.join('；')
  if (text.includes('重复') || text.includes('已生成')) return '建议查看已生成的供应商付款草稿，避免重复生成；如原草稿已取消，可重新生成。'
  if (text.includes('paymentPending') || text.includes('confirmed')) return '建议先确认应付账款草稿，或标记为等待后续付款。'
  if (text.includes('未付款金额')) return '建议检查应付账款草稿的已付金额和未付金额。'
  if (text.includes('草稿状态')) return '建议检查付款草稿是否处于可流转节点。'
  return '请按失败原因处理后重新执行。'
}

function normalizeBatchResult(result = {}, operationName = '批量操作') {
  const failedReason = result.failedReason || []
  return {
    operationName,
    total: result.total ?? 0,
    successCount: result.successCount || 0,
    failedCount: result.failedCount || 0,
    failedReason,
    nextSuggestion: nextBatchSuggestion(failedReason),
  }
}

function showSourceBatchResult(result, operationName) {
  refresh()
  clearSourceSelection()
  sourceBatchResult.value = normalizeBatchResult(result, operationName)
  sourceBatchResultType.value = result?.failedCount ? (result.successCount ? 'warning' : 'error') : 'success'
}

function showDraftBatchResult(result, operationName) {
  refresh()
  clearDraftSelection()
  draftBatchResult.value = normalizeBatchResult(result, operationName)
  draftBatchResultType.value = result?.failedCount ? (result.successCount ? 'warning' : 'error') : 'success'
}

function runBatchCreateDrafts() {
  if (!sourceIds.value.length) return notify('请先选择可生成供应商付款草稿的应付账款草稿', 'warning')
  showSourceBatchResult(batchCreatePaymentDraftsFromApDrafts(sourceIds.value), '批量生成供应商付款草稿')
}

function runBatchSubmit() {
  if (!draftIds.value.length) return notify('请先选择供应商付款草稿', 'warning')
  showDraftBatchResult(batchSubmitPaymentDrafts(draftIds.value), '批量提交付款申请')
}

function runBatchApprove() {
  if (!draftIds.value.length) return notify('请先选择供应商付款草稿', 'warning')
  showDraftBatchResult(batchApprovePaymentDrafts(draftIds.value), '批量审批付款申请')
}

function runBatchReady() {
  if (!draftIds.value.length) return notify('请先选择供应商付款草稿', 'warning')
  showDraftBatchResult(batchMarkPaymentReady(draftIds.value), '批量标记可付款')
}

function runBatchCancel() {
  if (!draftIds.value.length) return notify('请先选择供应商付款草稿', 'warning')
  showDraftBatchResult(batchCancelPaymentDrafts(draftIds.value), '批量取消付款草稿')
}

function createDraft(row) {
  const outcome = createPaymentDraftFromApDraft(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  notify(`已生成供应商付款草稿 ${outcome.paymentDraftNo}`)
}

function viewPaymentDraftFromSource(row = {}) {
  if (row.targetPaymentDraftId) return router.push(`/finance/payment-draft/${row.targetPaymentDraftId}`)
  notify(row.targetPaymentDraftNo ? `已生成供应商付款草稿 ${row.targetPaymentDraftNo}，请在列表中查看。` : '已生成供应商付款草稿，请在列表中查看。', 'warning')
  return router.push('/finance/payment-drafts')
}

function submitDraft(row) {
  const outcome = submitPaymentDraft(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  notify('已提交付款申请')
}

function approveDraft(row) {
  const outcome = approvePaymentDraft(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  notify('已审批付款申请')
}

function readyDraft(row) {
  const outcome = markPaymentReady(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  notify('已标记可付款，本轮不执行真实付款')
}

function openPaymentPrepareFromDraft(row = {}) {
  if (row.targetPaymentPrepareId) return router.push(`/finance/payment-prepare/${row.targetPaymentPrepareId}`)
  return router.push('/finance/payment-prepares')
}

function cancelDraft(row) {
  const outcome = cancelPaymentDraft(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  notify('供应商付款草稿已取消')
}

function apStatusLabel(status) {
  return { draft: '草稿', confirmed: '可生成供应商付款草稿', paymentPending: '等待付款', paymentDraftGenerated: '已生成供应商付款草稿', partiallyPaid: '部分付款', paid: '已付款', cancelled: '取消', closed: '关闭' }[status] || status || '-'
}
function apStatusType(status) {
  return { draft: 'info', confirmed: 'success', paymentPending: 'warning', paymentDraftGenerated: 'success', partiallyPaid: 'warning', paid: 'success', cancelled: 'info', closed: 'info' }[status] || 'info'
}
function paymentDraftStatusLabel(status) {
  return { draft: '草稿', submitted: '已提交', approved: '已审批', paymentReady: '可付款', cancelled: '取消', closed: '关闭' }[status] || status || '-'
}
function paymentDraftStatusType(status) {
  return { draft: 'info', submitted: 'primary', approved: 'success', paymentReady: 'warning', cancelled: 'info', closed: 'info' }[status] || 'info'
}
function approvalStatusLabel(status) {
  return { draft: '未提交', submitted: '已提交', approved: '已审批', cancelled: '取消' }[status] || status || '-'
}
function paymentStatusLabel(status) {
  return { unpaid: '未付款', partial: '部分付款', paid: '已付款' }[status] || status || '-'
}
function voucherStatusLabel(status) {
  return { notGenerated: '未生成凭证', voucherReady: '可生成凭证', generated: '已生成凭证' }[status] || status || '-'
}
function paymentMethodLabel(method) {
  return { bankTransfer: '银行转账', cash: '现金', acceptance: '承兑', other: '其他' }[method] || method || '-'
}

function sourceInventoryText(row = {}) {
  const nos = row.sourceInventoryTransactionNos || row.sourceInventoryTransactionNo || ''
  if (Array.isArray(nos)) return nos.filter(Boolean).join('、') || '-'
  return nos || '-'
}

watch(() => route.fullPath, refresh, { immediate: true })
</script>

<style scoped>
.payment-draft-page { display: flex; flex-direction: column; gap: 16px; min-height: 100%; padding: 22px; background: #f5f7fb; color: #172033; }
.page-header, .card-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.eyebrow, .card-header span, .info-grid span { color: #64748b; font-size: 13px; }
h1, h2 { margin: 0; }
.page-tabs, .button-row, .batch-bar { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.finance-flow-nav { align-items: stretch; border: 1px solid #dbeafe; border-radius: 8px; padding: 10px; background: #f8fbff; }
.finance-nav-title { display: flex; align-items: center; color: #475467; font-size: 13px; font-weight: 700; margin-right: 4px; }
.page-tabs a, .finance-nav-button { border: 1px solid #bfdbfe; border-radius: 6px; padding: 8px 12px; background: #fff; color: #1d4ed8; font-weight: 700; text-decoration: none; white-space: nowrap; }
.page-tabs a.finance-nav-button-active { border-color: #0f766e; background: #0f766e; color: #fff; box-shadow: 0 6px 14px rgba(15, 118, 110, 0.18); }
.finance-current-tag { display: inline-flex; align-items: center; margin-left: 6px; border-radius: 999px; padding: 2px 7px; background: rgba(255, 255, 255, 0.22); color: inherit; font-size: 12px; }
.finance-current-module-badge { display: inline-flex; width: fit-content; border: 1px solid #99f6e4; border-radius: 999px; padding: 5px 10px; background: #ecfdf5; color: #0f766e !important; font-weight: 800; }
.operation-shell { display: flex; flex-direction: column; gap: 16px; }
.plain-flow-guide { display: grid; gap: 10px; border: 1px solid #a7f3d0; border-radius: 8px; padding: 14px; background: #ecfdf5; color: #064e3b; line-height: 1.6; }
.plain-flow-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
.plain-flow-grid span { display: grid; gap: 4px; border: 1px solid rgba(6, 78, 59, 0.14); border-radius: 8px; padding: 10px; background: #fff; }
.flow-guide { display: grid; gap: 6px; border: 1px solid #bfdbfe; border-radius: 8px; padding: 12px; background: #eff6ff; color: #1e3a8a; line-height: 1.6; }
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
  .plain-flow-grid { grid-template-columns: 1fr; }
}
</style>
