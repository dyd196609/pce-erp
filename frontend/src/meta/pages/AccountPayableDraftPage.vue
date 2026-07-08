<template>
  <main class="ap-draft-page">
    <header class="page-header">
      <section>
        <p class="eyebrow">V1.12.5 采购应付账款草稿</p>
        <h1>{{ detail ? '应付账款草稿详情' : '采购应付账款草稿' }}</h1>
        <p>本页根据发票预备生成应付账款草稿，只形成应付账款待确认数据，不生成付款单，不生成财务凭证。</p>
        <p class="finance-current-module-badge">当前操作模块：应付账款草稿</p>
      </section>
      <nav class="page-tabs finance-flow-nav" aria-label="财务前置流程导航">
        <span class="finance-nav-title">财务前置流程导航</span>
        <router-link class="finance-nav-button" to="/finance/payable-prepares">应付预备</router-link>
        <router-link class="finance-nav-button" to="/finance/payable-checks">应付核对</router-link>
        <router-link class="finance-nav-button" to="/finance/invoice-prepares">发票预备</router-link>
        <router-link class="finance-nav-button finance-nav-button-active" to="/finance/ap-drafts">应付账款草稿 <span class="finance-current-tag">当前</span></router-link>
        <router-link class="finance-nav-button" to="/finance/payment-drafts">供应商付款草稿</router-link>
        <router-link class="finance-nav-button" to="/finance/payment-prepares">正式付款单预备</router-link>
      </nav>
    </header>

    <el-alert v-if="message" :title="message" :type="messageType" show-icon :closable="false" />

    <section v-if="detail" class="operation-shell">
      <section class="plain-flow-guide">
        <strong>财务前置总流程：采购入库完成 -> 生成应付预备 -> 核对数量和金额 -> 准备发票信息 -> 生成应付账款草稿 -> 确认应付 -> 等待后续付款</strong>
        <div class="plain-flow-grid">
          <span><b>当前步骤</b>第 4 步：生成应付账款草稿</span>
          <span><b>本页要做</b>根据已匹配的发票预备，生成一张“准备成为正式应付账款”的草稿。</span>
          <span><b>下一步</b>确认应付账款草稿后，标记为“等待后续付款”。付款和凭证将在后续模块处理。</span>
          <span><b>本页不会做</b>不生成付款单、财务凭证或总账。</span>
        </div>
      </section>
      <section class="next-step-guide">
        <strong>下一步操作</strong>
        <span>确认草稿后，标记为“等待后续付款”。付款和凭证将在后续模块处理。</span>
      </section>
      <section class="flow-guide">
        <strong>采购应付账款草稿流程：发票预备 -> 应付账款草稿 -> 应付确认 -> 后续付款 / 凭证</strong>
        <span>本页只生成应付账款草稿和待付款准备数据；本页不生成付款单，不生成财务凭证。</span>
      </section>

      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>{{ detail.apDraftNo }}</h2>
              <span>{{ detail.sourceInvoicePrepareNo || '-' }} / {{ detail.supplierName || '-' }}</span>
            </div>
            <div class="button-row">
              <el-button @click="router.push('/finance/ap-drafts')">返回列表</el-button>
              <el-button @click="router.push(`/finance/invoice-prepare/${detail.sourceInvoicePrepareId}`)">查看发票预备</el-button>
              <el-button v-if="isPaymentDraftGeneratedRow(detail)" type="primary" @click="viewPaymentDraft(detail)">查看供应商付款草稿</el-button>
              <el-button v-else-if="canGeneratePaymentDraft(detail)" type="primary" @click="router.push('/finance/payment-drafts')">生成供应商付款草稿</el-button>
              <el-button v-if="detail.apStatus === 'draft'" type="success" @click="confirmDraft(detail)">确认应付账款草稿</el-button>
              <el-button v-if="detail.apStatus === 'confirmed'" type="primary" @click="markPaymentPending(detail)">标记等待后续付款</el-button>
              <el-button v-if="['draft', 'confirmed'].includes(detail.apStatus)" type="danger" @click="cancelDraft(detail)">取消草稿</el-button>
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
        <template #header><h2>应付账款草稿明细</h2></template>
        <el-table :data="detail.lines || []" border stripe height="520">
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="materialCode" label="物料编码" min-width="130" />
          <el-table-column prop="materialName" label="物料名称" min-width="160" />
          <el-table-column prop="spec" label="规格型号" min-width="120" />
          <el-table-column prop="unit" label="单位" width="90" />
          <el-table-column prop="checkedQty" label="核对数量" width="110" />
          <el-table-column prop="checkedPrice" label="核对单价" width="110" />
          <el-table-column prop="checkedAmount" label="核对金额" width="120" />
          <el-table-column prop="noTaxAmount" label="未税金额" width="120" />
          <el-table-column prop="taxRate" label="税率%" width="90" />
          <el-table-column prop="taxAmount" label="税额" width="110" />
          <el-table-column prop="invoiceAmount" label="发票金额" width="120" />
          <el-table-column prop="payableAmount" label="应付金额" width="120" />
          <el-table-column prop="sourcePurchaseOrderNo" label="采购订单" min-width="150" />
          <el-table-column prop="sourceReceiveNo" label="收货单" min-width="150" />
          <el-table-column prop="sourceInspectionNo" label="检验单" min-width="150" />
          <el-table-column prop="rootRequestNo" label="原始请购单" min-width="150" />
          <el-table-column prop="remark" label="备注" min-width="180" />
        </el-table>
      </el-card>
    </section>

    <section v-else class="operation-shell">
      <section class="plain-flow-guide">
        <strong>财务前置总流程：采购入库完成 -> 生成应付预备 -> 核对数量和金额 -> 准备发票信息 -> 生成应付账款草稿 -> 确认应付 -> 等待后续付款</strong>
        <div class="plain-flow-grid">
          <span><b>当前步骤</b>第 4 步：生成应付账款草稿</span>
          <span><b>本页要做</b>根据已匹配的发票预备，生成一张“准备成为正式应付账款”的草稿。</span>
          <span><b>下一步</b>确认应付账款草稿后，标记为“等待后续付款”。</span>
          <span><b>本页不会做</b>不生成付款单、财务凭证或总账。</span>
        </div>
      </section>
      <section class="next-step-guide">
        <strong>下一步操作</strong>
        <span>先生成应付账款草稿；确认草稿后，标记为“等待后续付款”。付款和凭证将在后续模块处理。</span>
      </section>
      <section class="flow-guide">
        <strong>采购应付账款草稿流程：发票预备 -> 应付账款草稿 -> 应付确认 -> 后续付款 / 凭证</strong>
        <span>本页只生成应付账款草稿和待付款准备数据；不生成付款单，不生成财务凭证。</span>
        <el-button type="primary" @click="router.push('/finance/payment-drafts')">进入供应商付款草稿</el-button>
      </section>

      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>来源发票预备</h2>
              <span>来源为 matched / payableReady 状态的发票预备单。</span>
            </div>
            <div class="button-row">
              <el-button type="primary" @click="refresh">刷新来源</el-button>
              <el-button @click="router.push('/finance/invoice-prepares')">查看发票预备</el-button>
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
          <el-button size="small" type="success" :disabled="!sourceBatchCounts.create" @click="runBatchCreateDrafts">批量生成应付账款草稿</el-button>
        </div>
        <BatchResult v-if="sourceBatchResult" :result="sourceBatchResult" :type="sourceBatchResultType" @close="sourceBatchResult = null" />
        <el-table ref="sourceTableRef" :data="sortedSourceRows" border stripe height="460" @selection-change="handleSourceSelectionChange" @sort-change="handleSourceSortChange">
          <el-table-column type="selection" width="48" fixed="left" :selectable="sourceSelectable" />
          <el-table-column type="expand" width="44" fixed="left">
            <template #default="{ row }">{{ row.sourceRejectReason || '可生成应付账款草稿' }}</template>
          </el-table-column>
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="invoicePrepareNo" label="发票预备单号" min-width="170" sortable="custom" />
          <el-table-column prop="sourcePayableCheckNo" label="应付核对单号" min-width="160" sortable="custom" />
          <el-table-column prop="sourcePayablePrepareNo" label="应付预备单号" min-width="160" />
          <el-table-column prop="supplierName" label="供应商" min-width="150" sortable="custom" />
          <el-table-column prop="sourcePurchaseOrderNo" label="采购订单" min-width="150" sortable="custom" />
          <el-table-column prop="sourceReceiveNo" label="收货单" min-width="150" />
          <el-table-column prop="sourceInspectionNo" label="检验单" min-width="150" />
          <el-table-column prop="rootRequestNo" label="原始请购单" min-width="150" />
          <el-table-column prop="invoiceType" label="发票类型" min-width="130" />
          <el-table-column prop="invoiceNo" label="发票号码" min-width="130" />
          <el-table-column prop="invoiceDate" label="发票日期" width="120" />
          <el-table-column prop="totalNoTaxAmount" label="未税金额" width="120" sortable="custom" />
          <el-table-column prop="totalTaxAmount" label="税额" width="110" sortable="custom" />
          <el-table-column prop="totalInvoiceAmount" label="含税金额" width="120" sortable="custom" />
          <el-table-column prop="invoicePrepareStatus" label="状态" width="170" sortable="custom">
            <template #default="{ row }"><el-tag :type="invoiceStatusType(row.invoicePrepareStatus)">{{ invoiceStatusLabel(row.invoicePrepareStatus) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="是否已生成" width="120">
            <template #default="{ row }"><el-tag :type="row.apDraftGenerated ? 'success' : 'info'">{{ row.apDraftGeneratedText }}</el-tag></template>
          </el-table-column>
          <el-table-column label="操作" fixed="right" :width="getActionColumnWidth(['查看发票预备', '生成应付账款草稿'])">
            <template #default="{ row }">
              <div class="app-action-cell">
                <el-button size="small" class="app-action-button-md" @click="router.push(`/finance/invoice-prepare/${row.id}`)">查看发票预备</el-button>
                <el-button v-if="!row.apDraftGenerated" size="small" class="app-action-button-lg" type="success" :disabled="!row.canCreateApDraft" @click="createDraft(row)">生成应付账款草稿</el-button>
                <el-button v-else size="small" class="app-action-button-lg" type="success" @click="viewApDraftFromSource(row)">查看应付账款草稿</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>应付账款草稿列表</h2></template>
        <div class="batch-bar">
          <span>已选择 {{ selectedDraftRows.length }} 条</span>
          <span class="sort-help">排序：点击表格表头字段可升序/降序排序；点击“清除排序”恢复默认顺序。</span>
          <span class="sort-help">{{ draftSortText }}</span>
          <el-button size="small" @click="resetDraftSorting">清除排序</el-button>
          <el-button size="small" @click="clearDraftSelection">清空选择</el-button>
          <span class="batch-action-title">当前模块操作（立即生效）</span>
          <span class="batch-action-tip">以下按钮会立即修改所选记录状态，请确认选择无误后再执行。</span>
          <el-button size="small" type="success" :disabled="!selectedDraftRows.length" @click="runBatchConfirm">批量确认应付账款草稿</el-button>
          <el-button size="small" type="primary" :disabled="!selectedDraftRows.length" @click="runBatchPaymentPending">批量标记等待后续付款</el-button>
          <el-button size="small" type="danger" :disabled="!selectedDraftRows.length" @click="runBatchCancel">批量取消草稿</el-button>
        </div>
        <BatchResult v-if="draftBatchResult" :result="draftBatchResult" :type="draftBatchResultType" @close="draftBatchResult = null" />
        <el-table ref="draftTableRef" :data="sortedDraftRows" border stripe height="520" @selection-change="handleDraftSelectionChange" @sort-change="handleDraftSortChange">
          <el-table-column type="selection" width="48" fixed="left" />
          <el-table-column type="expand" width="44" fixed="left">
            <template #default="{ row }">来源：{{ row.sourceInvoicePrepareNo }}；本页不生成付款单或财务凭证。</template>
          </el-table-column>
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="apDraftNo" label="应付草稿单号" min-width="170" sortable="custom" />
          <el-table-column prop="sourceInvoicePrepareNo" label="来源发票预备" min-width="170" sortable="custom" />
          <el-table-column prop="supplierName" label="供应商" min-width="150" sortable="custom" />
          <el-table-column prop="sourcePurchaseOrderNo" label="采购订单" min-width="150" sortable="custom" />
          <el-table-column prop="invoiceNo" label="发票号码" min-width="130" />
          <el-table-column prop="totalPayableAmount" label="应付金额" width="120" sortable="custom" />
          <el-table-column prop="unpaidAmount" label="未付款金额" width="120" sortable="custom" />
          <el-table-column prop="apStatus" label="应付状态" width="130" sortable="custom">
            <template #default="{ row }"><el-tag :type="apStatusType(row.apStatus)">{{ apStatusLabel(row.apStatus) }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="paymentStatus" label="付款状态" width="120">
            <template #default="{ row }">{{ paymentStatusLabel(row.paymentStatus) }}</template>
          </el-table-column>
          <el-table-column prop="voucherStatus" label="凭证状态" width="130">
            <template #default="{ row }">{{ voucherStatusLabel(row.voucherStatus) }}</template>
          </el-table-column>
          <el-table-column label="操作" fixed="right" :width="getActionColumnWidth(['查看详情', '确认应付账款草稿', '生成供应商付款草稿'])">
            <template #default="{ row }">
              <div class="app-action-cell">
                <el-button size="small" class="app-action-button-sm" @click="router.push(`/finance/ap-draft/${row.id}`)">查看详情</el-button>
                <el-button v-if="row.apStatus === 'draft'" size="small" class="app-action-button-lg" type="success" @click="confirmDraft(row)">确认应付账款草稿</el-button>
                <el-button v-if="row.apStatus === 'confirmed'" size="small" class="app-action-button-lg" type="primary" @click="markPaymentPending(row)">标记等待后续付款</el-button>
                <el-button v-if="isPaymentDraftGeneratedRow(row)" size="small" class="app-action-button-lg" type="warning" @click="viewPaymentDraft(row)">查看供应商付款草稿</el-button>
                <el-button v-else-if="canGeneratePaymentDraft(row)" size="small" class="app-action-button-lg" type="warning" @click="router.push('/finance/payment-drafts')">生成供应商付款草稿</el-button>
                <el-button v-if="['draft', 'confirmed'].includes(row.apStatus)" size="small" class="app-action-button-md" type="danger" @click="cancelDraft(row)">取消草稿</el-button>
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
  batchCancelApDrafts,
  batchCreateApDraftsFromInvoicePrepares,
  batchMarkApDraftConfirmed,
  batchMarkApDraftPaymentPending,
  cancelApDraft,
  createApDraftFromInvoicePrepare,
  getAccountPayableDraftById,
  getApDraftSourcesFromInvoicePrepares,
  listAccountPayableDrafts,
  markApDraftConfirmed,
  markApDraftPaymentPending,
} from '../finance/accountPayableDraftStore.js'
import { listSupplierPaymentDrafts } from '../finance/supplierPaymentDraftStore.js'
import { getActionColumnWidth } from '../runtime/tableActionColumnEngine.js'
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
      props.result.writeBackCount != null ? h('span', `已回写状态：${props.result.writeBackCount} 条`) : null,
      props.result.failedReason?.length ? h('ol', props.result.failedReason.map((reason) => h('li', { key: reason }, reason))) : null,
      props.result.failedReason?.length ? h('span', `下一步建议：${props.result.nextSuggestion}`) : null,
    ])
  },
})

const route = useRoute()
const router = useRouter()
const sourceRows = ref([])
const draftRows = ref([])
const paymentDraftRows = ref([])
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

const detail = computed(() => route.params.id ? normalizeApDraftRow(getAccountPayableDraftById(route.params.id)) : null)
const sourceIds = computed(() => selectedSourceRows.value.map((row) => row.id).filter(Boolean))
const draftIds = computed(() => selectedDraftRows.value.map((row) => row.id).filter(Boolean))
const sourceSortColumns = [
  { key: 'invoicePrepareNo', sortType: 'string' },
  { key: 'sourcePayableCheckNo', sortType: 'string' },
  { key: 'supplierName', sortType: 'string' },
  { key: 'sourcePurchaseOrderNo', sortType: 'string' },
  { key: 'totalNoTaxAmount', sortType: 'amount' },
  { key: 'totalTaxAmount', sortType: 'amount' },
  { key: 'totalInvoiceAmount', sortType: 'amount' },
  { key: 'invoicePrepareStatus', sortType: 'status' },
]
const draftSortColumns = [
  { key: 'apDraftNo', sortType: 'string' },
  { key: 'sourceInvoicePrepareNo', sortType: 'string' },
  { key: 'supplierName', sortType: 'string' },
  { key: 'sourcePurchaseOrderNo', sortType: 'string' },
  { key: 'totalPayableAmount', sortType: 'amount' },
  { key: 'unpaidAmount', sortType: 'amount' },
  { key: 'apStatus', sortType: 'status' },
]
const sortedSourceRows = computed(() => sortRecords(sourceRows.value, sourceSortState.value, sourceSortColumns))
const sortedDraftRows = computed(() => sortRecords(draftRows.value, draftSortState.value, draftSortColumns))
const sourceBatchCounts = computed(() => ({ create: selectedSourceRows.value.filter((row) => row.canCreateApDraft).length }))
const sourceSortText = computed(() => currentSortText(sourceSortState.value, {
  invoicePrepareNo: '发票预备单号',
  sourcePayableCheckNo: '应付核对单号',
  supplierName: '供应商',
  sourcePurchaseOrderNo: '采购订单',
  totalNoTaxAmount: '未税金额',
  totalTaxAmount: '税额',
  totalInvoiceAmount: '含税金额',
  invoicePrepareStatus: '状态',
}))
const draftSortText = computed(() => currentSortText(draftSortState.value, {
  apDraftNo: '应付草稿单号',
  sourceInvoicePrepareNo: '来源发票预备',
  supplierName: '供应商',
  sourcePurchaseOrderNo: '采购订单',
  totalPayableAmount: '应付金额',
  unpaidAmount: '未付款金额',
  apStatus: '应付状态',
}))
const detailFields = computed(() => detail.value ? [
  { label: '应付草稿单号', value: detail.value.apDraftNo },
  { label: '来源发票预备', value: detail.value.sourceInvoicePrepareNo || '-' },
  { label: '来源应付核对', value: detail.value.sourcePayableCheckNo || '-' },
  { label: '来源应付预备', value: detail.value.sourcePayablePrepareNo || '-' },
  { label: '供应商', value: detail.value.supplierName || '-' },
  { label: '采购订单', value: detail.value.sourcePurchaseOrderNo || '-' },
  { label: '收货单', value: detail.value.sourceReceiveNo || '-' },
  { label: '检验单', value: detail.value.sourceInspectionNo || '-' },
  { label: '原始请购单', value: detail.value.rootRequestNo || '-' },
  { label: '发票类型', value: invoiceTypeLabel(detail.value.invoiceType) },
  { label: '发票号码', value: detail.value.invoiceNo || '-' },
  { label: '发票日期', value: detail.value.invoiceDate || '-' },
  { label: '未税金额', value: detail.value.totalNoTaxAmount },
  { label: '税额', value: detail.value.totalTaxAmount },
  { label: '含税金额', value: detail.value.totalInvoiceAmount },
  { label: '应付金额', value: detail.value.totalPayableAmount },
  { label: '已付款金额', value: detail.value.paidAmount },
  { label: '未付款金额', value: detail.value.unpaidAmount },
  { label: '应付状态', value: apStatusLabel(detail.value.apStatus) },
  { label: '付款状态', value: paymentStatusLabel(detail.value.paymentStatus) },
  { label: '凭证状态', value: voucherStatusLabel(detail.value.voucherStatus) },
  { label: '目标供应商付款草稿', value: detail.value.targetPaymentDraftNo || '-' },
] : [])

function refresh() {
  sourceRows.value = getApDraftSourcesFromInvoicePrepares()
  paymentDraftRows.value = listSupplierPaymentDrafts()
  draftRows.value = listAccountPayableDrafts().map(normalizeApDraftRow)
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
function sourceSelectable(row) { return row.canCreateApDraft }

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
  if (text.includes('重复') || text.includes('已生成')) return '建议查看已生成的应付账款草稿，避免重复生成。'
  if (text.includes('matched') || text.includes('payableReady')) return '建议先将发票预备确认到“发票已匹配”或“可生成应付账款草稿”。'
  if (text.includes('草稿')) return '建议检查应付草稿状态是否处于可流转节点。'
  return '请按失败原因处理后重新执行。'
}

function normalizeBatchResult(result = {}, operationName = '批量操作') {
  const failedReason = result.failedReason || []
  return {
    operationName,
    total: result.total ?? 0,
    successCount: result.successCount || 0,
    failedCount: result.failedCount || 0,
    writeBackCount: result.writeBackCount,
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
  if (!sourceIds.value.length) return notify('请先选择可生成应付账款草稿的发票预备', 'warning')
  showSourceBatchResult(batchCreateApDraftsFromInvoicePrepares(sourceIds.value), '批量生成应付账款草稿')
}

function runBatchConfirm() {
  if (!draftIds.value.length) return notify('请先选择应付账款草稿', 'warning')
  showDraftBatchResult(batchMarkApDraftConfirmed(draftIds.value), '批量确认应付账款草稿')
}

function runBatchPaymentPending() {
  if (!draftIds.value.length) return notify('请先选择应付账款草稿', 'warning')
  showDraftBatchResult(batchMarkApDraftPaymentPending(draftIds.value), '批量标记等待后续付款')
}

function runBatchCancel() {
  if (!draftIds.value.length) return notify('请先选择应付账款草稿', 'warning')
  showDraftBatchResult(batchCancelApDrafts(draftIds.value), '批量取消草稿')
}

function createDraft(row) {
  const outcome = createApDraftFromInvoicePrepare(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  notify(`已生成应付账款草稿 ${outcome.apDraftNo}`)
}

function confirmDraft(row) {
  const outcome = markApDraftConfirmed(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  notify('已确认应付账款草稿')
}

function markPaymentPending(row) {
  const outcome = markApDraftPaymentPending(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  notify('已标记等待后续付款，本轮不生成付款单')
}

function cancelDraft(row) {
  const outcome = cancelApDraft(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  notify('应付账款草稿已取消')
}

function generatedPaymentDraft(row = {}) {
  return paymentDraftRows.value.find((draft) => (
    String(draft.sourceApDraftId) === String(row.id)
    && !['cancelled', 'closed'].includes(draft.paymentDraftStatus)
  )) || null
}

function isPaymentDraftGeneratedRow(row = {}) {
  const activeDraft = generatedPaymentDraft(row)
  if (activeDraft) return true
  const targetDraft = paymentDraftRows.value.find((draft) => (
    (row?.targetPaymentDraftId && String(draft.id) === String(row.targetPaymentDraftId))
    || (row?.targetPaymentDraftNo && String(draft.paymentDraftNo) === String(row.targetPaymentDraftNo))
  ))
  if (targetDraft) return !['cancelled', 'closed'].includes(targetDraft.paymentDraftStatus)
  return Boolean(row?.paymentDraftGenerated || row?.targetPaymentDraftId || row?.targetPaymentDraftNo)
}

function normalizeApDraftRow(row = {}) {
  if (!row?.id) return row
  const generated = generatedPaymentDraft(row)
  if (!isPaymentDraftGeneratedRow(row) && !generated) return row
  const targetStatus = generated?.paymentDraftStatus || row.targetPaymentDraftStatus || ''
  return {
    ...row,
    apStatus: targetStatus === 'paymentReady' ? 'paymentPending' : 'paymentDraftGenerated',
    paymentDraftGenerated: true,
    targetPaymentDraftId: row.targetPaymentDraftId || generated?.id || '',
    targetPaymentDraftNo: row.targetPaymentDraftNo || generated?.paymentDraftNo || '',
    targetPaymentDraftStatus: targetStatus,
  }
}

function canGeneratePaymentDraft(row = {}) {
  return ['confirmed', 'paymentPending'].includes(row.apStatus) && !isPaymentDraftGeneratedRow(row)
}

function viewPaymentDraft(row = {}) {
  const generated = generatedPaymentDraft(row)
  const targetId = row.targetPaymentDraftId || generated?.id || ''
  if (targetId) return router.push(`/finance/payment-draft/${targetId}`)
  notify(row.targetPaymentDraftNo ? `已生成供应商付款草稿 ${row.targetPaymentDraftNo}，请在列表中查看。` : '已生成供应商付款草稿，请在列表中查看。', 'warning')
  return router.push('/finance/payment-drafts')
}

function viewApDraftFromSource(row = {}) {
  if (row.targetApDraftId) return router.push(`/finance/ap-draft/${row.targetApDraftId}`)
  notify(row.targetApDraftNo ? `已生成应付账款草稿 ${row.targetApDraftNo}，请在列表中查看。` : '已生成应付账款草稿，请在列表中查看。', 'warning')
  return router.push('/finance/ap-drafts')
}

function invoiceStatusLabel(status) {
  return { prepared: '已预备', waitingInvoice: '等待供应商开票', invoiceReceived: '已收到发票', matched: '可生成应付账款草稿', difference: '发票存在差异', payableReady: '可生成应付账款草稿', apDraftGenerated: '已生成应付账款草稿', cancelled: '取消', closed: '关闭' }[status] || status || '-'
}
function invoiceStatusType(status) {
  return { prepared: 'primary', waitingInvoice: 'warning', invoiceReceived: 'success', matched: 'success', difference: 'danger', payableReady: 'success', apDraftGenerated: 'success', cancelled: 'info', closed: 'info' }[status] || 'info'
}
function apStatusLabel(status) {
  return { draft: '草稿', confirmed: '可生成供应商付款草稿', paymentPending: '等待付款', paymentDraftGenerated: '已生成供应商付款草稿', partiallyPaid: '部分付款', paid: '已付款', cancelled: '取消', closed: '关闭' }[status] || status || '-'
}
function apStatusType(status) {
  return { draft: 'info', confirmed: 'success', paymentPending: 'warning', paymentDraftGenerated: 'success', partiallyPaid: 'warning', paid: 'success', cancelled: 'info', closed: 'info' }[status] || 'info'
}
function paymentStatusLabel(status) {
  return { unpaid: '未付款', partial: '部分付款', paid: '已付款' }[status] || status || '-'
}
function voucherStatusLabel(status) {
  return { notGenerated: '未生成凭证', voucherReady: '可生成凭证', generated: '已生成凭证' }[status] || status || '-'
}
function invoiceTypeLabel(type) {
  return { specialVat: '增值税专用发票', normalVat: '普通发票', receipt: '收据', other: '其他' }[type] || type || '-'
}

watch(() => route.fullPath, refresh, { immediate: true })
</script>

<style scoped>
.ap-draft-page { display: flex; flex-direction: column; gap: 16px; min-height: 100%; padding: 22px; background: #f5f7fb; color: #172033; }
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
.plain-flow-guide, .next-step-guide { display: grid; gap: 10px; border: 1px solid #a7f3d0; border-radius: 8px; padding: 14px; background: #ecfdf5; color: #064e3b; line-height: 1.6; }
.next-step-guide { border-color: #fde68a; background: #fffbeb; color: #78350f; }
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
