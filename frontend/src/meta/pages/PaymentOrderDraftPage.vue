<template>
  <main class="payment-order-draft-page">
    <header class="page-header">
      <section>
        <p class="eyebrow">V1.12.8 正式付款单草稿 / 付款执行确认</p>
        <h1>{{ detail ? '正式付款单草稿详情' : '正式付款单草稿' }}</h1>
        <p>本页根据正式付款单预备生成正式付款单草稿，只做付款执行确认，不执行真实付款，不生成银行付款，不生成财务凭证。</p>
        <p class="finance-current-module-badge">当前操作模块：正式付款单草稿</p>
      </section>
      <nav class="page-tabs finance-flow-nav" aria-label="财务前置流程导航">
        <span class="finance-nav-title">财务前置流程导航</span>
        <router-link class="finance-nav-button" to="/finance/payable-prepares">应付预备</router-link>
        <router-link class="finance-nav-button" to="/finance/payable-checks">应付核对</router-link>
        <router-link class="finance-nav-button" to="/finance/invoice-prepares">发票预备</router-link>
        <router-link class="finance-nav-button" to="/finance/ap-drafts">应付账款草稿</router-link>
        <router-link class="finance-nav-button" to="/finance/payment-drafts">供应商付款草稿</router-link>
        <router-link class="finance-nav-button" to="/finance/payment-prepares">正式付款单预备</router-link>
        <router-link class="finance-nav-button finance-nav-button-active" to="/finance/payment-order-drafts">正式付款单草稿 <span class="finance-current-tag">当前</span></router-link>
        <router-link class="finance-nav-button" to="/finance/payment-risk-reviews">真实付款风险评审</router-link>
      </nav>
    </header>

    <el-alert v-if="message" :title="message" :type="messageType" show-icon :closable="false" />

    <section v-if="detail" class="operation-shell">
      <section class="plain-flow-guide">
        <strong>正式付款单草稿流程：正式付款单预备 -> 正式付款单草稿 -> 付款执行确认 -> 可进入真实付款</strong>
        <div class="plain-flow-grid">
          <span><b>当前步骤</b>正式付款单草稿 / 付款执行确认。</span>
          <span><b>本页要做</b>检查付款单预备、供应商、金额、付款账户、防重复和财务边界。</span>
          <span><b>下一步做什么</b>确认通过后，只表示允许进入后续真实付款模块。</span>
          <span><b>本页不会做</b>不真实付款、不生成银行付款、不生成财务凭证、不写总账。</span>
          <span><b>状态边界</b>“可进入真实付款”表示付款执行前放行完成，真实付款尚未发生。</span>
        </div>
      </section>

      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>{{ detail.paymentOrderDraftNo }}</h2>
              <span>{{ detail.sourcePaymentPrepareNo || '-' }} / {{ detail.supplierName || '-' }}</span>
            </div>
            <div class="button-row">
              <el-button @click="router.push('/finance/payment-order-drafts')">返回列表</el-button>
              <el-button @click="router.push(`/finance/payment-prepare/${detail.sourcePaymentPrepareId}`)">查看正式付款单预备</el-button>
              <el-button v-if="canCheck(detail)" type="primary" @click="checkDraft(detail)">执行付款确认检查</el-button>
              <el-button v-if="canConfirm(detail)" type="success" @click="confirmDraft(detail)">确认付款执行</el-button>
              <el-button v-if="canReady(detail)" type="warning" @click="readyDraft(detail)">标记可进入真实付款</el-button>
              <el-button v-if="canRiskReview(detail)" type="primary" @click="enterRiskReview(detail)">进入真实付款风险评审</el-button>
              <el-button v-if="canCancel(detail)" type="danger" @click="cancelDraft(detail)">取消草稿</el-button>
            </div>
          </div>
        </template>
        <div class="info-grid">
          <article v-for="item in detailFields" :key="item.label">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </article>
        </div>
        <div v-if="detail.paymentOrderStatus === 'paymentReady'" class="payment-boundary-note">
          <strong>当前状态：可进入真实付款</strong>
          <span>该状态表示付款单草稿已经完成执行确认，可进入后续真实付款流程；本页没有执行真实付款，也不会生成银行流水或财务凭证。</span>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>付款执行确认检查项</h2></template>
        <el-table :data="detail.executionCheckItems || []" border stripe height="360">
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="label" label="检查项" min-width="190" />
          <el-table-column prop="passed" label="结果" width="120">
            <template #default="{ row }">
              <el-tag :type="row.passed ? 'success' : (row.severity === 'warning' ? 'warning' : 'danger')">
                {{ row.passed ? '通过' : (row.severity === 'warning' ? '警告' : '阻断') }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="message" label="说明" min-width="280" />
          <el-table-column prop="suggestion" label="处理建议" min-width="320" />
          <el-table-column prop="severity" label="级别" width="110" fixed="right">
            <template #default="{ row }">{{ severityLabel(row.severity) }}</template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>正式付款单草稿明细</h2></template>
        <el-table :data="detail.lines || []" border stripe height="500">
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="materialCode" label="物料编码" min-width="130" />
          <el-table-column prop="materialName" label="物料名称" min-width="160" />
          <el-table-column prop="spec" label="规格型号" min-width="120" />
          <el-table-column prop="unit" label="单位" width="90" />
          <el-table-column prop="payableAmount" label="应付金额" width="120" />
          <el-table-column prop="paidAmount" label="已付金额" width="120" />
          <el-table-column prop="unpaidAmount" label="未付金额" width="120" />
          <el-table-column prop="applyPayAmount" label="申请付款金额" width="140" />
          <el-table-column prop="approvedPayAmount" label="批准付款金额" width="140" />
          <el-table-column prop="draftPayAmount" label="草稿付款金额" width="140" />
          <el-table-column prop="confirmedPayAmount" label="确认付款金额" width="140" />
          <el-table-column prop="sourcePurchaseOrderNo" label="采购订单" min-width="150" />
          <el-table-column prop="sourceReceiveNo" label="收货单" min-width="150" />
          <el-table-column prop="sourceInspectionNo" label="检验单" min-width="150" />
          <el-table-column prop="sourceInventoryTransactionNo" label="库存流水" min-width="150" />
          <el-table-column prop="rootRequestNo" label="原始请购单" min-width="150" />
          <el-table-column prop="remark" label="备注" min-width="180" fixed="right" />
        </el-table>
      </el-card>
    </section>

    <section v-else class="operation-shell">
      <section class="plain-flow-guide">
        <strong>正式付款单草稿流程：正式付款单预备 -> 正式付款单草稿 -> 付款执行确认 -> 可进入真实付款</strong>
        <div class="plain-flow-grid">
          <span><b>当前步骤</b>正式付款单草稿 / 付款执行确认。</span>
          <span><b>本页要做</b>根据已检查通过的正式付款单预备，生成正式付款单草稿并确认是否可进入后续真实付款。</span>
          <span><b>下一步做什么</b>付款执行确认后，可标记“可进入真实付款”。</span>
          <span><b>本页不会做</b>不真实付款、不生成银行付款、不生成财务凭证、不写总账。</span>
          <span><b>状态边界</b>“可进入真实付款”表示付款执行前放行完成，真实付款尚未发生。</span>
        </div>
      </section>

      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>来源正式付款单预备</h2>
              <span>只允许 ready / checked 且未重复生成的正式付款单预备进入本页。</span>
            </div>
            <div class="button-row">
              <el-button type="primary" @click="refresh">刷新来源</el-button>
              <el-button @click="router.push('/finance/payment-prepares')">查看正式付款单预备</el-button>
            </div>
          </div>
        </template>
        <div class="batch-bar">
          <span>已选择 {{ selectedSourceRows.length }} 条</span>
          <span>可生成 {{ sourceBatchCounts.create }} 条</span>
          <span>跳过 {{ selectedSourceRows.length - sourceBatchCounts.create }} 条</span>
          <span class="sort-help">{{ sourceSortText }}</span>
          <el-button size="small" @click="resetSourceSorting">清除排序</el-button>
          <el-button size="small" @click="clearSourceSelection">清空选择</el-button>
          <span class="batch-action-title">当前模块操作（立即生效）</span>
          <span class="batch-action-tip">以下按钮会立即修改所选记录状态，请确认选择无误后再执行。</span>
          <el-button size="small" type="success" :disabled="!sourceBatchCounts.create" @click="runBatchCreateDrafts">批量生成正式付款单草稿</el-button>
        </div>
        <BatchResult v-if="sourceBatchResult" :result="sourceBatchResult" :type="sourceBatchResultType" @close="sourceBatchResult = null" />
        <el-table ref="sourceTableRef" :data="sortedSourceRows" border stripe height="460" @selection-change="handleSourceSelectionChange" @sort-change="handleSourceSortChange">
          <el-table-column type="selection" width="48" fixed="left" :selectable="sourceSelectable" />
          <el-table-column type="expand" width="44" fixed="left">
            <template #default="{ row }">{{ row.sourceRejectReason || '可生成正式付款单草稿；生成后会自动执行付款确认检查。' }}</template>
          </el-table-column>
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="paymentPrepareNo" label="付款预备单号" min-width="170" sortable="custom" />
          <el-table-column prop="sourcePaymentDraftNo" label="来源付款草稿" min-width="170" sortable="custom" />
          <el-table-column prop="sourceApDraftNo" label="来源应付草稿" min-width="170" sortable="custom" />
          <el-table-column prop="supplierName" label="供应商" min-width="150" sortable="custom" />
          <el-table-column prop="sourcePurchaseOrderNo" label="采购订单" min-width="150" sortable="custom" />
          <el-table-column prop="sourceReceiveNo" label="收货单" min-width="150" />
          <el-table-column prop="sourceInspectionNo" label="检验单" min-width="150" />
          <el-table-column prop="sourceInventoryTransactionNos" label="库存流水" min-width="150">
            <template #default="{ row }">{{ sourceInventoryText(row) }}</template>
          </el-table-column>
          <el-table-column prop="rootRequestNo" label="原始请购单" min-width="150" />
          <el-table-column prop="preparePayAmount" label="预备付款金额" width="140" sortable="custom" />
          <el-table-column prop="preCheckStatus" label="检查状态" width="130" sortable="custom">
            <template #default="{ row }"><el-tag :type="preCheckStatusType(row.preCheckStatus)">{{ preCheckStatusLabel(row.preCheckStatus) }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="paymentPrepareStatus" label="状态" width="150" sortable="custom">
            <template #default="{ row }"><el-tag :type="paymentPrepareStatusType(row.paymentPrepareStatus)">{{ paymentPrepareStatusLabel(row.paymentPrepareStatus) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="是否已生成付款单草稿" width="190">
            <template #default="{ row }"><el-tag :type="row.paymentOrderDraftGenerated ? 'success' : 'info'">{{ row.paymentOrderDraftGeneratedText }}</el-tag></template>
          </el-table-column>
          <el-table-column label="操作" fixed="right" :width="sourceActionColumnWidth">
            <template #default="{ row }">
              <div class="app-action-cell">
                <el-button size="small" class="app-action-button-lg" @click="router.push(`/finance/payment-prepare/${row.id}`)">查看正式付款单预备</el-button>
                <el-button v-if="!row.paymentOrderDraftGenerated" size="small" class="app-action-button-lg" type="success" :disabled="!row.canCreatePaymentOrderDraft" @click="createDraft(row)">生成正式付款单草稿</el-button>
                <el-button v-else size="small" class="app-action-button-lg" type="success" @click="viewPaymentOrderDraftFromSource(row)">查看正式付款单草稿</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>正式付款单草稿列表</h2></template>
        <div class="batch-bar">
          <span>已选择 {{ selectedDraftRows.length }} 条</span>
          <span class="sort-help">{{ draftSortText }}</span>
          <el-button size="small" @click="resetDraftSorting">清除排序</el-button>
          <el-button size="small" @click="clearDraftSelection">清空选择</el-button>
          <span class="batch-action-title">当前模块操作（会立即修改状态）</span>
          <span class="batch-action-tip">以下按钮作用和风险不同，请先核对说明再执行；本页不会执行真实付款。</span>
          <el-button size="small" type="primary" :disabled="!selectedDraftRows.length" @click="runBatchChecks">批量执行付款确认检查</el-button>
          <el-button size="small" type="success" :disabled="!selectedDraftRows.length" @click="runBatchConfirm">批量确认付款执行</el-button>
          <el-button size="small" type="warning" :disabled="!selectedDraftRows.length" @click="runBatchReady">批量标记可进入真实付款</el-button>
          <el-button size="small" type="danger" :disabled="!selectedDraftRows.length" @click="runBatchCancel">批量取消付款单草稿</el-button>
        </div>
        <div class="batch-action-guide" aria-label="正式付款单草稿批量操作说明">
          <article class="batch-action-card confirm">
            <strong>【确认类】批量确认付款执行</strong>
            <span class="risk-level">风险等级：中等</span>
            <p>确认所选付款草稿已完成付款执行确认，但不执行真实付款，也不是银行付款。</p>
          </article>
          <article class="batch-action-card release">
            <strong>【放行类】批量标记可进入真实付款</strong>
            <span class="risk-level">风险等级：重要放行</span>
            <p>将已确认的付款草稿标记为“可进入真实付款”，仅表示允许进入后续真实付款模块，不代表已经付款。</p>
          </article>
          <article class="batch-action-card danger">
            <strong>【取消类 / 高风险】批量取消付款单草稿</strong>
            <span class="risk-level">风险等级：高风险</span>
            <p>取消所选付款草稿。取消后不能继续进入真实付款；如需继续，需按规则重新生成或重新处理。</p>
          </article>
        </div>
        <BatchResult v-if="draftBatchResult" :result="draftBatchResult" :type="draftBatchResultType" @close="draftBatchResult = null" />
        <el-table ref="draftTableRef" :data="sortedDraftRows" border stripe height="540" @selection-change="handleDraftSelectionChange" @sort-change="handleDraftSortChange">
          <el-table-column type="selection" width="48" fixed="left" />
          <el-table-column type="expand" width="44" fixed="left">
            <template #default="{ row }">来源链路：{{ row.sourcePaymentPrepareNo }} / {{ row.sourcePaymentDraftNo }} / {{ row.sourceApDraftNo }}；本页只做付款执行确认，不真实付款。</template>
          </el-table-column>
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="paymentOrderDraftNo" label="正式付款单草稿号" min-width="180" sortable="custom" />
          <el-table-column prop="sourcePaymentPrepareNo" label="来源付款预备号" min-width="170" sortable="custom" />
          <el-table-column prop="supplierName" label="供应商" min-width="150" sortable="custom" />
          <el-table-column prop="draftPayAmount" label="草稿付款金额" width="140" sortable="custom" />
          <el-table-column prop="confirmedPayAmount" label="确认付款金额" width="140" sortable="custom" />
          <el-table-column prop="paymentMethod" label="付款方式" width="130">
            <template #default="{ row }">{{ paymentMethodLabel(row.paymentMethod) }}</template>
          </el-table-column>
          <el-table-column prop="paymentAccount" label="付款账户" min-width="150" />
          <el-table-column prop="supplierBankAccount" label="收款账户" min-width="170" />
          <el-table-column prop="executionCheckStatus" label="执行检查状态" width="150" sortable="custom">
            <template #default="{ row }"><el-tag :type="executionCheckStatusType(row.executionCheckStatus)">{{ executionCheckStatusLabel(row.executionCheckStatus) }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="paymentOrderStatus" label="付款状态" width="150" sortable="custom">
            <template #default="{ row }"><el-tag :type="paymentOrderStatusType(row.paymentOrderStatus)">{{ paymentOrderStatusLabel(row.paymentOrderStatus) }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="voucherStatus" label="凭证状态" width="130" sortable="custom">
            <template #default="{ row }">{{ voucherStatusLabel(row.voucherStatus) }}</template>
          </el-table-column>
          <el-table-column label="操作" fixed="right" :width="draftActionColumnWidth">
            <template #default="{ row }">
              <div class="app-action-cell">
                <el-button size="small" class="app-action-button-sm" @click="router.push(`/finance/payment-order-draft/${row.id}`)">查看详情</el-button>
                <el-button v-if="canCheck(row)" size="small" class="app-action-button-lg" type="primary" @click="checkDraft(row)">执行付款确认检查</el-button>
                <el-button v-if="canConfirm(row)" size="small" class="app-action-button-md" type="success" @click="confirmDraft(row)">确认付款执行</el-button>
                <el-button v-if="canReady(row)" size="small" class="app-action-button-lg" type="warning" @click="readyDraft(row)">可进入真实付款</el-button>
                <el-button v-if="canRiskReview(row)" size="small" class="app-action-button-lg" type="primary" @click="enterRiskReview(row)">进入真实付款风险评审</el-button>
                <el-button v-if="canCancel(row)" size="small" class="app-action-button-sm" type="danger" @click="cancelDraft(row)">取消</el-button>
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
  batchCancelPaymentOrderDrafts,
  batchCreatePaymentOrderDraftsFromPaymentPrepares,
  batchMarkPaymentExecutionConfirmed,
  batchMarkPaymentOrderPaymentReady,
  batchRunPaymentExecutionChecks,
  cancelPaymentOrderDraft,
  createPaymentOrderDraftFromPaymentPrepare,
  getPaymentOrderDraftById,
  getPaymentOrderDraftSourcesFromPaymentPrepares,
  listPaymentOrderDrafts,
  markPaymentExecutionConfirmed,
  markPaymentOrderDraftChecking,
  markPaymentOrderPaymentReady,
} from '../finance/paymentOrderDraftStore.js'
import { getActionColumnWidthForRows } from '../runtime/tableActionColumnEngine.js'
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
      h('span', `已达成：${props.result.alreadyDoneCount || 0} 条`),
      h('span', `失败/跳过：${props.result.failedCount} 条`),
      props.result.alreadyDoneItems?.length ? h('ol', { class: 'already-done-list' }, props.result.alreadyDoneItems.map((item) => h('li', { key: item.id }, `${item.no}：${item.reason}`))) : null,
      props.result.failedReason?.length ? h('ol', props.result.failedReason.map((reason) => h('li', { key: reason }, reason))) : null,
      props.result.resultNote ? h('span', `说明：${props.result.resultNote}`) : null,
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
const detailVersion = ref(0)

const detail = computed(() => {
  detailVersion.value
  return route.params.id ? getPaymentOrderDraftById(route.params.id) : null
})
const sourceIds = computed(() => selectedSourceRows.value.map((row) => row.id).filter(Boolean))
const draftIds = computed(() => selectedDraftRows.value.map((row) => row.id).filter(Boolean))
const sourceSortColumns = [
  { key: 'paymentPrepareNo', sortType: 'string' },
  { key: 'sourcePaymentDraftNo', sortType: 'string' },
  { key: 'sourceApDraftNo', sortType: 'string' },
  { key: 'supplierName', sortType: 'string' },
  { key: 'sourcePurchaseOrderNo', sortType: 'string' },
  { key: 'preparePayAmount', sortType: 'amount' },
  { key: 'preCheckStatus', sortType: 'status' },
  { key: 'paymentPrepareStatus', sortType: 'status' },
]
const draftSortColumns = [
  { key: 'paymentOrderDraftNo', sortType: 'string' },
  { key: 'sourcePaymentPrepareNo', sortType: 'string' },
  { key: 'supplierName', sortType: 'string' },
  { key: 'draftPayAmount', sortType: 'amount' },
  { key: 'confirmedPayAmount', sortType: 'amount' },
  { key: 'executionCheckStatus', sortType: 'status' },
  { key: 'paymentOrderStatus', sortType: 'status' },
  { key: 'voucherStatus', sortType: 'status' },
]
const sortedSourceRows = computed(() => sortRecords(sourceRows.value, sourceSortState.value, sourceSortColumns))
const sortedDraftRows = computed(() => sortRecords(draftRows.value, draftSortState.value, draftSortColumns))
const sourceBatchCounts = computed(() => ({ create: selectedSourceRows.value.filter((row) => row.canCreatePaymentOrderDraft).length }))
const sourceActionColumnWidth = computed(() => getActionColumnWidthForRows(sortedSourceRows.value, sourceRowActions, ['查看正式付款单预备', '生成正式付款单草稿']))
const draftActionColumnWidth = computed(() => getActionColumnWidthForRows(sortedDraftRows.value, draftRowActions, ['查看详情', '进入真实付款风险评审']))
const sourceSortText = computed(() => currentSortText(sourceSortState.value, {
  paymentPrepareNo: '付款预备单号',
  sourcePaymentDraftNo: '来源付款草稿',
  sourceApDraftNo: '来源应付草稿',
  supplierName: '供应商',
  sourcePurchaseOrderNo: '采购订单',
  preparePayAmount: '预备付款金额',
  preCheckStatus: '检查状态',
  paymentPrepareStatus: '状态',
}))
const draftSortText = computed(() => currentSortText(draftSortState.value, {
  paymentOrderDraftNo: '正式付款单草稿号',
  sourcePaymentPrepareNo: '来源付款预备号',
  supplierName: '供应商',
  draftPayAmount: '草稿付款金额',
  confirmedPayAmount: '确认付款金额',
  executionCheckStatus: '执行检查状态',
  paymentOrderStatus: '付款状态',
  voucherStatus: '凭证状态',
}))
const detailFields = computed(() => detail.value ? [
  { label: '正式付款单草稿号', value: detail.value.paymentOrderDraftNo },
  { label: '来源付款预备', value: detail.value.sourcePaymentPrepareNo || '-' },
  { label: '来源供应商付款草稿', value: detail.value.sourcePaymentDraftNo || '-' },
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
  { label: '批准付款金额', value: detail.value.approvedPayAmount },
  { label: '草稿付款金额', value: detail.value.draftPayAmount },
  { label: '确认付款金额', value: detail.value.confirmedPayAmount },
  { label: '预计付款日期', value: detail.value.expectedPayDate || '-' },
  { label: '付款方式', value: paymentMethodLabel(detail.value.paymentMethod) },
  { label: '付款账户', value: detail.value.paymentAccount || '-' },
  { label: '付款账户名称', value: detail.value.paymentAccountName || '-' },
  { label: '付款银行', value: detail.value.paymentBankName || '-' },
  { label: '供应商开户行', value: detail.value.supplierBankName || '-' },
  { label: '供应商银行账号', value: detail.value.supplierBankAccount || '-' },
  { label: '供应商账户名称', value: detail.value.supplierBankAccountName || '-' },
  { label: '执行检查状态', value: executionCheckStatusLabel(detail.value.executionCheckStatus) },
  { label: '付款状态', value: paymentOrderStatusLabel(detail.value.paymentOrderStatus) },
  { label: '银行付款状态', value: bankPaymentStatusLabel(detail.value.bankPaymentStatus) },
  { label: '凭证状态', value: voucherStatusLabel(detail.value.voucherStatus) },
] : [])

function refresh() {
  sourceRows.value = getPaymentOrderDraftSourcesFromPaymentPrepares()
  draftRows.value = listPaymentOrderDrafts()
  detailVersion.value += 1
}

function notify(text, type = 'success') {
  message.value = text
  messageType.value = type
  window.clearTimeout(notify.timer)
  notify.timer = window.setTimeout(() => { message.value = '' }, 2400)
}

function currentSortText(state = {}, labels = {}) {
  if (!state.key) return '排序：点击表格表头字段可升序/降序排序；点击‘清除排序’恢复默认顺序。'
  return `当前排序：${labels[state.key] || state.key} / ${state.direction === 'desc' ? '降序' : '升序'}`
}

function handleSourceSelectionChange(rows) { selectedSourceRows.value = rows || [] }
function handleDraftSelectionChange(rows) { selectedDraftRows.value = rows || [] }
function clearSourceSelection() { selectedSourceRows.value = []; sourceTableRef.value?.clearSelection?.() }
function clearDraftSelection() { selectedDraftRows.value = []; draftTableRef.value?.clearSelection?.() }
function sourceSelectable(row) { return row.canCreatePaymentOrderDraft }

function sourceRowActions(row = {}) {
  return [
    '查看正式付款单预备',
    row.paymentOrderDraftGenerated ? '查看正式付款单草稿' : '生成正式付款单草稿',
  ]
}

function draftRowActions(row = {}) {
  return [
    '查看详情',
    { label: '执行付款确认检查', visible: canCheck(row) },
    { label: '确认付款执行', visible: canConfirm(row) },
    { label: '可进入真实付款', visible: canReady(row) },
    { label: '进入真实付款风险评审', visible: canRiskReview(row) },
    { label: '取消', visible: canCancel(row) },
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

function nextBatchSuggestion(reasons = [], alreadyDoneCount = 0) {
  if (!reasons.length && alreadyDoneCount > 0) return '所选记录已是目标状态，无需重复操作。'
  const text = reasons.join('；')
  if (text.includes('重复') || text.includes('已生成')) return '建议查看已生成的付款单草稿；若原草稿已取消，可重新生成。'
  if (text.includes('ready') || text.includes('checked') || text.includes('状态')) return '建议先在正式付款单预备中完成检查并标记可进入正式付款。'
  if (text.includes('金额') || text.includes('未付款')) return '建议检查未付金额、预备付款金额和确认付款金额。'
  if (text.includes('银行') || text.includes('账户')) return '建议补充付款账户和供应商收款账户后重新检查。'
  if (text.includes('检查')) return '建议处理阻断项后重新执行付款确认检查。'
  return '请按失败原因处理后重新执行。'
}

function normalizeBatchResult(result = {}, operationName = '批量操作') {
  const failedReason = result.failedReason || []
  const alreadyDoneItems = result.alreadyDoneItems || []
  const alreadyDoneCount = result.alreadyDoneCount || alreadyDoneItems.length || 0
  const resultNote = operationName.includes('可进入真实付款')
    ? (result.successCount ? '所选记录已标记为“可进入真实付款”，但尚未执行真实付款。' : (alreadyDoneCount ? '所选记录已经是“可进入真实付款”，无需重复标记。' : ''))
    : ''
  return {
    operationName,
    total: result.total ?? 0,
    successCount: result.successCount || 0,
    alreadyDoneCount,
    alreadyDoneItems,
    failedCount: result.failedCount || 0,
    failedReason,
    resultNote,
    nextSuggestion: nextBatchSuggestion(failedReason, alreadyDoneCount),
  }
}

function batchResultType(result = {}) {
  if (!result?.failedCount) return 'success'
  return (result.successCount || result.alreadyDoneCount) ? 'warning' : 'error'
}

function showSourceBatchResult(result, operationName) {
  refresh()
  clearSourceSelection()
  sourceBatchResult.value = normalizeBatchResult(result, operationName)
  sourceBatchResultType.value = batchResultType(result)
}

function showDraftBatchResult(result, operationName) {
  refresh()
  clearDraftSelection()
  draftBatchResult.value = normalizeBatchResult(result, operationName)
  draftBatchResultType.value = batchResultType(result)
}

function runBatchCreateDrafts() {
  if (!sourceIds.value.length) return notify('请先选择可生成正式付款单草稿的正式付款单预备。', 'warning')
  showSourceBatchResult(batchCreatePaymentOrderDraftsFromPaymentPrepares(sourceIds.value), '批量生成正式付款单草稿')
}

function runBatchChecks() {
  if (!draftIds.value.length) return notify('请先选择正式付款单草稿。', 'warning')
  showDraftBatchResult(batchRunPaymentExecutionChecks(draftIds.value), '批量执行付款确认检查')
}

function runBatchConfirm() {
  if (!draftIds.value.length) return notify('请先选择正式付款单草稿。', 'warning')
  showDraftBatchResult(batchMarkPaymentExecutionConfirmed(draftIds.value), '批量确认付款执行')
}

function runBatchReady() {
  if (!draftIds.value.length) return notify('请先选择正式付款单草稿。', 'warning')
  showDraftBatchResult(batchMarkPaymentOrderPaymentReady(draftIds.value), '批量标记可进入真实付款')
}

function runBatchCancel() {
  if (!draftIds.value.length) return notify('请先选择正式付款单草稿。', 'warning')
  showDraftBatchResult(batchCancelPaymentOrderDrafts(draftIds.value), '批量取消付款单草稿')
}

function createDraft(row) {
  const outcome = createPaymentOrderDraftFromPaymentPrepare(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  notify(`已生成正式付款单草稿 ${outcome.paymentOrderDraftNo}`)
}

function viewPaymentOrderDraftFromSource(row = {}) {
  if (row.targetPaymentOrderDraftId) return router.push(`/finance/payment-order-draft/${row.targetPaymentOrderDraftId}`)
  notify(row.targetPaymentOrderDraftNo ? `已生成正式付款单草稿 ${row.targetPaymentOrderDraftNo}，请在列表中查看。` : '已生成正式付款单草稿，请在列表中查看。', 'warning')
  return router.push('/finance/payment-order-drafts')
}

function checkDraft(row) {
  const outcome = markPaymentOrderDraftChecking(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  notify(outcome.paymentOrderDraft.executionCheckStatus === 'blocked' ? '付款确认检查存在阻断项。' : '付款确认检查已执行。', outcome.paymentOrderDraft.executionCheckStatus === 'blocked' ? 'warning' : 'success')
}

function confirmDraft(row) {
  const outcome = markPaymentExecutionConfirmed(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  notify(outcome.paymentOrderDraft.executionCheckStatus === 'blocked' ? '付款确认检查未通过，不能确认付款执行。' : '已确认付款执行；本轮未真实付款。', outcome.paymentOrderDraft.executionCheckStatus === 'blocked' ? 'warning' : 'success')
}

function readyDraft(row) {
  const outcome = markPaymentOrderPaymentReady(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  notify('已标记可进入真实付款；本轮不执行真实付款。')
}

function enterRiskReview(row = {}) {
  router.push(`/finance/payment-risk-reviews?sourceId=${row.id}`)
}

function cancelDraft(row) {
  const outcome = cancelPaymentOrderDraft(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  notify('正式付款单草稿已取消。')
}

function canCheck(row = {}) {
  return ['draft', 'checking'].includes(row.paymentOrderStatus)
}

function canConfirm(row = {}) {
  return ['draft', 'checking'].includes(row.paymentOrderStatus)
}

function canReady(row = {}) {
  return row.paymentOrderStatus === 'confirmed'
}

function canRiskReview(row = {}) {
  return row.paymentOrderStatus === 'paymentReady'
}

function canCancel(row = {}) {
  return ['draft', 'checking'].includes(row.paymentOrderStatus)
}

function paymentPrepareStatusLabel(status) {
  return { draft: '草稿', checking: '检查中', checked: '已检查', ready: '可进入正式付款', blocked: '检查未通过', cancelled: '取消', closed: '关闭' }[status] || status || '-'
}
function paymentPrepareStatusType(status) {
  return { draft: 'info', checking: 'primary', checked: 'success', ready: 'warning', blocked: 'danger', cancelled: 'info', closed: 'info' }[status] || 'info'
}
function paymentOrderStatusLabel(status) {
  return { draft: '草稿', checking: '执行确认中', confirmed: '付款执行已确认', paymentReady: '可进入真实付款', cancelled: '取消', closed: '关闭' }[status] || status || '-'
}
function paymentOrderStatusType(status) {
  return { draft: 'info', checking: 'primary', confirmed: 'success', paymentReady: 'warning', cancelled: 'info', closed: 'info' }[status] || 'info'
}
function preCheckStatusLabel(status) {
  return { notChecked: '未检查', passed: '通过', warning: '有警告', blocked: '阻断' }[status] || status || '-'
}
function preCheckStatusType(status) {
  return { notChecked: 'info', passed: 'success', warning: 'warning', blocked: 'danger' }[status] || 'info'
}
function executionCheckStatusLabel(status) {
  return { notChecked: '未检查', passed: '通过', warning: '有警告', blocked: '阻断' }[status] || status || '-'
}
function executionCheckStatusType(status) {
  return { notChecked: 'info', passed: 'success', warning: 'warning', blocked: 'danger' }[status] || 'info'
}
function paymentMethodLabel(method) {
  return { bankTransfer: '银行转账', cash: '现金', acceptance: '承兑', other: '其他' }[method] || method || '-'
}
function bankPaymentStatusLabel(status) {
  return { notPaid: '未真实付款', readyForBankPayment: '可进入银行付款', paid: '已付款' }[status] || status || '-'
}
function voucherStatusLabel(status) {
  return { notGenerated: '未生成凭证', voucherReady: '可生成凭证', generated: '已生成凭证' }[status] || status || '-'
}
function severityLabel(severity) {
  return { info: '提示', warning: '警告', error: '阻断' }[severity] || severity || '-'
}
function sourceInventoryText(row = {}) {
  const nos = row.sourceInventoryTransactionNos || row.sourceInventoryTransactionNo || ''
  if (Array.isArray(nos)) return nos.filter(Boolean).join('、') || '-'
  return nos || '-'
}

watch(() => route.fullPath, refresh, { immediate: true })
</script>

<style scoped>
.payment-order-draft-page { display: flex; flex-direction: column; gap: 16px; min-height: 100%; padding: 22px; background: #f5f7fb; color: #172033; }
.page-header, .card-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.page-header p { margin: 6px 0 0; color: #475467; line-height: 1.5; }
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
.info-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; margin-top: 14px; }
.info-grid article { border: 1px solid #dbe3ef; border-radius: 8px; padding: 12px; background: #fff; }
.info-grid strong { display: block; margin-top: 4px; }
.payment-boundary-note { display: grid; gap: 6px; margin-top: 12px; border: 1px solid #fed7aa; border-radius: 8px; padding: 12px; background: #fff7ed; color: #9a3412; line-height: 1.6; }
.batch-bar { border: 1px solid #dbe3ef; border-radius: 8px; padding: 10px; margin-bottom: 12px; background: #f8fafc; }
.batch-action-guide { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin: -4px 0 12px; }
.batch-action-card { display: grid; gap: 6px; border: 1px solid #bfdbfe; border-radius: 8px; padding: 10px; background: #eff6ff; color: #1e3a8a; line-height: 1.5; }
.batch-action-card p { margin: 0; }
.batch-action-card.release { border-color: #fcd34d; background: #fffbeb; color: #92400e; }
.batch-action-card.danger { border-color: #fecaca; background: #fef2f2; color: #991b1b; }
.risk-level { font-size: 12px; font-weight: 800; }
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
  .batch-action-guide { grid-template-columns: 1fr; }
}
</style>
