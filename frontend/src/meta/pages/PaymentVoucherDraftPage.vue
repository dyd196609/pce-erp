<template>
  <main class="payment-voucher-draft-page">
    <header class="page-header">
      <section>
        <p class="eyebrow">V1.13.4 付款凭证草稿页面原型</p>
        <h1>{{ detail ? '付款凭证草稿详情' : '付款凭证草稿' }}</h1>
        <p>本页只生成付款凭证草稿，不生成正式财务凭证，不写总账，不过账，不做付款核销。</p>
        <p class="finance-current-module-badge">当前操作模块：付款凭证草稿</p>
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
        <router-link class="finance-nav-button" to="/finance/payment-risk-reviews">真实付款风险评审</router-link>
        <router-link class="finance-nav-button" to="/finance/payment-executions">付款执行草稿</router-link>
        <router-link class="finance-nav-button" to="/finance/payment-record-reviews">付款记录复核</router-link>
        <router-link class="finance-nav-button finance-nav-button-active" to="/finance/payment-voucher-drafts">付款凭证草稿<span class="finance-current-tag">当前</span></router-link>
        <router-link class="finance-nav-button" to="/finance/payment-voucher-reviews">付款凭证复核</router-link>
      </nav>
    </header>

    <el-alert v-if="message" :title="message" :type="messageType" show-icon :closable="false" />

    <section v-if="detail" class="operation-shell">
      <section class="plain-flow-guide">
        <strong>付款凭证草稿流程：付款记录复核通过 -> 生成付款凭证草稿 -> 提交凭证复核</strong>
        <div class="plain-flow-grid">
          <span><b>当前步骤</b>维护付款凭证草稿和分录草案。</span>
          <span><b>本页做什么</b>查看来源链、风险检查、借贷分录草案、提交复核或取消草稿。</span>
          <span><b>下一步做什么</b>进入后续凭证复核；本轮终点是“待凭证复核”。</span>
          <span><b>本页不做什么</b>不生成正式凭证、不写总账、不过账、不核销。</span>
        </div>
      </section>

      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>{{ detail.voucherDraftNo }}</h2>
              <span>{{ detail.sourcePaymentRecordReviewNo || '-' }} / {{ detail.supplierName || '-' }}</span>
            </div>
            <div class="button-row">
              <el-button @click="router.push('/finance/payment-voucher-drafts')">返回列表</el-button>
              <el-button @click="router.push(`/finance/payment-record-review/${detail.sourcePaymentRecordReviewId}`)">查看付款记录复核</el-button>
              <el-button v-if="detail.voucherStatus === 'draft'" class="app-next-action-button" type="primary" @click="handleSubmit(detail)">提交凭证复核<span class="app-next-action-badge">下一步</span></el-button>
              <el-button v-if="detail.voucherStatus === 'draft'" type="danger" @click="handleCancel(detail)">取消凭证草稿</el-button>
              <el-button v-if="showVoucherReviewEntry(detail)" :class="{ 'app-next-action-button': !voucherReviewTarget(detail) }" type="success" @click="handleVoucherReviewEntry(detail)">{{ voucherReviewEntryLabel(detail) }}<span v-if="!voucherReviewTarget(detail)" class="app-next-action-badge">下一步</span></el-button>
            </div>
          </div>
        </template>
        <div class="boundary-note">当前状态：{{ statusLabel(detail.voucherStatus) }}。付款凭证草稿不是正式凭证，不写总账，不过账，不做付款核销。</div>
        <div :class="nextStepGuideClass(detail.voucherStatus)">
          <strong>{{ nextStepTitle(detail.voucherStatus) }}</strong>
          <span>{{ nextStepDescription(detail.voucherStatus) }}</span>
        </div>
        <div class="subject-note">当前科目为草稿占位：2202 应付账款 / 1002 银行存款。后续需接入正式会计科目体系。</div>
        <div class="info-grid">
          <article v-for="item in detailFields" :key="item.label">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </article>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>来源追踪</h2></template>
        <div class="source-chain">
          <article v-for="item in sourceChain" :key="item.label">
            <span>{{ item.label }}</span>
            <strong>{{ item.value || '-' }}</strong>
          </article>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>风险检查</h2></template>
        <el-table :data="detail.riskItems || []" border stripe height="320">
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="itemName" label="检查项" min-width="180" />
          <el-table-column prop="result" label="结果" width="120">
            <template #default="{ row }"><el-tag :type="riskItemType(row.level)">{{ riskItemLabel(row.result) }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="message" label="说明" min-width="360" />
          <el-table-column prop="level" label="级别" width="120" fixed="right">
            <template #default="{ row }">{{ riskItemLabel(row.level) }}</template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>凭证分录草稿</h2></template>
        <el-table :data="detail.lines || []" border stripe height="360">
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="direction" label="借贷方向" width="110">
            <template #default="{ row }">{{ row.direction === 'debit' ? '借方' : '贷方' }}</template>
          </el-table-column>
          <el-table-column prop="accountCode" label="科目编码" width="120" />
          <el-table-column prop="accountName" label="科目名称" min-width="150" />
          <el-table-column prop="amount" label="金额" width="130" sortable />
          <el-table-column prop="cashFlowItem" label="现金流量项目" min-width="200" />
          <el-table-column prop="sourcePurchaseOrderNo" label="来源采购订单" min-width="150" />
          <el-table-column prop="sourceReceiveNo" label="来源收货单" min-width="150" />
          <el-table-column prop="sourceInspectionNo" label="来源检验单" min-width="150" />
          <el-table-column prop="sourceInventoryTransactionNo" label="来源库存流水" min-width="160" />
          <el-table-column prop="rootRequestNo" label="原始请购单" min-width="150" />
          <el-table-column prop="remark" label="备注" min-width="260" fixed="right" />
        </el-table>
      </el-card>
    </section>

    <section v-else class="operation-shell">
      <section class="plain-flow-guide">
        <strong>付款凭证草稿边界</strong>
        <div class="plain-flow-grid">
          <span><b>来源</b>只允许从付款记录复核通过的记录生成。</span>
          <span><b>草稿</b>只生成借贷分录草案，不生成正式凭证号。</span>
          <span><b>复核</b>提交后仅进入“待凭证复核”，本轮不继续推进。</span>
          <span><b>财务边界</b>不写总账、不过账、不做付款核销。</span>
        </div>
      </section>

      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>来源付款记录复核区</h2>
              <span>只允许从“复核通过”的付款记录复核生成付款凭证草稿。</span>
            </div>
            <div class="button-row">
              <el-button @click="refresh">刷新来源</el-button>
              <el-button @click="router.push('/finance/payment-record-reviews')">查看付款记录复核</el-button>
            </div>
          </div>
        </template>
        <div class="batch-bar">
          <span>已选择 {{ selectedSourceRows.length }} 条</span>
          <span class="batch-action-title">当前模块操作（生成凭证草稿）</span>
          <span class="batch-action-tip">只生成付款凭证草稿，不生成正式财务凭证、不写总账。</span>
          <el-button type="primary" size="small" :disabled="!sourceIds.length" @click="handleBatchCreate">批量生成付款凭证草稿</el-button>
        </div>
        <BatchResult v-if="sourceBatchResult" :result="sourceBatchResult" :type="batchResultType(sourceBatchResult)" @close="sourceBatchResult = null" />
        <BusinessTableScrollContainer class="pce-baseline-table-shell" acceptance-id="business-table-scroll-payment-voucher-drafts-source" page-id="payment-voucher-draft" table-id="payment-voucher-drafts-source" min-width="2200px">
        <el-table ref="sourceTableRef" class="global-sort-arrow" :data="filteredSources" border stripe height="420" @selection-change="selectedSourceRows = $event">
          <el-table-column type="selection" width="48" fixed="left" class-name="business-table-selection-column" header-class-name="business-table-selection-column" label-class-name="business-table-selection-column" />
          <el-table-column type="index" label="序号" width="70" fixed="left" class-name="pce-fixed-index-column" header-class-name="pce-fixed-index-column" label-class-name="pce-fixed-index-column" />
          <el-table-column prop="paymentRecordReviewNo" label="付款记录复核单号" min-width="180" sortable fixed="left" class-name="pce-fixed-primary-no-column" header-class-name="pce-fixed-primary-no-column" label-class-name="pce-fixed-primary-no-column" />
          <el-table-column prop="sourcePaymentExecutionNo" label="来源付款执行草稿" min-width="180" />
          <el-table-column prop="supplierName" label="供应商" min-width="150" />
          <el-table-column prop="executionAmount" label="执行金额" width="130" sortable />
          <el-table-column prop="reviewStatus" label="复核状态" width="130">
            <template #default="{ row }"><el-tag :type="row.reviewStatus === 'passed' ? 'success' : 'info'">{{ row.reviewStatus === 'passed' ? '复核通过' : row.reviewStatus }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="reviewerName" label="复核人" width="130">
            <template #default="{ row }">{{ row.reviewerName || row.reviewer || row.currentReviewerName || '-' }}</template>
          </el-table-column>
          <el-table-column label="凭证草稿" width="170">
            <template #default="{ row }"><el-tag :type="row.paymentVoucherDraftGenerated ? 'success' : (row.canGeneratePaymentVoucherDraft ? 'primary' : 'info')">{{ row.paymentVoucherDraftGenerated ? '已生成凭证草稿' : (row.canGeneratePaymentVoucherDraft ? '可生成凭证草稿' : '暂不可生成') }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="disabledReason" label="限制原因" min-width="260" />
          <el-table-column label="操作" fixed="right" :width="sourceActionColumnWidth" class-name="payment-fixed-action-column" header-class-name="payment-fixed-action-column" label-class-name="payment-fixed-action-column">
            <template #default="{ row }">
              <div class="app-action-cell">
                <el-button v-if="row.paymentVoucherDraftGenerated" class="app-action-button-lg" size="small" @click="router.push(`/finance/payment-voucher-draft/${row.targetPaymentVoucherDraftId}`)">查看付款凭证草稿</el-button>
                <el-button v-else class="app-action-button-lg app-next-action-button" size="small" type="primary" :disabled="!row.canGeneratePaymentVoucherDraft" @click="handleCreate(row)">生成付款凭证草稿<span class="app-next-action-badge">下一步</span></el-button>
                <el-button class="app-action-button-lg" size="small" @click="router.push(`/finance/payment-record-review/${row.id}`)">查看付款记录复核</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
        </BusinessTableScrollContainer>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>付款凭证草稿列表</h2>
              <span>本轮终点为“待凭证复核”，不生成正式凭证，不写总账。</span>
            </div>
            <div class="button-row">
              <el-button @click="quickSearchOpen = !quickSearchOpen">{{ quickSearchOpen ? '收起快速搜索' : '展开快速搜索' }}</el-button>
              <el-button data-acceptance-id="list-advanced-filter-toggle" data-pce-filter-toggle-for="payment-voucher-draft-main" :aria-expanded="String(advancedFilterOpen)" @click="advancedFilterOpen = !advancedFilterOpen">{{ advancedFilterOpen ? '收起高级筛选' : '展开高级筛选' }}</el-button>
              <el-button @click="clearSort">清除排序</el-button>
              <el-button data-acceptance-id="list-clear-filter-button" @click="resetFilters">重置</el-button>
            </div>
          </div>
        </template>

        <section v-if="quickSearchOpen" class="filter-line">
          <label>快速搜索<input v-model="quickSearch" placeholder="草稿号 / 来源单号 / 供应商 / 状态" /></label>
        </section>

        <section v-if="advancedFilterOpen" class="filter-grid advanced-filter-panel" data-acceptance-id="list-advanced-filter-panel" data-pce-filter-for="payment-voucher-draft-main">
          <label>凭证草稿号<PceResultFilterSelect v-model="filters.voucherDraftNo" :options="voucherDraftNoOptions" /></label>
          <label>来源付款记录复核单号<PceResultFilterSelect v-model="filters.sourcePaymentRecordReviewNo" :options="recordReviewNoOptions" /></label>
          <label>供应商<PceResultFilterSelect v-model="filters.supplierName" :options="voucherSupplierOptions" /></label>
          <label>凭证日期起<input v-model="filters.voucherStart" type="date" /></label>
          <label>凭证日期止<input v-model="filters.voucherEnd" type="date" /></label>
          <label>会计期间<PceResultFilterSelect v-model="filters.accountingPeriod" :options="periodOptions" /></label>
          <label>借方金额下限<input v-model="filters.debitMin" type="number" /></label>
          <label>借方金额上限<input v-model="filters.debitMax" type="number" /></label>
          <label>贷方金额下限<input v-model="filters.creditMin" type="number" /></label>
          <label>贷方金额上限<input v-model="filters.creditMax" type="number" /></label>
          <label>凭证状态<select v-model="filters.voucherStatus"><option value="">全部</option><option value="draft">凭证草稿</option><option value="readyForReview">待凭证复核</option><option value="cancelled">已取消</option></select></label>
          <label>复核状态<select v-model="filters.reviewStatus"><option value="">全部</option><option value="notSubmitted">未提交</option><option value="pending">待复核</option></select></label>
          <label>总账状态<select v-model="filters.ledgerStatus"><option value="">全部</option><option value="notPosted">未过账</option></select></label>
          <label>风险等级<select v-model="filters.riskLevel"><option value="">全部</option><option value="low">低风险</option><option value="warning">有警告</option><option value="blocked">阻断</option></select></label>
          <label>是否已提交复核<select v-model="filters.submitted"><option value="">全部</option><option value="yes">是</option><option value="no">否</option></select></label>
          <label>是否已取消<select v-model="filters.cancelled"><option value="">全部</option><option value="yes">是</option><option value="no">否</option></select></label>
        </section>

        <div class="batch-bar">
          <span>已选择 {{ selectedDraftRows.length }} 条</span>
          <span class="sort-help">{{ sortText }}</span>
          <span class="batch-action-title">当前模块操作（只修改草稿状态）</span>
          <span class="batch-action-tip">提交复核只进入“待凭证复核”，不生成正式凭证、不写总账。</span>
          <span :class="batchRecommendationClass">{{ batchRecommendationText }}</span>
          <el-button size="small" type="primary" :disabled="!draftIds.length" @click="handleBatchSubmit">批量提交凭证复核</el-button>
          <el-button size="small" type="danger" :disabled="!draftIds.length" @click="handleBatchCancel">批量取消凭证草稿</el-button>
        </div>
        <BatchResult v-if="draftBatchResult" :result="draftBatchResult" :type="batchResultType(draftBatchResult)" @close="draftBatchResult = null" />

        <BusinessTableScrollContainer class="pce-baseline-table-shell" acceptance-id="business-table-scroll-payment-voucher-drafts-main" page-id="payment-voucher-draft" table-id="payment-voucher-drafts-main" min-width="3000px">
        <el-table ref="draftTableRef" class="global-sort-arrow" :data="sortedDrafts" border stripe height="520" @selection-change="selectedDraftRows = $event" @sort-change="handleSortChange">
          <el-table-column type="selection" width="48" fixed="left" class-name="business-table-selection-column" header-class-name="business-table-selection-column" label-class-name="business-table-selection-column" />
          <el-table-column type="index" label="序号" width="70" fixed="left" class-name="pce-fixed-index-column" header-class-name="pce-fixed-index-column" label-class-name="pce-fixed-index-column" />
          <el-table-column prop="voucherDraftNo" label="凭证草稿号" min-width="170" sortable="custom" fixed="left" class-name="pce-fixed-primary-no-column" header-class-name="pce-fixed-primary-no-column" label-class-name="pce-fixed-primary-no-column" />
          <el-table-column prop="sourcePaymentRecordReviewNo" label="来源付款记录复核" min-width="180" sortable="custom" />
          <el-table-column prop="supplierName" label="供应商" min-width="150" sortable="custom" />
          <el-table-column prop="voucherDate" label="凭证日期" width="130" sortable="custom" />
          <el-table-column prop="accountingPeriod" label="会计期间" width="120" />
          <el-table-column prop="debitAmount" label="借方金额" width="130" sortable="custom" />
          <el-table-column prop="creditAmount" label="贷方金额" width="130" sortable="custom" />
          <el-table-column prop="differenceAmount" label="差异金额" width="130" />
          <el-table-column prop="voucherStatus" label="凭证状态" width="140" sortable="custom">
            <template #default="{ row }"><el-tag :type="statusType(row.voucherStatus)">{{ statusLabel(row.voucherStatus) }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="reviewStatus" label="复核状态" width="120">
            <template #default="{ row }">{{ reviewStatusLabel(row.reviewStatus) }}</template>
          </el-table-column>
          <el-table-column prop="voucherReviewStatus" label="凭证复核状态" width="150">
            <template #default="{ row }"><el-tag :type="voucherReviewStatusType(row)">{{ voucherReviewStateLabel(row) }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="ledgerStatus" label="总账状态" width="120">
            <template #default="{ row }">{{ ledgerStatusLabel(row.ledgerStatus) }}</template>
          </el-table-column>
          <el-table-column prop="riskLevel" label="风险等级" width="120">
            <template #default="{ row }"><el-tag :type="riskLevelType(row.riskLevel)">{{ riskLevelLabel(row.riskLevel) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="操作" fixed="right" :width="draftActionColumnWidth" class-name="payment-fixed-action-column" header-class-name="payment-fixed-action-column" label-class-name="payment-fixed-action-column">
            <template #default="{ row }">
              <div class="app-action-cell">
                <el-button class="app-action-button-sm" size="small" @click="router.push(`/finance/payment-voucher-draft/${row.id}`)">查看详情</el-button>
                <el-button v-if="row.voucherStatus === 'draft'" class="app-action-button-lg app-next-action-button" size="small" type="primary" @click="handleSubmit(row)">提交凭证复核<span class="app-next-action-badge">下一步</span></el-button>
                <el-button v-if="showVoucherReviewEntry(row)" class="app-action-button-lg" :class="{ 'app-next-action-button': !voucherReviewTarget(row) }" size="small" type="success" @click="handleVoucherReviewEntry(row)">{{ voucherReviewEntryLabel(row) }}<span v-if="!voucherReviewTarget(row)" class="app-next-action-badge">下一步</span></el-button>
                <el-button v-if="row.voucherStatus === 'draft'" class="app-action-button-md" size="small" type="danger" @click="handleCancel(row)">取消凭证草稿</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
        </BusinessTableScrollContainer>
      </el-card>
    </section>
  </main>
</template>

<script setup>
import { computed, defineComponent, h, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  batchCancelPaymentVoucherDrafts,
  batchCreatePaymentVoucherDraftsFromRecordReviews,
  batchSubmitPaymentVoucherDraftReview,
  cancelPaymentVoucherDraft,
  createPaymentVoucherDraftFromRecordReview,
  getPaymentVoucherDraftById,
  getPaymentVoucherDraftSourcesFromRecordReviews,
  getPaymentVoucherDraftStatusLabel,
  getPaymentVoucherDraftStatusType,
  getPaymentVoucherLedgerStatusLabel,
  getPaymentVoucherReviewStatusLabel,
  getPaymentVoucherRiskLevelLabel,
  getPaymentVoucherRiskLevelType,
  listPaymentVoucherDrafts,
  submitPaymentVoucherDraftReview,
} from '../finance/paymentVoucherDraftStore.js'
import {
  createPaymentVoucherReviewFromVoucherDraft,
  isPaymentVoucherReviewGenerated,
} from '../finance/paymentVoucherReviewStore.js'
import BusinessTableScrollContainer from '../components/BusinessTableScrollContainer.vue'
import PceResultFilterSelect from '../components/PceResultFilterSelect.vue'
import { getActionColumnWidthForRows } from '../runtime/tableActionColumnEngine.js'
import { sortRecords } from '../runtime/tableSortEngine.js'

const BatchResult = defineComponent({
  props: { result: { type: Object, required: true }, type: { type: String, default: 'success' } },
  emits: ['close'],
  setup(props, { emit }) {
    return () => h('div', { class: ['batch-result', props.type] }, [
      h('button', { type: 'button', onClick: () => emit('close') }, '关闭'),
      h('strong', props.result.operationName || '批量操作完成'),
      h('span', `已选择：${props.result.total} 条`),
      h('span', `成功：${props.result.successCount} 条`),
      h('span', `已达成：${props.result.alreadyDoneCount} 条`),
      h('span', `失败 / 跳过：${props.result.failedCount} 条`),
      props.result.failedReason?.length ? h('ol', props.result.failedReason.map((reason) => h('li', { key: reason }, reason))) : null,
      h('span', `下一步建议：${props.result.nextSuggestion || '按当前草稿状态处理下一步。'}`),
      h('span', '边界说明：本批量结果不代表正式财务凭证已生成，不写总账，不过账，不做付款核销。'),
    ])
  },
})

const route = useRoute()
const router = useRouter()
const sources = ref([])
const drafts = ref([])
const selectedSourceRows = ref([])
const selectedDraftRows = ref([])
const sourceTableRef = ref(null)
const draftTableRef = ref(null)
const sourceBatchResult = ref(null)
const draftBatchResult = ref(null)
const quickSearchOpen = ref(false)
const advancedFilterOpen = ref(false)
const quickSearch = ref('')
const sortState = ref({ key: '', direction: 'asc' })
const message = ref('')
const messageType = ref('success')
const filters = reactive(defaultFilters())

const detail = computed(() => route.params.id ? getPaymentVoucherDraftById(route.params.id) : null)
const sourceIds = computed(() => selectedSourceRows.value.map((row) => row.id).filter(Boolean))
const draftIds = computed(() => selectedDraftRows.value.map((row) => row.id).filter(Boolean))
const filterSuggestions = computed(() => ({
  voucherDraftNo: uniqueValues(drafts.value.map((row) => row.voucherDraftNo)),
  sourcePaymentRecordReviewNo: uniqueValues(drafts.value.map((row) => row.sourcePaymentRecordReviewNo)),
  supplierName: uniqueValues(drafts.value.map((row) => row.supplierName)),
  accountingPeriod: uniqueValues(drafts.value.map((row) => row.accountingPeriod)),
}))
const filteredSources = computed(() => {
  if (!route.query.sourcePaymentRecordReviewId) return sources.value
  return sources.value.filter((row) => String(row.id) === String(route.query.sourcePaymentRecordReviewId))
})
const filteredDrafts = computed(() => drafts.value.filter((row) => {
  const haystack = [
    row.voucherDraftNo,
    row.sourcePaymentRecordReviewNo,
    row.sourcePaymentExecutionNo,
    row.supplierName,
    row.sourcePurchaseOrderNo,
    row.rootRequestNo,
    statusLabel(row.voucherStatus),
    riskLevelLabel(row.riskLevel),
  ].join(' ').toLowerCase()
  return (!quickSearch.value || haystack.includes(quickSearch.value.trim().toLowerCase()))
    && includesText(row.voucherDraftNo, filters.voucherDraftNo)
    && includesText(row.sourcePaymentRecordReviewNo, filters.sourcePaymentRecordReviewNo)
    && includesText(row.supplierName, filters.supplierName)
    && inDateRange(row.voucherDate, filters.voucherStart, filters.voucherEnd)
    && includesText(row.accountingPeriod, filters.accountingPeriod)
    && inAmountRange(row.debitAmount, filters.debitMin, filters.debitMax)
    && inAmountRange(row.creditAmount, filters.creditMin, filters.creditMax)
    && (!filters.voucherStatus || row.voucherStatus === filters.voucherStatus)
    && (!filters.reviewStatus || row.reviewStatus === filters.reviewStatus)
    && (!filters.ledgerStatus || row.ledgerStatus === filters.ledgerStatus)
    && (!filters.riskLevel || row.riskLevel === filters.riskLevel)
    && boolStatus(row.voucherStatus === 'readyForReview', filters.submitted)
    && boolStatus(row.voucherStatus === 'cancelled', filters.cancelled)
}))
const sortColumns = [
  { key: 'voucherDraftNo', sortType: 'string' },
  { key: 'sourcePaymentRecordReviewNo', sortType: 'string' },
  { key: 'supplierName', sortType: 'string' },
  { key: 'voucherDate', sortType: 'date' },
  { key: 'debitAmount', sortType: 'amount' },
  { key: 'creditAmount', sortType: 'amount' },
  { key: 'voucherStatus', sortType: 'status' },
]
const sortedDrafts = computed(() => sortRecords(filteredDrafts.value, sortState.value, sortColumns))
const sortText = computed(() => sortState.value.key ? `当前排序：${sortState.value.key} / ${sortState.value.direction === 'desc' ? '降序' : '升序'}` : '排序：点击表头可排序，点击清除排序恢复默认顺序。')
const sourceActionColumnWidth = computed(() => getActionColumnWidthForRows(filteredSources.value, sourceActions, ['生成付款凭证草稿', '查看付款凭证草稿', '查看付款记录复核']))
const draftActionColumnWidth = computed(() => getActionColumnWidthForRows(sortedDrafts.value, draftActions, ['查看详情', '提交凭证复核', '生成付款凭证复核', '查看付款凭证复核', '取消凭证草稿']))
const batchRecommendationText = computed(() => {
  if (!selectedDraftRows.value.length) return '推荐下一步：请选择草稿状态记录后再批量处理。'
  const statuses = [...new Set(selectedDraftRows.value.map((row) => row.voucherStatus))]
  if (statuses.length > 1) return '所选记录包含多个状态，请按状态分别批量处理。'
  if (statuses[0] === 'draft') return '推荐下一步：批量提交凭证复核，或取消不需要的草稿。'
  return '所选记录已到本轮终点或已取消，只建议查看详情。'
})
const batchRecommendationClass = computed(() => {
  if (!selectedDraftRows.value.length) return 'app-current-step-tip'
  const statuses = [...new Set(selectedDraftRows.value.map((row) => row.voucherStatus))]
  return statuses.length === 1 && statuses[0] === 'draft' ? 'app-current-step-tip' : 'app-terminal-step-tip'
})
const detailFields = computed(() => detail.value ? [
  { label: '凭证草稿号', value: detail.value.voucherDraftNo },
  { label: '来源付款记录复核', value: detail.value.sourcePaymentRecordReviewNo || '-' },
  { label: '供应商', value: detail.value.supplierName || '-' },
  { label: '凭证日期', value: detail.value.voucherDate || '-' },
  { label: '会计期间', value: detail.value.accountingPeriod || '-' },
  { label: '凭证状态', value: statusLabel(detail.value.voucherStatus) },
  { label: '复核状态', value: reviewStatusLabel(detail.value.reviewStatus) },
  { label: '凭证复核状态', value: voucherReviewStateLabel(detail.value) },
  { label: '凭证复核结果', value: voucherReviewResultLabel(detail.value.voucherReviewResult) },
  { label: '凭证复核人', value: detail.value.voucherReviewerName || '-' },
  { label: '总账状态', value: ledgerStatusLabel(detail.value.ledgerStatus) },
  { label: '借方金额', value: amountText(detail.value.debitAmount) },
  { label: '贷方金额', value: amountText(detail.value.creditAmount) },
  { label: '差异金额', value: amountText(detail.value.differenceAmount) },
  { label: '风险等级', value: riskLevelLabel(detail.value.riskLevel) },
] : [])
const sourceChain = computed(() => detail.value ? [
  { label: '付款记录复核', value: detail.value.sourcePaymentRecordReviewNo },
  { label: '付款执行草稿', value: detail.value.sourcePaymentExecutionNo },
  { label: '真实付款风险评审', value: detail.value.sourceRiskReviewNo },
  { label: '正式付款单草稿', value: detail.value.sourcePaymentOrderDraftNo },
  { label: '正式付款单预备', value: detail.value.sourcePaymentPrepareNo },
  { label: '供应商付款草稿', value: detail.value.sourcePaymentDraftNo },
  { label: '应付账款草稿', value: detail.value.sourceApDraftNo },
  { label: '发票预备', value: detail.value.sourceInvoicePrepareNo },
  { label: '应付核对', value: detail.value.sourcePayableCheckNo },
  { label: '应付预备', value: detail.value.sourcePayablePrepareNo },
  { label: '库存流水', value: (detail.value.sourceInventoryTransactionNos || []).join('；') },
  { label: '检验单', value: detail.value.sourceInspectionNo },
  { label: '收货单', value: detail.value.sourceReceiveNo },
  { label: '采购订单', value: detail.value.sourcePurchaseOrderNo },
  { label: '原始请购单', value: detail.value.rootRequestNo },
] : [])

function defaultFilters() {
  return {
    voucherDraftNo: '',
    sourcePaymentRecordReviewNo: '',
    supplierName: '',
    voucherStart: '',
    voucherEnd: '',
    accountingPeriod: '',
    debitMin: '',
    debitMax: '',
    creditMin: '',
    creditMax: '',
    voucherStatus: '',
    reviewStatus: '',
    ledgerStatus: '',
    riskLevel: '',
    submitted: '',
    cancelled: '',
  }
}

function refresh() {
  sources.value = getPaymentVoucherDraftSourcesFromRecordReviews()
  drafts.value = listPaymentVoucherDrafts()
}

function notify(text, type = 'success') {
  message.value = text
  messageType.value = type
  window.clearTimeout(notify.timer)
  notify.timer = window.setTimeout(() => { message.value = '' }, 2600)
}

function includesText(value, keyword) {
  return !keyword || String(value || '').toLowerCase().includes(String(keyword).trim().toLowerCase())
}

function inDateRange(value, start, end) {
  if (!start && !end) return true
  if (!value) return false
  return (!start || value >= start) && (!end || value <= end)
}

function inAmountRange(value, min, max) {
  const amount = Number(value || 0)
  return (!min || amount >= Number(min)) && (!max || amount <= Number(max))
}

function boolStatus(value, flag) {
  if (!flag) return true
  return flag === 'yes' ? Boolean(value) : !value
}

function amountText(value) {
  return Number(value || 0).toFixed(2)
}

function uniqueValues(values = []) {
  return [...new Set(values.map((value) => String(value || '').trim()).filter(Boolean))]
}

function handleOutcome(outcome, successText) {
  if (!outcome?.success) {
    refresh()
    return notify(outcome?.error || '操作失败。', 'warning')
  }
  refresh()
  notify(outcome.alreadyDone ? (outcome.message || '当前状态已达成，无需重复操作。') : successText)
}

function handleCreate(row) {
  const outcome = createPaymentVoucherDraftFromRecordReview(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  router.push(`/finance/payment-voucher-draft/${outcome.draft.id}`)
}

function handleBatchCreate() { showSourceBatch(batchCreatePaymentVoucherDraftsFromRecordReviews(sourceIds.value)) }
function handleBatchSubmit() { showDraftBatch(batchSubmitPaymentVoucherDraftReview(draftIds.value)) }
function handleBatchCancel() { showDraftBatch(batchCancelPaymentVoucherDrafts(draftIds.value)) }
function handleSubmit(row) { handleOutcome(submitPaymentVoucherDraftReview(row.id), '已提交凭证复核；仍未生成正式凭证，不写总账。') }
function handleCancel(row) { handleOutcome(cancelPaymentVoucherDraft(row.id), '已取消付款凭证草稿；不影响前序付款记录复核。') }

function voucherReviewTarget(row = {}) {
  const target = isPaymentVoucherReviewGenerated(row.id)
  if (target?.id) return target
  if (row.paymentVoucherReviewGenerated && row.targetPaymentVoucherReviewId && row.voucherReviewStatus !== 'cancelled') {
    return {
      id: row.targetPaymentVoucherReviewId,
      voucherReviewNo: row.targetPaymentVoucherReviewNo,
      voucherReviewStatus: row.voucherReviewStatus,
    }
  }
  return null
}

function voucherReviewEntryLabel(row = {}) {
  return voucherReviewTarget(row) ? '查看付款凭证复核' : '生成付款凭证复核'
}

function showVoucherReviewEntry(row = {}) {
  return row.voucherStatus === 'readyForReview' || Boolean(voucherReviewTarget(row))
}

function voucherReviewStateLabel(row = {}) {
  const status = voucherReviewTarget(row)?.voucherReviewStatus || row.voucherReviewStatus
  if (status === 'pending') return '已生成付款凭证复核'
  if (status === 'reviewing') return '付款凭证复核中'
  if (status === 'passed') return '凭证复核通过'
  if (status === 'rejected') return '凭证复核退回'
  if (status === 'cancelled') return '复核任务已取消'
  return row.voucherStatus === 'readyForReview' ? '待生成付款凭证复核' : '未进入凭证复核'
}

function voucherReviewStatusType(row = {}) {
  const status = voucherReviewTarget(row)?.voucherReviewStatus || row.voucherReviewStatus
  return {
    pending: 'warning',
    reviewing: 'primary',
    passed: 'success',
    rejected: 'danger',
    cancelled: 'info',
  }[status] || 'info'
}

function voucherReviewResultLabel(result) {
  return {
    notReviewed: '未复核',
    passed: '通过',
    rejected: '退回',
  }[result] || result || '-'
}

function handleVoucherReviewEntry(row = {}) {
  const target = voucherReviewTarget(row)
  if (target?.id) return router.push(`/finance/payment-voucher-review/${target.id}`)
  const outcome = createPaymentVoucherReviewFromVoucherDraft(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  return router.push(`/finance/payment-voucher-review/${outcome.review.id}`)
}

function showSourceBatch(result) {
  sourceBatchResult.value = result
  selectedSourceRows.value = []
  sourceTableRef.value?.clearSelection?.()
  refresh()
}

function showDraftBatch(result) {
  draftBatchResult.value = result
  selectedDraftRows.value = []
  draftTableRef.value?.clearSelection?.()
  refresh()
}

function batchResultType(result = {}) {
  if (result.failedCount && !result.successCount && !result.alreadyDoneCount) return 'error'
  if (result.failedCount) return 'warning'
  return 'success'
}

function clearSort() {
  sortState.value = { key: '', direction: 'asc' }
}

function resetFilters() {
  Object.assign(filters, defaultFilters())
  quickSearch.value = ''
}

function handleSortChange({ prop, order }) {
  sortState.value = { key: prop || '', direction: order === 'descending' ? 'desc' : 'asc' }
}

function sourceActions(row = {}) {
  return [
    { label: '查看付款凭证草稿', visible: row.paymentVoucherDraftGenerated },
    { label: '生成付款凭证草稿', visible: !row.paymentVoucherDraftGenerated },
    '查看付款记录复核',
  ]
}

function draftActions(row = {}) {
  return [
    '查看详情',
    { label: '提交凭证复核', visible: row.voucherStatus === 'draft' },
    { label: voucherReviewEntryLabel(row), visible: showVoucherReviewEntry(row) },
    { label: '取消凭证草稿', visible: row.voucherStatus === 'draft' },
  ]
}

function nextStepTitle(status) {
  if (status === 'draft') return '推荐下一步：提交凭证复核'
  if (status === 'readyForReview') return '当前阶段终点：待凭证复核'
  if (status === 'cancelled') return '当前草稿已取消'
  return '当前状态只建议查看'
}

function nextStepDescription(status) {
  if (status === 'draft') return '当前可以提交凭证复核；提交后仍不生成正式凭证，不写总账。'
  if (status === 'readyForReview') return '本轮到“待凭证复核”为止，不继续复核、不生成正式凭证。'
  if (status === 'cancelled') return '该草稿已取消，只保留查看。'
  return '请查看详情或返回列表。'
}

function nextStepGuideClass(status) {
  return status === 'draft' ? 'app-current-step-tip app-step-guide' : 'app-terminal-step-tip app-step-guide'
}

function statusLabel(status) {
  return getPaymentVoucherDraftStatusLabel(status)
}

function statusType(status) {
  return getPaymentVoucherDraftStatusType(status)
}

function reviewStatusLabel(status) {
  return getPaymentVoucherReviewStatusLabel(status)
}

function ledgerStatusLabel(status) {
  return getPaymentVoucherLedgerStatusLabel(status)
}

function riskLevelLabel(level) {
  return getPaymentVoucherRiskLevelLabel(level)
}

function riskLevelType(level) {
  return getPaymentVoucherRiskLevelType(level)
}

function riskItemType(level) {
  return { blocked: 'danger', warning: 'warning', info: 'success' }[level] || 'info'
}

function riskItemLabel(value) {
  return {
    passed: '通过',
    blocked: '阻断',
    warning: '警告',
    info: '提示',
  }[value] || value || '-'
}

watch(() => route.fullPath, refresh, { immediate: true })
</script>

<style scoped>
.payment-voucher-draft-page { display: flex; flex-direction: column; gap: 16px; min-height: 100%; padding: 22px; background: #f5f7fb; color: #172033; }
.page-header, .card-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.page-header p { margin: 6px 0 0; color: #475467; line-height: 1.5; }
.eyebrow, .card-header span, .info-grid span, .source-chain span { color: #64748b; font-size: 13px; }
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
.boundary-note { border: 1px solid #fed7aa; border-radius: 8px; padding: 10px; margin-bottom: 12px; background: #fff7ed; color: #9a3412; font-weight: 700; }
.subject-note { border: 1px solid #bfdbfe; border-radius: 8px; padding: 10px; margin-bottom: 12px; background: #eff6ff; color: #1e3a8a; font-weight: 700; }
.info-grid, .source-chain, .filter-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; }
.info-grid article, .source-chain article { border: 1px solid #dbe3ef; border-radius: 8px; padding: 12px; background: #fff; }
.info-grid strong, .source-chain strong { display: block; margin-top: 4px; }
.batch-bar { border: 1px solid #dbe3ef; border-radius: 8px; padding: 10px; margin-bottom: 12px; background: #f8fafc; }
.button-row .el-button, .batch-bar .el-button { min-width: 96px; white-space: nowrap; }
.button-row .el-button--primary, .button-row .el-button--success, .button-row .el-button--warning,
.batch-bar .el-button--primary, .batch-bar .el-button--success, .batch-bar .el-button--warning { min-width: 132px; }
.batch-bar .el-button--danger, .button-row .el-button--danger { min-width: 96px; }
.batch-action-title { color: #172033; font-weight: 800; }
.batch-action-tip, .sort-help { color: #64748b; font-size: 13px; }
.app-step-guide { display: grid; gap: 6px; margin: 0 0 12px; line-height: 1.6; }
.app-current-step-tip, .app-terminal-step-tip { display: inline-flex; align-items: center; gap: 6px; border-radius: 999px; padding: 5px 10px; font-size: 13px; font-weight: 800; }
.app-current-step-tip { border: 1px solid #99f6e4; background: #ecfdf5; color: #0f766e; }
.app-terminal-step-tip { border: 1px solid #cbd5e1; background: #f8fafc; color: #475467; }
.app-step-guide.app-current-step-tip, .app-step-guide.app-terminal-step-tip { display: grid; align-items: stretch; border-radius: 8px; padding: 10px 12px; }
.app-next-action-button { border-color: #0f766e !important; background: #0f766e !important; color: #fff !important; box-shadow: 0 8px 16px rgba(15, 118, 110, 0.2); }
.app-next-action-button.is-disabled, .app-next-action-button:disabled { border-color: #94a3b8 !important; background: #94a3b8 !important; box-shadow: none; }
.app-next-action-badge { display: inline-flex; align-items: center; margin-left: 6px; border-radius: 999px; padding: 2px 7px; background: rgba(255, 255, 255, 0.22); color: inherit; font-size: 12px; font-weight: 900; }
.batch-result { position: relative; display: grid; gap: 6px; margin-bottom: 12px; border-radius: 8px; padding: 12px; background: #ecfdf5; color: #065f46; }
.batch-result.warning { background: #fffbeb; color: #92400e; }
.batch-result.error { background: #fef2f2; color: #991b1b; }
.batch-result button { position: absolute; top: 8px; right: 8px; border: 0; background: transparent; color: inherit; cursor: pointer; }
.filter-line, .filter-grid { border: 1px solid #dbe3ef; border-radius: 8px; padding: 12px; margin-bottom: 12px; background: #fff; }
label { display: grid; gap: 6px; color: #334155; font-weight: 700; }
input, select { width: 100%; box-sizing: border-box; border: 1px solid #cbd5e1; border-radius: 6px; padding: 8px 10px; background: #fff; color: #172033; }
@media (max-width: 900px) {
  .page-header { align-items: flex-start; flex-direction: column; }
  .plain-flow-grid { grid-template-columns: 1fr; }
}
</style>
