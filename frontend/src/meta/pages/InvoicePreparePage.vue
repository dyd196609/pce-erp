<template>
  <main class="finance-flow-page">
    <header class="page-header">
      <section>
        <p class="eyebrow">V1.12.4 采购发票预备</p>
        <h1>{{ detail ? '发票预备详情' : '采购发票预备' }}</h1>
        <p>本页根据应付核对生成发票预备，只做发票信息预登记和匹配准备，不生成正式应付，不生成付款，不生成财务凭证。</p>
        <p class="finance-current-module-badge">当前操作模块：发票预备</p>
      </section>
      <nav class="page-tabs finance-flow-nav" aria-label="财务前置流程导航">
        <span class="finance-nav-title">财务前置流程导航</span>
        <router-link class="finance-nav-button" to="/finance/payable-prepares">应付预备</router-link>
        <router-link class="finance-nav-button" to="/finance/payable-checks">应付核对</router-link>
        <router-link class="finance-nav-button finance-nav-button-active" to="/finance/invoice-prepares">发票预备 <span class="finance-current-tag">当前</span></router-link>
        <router-link class="finance-nav-button" to="/finance/ap-drafts">应付账款草稿</router-link>
        <router-link class="finance-nav-button" to="/finance/payment-drafts">供应商付款草稿</router-link>
        <router-link class="finance-nav-button" to="/finance/payment-prepares">正式付款单预备</router-link>
      </nav>
    </header>

    <el-alert v-if="message" :title="message" :type="messageType" show-icon :closable="false" />

    <section v-if="detail" class="operation-shell">
      <section class="plain-flow-guide">
        <strong>财务前置总流程：采购入库完成 -> 生成应付预备 -> 核对数量和金额 -> 准备发票信息 -> 生成应付账款草稿 -> 确认应付 -> 等待后续付款</strong>
        <div class="plain-flow-grid">
          <span><b>当前步骤</b>第 3 步：准备发票信息</span>
          <span><b>本页要做</b>根据已核对通过的应付核对单，记录等待供应商开票、已收到发票、发票金额是否匹配。</span>
          <span><b>下一步</b>发票确认匹配后，生成“应付账款草稿”。</span>
          <span><b>本页不会做</b>不生成正式应付账款、付款单或财务凭证。</span>
        </div>
      </section>
      <section class="next-step-guide">
        <strong>下一步操作</strong>
        <span>登记发票状态，确认发票已匹配后，点击“生成应付账款草稿”。</span>
        <el-button type="primary" @click="router.push('/finance/ap-drafts')">进入应付账款草稿</el-button>
      </section>
      <section class="flow-guide">
        <strong>作业流程：应付核对 -> 发票预备 -> 发票匹配 -> 后续正式应付</strong>
        <span>本页只做发票信息预登记和价税拆分准备，不生成正式应付、付款或财务凭证；发票匹配完成后，后续才可进入正式应付。</span>
      </section>
      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>{{ detail.invoicePrepareNo }}</h2>
              <span>{{ detail.sourcePayableCheckNo || '-' }} / {{ detail.supplierName || '-' }}</span>
            </div>
            <div class="button-row">
              <el-button @click="router.push('/finance/invoice-prepares')">返回列表</el-button>
              <el-button @click="router.push(`/finance/payable-check/${detail.sourcePayableCheckId}`)">查看应付核对</el-button>
              <el-button v-if="isApDraftGeneratedRow(detail)" @click="viewApDraft(detail)">查看应付账款草稿</el-button>
              <el-button v-else @click="router.push('/finance/ap-drafts')">查看应付账款草稿</el-button>
              <el-button v-if="detail.invoicePrepareStatus === 'prepared'" type="warning" @click="markWaiting(detail)">标记等待供应商开票</el-button>
              <el-button v-if="['prepared', 'waitingInvoice'].includes(detail.invoicePrepareStatus)" type="success" @click="markReceived(detail)">登记已收到发票</el-button>
              <el-button v-if="['invoiceReceived'].includes(detail.invoicePrepareStatus)" type="success" @click="markMatched(detail)">确认发票已匹配</el-button>
              <el-button v-if="!isApDraftGeneratedRow(detail) && !['cancelled', 'closed', 'payableReady'].includes(detail.invoicePrepareStatus)" type="danger" @click="markDifference(detail)">标记发票差异</el-button>
              <el-button v-if="!isApDraftGeneratedRow(detail) && ['matched'].includes(detail.invoicePrepareStatus)" type="primary" @click="markReady(detail)">准备生成应付账款草稿</el-button>
              <el-button v-if="canGenerateApDraft(detail)" type="success" @click="router.push('/finance/ap-drafts')">生成应付账款草稿</el-button>
              <el-button v-if="!isApDraftGeneratedRow(detail) && !['cancelled', 'closed', 'payableReady'].includes(detail.invoicePrepareStatus)" type="danger" @click="cancelPrepare(detail)">取消</el-button>
            </div>
          </div>
        </template>
        <el-alert title="采购发票预备流程：应付核对 -> 发票预备 -> 发票匹配 -> 后续正式应付。本页不生成正式应付、付款或财务凭证。" type="info" show-icon :closable="false" />
        <section class="amount-guide">
          <strong>金额口径</strong>
          <span>核对金额/含税金额 checkedAmount 等于发票金额 invoiceAmount；未税金额 noTaxAmount = 核对金额 / (1 + 税率)，税额 taxAmount = 核对金额 - 未税金额。默认税率显示为 13%，金额保留 2 位小数。</span>
        </section>
        <div class="info-grid">
          <article v-for="item in detailFields" :key="item.label">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </article>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>发票预备明细</h2></template>
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
          <el-table-column prop="invoiceAmount" label="含税金额" width="120" />
          <el-table-column prop="sourcePurchaseOrderNo" label="采购订单" min-width="150" />
          <el-table-column prop="sourceReceiveNo" label="收货单" min-width="150" />
          <el-table-column prop="sourceInspectionNo" label="检验单" min-width="150" />
          <el-table-column prop="rootRequestNo" label="原始请购单" min-width="150" />
        </el-table>
      </el-card>
    </section>

    <section v-else class="operation-shell">
      <section class="plain-flow-guide">
        <strong>财务前置总流程：采购入库完成 -> 生成应付预备 -> 核对数量和金额 -> 准备发票信息 -> 生成应付账款草稿 -> 确认应付 -> 等待后续付款</strong>
        <div class="plain-flow-grid">
          <span><b>当前步骤</b>第 3 步：准备发票信息</span>
          <span><b>本页要做</b>准备供应商发票信息，记录等待开票、已收票、发票是否匹配。</span>
          <span><b>下一步</b>发票确认匹配后，生成“应付账款草稿”。</span>
          <span><b>本页不会做</b>不生成正式应付账款、付款单或财务凭证。</span>
        </div>
      </section>
      <section class="next-step-guide">
        <strong>下一步操作</strong>
        <span>先生成发票预备，再登记发票状态；确认发票已匹配后，点击“生成应付账款草稿”。</span>
        <el-button type="primary" @click="router.push('/finance/ap-drafts')">进入应付账款草稿</el-button>
      </section>
      <section class="flow-guide">
        <strong>作业流程：应付核对 -> 发票预备 -> 发票匹配 -> 后续正式应付</strong>
        <span>发票预备金额来自应付核对金额，本页只做预登记和价税拆分，不生成正式应付、付款或财务凭证。</span>
      </section>
      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>发票预备来源</h2>
              <span>来源为 checked / invoicePrepareReady 状态的应付核对单。</span>
            </div>
            <div class="button-row">
              <el-button type="primary" @click="refresh">刷新来源</el-button>
              <el-button @click="router.push('/finance/payable-checks')">查看应付核对</el-button>
              <el-button @click="router.push('/finance/ap-drafts')">查看应付账款草稿</el-button>
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
          <el-button size="small" type="success" :disabled="!sourceBatchCounts.create" @click="runBatchCreateInvoices">批量生成发票预备</el-button>
        </div>
        <BatchResult v-if="sourceBatchResult" :result="sourceBatchResult" :type="sourceBatchResultType" @close="sourceBatchResult = null" />
        <el-table ref="sourceTableRef" :data="sortedSourceRows" border stripe height="460" @selection-change="handleSourceSelectionChange" @sort-change="handleSourceSortChange">
          <el-table-column type="selection" width="48" fixed="left" :selectable="sourceSelectable" />
          <el-table-column type="expand" width="44" fixed="left">
            <template #default="{ row }">{{ row.sourceRejectReason || '可生成发票预备' }}</template>
          </el-table-column>
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="payableCheckNo" label="应付核对单号" min-width="170" sortable="custom" />
          <el-table-column prop="sourcePayablePrepareNo" label="应付预备单号" min-width="170" sortable="custom" />
          <el-table-column prop="supplierName" label="供应商" min-width="150" sortable="custom" />
          <el-table-column prop="sourcePurchaseOrderNo" label="采购订单" min-width="150" sortable="custom" />
          <el-table-column prop="sourceReceiveNo" label="收货单" min-width="150" />
          <el-table-column prop="sourceInspectionNo" label="检验单" min-width="150" />
          <el-table-column prop="totalCheckedAmount" label="核对金额" width="120" sortable="custom" />
          <el-table-column prop="checkStatus" label="状态" width="140" sortable="custom">
            <template #default="{ row }"><el-tag :type="checkStatusType(row.checkStatus)">{{ checkStatusLabel(row.checkStatus) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="是否已生成" width="120">
            <template #default="{ row }"><el-tag :type="row.invoicePrepareGenerated ? 'success' : 'info'">{{ row.invoicePrepareGeneratedText }}</el-tag></template>
          </el-table-column>
          <el-table-column label="操作" fixed="right" :width="getActionColumnWidth(['查看应付核对', '生成发票预备'])">
            <template #default="{ row }">
              <div class="app-action-cell">
                <el-button size="small" class="app-action-button-md" @click="router.push(`/finance/payable-check/${row.id}`)">查看应付核对</el-button>
                <el-button v-if="!row.invoicePrepareGenerated" size="small" class="app-action-button-md" type="success" :disabled="!row.canCreateInvoicePrepare" @click="createInvoice(row)">生成发票预备</el-button>
                <el-button v-else size="small" class="app-action-button-md" @click="router.push('/finance/invoice-prepares')">查看发票预备</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>发票预备列表</h2></template>
        <div class="batch-bar">
          <span>已选择 {{ selectedInvoiceRows.length }} 条</span>
          <span class="sort-help">排序：点击表格表头字段可升序/降序排序；点击“清除排序”恢复默认顺序。</span>
          <span class="sort-help">{{ invoiceSortText }}</span>
          <el-button size="small" @click="resetInvoiceSorting">清除排序</el-button>
          <el-button size="small" @click="clearInvoiceSelection">清空选择</el-button>
          <span class="batch-action-title">当前模块操作（立即生效）</span>
          <span class="batch-action-tip">以下按钮会立即修改所选记录状态，请确认选择无误后再执行。</span>
          <el-button size="small" type="warning" :disabled="!selectedInvoiceRows.length" @click="runBatchWaiting">批量标记等待供应商开票</el-button>
          <el-button size="small" type="success" :disabled="!selectedInvoiceRows.length" @click="runBatchReceived">批量登记已收到发票</el-button>
          <el-button size="small" type="success" :disabled="!selectedInvoiceRows.length" @click="runBatchMatched">批量确认发票已匹配</el-button>
          <el-button size="small" type="primary" :disabled="!selectedInvoiceRows.length" @click="runBatchPayableReady">批量准备生成应付账款草稿</el-button>
        </div>
        <BatchResult v-if="invoiceBatchResult" :result="invoiceBatchResult" :type="invoiceBatchResultType" @close="invoiceBatchResult = null" />
        <el-table ref="invoiceTableRef" :data="sortedInvoiceRows" border stripe height="520" @selection-change="handleInvoiceSelectionChange" @sort-change="handleInvoiceSortChange">
          <el-table-column type="selection" width="48" fixed="left" />
          <el-table-column type="expand" width="44" fixed="left">
            <template #default="{ row }">来源：{{ row.sourcePayableCheckNo }}；差异原因：{{ row.differenceReason || '-' }}</template>
          </el-table-column>
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="invoicePrepareNo" label="发票预备单号" min-width="170" sortable="custom" />
          <el-table-column prop="sourcePayableCheckNo" label="来源应付核对" min-width="170" sortable="custom" />
          <el-table-column prop="supplierName" label="供应商" min-width="150" sortable="custom" />
          <el-table-column prop="invoiceType" label="发票类型" min-width="130" sortable="custom">
            <template #default="{ row }">{{ invoiceTypeLabel(row.invoiceType) }}</template>
          </el-table-column>
          <el-table-column prop="taxRate" label="税率%" width="90" sortable="custom" />
          <el-table-column prop="totalNoTaxAmount" label="未税金额" width="120" sortable="custom" />
          <el-table-column prop="totalTaxAmount" label="税额" width="110" sortable="custom" />
          <el-table-column prop="totalInvoiceAmount" label="含税金额" width="120" sortable="custom" />
          <el-table-column prop="invoicePrepareStatus" label="状态" width="170" sortable="custom">
            <template #default="{ row }"><el-tag :type="invoiceStatusType(row.invoicePrepareStatus)">{{ invoiceStatusLabel(row.invoicePrepareStatus) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="操作" fixed="right" :width="getActionColumnWidth(['查看详情', '等待供应商开票', '生成应付账款草稿'])">
            <template #default="{ row }">
              <div class="app-action-cell">
                <el-button size="small" class="app-action-button-sm" @click="router.push(`/finance/invoice-prepare/${row.id}`)">查看详情</el-button>
                <el-button v-if="row.invoicePrepareStatus === 'prepared'" size="small" class="app-action-button-lg" type="warning" @click="markWaiting(row)">标记等待供应商开票</el-button>
                <el-button v-if="['prepared', 'waitingInvoice'].includes(row.invoicePrepareStatus)" size="small" class="app-action-button-lg" type="success" @click="markReceived(row)">登记已收到发票</el-button>
                <el-button v-if="row.invoicePrepareStatus === 'invoiceReceived'" size="small" class="app-action-button-lg" type="success" @click="markMatched(row)">确认发票已匹配</el-button>
                <el-button v-if="!isApDraftGeneratedRow(row) && row.invoicePrepareStatus === 'matched'" size="small" class="app-action-button-lg" type="primary" @click="markReady(row)">准备生成应付账款草稿</el-button>
                <el-button v-if="canGenerateApDraft(row)" size="small" class="app-action-button-lg" type="success" @click="router.push('/finance/ap-drafts')">生成应付账款草稿</el-button>
                <el-button v-if="isApDraftGeneratedRow(row)" size="small" class="app-action-button-lg" type="success" @click="viewApDraft(row)">查看应付账款草稿</el-button>
                <el-button v-if="!isApDraftGeneratedRow(row) && !['cancelled', 'closed', 'payableReady'].includes(row.invoicePrepareStatus)" size="small" class="app-action-button-sm" type="danger" @click="cancelPrepare(row)">取消</el-button>
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
  batchCreateInvoicePreparesFromPayableChecks,
  batchMarkInvoiceMatched,
  batchMarkInvoiceReceived,
  batchMarkPayableReady,
  batchMarkWaitingInvoice,
  cancelInvoicePrepare,
  createInvoicePrepareFromPayableCheck,
  getInvoicePrepareById,
  getInvoicePrepareSourcesFromPayableChecks,
  listInvoicePrepares,
  markInvoiceDifference,
  markInvoiceMatched,
  markInvoiceReceived,
  markPayableReady,
  markWaitingInvoice,
} from '../finance/invoicePrepareStore.js'
import { listAccountPayableDrafts } from '../finance/accountPayableDraftStore.js'
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
      props.result.failedReason?.length ? h('ol', props.result.failedReason.map((reason) => h('li', { key: reason }, reason))) : null,
      props.result.failedReason?.length ? h('span', `下一步建议：${props.result.nextSuggestion}`) : null,
    ])
  },
})

const route = useRoute()
const router = useRouter()
const sourceRows = ref([])
const invoiceRows = ref([])
const apDraftRows = ref([])
const selectedSourceRows = ref([])
const selectedInvoiceRows = ref([])
const sourceSortState = ref({ key: '', direction: 'asc' })
const invoiceSortState = ref({ key: '', direction: 'asc' })
const sourceTableRef = ref(null)
const invoiceTableRef = ref(null)
const message = ref('')
const messageType = ref('success')
const sourceBatchResult = ref(null)
const sourceBatchResultType = ref('success')
const invoiceBatchResult = ref(null)
const invoiceBatchResultType = ref('success')

const detail = computed(() => route.params.id ? normalizeInvoicePrepareRow(getInvoicePrepareById(route.params.id)) : null)
const sourceIds = computed(() => selectedSourceRows.value.map((row) => row.id).filter(Boolean))
const invoiceIds = computed(() => selectedInvoiceRows.value.map((row) => row.id).filter(Boolean))
const sourceSortColumns = [
  { key: 'payableCheckNo', sortType: 'string' },
  { key: 'sourcePayablePrepareNo', sortType: 'string' },
  { key: 'supplierName', sortType: 'string' },
  { key: 'sourcePurchaseOrderNo', sortType: 'string' },
  { key: 'totalCheckedAmount', sortType: 'amount' },
  { key: 'checkStatus', sortType: 'status' },
]
const invoiceSortColumns = [
  { key: 'invoicePrepareNo', sortType: 'string' },
  { key: 'sourcePayableCheckNo', sortType: 'string' },
  { key: 'supplierName', sortType: 'string' },
  { key: 'invoiceType', sortType: 'string' },
  { key: 'taxRate', sortType: 'number' },
  { key: 'totalNoTaxAmount', sortType: 'amount' },
  { key: 'totalTaxAmount', sortType: 'amount' },
  { key: 'totalInvoiceAmount', sortType: 'amount' },
  { key: 'invoicePrepareStatus', sortType: 'status' },
]
const sortedSourceRows = computed(() => sortRecords(sourceRows.value, sourceSortState.value, sourceSortColumns))
const sortedInvoiceRows = computed(() => sortRecords(invoiceRows.value, invoiceSortState.value, invoiceSortColumns))
const sourceBatchCounts = computed(() => ({ create: selectedSourceRows.value.filter((row) => row.canCreateInvoicePrepare).length }))
const sourceSortText = computed(() => currentSortText(sourceSortState.value, {
  payableCheckNo: '应付核对单号',
  sourcePayablePrepareNo: '应付预备单号',
  supplierName: '供应商',
  sourcePurchaseOrderNo: '采购订单',
  totalCheckedAmount: '核对金额',
  checkStatus: '状态',
}))
const invoiceSortText = computed(() => currentSortText(invoiceSortState.value, {
  invoicePrepareNo: '发票预备单号',
  sourcePayableCheckNo: '来源应付核对',
  supplierName: '供应商',
  invoiceType: '发票类型',
  taxRate: '税率',
  totalNoTaxAmount: '未税金额',
  totalTaxAmount: '税额',
  totalInvoiceAmount: '含税金额',
  invoicePrepareStatus: '状态',
}))
const detailFields = computed(() => detail.value ? [
  { label: '发票预备单号', value: detail.value.invoicePrepareNo },
  { label: '来源应付核对', value: detail.value.sourcePayableCheckNo || '-' },
  { label: '来源应付预备', value: detail.value.sourcePayablePrepareNo || '-' },
  { label: '供应商', value: detail.value.supplierName || '-' },
  { label: '采购订单', value: detail.value.sourcePurchaseOrderNo || '-' },
  { label: '收货单', value: detail.value.sourceReceiveNo || '-' },
  { label: '检验单', value: detail.value.sourceInspectionNo || '-' },
  { label: '原始请购单', value: detail.value.rootRequestNo || '-' },
  { label: '发票类型', value: invoiceTypeLabel(detail.value.invoiceType) },
  { label: '税率', value: `${detail.value.taxRate}%` },
  { label: '未税金额', value: detail.value.totalNoTaxAmount },
  { label: '税额', value: detail.value.totalTaxAmount },
  { label: '含税金额', value: detail.value.totalInvoiceAmount },
  { label: '状态', value: invoiceStatusLabel(detail.value.invoicePrepareStatus) },
  { label: '目标应付账款草稿', value: detail.value.targetApDraftNo || '-' },
] : [])

function refresh() {
  sourceRows.value = getInvoicePrepareSourcesFromPayableChecks()
  apDraftRows.value = listAccountPayableDrafts()
  invoiceRows.value = listInvoicePrepares().map(normalizeInvoicePrepareRow)
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
function handleInvoiceSelectionChange(rows) { selectedInvoiceRows.value = rows || [] }
function clearSourceSelection() { selectedSourceRows.value = []; sourceTableRef.value?.clearSelection?.() }
function clearInvoiceSelection() { selectedInvoiceRows.value = []; invoiceTableRef.value?.clearSelection?.() }
function sourceSelectable(row) { return row.canCreateInvoicePrepare }

function handleSourceSortChange({ prop, order }) {
  sourceSortState.value = { key: prop || '', direction: order === 'descending' ? 'desc' : 'asc' }
  clearSourceSelection()
}

function handleInvoiceSortChange({ prop, order }) {
  invoiceSortState.value = { key: prop || '', direction: order === 'descending' ? 'desc' : 'asc' }
  clearInvoiceSelection()
}

function resetSourceSorting() { sourceSortState.value = { key: '', direction: 'asc' }; clearSourceSelection() }
function resetInvoiceSorting() { invoiceSortState.value = { key: '', direction: 'asc' }; clearInvoiceSelection() }

function nextBatchSuggestion(reasons = []) {
  const text = reasons.join('；')
  if (text.includes('重复') || text.includes('已生成')) return '建议查看已生成发票预备，避免重复生成。'
  if (text.includes('状态')) return '建议检查应付核对状态是否已达到 checked 或 invoicePrepareReady。'
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

function showInvoiceBatchResult(result, operationName) {
  refresh()
  clearInvoiceSelection()
  invoiceBatchResult.value = normalizeBatchResult(result, operationName)
  invoiceBatchResultType.value = result?.failedCount ? (result.successCount ? 'warning' : 'error') : 'success'
}

function runBatchCreateInvoices() {
  if (!sourceIds.value.length) return notify('请先选择可生成发票预备的应付核对', 'warning')
  showSourceBatchResult(batchCreateInvoicePreparesFromPayableChecks(sourceIds.value), '批量生成发票预备')
}

function runBatchWaiting() { showInvoiceBatchResult(batchMarkWaitingInvoice(invoiceIds.value), '批量标记等待供应商开票') }
function runBatchReceived() { showInvoiceBatchResult(batchMarkInvoiceReceived(invoiceIds.value), '批量登记已收到发票') }
function runBatchMatched() { showInvoiceBatchResult(batchMarkInvoiceMatched(invoiceIds.value), '批量确认发票已匹配') }
function runBatchPayableReady() { showInvoiceBatchResult(batchMarkPayableReady(invoiceIds.value), '批量准备生成应付账款草稿') }

function createInvoice(row) {
  const outcome = createInvoicePrepareFromPayableCheck(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  notify(`已生成发票预备 ${outcome.invoicePrepareNo}`)
}

function markWaiting(row) { const outcome = markWaitingInvoice(row.id); if (!outcome.success) return notify(outcome.error, 'warning'); refresh(); notify('已标记等待供应商开票') }
function markReceived(row) { const outcome = markInvoiceReceived(row.id); if (!outcome.success) return notify(outcome.error, 'warning'); refresh(); notify('已登记收到发票') }
function markMatched(row) { const outcome = markInvoiceMatched(row.id); if (!outcome.success) return notify(outcome.error, 'warning'); refresh(); notify('已确认发票匹配') }
function markDifference(row) { const outcome = markInvoiceDifference(row.id); if (!outcome.success) return notify(outcome.error, 'warning'); refresh(); notify('已标记发票差异') }
function markReady(row) { const outcome = markPayableReady(row.id); if (!outcome.success) return notify(outcome.error, 'warning'); refresh(); notify('已准备生成应付账款草稿，本轮不生成正式应付') }
function cancelPrepare(row) { const outcome = cancelInvoicePrepare(row.id); if (!outcome.success) return notify(outcome.error, 'warning'); refresh(); notify('发票预备已取消') }

function generatedApDraft(row = {}) {
  return apDraftRows.value.find((draft) => String(draft.sourceInvoicePrepareId) === String(row.id)) || null
}

function isApDraftGeneratedRow(row = {}) {
  return Boolean(row?.invoicePrepareStatus === 'apDraftGenerated' || row?.apDraftGenerated || row?.targetApDraftId || row?.targetApDraftNo || generatedApDraft(row))
}

function normalizeInvoicePrepareRow(row = {}) {
  if (!row?.id) return row
  const generated = generatedApDraft(row)
  if (!isApDraftGeneratedRow(row) && !generated) return row
  return {
    ...row,
    invoicePrepareStatus: 'apDraftGenerated',
    apDraftGenerated: true,
    targetApDraftId: row.targetApDraftId || generated?.id || '',
    targetApDraftNo: row.targetApDraftNo || generated?.apDraftNo || '',
  }
}

function canGenerateApDraft(row = {}) {
  return ['matched', 'payableReady'].includes(row.invoicePrepareStatus) && !isApDraftGeneratedRow(row)
}

function viewApDraft(row = {}) {
  const generated = generatedApDraft(row)
  const targetId = row.targetApDraftId || generated?.id || ''
  if (targetId) return router.push(`/finance/ap-draft/${targetId}`)
  notify(row.targetApDraftNo ? `已生成应付账款草稿 ${row.targetApDraftNo}，请在列表中查看。` : '已生成应付账款草稿，请在列表中查看。', 'warning')
  return router.push('/finance/ap-drafts')
}

function checkStatusLabel(status) {
  return { draft: '草稿', checking: '核对中', checked: '已核对', difference: '存在差异', invoicePrepareReady: '可生成发票预备', invoicePrepared: '已生成发票预备', cancelled: '取消', closed: '关闭' }[status] || status || '-'
}
function checkStatusType(status) {
  return { draft: 'info', checking: 'warning', checked: 'success', difference: 'danger', invoicePrepareReady: 'success', invoicePrepared: 'success', cancelled: 'info', closed: 'info' }[status] || 'info'
}
function invoiceStatusLabel(status) {
  return { prepared: '已预备', waitingInvoice: '等待供应商开票', invoiceReceived: '已收到发票', matched: '可生成应付账款草稿', difference: '发票存在差异', payableReady: '可生成应付账款草稿', apDraftGenerated: '已生成应付账款草稿', cancelled: '取消', closed: '关闭' }[status] || status || '-'
}
function invoiceStatusType(status) {
  return { prepared: 'primary', waitingInvoice: 'warning', invoiceReceived: 'success', matched: 'success', difference: 'danger', payableReady: 'success', apDraftGenerated: 'success', cancelled: 'info', closed: 'info' }[status] || 'info'
}
function invoiceTypeLabel(type) {
  return { specialVat: '增值税专用发票', normalVat: '普通发票', receipt: '收据', other: '其他' }[type] || type || '-'
}

watch(() => route.fullPath, refresh, { immediate: true })
</script>

<style scoped>
.finance-flow-page { display: flex; flex-direction: column; gap: 16px; min-height: 100%; padding: 22px; background: #f5f7fb; color: #172033; }
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
.next-step-guide { grid-template-columns: auto 1fr auto; align-items: center; border-color: #fde68a; background: #fffbeb; color: #78350f; }
.plain-flow-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
.plain-flow-grid span { display: grid; gap: 4px; border: 1px solid rgba(6, 78, 59, 0.14); border-radius: 8px; padding: 10px; background: #fff; }
.flow-guide, .amount-guide { display: grid; gap: 6px; border: 1px solid #bfdbfe; border-radius: 8px; padding: 12px; background: #eff6ff; color: #1e3a8a; line-height: 1.6; }
.amount-guide { margin-top: 12px; border-color: #dbe3ef; background: #f8fafc; color: #334155; }
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
  .plain-flow-grid, .next-step-guide { grid-template-columns: 1fr; }
}
</style>
