<template>
  <main class="pop-page" data-acceptance-id="payment-order-draft-business-content">
    <el-alert v-if="pageFacts?.factLoadStatus === 'read_failed'" type="error" title="服务端资料读取失败，数量未知；请检查登录身份后刷新。" :description="pageFacts.errorMessage" :closable="false" show-icon />
    <section class="business-card capacity-card" data-acceptance-id="payment-order-draft-capacity">
      <Heading title="持久金丝雀容量" :note="pageFacts?.factLoadStatus === 'read_failed' ? '读取失败，数量未知' : `成功链=${capacity.passThroughLineageCount ?? '未知'} / 阻断场景=${capacity.blockedScenarioCount ?? '未知'}`" />
      <div class="facts">
        <Fact label="正式付款单预备来源数量" :value="capacity.paymentOrderPrepareSourceCount" />
        <Fact label="来源已消费数量" :value="capacity.paymentOrderPrepareConsumedCount" />
        <Fact label="正式付款单草稿数量" :value="capacity.formalPaymentOrderDraftCount" />
        <Fact label="已复核数量" :value="capacity.reviewedPaymentOrderDraftCount" />
        <Fact label="下游合格来源数量" :value="capacity.downstreamEligibleSourceCount" />
        <Fact label="下一阶段已消费数量" :value="capacity.nextStageConsumedCount" />
      </div>
      <p class="ctrl-f">Ctrl+F：持久金丝雀容量</p>
    </section>

    <section class="business-card" data-acceptance-id="payment-order-draft-scenarios">
      <Heading title="金丝雀业务场景" :note="`成功=${rows.length} / 阻断=${capacity.blockedScenarioCount || 0}`" />
      <div class="facts">
        <Fact label="成功场景数量" :value="rows.length" />
        <Fact label="阻断场景数量" :value="capacity.blockedScenarioCount" />
        <Fact label="当前批次" :value="serverMeta.canaryBatchId" />
        <Fact label="状态来源" :value="serverMeta.currentStateSource" />
      </div>
      <p class="ctrl-f">Ctrl+F：金丝雀业务场景</p>
    </section>

    <section class="business-card" data-acceptance-id="payment-order-draft-source">
      <Heading title="正式付款单预备来源" note="唯一直接来源：paymentOrderPrepare" />
      <div class="facts">
        <Fact label="来源正式付款单预备编号" :value="current?.sourcePaymentOrderPrepareNo" />
        <Fact label="来源状态" :value="paymentOrderDraftDisplayValue(current?.source?.status)" />
        <Fact label="来源校验状态" :value="paymentOrderDraftDisplayValue(current?.source?.validationStatus)" />
        <Fact label="来源版本" :value="current?.sourceOrderPrepareVersion" />
        <Fact label="来源资料版本" :value="current?.sourceOrderDataVersion" />
        <Fact label="来源校验版本" :value="current?.sourceOrderValidationVersion" />
      </div>
      <p class="ctrl-f">Ctrl+F：正式付款单预备来源</p>
    </section>

    <section class="business-card" data-acceptance-id="payment-order-draft-object">
      <Heading title="草稿核心资料" :note="paymentOrderDraftDisplayValue(current?.status)" />
      <div class="facts">
        <Fact label="正式付款单草稿编号" :value="current?.draftNo" />
        <Fact label="业务状态" :value="paymentOrderDraftDisplayValue(current?.status)" />
        <Fact label="供应商" :value="current?.supplierName" />
        <Fact label="法人主体" :value="current?.legalEntityName" />
        <Fact label="账簿" :value="current?.ledgerBookId" />
        <Fact label="币种" :value="current?.currency" />
        <Fact label="付款金额" :value="current?.paymentAmount" />
        <Fact label="计划执行日期" :value="current?.plannedExecutionDate" />
        <Fact label="对象版本" :value="current?.version" />
      </div>
      <p class="ctrl-f">Ctrl+F：正式付款单草稿编号</p>
    </section>

    <section class="business-card" data-acceptance-id="payment-order-draft-routing">
      <Heading title="账户、路由和银行接口" note="全部来自服务端权威 Provider" />
      <div class="facts">
        <Fact label="付款方银行账户" :value="current?.preview?.debtorAccountMasked" />
        <Fact label="收款方银行账户" :value="current?.preview?.creditorAccountMasked" />
        <Fact label="支付路由" :value="current?.paymentRouteId" />
        <Fact label="银行接口" :value="current?.bankInterfaceProfileId" />
        <Fact label="支付方式" :value="current?.paymentMethodCode" />
        <Fact label="计划执行时间" :value="current?.plannedExecutionTime" />
      </div>
      <p class="ctrl-f">Ctrl+F：账户、路由和银行接口</p>
    </section>

    <section class="business-card" data-acceptance-id="payment-order-draft-funds">
      <Heading title="资金可用性证据" note="只读复核；不冻结资金；不扣减余额" />
      <div class="facts">
        <Fact label="资金证据编号" :value="authority('funds').fundsEvidenceId" />
        <Fact label="可用余额" :value="authority('funds').availableBalance" />
        <Fact label="已承诺金额" :value="authority('funds').committedAmount" />
        <Fact label="已预留金额" :value="authority('funds').reservedAmount" />
        <Fact label="本次可用金额" :value="authority('funds').availableForNewPayment" />
        <Fact label="资金充足" :value="authority('funds').sufficient" />
        <Fact label="资金冻结已创建" :value="authority('funds').fundsReservationCreated" />
        <Fact label="银行余额已扣减" :value="authority('funds').bankBalanceDebited" />
      </div>
      <p class="ctrl-f">Ctrl+F：资金可用性证据</p>
    </section>

    <section class="business-card" data-acceptance-id="payment-order-draft-signing">
      <Heading title="签署策略与授权路径" note="独立权威 Provider / Repository" />
      <div class="facts">
        <Fact label="签署策略编号" :value="authority('signingPolicy').signingPolicyId" />
        <Fact label="签署策略编码" :value="authority('signingPolicy').policyCode" />
        <Fact label="所需签名数" :value="authority('signingPolicy').requiredSignatures" />
        <Fact label="授权路径编号" :value="authority('authorizationRoute').authorizationRouteId" />
        <Fact label="授权步骤数" :value="authority('authorizationRoute').stepCount" />
        <Fact label="签署能力编号" :value="authority('signingCapability').signingCapabilityId" />
        <Fact label="凭据状态" :value="authority('signingCapability').credentialStatus" />
        <Fact label="证书状态" :value="authority('signingCapability').certificateStatus" />
        <Fact label="签署服务状态" :value="authority('signingCapability').signingServiceStatus" />
      </div>
      <p class="ctrl-f">Ctrl+F：签署策略与授权路径</p>
    </section>

    <section class="business-card" data-acceptance-id="payment-order-draft-segregation">
      <Heading title="制单复核授权职责分离" note="maker / checker / authorizer 互斥" />
      <div class="facts">
        <Fact label="职责分离策略" :value="authority('segregation').segregationPolicyId" />
        <Fact label="制单人" :value="authority('segregation').makerUserId" />
        <Fact label="制单人不得复核" :value="authority('segregation').makerCannotCheck" />
        <Fact label="制单人不得授权" :value="authority('segregation').makerCannotAuthorize" />
        <Fact label="复核人不得最终授权" :value="authority('segregation').checkerCannotFinalAuthorize" />
        <Fact label="职责分离通过" :value="authority('segregation').segregationValid" />
      </div>
      <p class="ctrl-f">Ctrl+F：职责分离</p>
    </section>

    <section class="business-card preview-card" data-acceptance-id="payment-order-preview">
      <Heading title="正式付款单创建预览" note="只读；未使用正式编号、未签署、未发送、未创建正式付款单" />
      <div class="facts">
        <Fact label="建议付款单引用" :value="current?.preview?.proposedFormalOrderReference" />
        <Fact label="付款方" :value="current?.preview?.debtorName" />
        <Fact label="付款账户脱敏号" :value="current?.preview?.debtorAccountMasked" />
        <Fact label="收款方" :value="current?.preview?.creditorName" />
        <Fact label="收款账户脱敏号" :value="current?.preview?.creditorAccountMasked" />
        <Fact label="金额" :value="current?.preview?.amount" />
        <Fact label="路由" :value="current?.preview?.routeCode" />
        <Fact label="渠道" :value="current?.preview?.channelCode" />
        <Fact label="预览哈希" :value="current?.preview?.previewHash" />
      </div>
      <p class="ctrl-f">Ctrl+F：正式付款单只读预览</p>
    </section>

    <section class="business-card" data-acceptance-id="payment-order-draft-review">
      <Heading title="最终草稿复核结果" :note="paymentOrderDraftDisplayValue(current?.review?.resultCode)" />
      <div class="facts">
        <Fact label="复核状态" :value="paymentOrderDraftDisplayValue(current?.reviewStatus)" />
        <Fact label="生成及来源门禁规则数量" :value="ruleClassification.generationAndSourceGateRuleCount" />
        <Fact label="资料完整性规则数量" :value="ruleClassification.dataCompletenessRuleCount" />
        <Fact label="最终复核规则数量" :value="ruleClassification.finalReviewRuleCount" />
        <Fact label="规则总数" :value="ruleClassification.totalRuleCount" />
        <Fact label="通过数量" :value="current?.review?.passedCount" />
        <Fact label="阻断数量" :value="current?.review?.blockedCount" />
        <Fact label="问题数量" :value="current?.review?.issueCount" />
      </div>
      <p class="ctrl-f">Ctrl+F：最终草稿复核结果</p>
    </section>

    <section class="business-card" data-acceptance-id="payment-order-draft-review-issues">
      <Heading title="复核问题清单" :note="`问题=${current?.review?.issueCount || 0}`" />
      <BusinessTableScrollContainer acceptance-id="business-table-scroll-payment-order-issues" min-width="980px">
        <el-table :data="current?.review?.issues || []" border stripe>
          <el-table-column prop="ruleCode" label="规则编码" min-width="220" />
          <el-table-column prop="dimension" label="维度" min-width="140" />
          <el-table-column prop="expected" label="期望值" min-width="200" />
          <el-table-column prop="actual" label="实际值" min-width="200" />
          <el-table-column prop="message" label="说明" min-width="230" />
        </el-table>
      </BusinessTableScrollContainer>
      <p class="ctrl-f">Ctrl+F：复核问题清单</p>
    </section>

    <section class="business-card eligibility-card" data-acceptance-id="payment-order-draft-eligibility">
      <Heading title="真实付款风险评审放行资格" :note="paymentOrderDraftDisplayValue(current?.eligibility?.nextStepReadiness)" />
      <div class="facts">
        <Fact
          v-for="field in eligibilityFields"
          :key="field.key"
          :label="field.label"
          :value="paymentOrderDraftDisplayValue(current?.eligibility?.[field.key])"
        />
      </div>
      <PceBusinessActionBar
        current-module="payment-order-draft"
        :current-status="current?.status || ''"
        :selected-rows="selectedRows.length ? selectedRows : (current ? [current] : [])"
        :eligibility="current?.eligibility?.eligible ?? null"
        :show-unavailable="true"
      />
      <p class="ctrl-f">Ctrl+F：真实付款风险评审放行资格</p>
    </section>

    <section class="business-card" data-acceptance-id="payment-order-draft-audit">
      <Heading title="版本、幂等、事务与审计" note="currentStateSource=server" />
      <div class="facts">
        <Fact label="业务对象版本" :value="current?.version" />
        <Fact label="状态转换数量" :value="current?.statusTransitionCount" />
        <Fact label="状态机事实一致" :value="current?.stateMachineConsistent" />
        <Fact label="资料版本" :value="current?.currentDraftDataVersion" />
        <Fact label="复核版本" :value="current?.currentReviewVersion" />
        <Fact label="幂等状态" :value="paymentOrderDraftDisplayValue(current?.idempotencyStatus)" />
        <Fact label="编号状态" :value="paymentOrderDraftDisplayValue(current?.numberReservationStatus)" />
        <Fact label="事务状态" :value="paymentOrderDraftDisplayValue(current?.transactionStatus)" />
        <Fact label="审计状态" :value="paymentOrderDraftDisplayValue(current?.auditStatus)" />
      </div>
      <p class="ctrl-f">Ctrl+F：版本、幂等、事务与审计</p>
    </section>

    <section class="business-card" data-acceptance-id="payment-order-draft-toolbar-region">
      <Heading title="正式付款单草稿正式列表" note="普通页面仅提供只读操作" />
      <h4 class="list-toolbar-title">正式付款单草稿列表工具栏</h4>
      <StandardListToolbar
        page-id="payment-order-draft"
        table-id="payment-order-draft-main"
        v-model:quick-search="quickSearch"
        :placeholder="formalListContract.searchPlaceholder"
        :advanced-visible="advancedVisible"
        :result-count="filteredRows.length"
        :selected-count="selectedRows.length"
        :active-filter-count="formalEffectiveFilterCount"
        :sort-text="formalSortText"
        @search="clearSelection"
        @toggle-advanced="advancedVisible = !advancedVisible"
        @clear-filters="clearFilters"
        @clear-sort="clearSort"
        @export-current="exportCurrent"
        @clear-selection="clearSelection"
      />
      <div
        v-show="advancedVisible"
        class="advanced-filter-panel list-advanced-filter-panel"
        data-pce-filter-for="payment-order-draft-main"
        data-acceptance-id="formal-list-advanced-filter"
      >
        <label v-for="field in formalListContract.filterSchema" :key="field.key" :data-filter-key="field.key">
          <span>{{ field.label }}</span>
          <el-select v-if="field.type === 'select'" v-model="mainFilters[field.key]" clearable filterable>
            <el-option v-for="option in filterOptions(field, rows)" :key="String(option.value)" :label="option.label" :value="option.value" />
          </el-select>
          <el-date-picker
            v-else-if="field.type === 'dateRange'"
            v-model="mainFilters[field.key]"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="选择日期"
          />
          <el-input v-else v-model="mainFilters[field.key]" clearable :type="field.type === 'numberRange' ? 'number' : 'text'" :placeholder="field.placeholder || field.label" />
        </label>
      </div>
    </section>

    <section class="business-card" data-acceptance-id="payment-order-draft-list-region">
      <Heading title="正式付款单草稿正式列表" :note="`正式对象数量=${rows.length}`" />
      <BusinessTableScrollContainer acceptance-id="business-table-scroll-payment-order-draft-main" page-id="payment-order-draft" table-id="payment-order-draft-main" min-width="2200px">
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
          @sort-change="handleFormalSort"
          @row-click="selectDetail"
        >
          <el-table-column type="selection" width="55" fixed="left" class-name="business-table-selection-column" header-class-name="business-table-selection-column" />
          <el-table-column type="index" label="序号" width="64" fixed="left" class-name="pce-fixed-index-column" header-class-name="pce-fixed-index-column" />
          <el-table-column
            v-for="column in formalListContract.columnSchema"
            :key="column.key"
            :prop="column.key"
            :label="column.label"
            :width="column.width"
            :min-width="column.minWidth"
            :fixed="column.fixed"
            :class-name="column.className"
            :header-class-name="column.className"
            :sortable="column.sortable ? 'custom' : false"
            :align="column.align || 'left'"
            show-overflow-tooltip
          />
          <el-table-column label="操作" width="104" fixed="right" class-name="payment-fixed-action-column" header-class-name="payment-fixed-action-column">
            <template #default="{ row }"><el-button size="small" plain data-acceptance-id="formal-row-view-button" @click.stop="selectDetail(row)">查看</el-button></template>
          </el-table-column>
          <template #empty><span>{{ formalListContract.emptyState }}</span></template>
        </el-table>
      </BusinessTableScrollContainer>
      <p class="ctrl-f">Ctrl+F：{{ rows[0]?.draftNo || '正式付款单草稿编号' }}</p>
    </section>

    <section class="business-card boundary-card" data-acceptance-id="payment-order-draft-process-boundary">
      <Heading title="业务流程与后续边界" note="上一步正式付款单预备；当前正式付款单草稿；下一步真实付款风险评审" />
      <div class="facts">
        <Fact label="上一步" value="正式付款单预备" />
        <Fact label="当前页面" value="正式付款单草稿" />
        <Fact label="下一步" :value="capacity.nextCanonicalName || '真实付款风险评审'" />
        <Fact label="下一步仅导航" value="是" />
      </div>
      <p class="ctrl-f">Ctrl+F：业务流程与后续边界</p>
    </section>

    <section class="business-card boundary-card" data-acceptance-id="payment-order-draft-zero-boundary">
      <Heading title="下游零对象保护" note="导航不创建真实付款风险评审、正式付款单或任何付款对象" />
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
import { paymentOrderDraftApi } from '@/api/paymentOrderDraft.js'
import {
  PAYMENT_ORDER_DRAFT_RULE_CLASSIFICATION,
  PAYMENT_ORDER_DRAFT_VERSION,
  createPaymentOrderDraftPageFacts,
  paymentOrderDraftDisplayValue,
} from '@/meta/runtime/paymentOrderDraftRuntime.js'
import { PAGE_OBSERVABILITY_ACTIONS_KEY } from '@/meta/runtime/pageObservabilityActions.js'
import { stateMachineFactsFromServer } from '@/meta/runtime/pceStateMachineFactContract.js'
import { factLoadFailureFromError } from '@/meta/runtime/pceFactLoadContract.js'
import {
  applyStandardListQuery,
  countEffectiveFilters,
  createFilterState,
  createStandardListContract,
  resolveStandardFilterOptions,
  safeExportRows,
} from '@/meta/runtime/standardListContract.js'
import BusinessTableScrollContainer from '../components/BusinessTableScrollContainer.vue'
import StandardListToolbar from '../components/StandardListToolbar.vue'
import PceBusinessActionBar from '../components/PceBusinessActionBar.vue'

defineProps({ embeddedInCommonShell: { type: Boolean, default: false } })
const VERSION = PAYMENT_ORDER_DRAFT_VERSION
const filterOptions = resolveStandardFilterOptions
const router = useRouter()
const rows = ref([])
const current = ref(null)
const pageFacts = ref(null)
const quickSearch = ref('')
const advancedVisible = ref(false)
const selectedRows = ref([])
const tableRef = ref(null)
const sourceQuickSearch = ref('')
const sourceAdvancedVisible = ref(false)
const sourceSelectedRows = ref([])
const sourceTableRef = ref(null)
const sourceSort = reactive({ prop: 'sourcePaymentOrderPrepareNo', order: 'ascending' })
const formalSort = reactive({ prop: 'draftNo', order: 'ascending' })
const capacity = reactive({})
const downstream = reactive({})
const serverMeta = reactive({ canonicalName: '正式付款单草稿', currentStateSource: 'server', tenantId: '', canaryBatchId: '' })
const observabilityActions = inject(PAGE_OBSERVABILITY_ACTIONS_KEY, null)
const selectOptions = {
  sourceStatus: [{ label: 'prepared', value: 'prepared' }],
  reviewStatus: [{ label: 'passed', value: 'passed' }, { label: 'blocked', value: 'blocked' }],
  readiness: [{ label: 'ready_for_payment_order_draft', value: 'ready_for_payment_order_draft' }],
  businessStatus: [{ label: 'reviewed', value: 'reviewed' }, { label: 'draft', value: 'draft' }],
  formalReadiness: [{ label: 'ready_for_payment_risk_review', value: 'ready_for_payment_risk_review' }],
  boolean: [{ label: '是', value: 'true' }, { label: '否', value: 'false' }],
}
const sourceListContract = createStandardListContract({
  tableId: 'payment-order-draft-source',
  stateId: 'source-list',
  searchPlaceholder: '输入正式付款单预备编号、付款申请编号、供应商或关键词',
  filterSchema: [
    { key: 'sourceStatus', label: '来源状态', type: 'select', options: selectOptions.sourceStatus },
    { key: 'sourceValidationStatus', label: '来源校验状态', type: 'select', options: selectOptions.reviewStatus },
    { key: 'sourceNextStepReadiness', label: '来源下游资格', type: 'select', options: selectOptions.readiness },
    { key: 'supplierName', label: '供应商', match: 'contains' },
    { key: 'legalEntityName', label: '法人', match: 'contains' },
    { key: 'ledgerBookId', label: '账簿', match: 'contains' },
    { key: 'currency', label: '币种', match: 'contains' },
    { key: 'amountMin', sourceKey: 'paymentAmount', label: '付款金额最小值', type: 'decimal-min', placeholder: '0.00' },
    { key: 'amountMax', sourceKey: 'paymentAmount', label: '付款金额最大值', type: 'decimal-max', placeholder: '999999.99' },
    { key: 'executionDateFrom', sourceKey: 'plannedExecutionDate', label: '计划执行日期起', type: 'date-min' },
    { key: 'executionDateTo', sourceKey: 'plannedExecutionDate', label: '计划执行日期止', type: 'date-max' },
    { key: 'payerBankAccountMasked', label: '付款方银行账户', match: 'contains' },
    { key: 'payeeBankAccountMasked', label: '收款方银行账户', match: 'contains' },
    { key: 'paymentRouteId', label: '支付路由', match: 'contains' },
    { key: 'scenarioType', label: '场景类型', match: 'contains' },
    { key: 'scenarioCode', label: '场景编码', match: 'contains' },
  ],
  columnSchema: [
    { key: 'sourcePaymentOrderPrepareNo', label: '正式付款单预备编号', minWidth: 220, fixed: 'left', className: 'pce-fixed-primary-no-column', sortable: true },
    { key: 'sourcePaymentRequestNo', label: '来源付款申请', minWidth: 200, sortable: true },
    { key: 'sourceStatusDisplay', label: '来源状态', width: 130, sortable: true },
    { key: 'sourceValidationStatusDisplay', label: '来源校验状态', width: 140 },
    { key: 'supplierName', label: '供应商', minWidth: 180, sortable: true },
    { key: 'legalEntityName', label: '法人', minWidth: 180 },
    { key: 'ledgerBookId', label: '账簿', minWidth: 150 },
    { key: 'payerBankAccountMasked', label: '付款银行账户', minWidth: 190 },
    { key: 'payeeBankAccountMasked', label: '收款银行账户', minWidth: 190 },
    { key: 'currency', label: '币种', width: 90 },
    { key: 'paymentAmount', label: '付款金额', width: 140, align: 'right', sortable: true },
    { key: 'plannedExecutionDate', label: '计划执行日期', width: 160, sortable: true },
    { key: 'paymentRouteId', label: '支付路由', minWidth: 150 },
    { key: 'sourceNextStepReadiness', label: '下游资格', minWidth: 230 },
  ],
  defaultSort: { prop: 'sourcePaymentOrderPrepareNo', order: 'ascending' },
  exportColumns: [
    { key: 'sourcePaymentOrderPrepareNo' }, { key: 'sourcePaymentRequestNo' },
    { key: 'sourceStatusDisplay' }, { key: 'sourceValidationStatusDisplay' }, { key: 'supplierName' },
    { key: 'legalEntityName' }, { key: 'ledgerBookId' }, { key: 'payerBankAccountMasked' },
    { key: 'payeeBankAccountMasked' }, { key: 'currency' }, { key: 'paymentAmount' },
    { key: 'plannedExecutionDate' }, { key: 'paymentRouteId' }, { key: 'sourceNextStepReadiness' },
  ],
})
const sourceDynamicColumns = sourceListContract.columnSchema.slice(1)
const formalListContract = createStandardListContract({
  tableId: 'payment-order-draft-main',
  stateId: 'formal-list',
  searchPlaceholder: '输入正式付款单草稿编号、来源编号、供应商或关键词',
  filterSchema: [
    { key: 'status', label: '业务状态', type: 'select', options: selectOptions.businessStatus },
    { key: 'reviewStatus', label: '复核状态', type: 'select', options: selectOptions.reviewStatus },
    { key: 'reviewResultCode', label: '复核结果编码', match: 'contains' },
    { key: 'nextStepReadiness', label: '下游资格', type: 'select', options: selectOptions.formalReadiness },
    { key: 'supplierName', label: '供应商', match: 'contains' },
    { key: 'legalEntityName', label: '法人', match: 'contains' },
    { key: 'ledgerBookId', label: '账簿', match: 'contains' },
    { key: 'currency', label: '币种', match: 'contains' },
    { key: 'amountMin', sourceKey: 'paymentAmount', label: '付款金额最小值', type: 'decimal-min', placeholder: '0.00' },
    { key: 'amountMax', sourceKey: 'paymentAmount', label: '付款金额最大值', type: 'decimal-max', placeholder: '999999.99' },
    { key: 'executionDateFrom', sourceKey: 'plannedExecutionDate', label: '计划执行日期起', type: 'date-min' },
    { key: 'executionDateTo', sourceKey: 'plannedExecutionDate', label: '计划执行日期止', type: 'date-max' },
    { key: 'payerBankAccountMasked', label: '付款方银行账户', match: 'contains' },
    { key: 'payeeBankAccountMasked', label: '收款方银行账户', match: 'contains' },
    { key: 'paymentRouteId', label: '支付路由', match: 'contains' },
    { key: 'bankInterfaceProfileId', label: '银行接口', match: 'contains' },
    { key: 'signingPolicyId', label: '签署策略', match: 'contains' },
    { key: 'authorizationRouteId', label: '授权路线', match: 'contains' },
    { key: 'fundsSufficient', label: '资金是否充足', type: 'boolean', options: selectOptions.boolean },
    { key: 'segregationValid', label: '职责分离是否通过', type: 'boolean', options: selectOptions.boolean },
    { key: 'signingCapabilityStatus', label: '签署能力状态', match: 'contains' },
    { key: 'credentialStatus', label: '凭据状态', match: 'contains' },
    { key: 'scenarioType', label: '场景类型', match: 'contains' },
    { key: 'scenarioCode', label: '场景编码', match: 'contains' },
  ],
  columnSchema: [
    { key: 'draftNo', label: '正式付款单草稿编号', minWidth: 220, fixed: 'left', className: 'pce-fixed-primary-no-column', sortable: true },
    { key: 'sourcePaymentOrderPrepareNo', label: '来源正式付款单预备', minWidth: 220, sortable: true },
    { key: 'sourcePaymentRequestNo', label: '来源付款申请', minWidth: 200 },
    { key: 'supplierName', label: '供应商', minWidth: 180, sortable: true },
    { key: 'legalEntityName', label: '法人', minWidth: 180 },
    { key: 'ledgerBookId', label: '账簿', minWidth: 150 },
    { key: 'payerBankAccountMasked', label: '付款银行账户', minWidth: 190 },
    { key: 'payeeBankAccountMasked', label: '收款银行账户', minWidth: 190 },
    { key: 'currency', label: '币种', width: 90 },
    { key: 'paymentAmount', label: '付款金额', width: 140, align: 'right', sortable: true },
    { key: 'plannedExecutionDate', label: '计划执行日期', width: 160, sortable: true },
    { key: 'paymentRouteId', label: '支付路由', minWidth: 150 },
    { key: 'bankInterfaceProfileId', label: '银行接口', minWidth: 150 },
    { key: 'signingPolicyId', label: '签署策略', minWidth: 150 },
    { key: 'fundsSufficientLabel', label: '资金结果', width: 120 },
    { key: 'segregationValidLabel', label: '职责分离结果', width: 140 },
    { key: 'reviewStatusDisplay', label: '复核状态', width: 120 },
    { key: 'statusDisplay', label: '业务状态', width: 110 },
    { key: 'nextStepReadinessDisplay', label: '下一步骤放行状态', minWidth: 230 },
  ],
  defaultSort: { prop: 'draftNo', order: 'ascending' },
  exportColumns: [
    { key: 'draftNo' }, { key: 'sourcePaymentOrderPrepareNo' }, { key: 'sourcePaymentRequestNo' },
    { key: 'supplierName' }, { key: 'legalEntityName' }, { key: 'ledgerBookId' },
    { key: 'payerBankAccountMasked' }, { key: 'payeeBankAccountMasked' }, { key: 'currency' },
    { key: 'paymentAmount' }, { key: 'plannedExecutionDate' }, { key: 'paymentRouteId' },
    { key: 'bankInterfaceProfileId' }, { key: 'signingPolicyId' }, { key: 'fundsSufficientLabel' },
    { key: 'segregationValidLabel' }, { key: 'reviewStatusDisplay' }, { key: 'statusDisplay' }, { key: 'nextStepReadinessDisplay' },
  ],
})
const mainFilters = reactive(createFilterState(formalListContract))
const sourceFilters = reactive(createFilterState(sourceListContract))
const Fact = defineComponent({
  props: { label: { type: String, required: true }, value: { type: [String, Number, Boolean], default: '-' } },
  setup: props => () => h('div', { class: 'fact' }, [h('span', props.label), h('strong', String(props.value ?? '-'))]),
})
const Heading = defineComponent({
  props: { title: { type: String, required: true }, note: { type: String, default: '' } },
  setup: props => () => h('div', { class: 'section-heading' }, [h('h3', props.title), h('strong', props.note)]),
})
const ruleClassification = PAYMENT_ORDER_DRAFT_RULE_CLASSIFICATION
const eligibilityFields = [
  { key: 'status', label: '业务状态' },
  { key: 'draftDataStatus', label: '草稿资料状态' },
  { key: 'reviewStatus', label: '复核状态' },
  { key: 'fundsAvailable', label: '资金是否充足' },
  { key: 'signingPolicyValid', label: '签署策略是否有效' },
  { key: 'authorizationRouteValid', label: '授权路线是否有效' },
  { key: 'signingCapabilityReady', label: '签署能力是否就绪' },
  { key: 'makerCheckerSegregationValid', label: '职责分离是否通过' },
  { key: 'routeValid', label: '支付路由是否有效' },
  { key: 'bankInterfaceAvailable', label: '银行接口是否可用' },
  { key: 'businessDayValid', label: '银行工作日是否有效' },
  { key: 'cutoffValid', label: '截止时间是否有效' },
  { key: 'singleLimitPassed', label: '单笔限额是否通过' },
  { key: 'dailyLimitPassed', label: '日累计限额是否通过' },
  { key: 'paymentHold', label: '是否存在付款冻结' },
  { key: 'duplicatePaymentRisk', label: '是否存在重复付款风险' },
  { key: 'nextStepReadiness', label: '下一步骤放行状态' },
  { key: 'eligible', label: '是否允许进入下一模块' },
  { key: 'blockingReasons', label: '阻断原因' },
]
const formalDisplayRows = computed(() => rows.value.map(row => ({
  ...row,
  payerBankAccountMasked: row.preview?.debtorAccountMasked || '-',
  payeeBankAccountMasked: row.preview?.creditorAccountMasked || '-',
  fundsSufficient: Boolean(row.authorities?.funds?.payload?.sufficient),
  fundsSufficientLabel: row.authorities?.funds?.payload?.sufficient ? '充足' : '不足',
  segregationValid: Boolean(row.authorities?.segregation?.payload?.segregationValid),
  segregationValidLabel: row.authorities?.segregation?.payload?.segregationValid ? '通过' : '未通过',
  signingCapabilityStatus: row.authorities?.signingCapability?.payload?.signingServiceStatus || '-',
  credentialStatus: row.authorities?.signingCapability?.payload?.credentialStatus || '-',
  scenarioType: 'persistent_canary',
  scenarioCode: row.scenarioCode || '-',
  nextStepReadiness: row.eligibility?.nextStepReadiness || 'blocked',
  statusDisplay: paymentOrderDraftDisplayValue(row.status),
  reviewStatusDisplay: paymentOrderDraftDisplayValue(row.reviewStatus),
  nextStepReadinessDisplay: paymentOrderDraftDisplayValue(row.eligibility?.nextStepReadiness),
})))
const filteredRows = computed(() => applyStandardListQuery(formalDisplayRows.value, {
  quickSearch: quickSearch.value,
  filters: mainFilters,
  contract: formalListContract,
  sort: formalSort,
}))
const sourceRows = computed(() => rows.value.map(row => ({
  id: row.id,
  sourcePaymentOrderPrepareNo: row.sourcePaymentOrderPrepareNo,
  sourcePaymentRequestNo: row.sourcePaymentRequestNo,
  sourceStatus: row.source?.status,
  sourceValidationStatus: row.source?.validationStatus,
  sourceStatusDisplay: paymentOrderDraftDisplayValue(row.source?.status),
  sourceValidationStatusDisplay: paymentOrderDraftDisplayValue(row.source?.validationStatus),
  sourceNextStepReadiness: row.source?.nextStepReadiness,
  supplierName: row.supplierName,
  legalEntityName: row.legalEntityName,
  ledgerBookId: row.ledgerBookId,
  currency: row.currency,
  paymentAmount: row.paymentAmount,
  plannedExecutionDate: row.plannedExecutionDate,
  payerBankAccountMasked: row.preview?.debtorAccountMasked || '-',
  payeeBankAccountMasked: row.preview?.creditorAccountMasked || '-',
  paymentRouteId: row.paymentRouteId,
  scenarioType: 'persistent_canary',
  scenarioCode: serverMeta.canaryBatchId,
})))
const filteredSourceRows = computed(() => applyStandardListQuery(sourceRows.value, {
  quickSearch: sourceQuickSearch.value,
  filters: sourceFilters,
  contract: sourceListContract,
  sort: sourceSort,
}))
const sourceEffectiveFilterCount = computed(() => countEffectiveFilters(sourceQuickSearch.value, sourceFilters, sourceListContract))
const formalEffectiveFilterCount = computed(() => countEffectiveFilters(quickSearch.value, mainFilters, formalListContract))
const sortLabel = sort => `${sort.prop || '默认业务顺序'}${sort.order === 'descending' ? '降序' : '升序'}`
const sourceSortText = computed(() => sortLabel(sourceSort))
const formalSortText = computed(() => sortLabel(formalSort))
const unwrap = response => response?.data?.data || response?.data || {}
function authority(name) { return current.value?.authorities?.[name]?.payload || {} }
async function refresh() {
  try {
    const response = await paymentOrderDraftApi.list()
    const envelope = response?.data || response || {}
    const data = envelope.data || envelope
    serverMeta.canonicalName = envelope.canonicalName || '正式付款单草稿'
    serverMeta.currentStateSource = envelope.currentStateSource || 'server'
    serverMeta.tenantId = data.tenantId || ''
    serverMeta.canaryBatchId = data.canaryBatchId || ''
    pageFacts.value = createPaymentOrderDraftPageFacts(response)
    serverMeta.tenantId = pageFacts.value.tenantId
    serverMeta.canaryBatchId = pageFacts.value.canaryBatchId
    rows.value = pageFacts.value.rows
    Object.assign(capacity, pageFacts.value.capacity)
    Object.assign(downstream, pageFacts.value.downstreamCounts)
    if (rows.value.length) await selectDetail(rows.value[0])
  } catch (error) {
    const failed = factLoadFailureFromError(
      error,
      '/api/finance/payment-order-drafts/',
      pageFacts.value?.factLoadFacts,
    )
    pageFacts.value = createPaymentOrderDraftPageFacts({
      data: { factLoadFacts: failed },
    })
    rows.value = []
    current.value = null
    selectedRows.value = []
    for (const key of Object.keys(capacity)) capacity[key] = null
    for (const key of Object.keys(downstream)) downstream[key] = null
    serverMeta.tenantId = pageFacts.value.tenantId
    serverMeta.canaryBatchId = pageFacts.value.canaryBatchId
    ElMessage.error(error?.message || '正式付款单草稿服务端读取失败')
  }
}
async function selectDetail(row) {
  const detail = unwrap(await paymentOrderDraftApi.detail(row.id))
  current.value = {
    ...detail,
    ...stateMachineFactsFromServer(detail, `payment-order-draft-detail:${detail.draftNo}`),
  }
}
function clearSelection() { tableRef.value?.clearSelection?.(); selectedRows.value = [] }
function handleFormalSort({ prop, order }) {
  formalSort.prop = prop || formalListContract.defaultSort.prop
  formalSort.order = order || formalListContract.defaultSort.order
}
function handleSourceSort({ prop, order }) {
  sourceSort.prop = prop || sourceListContract.defaultSort.prop
  sourceSort.order = order || sourceListContract.defaultSort.order
}
function clearSort() {
  tableRef.value?.clearSort?.()
  Object.assign(formalSort, formalListContract.defaultSort)
  clearSelection()
}
function clearFilters() {
  quickSearch.value = ''
  Object.assign(mainFilters, createFilterState(formalListContract))
  clearSelection()
}
function clearSourceSelection() { sourceTableRef.value?.clearSelection?.(); sourceSelectedRows.value = [] }
function clearSourceSort() {
  sourceTableRef.value?.clearSort?.()
  Object.assign(sourceSort, sourceListContract.defaultSort)
  clearSourceSelection()
}
function clearSourceFilters() {
  sourceQuickSearch.value = ''
  Object.assign(sourceFilters, createFilterState(sourceListContract))
  clearSourceSelection()
}
function downloadRows(filename, safeRows, exportColumns) {
  const fields = exportColumns.map(column => column.key)
  const csv = [fields.join(','), ...safeRows.map(row => fields.map(field => `"${String(row[field] ?? '').replaceAll('"', '""')}"`).join(','))].join('\n')
  const link = document.createElement('a')
  link.href = URL.createObjectURL(new Blob([`\ufeff${csv}`], { type: 'text/csv;charset=utf-8;' }))
  link.download = filename
  link.click()
  URL.revokeObjectURL(link.href)
}
function exportCurrent() {
  downloadRows('payment-order-drafts.csv', safeExportRows(filteredRows.value, formalListContract), formalListContract.exportColumns)
}
function exportSourceCurrent() {
  downloadRows('payment-order-draft-sources.csv', safeExportRows(filteredSourceRows.value, sourceListContract), sourceListContract.exportColumns)
}
function navigateNext() {
  router.push({ path: capacity.nextRoute || '/finance/payment-risk-reviews', query: { navigationOnly: 'true', sourcePaymentOrderDraftNo: current.value?.draftNo } })
}
function buildDiagnostics() {
  if (!pageFacts.value) throw new Error('fact_load_not_completed')
  const row = current.value || {}
  const approval = authority('authorizationRoute')
  const eligibility = row?.eligibility || {}
  const stateMachineFacts = current.value
    ? stateMachineFactsFromServer(
        row,
        `payment-order-draft-diagnostic:${row.draftNo}`,
      )
    : null
  return {
    version: VERSION,
    canonicalName: serverMeta.canonicalName,
    fullUrl: window.location.href,
    currentStateSource: serverMeta.currentStateSource,
    ...pageFacts.value.factLoadFacts,
    factLoadFacts: pageFacts.value.factLoadFacts,
    passed: pageFacts.value.passed,
    stateMachineFacts,
    tenantId: serverMeta.tenantId,
    canaryBatchId: serverMeta.canaryBatchId,
    contractVersion: 'PCE-WEB-ACCEPTANCE-V1.1',
    businessVersion: VERSION,
    moduleCode: 'FIN_PAYMENT_ORDER_DRAFT',
    pageCode: 'payment-order-draft',
    pageType: 'list',
    process: { previousModuleCode: 'payment-order-prepare', currentModuleCode: 'payment-order-draft', nextModuleCode: capacity.nextModuleCode, nextCanonicalName: capacity.nextCanonicalName, nextRoute: capacity.nextRoute },
    capacity: pageFacts.value.factLoadStatus === 'read_failed'
      ? null
      : { ...capacity },
    resultCount: pageFacts.value.resultCount,
    currentObject: row,
    sourceObjects: pageFacts.value.sourceObjects,
    status: row?.status || '',
    strictServerFacts: {
      ...pageFacts.value.strictServerFacts,
      ...(stateMachineFacts ? { status: row.status, ...stateMachineFacts } : {}),
    },
    ruleClassification: { ...ruleClassification },
    displayValues: {
      status: { rawValue: row.status, displayValue: paymentOrderDraftDisplayValue(row.status) },
      draftDataStatus: { rawValue: row.draftDataStatus, displayValue: paymentOrderDraftDisplayValue(row.draftDataStatus) },
      reviewStatus: { rawValue: row.reviewStatus, displayValue: paymentOrderDraftDisplayValue(row.reviewStatus) },
      nextStepReadiness: {
        rawValue: eligibility.nextStepReadiness,
        displayValue: paymentOrderDraftDisplayValue(eligibility.nextStepReadiness),
      },
    },
    selectedObject: {
      draftNo: row.draftNo,
      sourcePaymentOrderPrepareNo: row.sourcePaymentOrderPrepareNo,
      status: row.status,
      draftDataStatus: row.draftDataStatus,
      reviewStatus: row.reviewStatus,
      reviewResultCode: row.reviewResultCode,
      reviewIssueCount: row.reviewIssueCount,
      currentDraftDataVersion: row.currentDraftDataVersion,
      currentReviewVersion: row.currentReviewVersion,
      ...stateMachineFacts,
    },
    funds: authority('funds'),
    signingPolicy: authority('signingPolicy'),
    approvalSteps: { stepCount: approval.stepCount, steps: approval.steps, active: approval.active },
    signingCapability: authority('signingCapability'),
    segregation: authority('segregation'),
    orderPreview: {
      proposedFormalOrderReference: row.preview?.proposedFormalOrderReference,
      debtorAccountMasked: row.preview?.debtorAccountMasked,
      creditorAccountMasked: row.preview?.creditorAccountMasked,
      currency: row.preview?.currency,
      amount: row.preview?.amount,
      routeCode: row.preview?.routeCode,
      channelCode: row.preview?.channelCode,
      previewHash: row.preview?.previewHash,
      readOnly: row.preview?.readOnly,
      formalPaymentOrderCreated: false,
      signed: false,
      sentExternally: false,
      paymentExecuted: false,
    },
    eligibility: {
      status: eligibility.status,
      draftDataStatus: eligibility.draftDataStatus,
      reviewStatus: eligibility.reviewStatus,
      fundsAvailable: eligibility.fundsAvailable,
      signingPolicyValid: eligibility.signingPolicyValid,
      signingCapabilityReady: eligibility.signingCapabilityReady,
      makerCheckerSegregationValid: eligibility.makerCheckerSegregationValid,
      routeValid: eligibility.routeValid,
      bankInterfaceAvailable: eligibility.bankInterfaceAvailable,
      nextStepReadiness: eligibility.nextStepReadiness,
      eligible: eligibility.eligible,
      blockingReasons: eligibility.blockingReasons,
      serverDerived: eligibility.serverDerived,
      serverRereviewRequired: eligibility.serverRereviewRequired,
    },
    persistence: { idempotencyStatus: row.idempotencyStatus, numberReservationStatus: row.numberReservationStatus, transactionStatus: row.transactionStatus, auditStatus: row.auditStatus },
    downstreamCounts: { ...downstream },
    boundaries: { formalPaymentOrderCreated: false, signed: false, sentExternally: false, paymentExecuted: false, productionRolloutEnabled: false },
  }
}
onMounted(() => {
  observabilityActions?.register({ refresh, buildDiagnostics })
  refresh()
})
onBeforeUnmount(() => observabilityActions?.unregister())
</script>

<style scoped>
.pop-page { display: grid; gap: 16px; min-width: 0; max-width: 100%; overflow-x: clip; }
.business-card { min-width: 0; max-width: 100%; padding: 18px; overflow: hidden; border: 1px solid #dce4ee; border-radius: 12px; background: #fff; box-sizing: border-box; }
.capacity-card { border-color: #a7d7c5; background: #f3fbf8; }
.preview-card { border-color: #a8c7ed; background: #f5f9ff; }
.eligibility-card { border-color: #e7c875; background: #fffaf0; }
.boundary-card { border-color: #efb4b4; background: #fff7f7; }
.section-heading { display: flex; justify-content: space-between; gap: 16px; align-items: baseline; margin-bottom: 14px; }
.section-heading h3 { margin: 0; color: #17233d; }
.section-heading strong { color: #47729f; font-size: 13px; }
.facts { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; }
.fact { display: grid; gap: 4px; padding: 10px; border-radius: 8px; background: #f6f8fb; overflow-wrap: anywhere; }
.fact span { color: #68758a; font-size: 12px; }
.fact strong { color: #17233d; }
.ctrl-f { margin: 12px 0 0; color: #76849a; font-size: 12px; }
.list-toolbar-title { margin: 0 0 10px; color: #334155; font-size: 14px; }
.advanced-filter-panel {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 14px;
  margin: 12px 0;
  padding: 14px;
  border: 1px solid #dbe4ef;
  border-radius: 8px;
  background: #f6f8fb;
}
.advanced-filter-panel label { display: grid; gap: 6px; min-width: 0; color: #68758a; font-size: 12px; }
.advanced-filter-panel :deep(.el-select),
.advanced-filter-panel :deep(.el-date-editor),
.advanced-filter-panel :deep(.el-input) { width: 100%; }
@media (max-width: 920px) {
  .business-card { padding: 12px; }
  .advanced-filter-panel { grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); }
}
</style>
