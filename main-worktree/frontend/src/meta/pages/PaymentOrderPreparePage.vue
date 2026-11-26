<template>
  <main class="pop-page" data-acceptance-id="payment-order-prepare-business-content">
    <section class="business-card capacity-card" data-acceptance-id="payment-order-prepare-capacity">
      <Heading title="持久金丝雀容量" :note="`成功链=${capacity.passThroughLineageCount || 0} / 阻断场景=${capacity.blockedScenarioCount || 0}`" />
      <div class="facts">
        <Fact label="付款指令准备来源数量" :value="capacity.paymentInstructionPrepareSourceCount" />
        <Fact label="来源已消费数量" :value="capacity.paymentInstructionPrepareConsumedCount" />
        <Fact label="正式付款单预备数量" :value="capacity.formalPaymentOrderPrepareCount" />
        <Fact label="prepared 数量" :value="capacity.preparedPaymentOrderPrepareCount" />
        <Fact label="下游合格来源数量" :value="capacity.downstreamEligibleSourceCount" />
        <Fact label="下一阶段已消费数量" :value="capacity.nextStageConsumedCount" />
      </div>
      <p class="ctrl-f">Ctrl+F：持久金丝雀容量</p>
    </section>

    <section class="business-card" data-acceptance-id="payment-order-prepare-source">
      <Heading title="付款指令准备来源" note="唯一直接来源：paymentInstructionPrepare" />
      <div class="facts">
        <Fact label="来源付款指令准备编号" :value="current?.sourcePaymentInstructionPrepareNo" />
        <Fact label="来源状态" :value="current?.source?.status" />
        <Fact label="来源校验状态" :value="current?.source?.validationStatus" />
        <Fact label="来源版本" :value="current?.sourceInstructionPrepareVersion" />
        <Fact label="来源资料版本" :value="current?.sourceInstructionDataVersion" />
        <Fact label="来源校验版本" :value="current?.sourceInstructionValidationVersion" />
      </div>
      <p class="ctrl-f">Ctrl+F：付款指令准备来源</p>
    </section>

    <section class="business-card" data-acceptance-id="payment-order-prepare-object">
      <Heading title="正式付款单预备对象" :note="current?.status || '-'" />
      <div class="facts">
        <Fact label="正式付款单预备编号" :value="current?.prepareNo" />
        <Fact label="供应商" :value="current?.supplierName" />
        <Fact label="法人主体" :value="current?.legalEntityName" />
        <Fact label="账簿" :value="current?.ledgerBookId" />
        <Fact label="币种" :value="current?.currency" />
        <Fact label="付款金额" :value="current?.paymentAmount" />
        <Fact label="计划执行日期" :value="current?.plannedExecutionDate" />
        <Fact label="对象版本" :value="current?.version" />
      </div>
      <p class="ctrl-f">Ctrl+F：正式付款单预备编号</p>
    </section>

    <section class="business-card" data-acceptance-id="payment-order-prepare-funds">
      <Heading title="资金可用性证据" note="只读校验；不冻结资金；不扣减余额" />
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

    <section class="business-card" data-acceptance-id="payment-order-prepare-signing">
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

    <section class="business-card" data-acceptance-id="payment-order-prepare-segregation">
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
      <Heading title="正式付款单只读预览" note="未签署、未发送、未创建正式付款单" />
      <div class="facts">
        <Fact label="建议付款单引用" :value="current?.preview?.proposedOrderReference" />
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

    <section class="business-card" data-acceptance-id="payment-order-prepare-validation">
      <Heading title="校验结果与问题明细" :note="current?.validation?.resultCode || 'not_validated'" />
      <div class="facts">
        <Fact label="校验状态" :value="current?.validationStatus" />
        <Fact label="规则数量" :value="current?.validation?.ruleCount" />
        <Fact label="通过数量" :value="current?.validation?.passedCount" />
        <Fact label="阻断数量" :value="current?.validation?.blockedCount" />
        <Fact label="问题数量" :value="current?.validation?.issueCount" />
      </div>
      <BusinessTableScrollContainer acceptance-id="business-table-scroll-payment-order-issues" min-width="980px">
        <el-table :data="current?.validation?.issues || []" border stripe>
          <el-table-column prop="ruleCode" label="规则编码" min-width="220" />
          <el-table-column prop="dimension" label="维度" min-width="140" />
          <el-table-column prop="expected" label="期望值" min-width="200" />
          <el-table-column prop="actual" label="实际值" min-width="200" />
          <el-table-column prop="message" label="说明" min-width="230" />
        </el-table>
      </BusinessTableScrollContainer>
      <p class="ctrl-f">Ctrl+F：校验结果与问题明细</p>
    </section>

    <section class="business-card eligibility-card" data-acceptance-id="payment-order-draft-eligibility">
      <Heading title="正式付款单草稿放行资格" :note="current?.eligibility?.nextStepReadiness || 'blocked'" />
      <div class="facts">
        <Fact v-for="field in eligibilityFields" :key="field" :label="field" :value="formatValue(current?.eligibility?.[field])" />
      </div>
      <PceBusinessActionBar
        current-module="payment-order-prepare"
        :current-status="current?.status || ''"
        :selected-rows="selectedRows.length ? selectedRows : (current ? [current] : [])"
        :eligibility="current?.eligibility?.eligible ?? null"
        :show-unavailable="true"
      />
      <p class="ctrl-f">Ctrl+F：正式付款单草稿放行资格</p>
    </section>

    <section class="business-card" data-acceptance-id="payment-order-prepare-audit">
      <Heading title="版本、幂等、事务与审计" note="currentStateSource=server" />
      <div class="facts">
        <Fact label="业务对象版本" :value="current?.version" />
        <Fact label="状态转换数量" :value="current?.statusTransitionCount" />
        <Fact label="状态机事实一致" :value="current?.stateMachineConsistent" />
        <Fact label="资料版本" :value="current?.currentOrderDataVersion" />
        <Fact label="校验版本" :value="current?.currentValidationVersion" />
        <Fact label="幂等状态" :value="current?.idempotencyStatus" />
        <Fact label="编号状态" :value="current?.numberReservationStatus" />
        <Fact label="事务状态" :value="current?.transactionStatus" />
        <Fact label="审计状态" :value="current?.auditStatus" />
      </div>
      <p class="ctrl-f">Ctrl+F：版本、幂等、事务与审计</p>
    </section>

    <section class="business-card" data-acceptance-id="payment-order-prepare-source-list-region">
      <Heading title="付款指令准备来源列表" :note="`来源数量=${sourceRows.length}`" />
      <h4 class="list-toolbar-title">付款指令准备来源列表工具栏</h4>
      <StandardListToolbar
        page-id="payment-order-prepare"
        table-id="payment-order-prepare-source"
        v-model:quick-search="sourceQuickSearch"
        :placeholder="sourceListContract.searchPlaceholder"
        :advanced-visible="sourceAdvancedVisible"
        :result-count="filteredSourceRows.length"
        :selected-count="sourceSelectedRows.length"
        :active-filter-count="sourceEffectiveFilterCount"
        :sort-text="sourceSortText"
        @search="clearSourceSelection"
        @toggle-advanced="sourceAdvancedVisible = !sourceAdvancedVisible"
        @clear-filters="clearSourceFilters"
        @clear-sort="clearSourceSort"
        @export-current="exportSourceCurrent"
        @clear-selection="clearSourceSelection"
      />
      <div
        v-show="sourceAdvancedVisible"
        class="advanced-filter-panel list-advanced-filter-panel"
        data-pce-filter-for="payment-order-prepare-source"
        data-acceptance-id="source-list-advanced-filter"
      >
        <label v-for="field in sourceListContract.filterSchema" :key="field.key" :data-filter-key="field.key">
          <span>{{ field.label }}</span>
          <el-select v-if="field.type === 'select'" v-model="sourceFilters[field.key]" clearable filterable>
            <el-option v-for="option in filterOptions(field, sourceRows)" :key="String(option.value)" :label="option.label" :value="option.value" />
          </el-select>
          <el-date-picker
            v-else-if="field.type === 'dateRange'"
            v-model="sourceFilters[field.key]"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="选择日期"
          />
          <el-input v-else v-model="sourceFilters[field.key]" clearable :type="field.type === 'numberRange' ? 'number' : 'text'" :placeholder="field.placeholder || field.label" />
        </label>
      </div>
      <BusinessTableScrollContainer acceptance-id="business-table-scroll-payment-order-prepare-source" page-id="payment-order-prepare" table-id="payment-order-prepare-source" min-width="1300px">
        <el-table
          ref="sourceTableRef"
          :data="filteredSourceRows"
          border
          stripe
          height="440"
          scrollbar-always-on
          row-key="sourcePaymentInstructionPrepareNo"
          data-acceptance-id="source-list-table"
          @selection-change="sourceSelectedRows = $event"
          @sort-change="handleSourceSort"
        >
          <el-table-column type="selection" width="55" fixed="left" class-name="business-table-selection-column" header-class-name="business-table-selection-column" />
          <el-table-column type="index" label="序号" width="64" fixed="left" class-name="pce-fixed-index-column" header-class-name="pce-fixed-index-column" />
          <el-table-column prop="sourcePaymentInstructionPrepareNo" label="付款指令准备编号" min-width="220" fixed="left" class-name="pce-fixed-primary-no-column" header-class-name="pce-fixed-primary-no-column" sortable="custom" show-overflow-tooltip />
          <el-table-column
            v-for="column in sourceDynamicColumns"
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
            <template #default="{ row }"><el-button size="small" plain data-acceptance-id="source-row-view-button" @click.stop="selectDetail(row)">查看</el-button></template>
          </el-table-column>
          <template #empty><span>{{ sourceListContract.emptyState }}</span></template>
        </el-table>
      </BusinessTableScrollContainer>
    </section>

    <section class="business-card" data-acceptance-id="payment-order-prepare-toolbar-region">
      <Heading title="正式付款单预备正式列表" note="普通页面仅提供只读操作" />
      <h4 class="list-toolbar-title">正式付款单预备列表工具栏</h4>
      <StandardListToolbar
        page-id="payment-order-prepare"
        table-id="payment-order-prepare-main"
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
        data-pce-filter-for="payment-order-prepare-main"
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

    <section class="business-card" data-acceptance-id="payment-order-prepare-list-region">
      <Heading title="正式付款单预备正式列表" :note="`正式对象数量=${rows.length}`" />
      <BusinessTableScrollContainer acceptance-id="business-table-scroll-payment-order-prepare-main" page-id="payment-order-prepare" table-id="payment-order-prepare-main" min-width="2200px">
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
      <p class="ctrl-f">Ctrl+F：{{ rows[0]?.prepareNo || '正式付款单预备编号' }}</p>
    </section>

    <section class="business-card boundary-card" data-acceptance-id="payment-order-prepare-zero-boundary">
      <Heading title="下游零对象保护" note="导航不创建正式付款单草稿或任何付款对象" />
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
import { paymentOrderPrepareApi } from '@/api/paymentOrderPrepare.js'
import { PAYMENT_ORDER_PREPARE_VERSION } from '@/meta/runtime/paymentOrderPrepareRuntime.js'
import { PAGE_OBSERVABILITY_ACTIONS_KEY } from '@/meta/runtime/pageObservabilityActions.js'
import { stateMachineFactsFromServer } from '@/meta/runtime/pceStateMachineFactContract.js'
import {
  factLoadFailureFromError,
  factLoadPassed,
  factLoadResultCount,
  readPceFactLoadEnvelope,
} from '@/meta/runtime/pceFactLoadContract.js'
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
const VERSION = PAYMENT_ORDER_PREPARE_VERSION
const FACT_LOAD_API_URL = '/api/finance/payment-order-prepares/'
const router = useRouter()
const rows = ref([])
const factLoadFacts = ref(null)
const current = ref(null)
const quickSearch = ref('')
const advancedVisible = ref(false)
const selectedRows = ref([])
const tableRef = ref(null)
const sourceQuickSearch = ref('')
const sourceAdvancedVisible = ref(false)
const sourceSelectedRows = ref([])
const sourceTableRef = ref(null)
const sourceSort = reactive({ prop: 'sourcePaymentInstructionPrepareNo', order: 'ascending' })
const formalSort = reactive({ prop: 'prepareNo', order: 'ascending' })
const capacity = reactive({})
const downstream = reactive({})
const serverMeta = reactive({ canonicalName: '正式付款单预备', currentStateSource: 'server', tenantId: '', canaryBatchId: '' })
const observabilityActions = inject(PAGE_OBSERVABILITY_ACTIONS_KEY, null)
const filterOptions = resolveStandardFilterOptions
const selectOptions = {
  sourceStatus: [{ label: 'prepared', value: 'prepared' }],
  validationStatus: [{ label: 'passed', value: 'passed' }, { label: 'blocked', value: 'blocked' }],
  readiness: [{ label: 'ready_for_payment_order_prepare', value: 'ready_for_payment_order_prepare' }],
  businessStatus: [{ label: 'prepared', value: 'prepared' }, { label: 'draft', value: 'draft' }],
  formalReadiness: [{ label: 'ready_for_payment_order_draft', value: 'ready_for_payment_order_draft' }],
  boolean: [{ label: '是', value: 'true' }, { label: '否', value: 'false' }],
}
const sourceListContract = createStandardListContract({
  tableId: 'payment-order-prepare-source',
  stateId: 'source-list',
  searchPlaceholder: '输入付款指令准备编号、付款申请编号、供应商或关键词',
  filterSchema: [
    { key: 'sourceStatus', label: '来源状态', type: 'select', options: selectOptions.sourceStatus },
    { key: 'sourceValidationStatus', label: '来源校验状态', type: 'select', options: selectOptions.validationStatus },
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
    { key: 'sourcePaymentInstructionPrepareNo', label: '付款指令准备编号', minWidth: 220, fixed: 'left', className: 'pce-fixed-primary-no-column', sortable: true },
    { key: 'sourcePaymentRequestNo', label: '来源付款申请', minWidth: 200, sortable: true },
    { key: 'sourceStatus', label: '来源状态', width: 130, sortable: true },
    { key: 'sourceValidationStatus', label: '来源校验状态', width: 140 },
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
  defaultSort: { prop: 'sourcePaymentInstructionPrepareNo', order: 'ascending' },
  exportColumns: [
    { key: 'sourcePaymentInstructionPrepareNo' }, { key: 'sourcePaymentRequestNo' },
    { key: 'sourceStatus' }, { key: 'sourceValidationStatus' }, { key: 'supplierName' },
    { key: 'legalEntityName' }, { key: 'ledgerBookId' }, { key: 'payerBankAccountMasked' },
    { key: 'payeeBankAccountMasked' }, { key: 'currency' }, { key: 'paymentAmount' },
    { key: 'plannedExecutionDate' }, { key: 'paymentRouteId' }, { key: 'sourceNextStepReadiness' },
  ],
})
const sourceDynamicColumns = sourceListContract.columnSchema.slice(1)
const formalListContract = createStandardListContract({
  tableId: 'payment-order-prepare-main',
  stateId: 'formal-list',
  searchPlaceholder: '输入正式付款单预备编号、来源编号、供应商或关键词',
  filterSchema: [
    { key: 'status', label: '业务状态', type: 'select', options: selectOptions.businessStatus },
    { key: 'validationStatus', label: '校验状态', type: 'select', options: selectOptions.validationStatus },
    { key: 'validationResultCode', label: '校验结果编码', match: 'contains' },
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
  ],
  columnSchema: [
    { key: 'prepareNo', label: '正式付款单预备编号', minWidth: 220, fixed: 'left', className: 'pce-fixed-primary-no-column', sortable: true },
    { key: 'sourcePaymentInstructionPrepareNo', label: '来源付款指令准备', minWidth: 220, sortable: true },
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
    { key: 'validationStatus', label: '校验状态', width: 120 },
    { key: 'status', label: '业务状态', width: 110 },
    { key: 'nextStepReadiness', label: '下游资格', minWidth: 230 },
  ],
  defaultSort: { prop: 'prepareNo', order: 'ascending' },
  exportColumns: [
    { key: 'prepareNo' }, { key: 'sourcePaymentInstructionPrepareNo' }, { key: 'sourcePaymentRequestNo' },
    { key: 'supplierName' }, { key: 'legalEntityName' }, { key: 'ledgerBookId' },
    { key: 'payerBankAccountMasked' }, { key: 'payeeBankAccountMasked' }, { key: 'currency' },
    { key: 'paymentAmount' }, { key: 'plannedExecutionDate' }, { key: 'paymentRouteId' },
    { key: 'bankInterfaceProfileId' }, { key: 'signingPolicyId' }, { key: 'fundsSufficientLabel' },
    { key: 'segregationValidLabel' }, { key: 'validationStatus' }, { key: 'status' }, { key: 'nextStepReadiness' },
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
const eligibilityFields = [
  'status', 'orderDataStatus', 'validationStatus', 'fundsAvailable',
  'signingPolicyValid', 'authorizationRouteValid', 'signingCapabilityReady',
  'makerCheckerSegregationValid', 'routeValid', 'bankInterfaceAvailable',
  'businessDayValid', 'cutoffValid', 'singleLimitPassed', 'dailyLimitPassed',
  'paymentHold', 'duplicatePaymentRisk', 'nextStepReadiness', 'eligible', 'blockingReasons',
]
const formalDisplayRows = computed(() => rows.value.map(row => ({
  ...row,
  payerBankAccountMasked: row.preview?.debtorAccountMasked || '-',
  payeeBankAccountMasked: row.preview?.creditorAccountMasked || '-',
  fundsSufficient: Boolean(row.authorities?.funds?.payload?.sufficient),
  fundsSufficientLabel: row.authorities?.funds?.payload?.sufficient ? '充足' : '不足',
  segregationValid: Boolean(row.authorities?.segregation?.payload?.segregationValid),
  segregationValidLabel: row.authorities?.segregation?.payload?.segregationValid ? '通过' : '未通过',
  nextStepReadiness: row.eligibility?.nextStepReadiness || 'blocked',
})))
const filteredRows = computed(() => applyStandardListQuery(formalDisplayRows.value, {
  quickSearch: quickSearch.value,
  filters: mainFilters,
  contract: formalListContract,
  sort: formalSort,
}))
const sourceRows = computed(() => rows.value.map(row => ({
  id: row.id,
  sourcePaymentInstructionPrepareNo: row.sourcePaymentInstructionPrepareNo,
  sourcePaymentRequestNo: row.sourcePaymentRequestNo,
  sourceStatus: row.source?.status,
  sourceValidationStatus: row.source?.validationStatus,
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
function formatValue(value) { return Array.isArray(value) ? (value.join(', ') || '无') : value }
async function refresh() {
  try {
    const loaded = readPceFactLoadEnvelope(
      await paymentOrderPrepareApi.list(),
      FACT_LOAD_API_URL,
    )
    factLoadFacts.value = loaded.factLoadFacts
    const envelope = loaded.payload
    const data = loaded.data
    serverMeta.canonicalName = envelope.canonicalName || '正式付款单预备'
    serverMeta.currentStateSource = envelope.currentStateSource || 'server'
    serverMeta.tenantId = data.tenantId || ''
    serverMeta.canaryBatchId = data.canaryBatchId || ''
    rows.value = (data.results || []).map((row) => ({
      ...row,
      ...stateMachineFactsFromServer(row, `payment-order-prepare-list:${row.prepareNo}`),
    }))
    Object.assign(capacity, data.capacity || {})
    Object.assign(downstream, data.downstreamCounts || {})
    if (rows.value.length) await selectDetail(rows.value[0])
  } catch (error) {
    factLoadFacts.value = factLoadFailureFromError(
      error,
      FACT_LOAD_API_URL,
      factLoadFacts.value,
    )
    ElMessage.error(error?.message || '正式付款单预备服务端读取失败')
  }
}
async function selectDetail(row) {
  const detail = unwrap(await paymentOrderPrepareApi.detail(row.id))
  current.value = {
    ...detail,
    ...stateMachineFactsFromServer(detail, `payment-order-prepare-detail:${detail.prepareNo}`),
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
  downloadRows('payment-order-prepares.csv', safeExportRows(filteredRows.value, formalListContract), formalListContract.exportColumns)
}
function exportSourceCurrent() {
  downloadRows('payment-order-prepare-sources.csv', safeExportRows(filteredSourceRows.value, sourceListContract), sourceListContract.exportColumns)
}
function navigateNext() {
  router.push({ path: capacity.nextRoute || '/finance/payment-order-drafts', query: { navigationOnly: 'true', sourcePaymentOrderPrepareNo: current.value?.prepareNo } })
}
function buildDiagnostics() {
  const row = current.value || {}
  const approval = authority('authorizationRoute')
  const eligibility = row?.eligibility || {}
  const stateMachineFacts = current.value
    ? stateMachineFactsFromServer(
        row,
        `payment-order-prepare-diagnostic:${row.prepareNo}`,
      )
    : null
  return {
    version: VERSION,
    canonicalName: serverMeta.canonicalName,
    fullUrl: window.location.href,
    currentStateSource: serverMeta.currentStateSource,
    ...factLoadFacts.value,
    factLoadFacts: factLoadFacts.value,
    resultCount: factLoadResultCount(factLoadFacts.value, rows.value.length),
    passed: factLoadPassed(factLoadFacts.value, Boolean(stateMachineFacts)),
    stateMachineFacts,
    strictFacts: {
      currentStateSource: 'server',
      ...factLoadFacts.value,
      factLoadFacts: factLoadFacts.value,
      resultCount: factLoadResultCount(factLoadFacts.value, rows.value.length),
      passed: factLoadPassed(factLoadFacts.value, Boolean(stateMachineFacts)),
      ...(stateMachineFacts ? { status: row.status, ...stateMachineFacts } : {}),
    },
    tenantId: serverMeta.tenantId,
    canaryBatchId: serverMeta.canaryBatchId,
    process: { previousModuleCode: 'payment_instruction_prepare', currentModuleCode: 'payment_order_prepare', nextModuleCode: capacity.nextModuleCode, nextCanonicalName: capacity.nextCanonicalName, nextRoute: capacity.nextRoute },
    capacity: { ...capacity },
    selectedObject: {
      prepareNo: row.prepareNo,
      sourcePaymentInstructionPrepareNo: row.sourcePaymentInstructionPrepareNo,
      status: row.status,
      orderDataStatus: row.orderDataStatus,
      validationStatus: row.validationStatus,
      validationResultCode: row.validationResultCode,
      validationIssueCount: row.validationIssueCount,
      currentOrderDataVersion: row.currentOrderDataVersion,
      currentValidationVersion: row.currentValidationVersion,
      ...stateMachineFacts,
    },
    funds: authority('funds'),
    signingPolicy: authority('signingPolicy'),
    approvalSteps: { stepCount: approval.stepCount, steps: approval.steps, active: approval.active },
    signingCapability: authority('signingCapability'),
    segregation: authority('segregation'),
    orderPreview: {
      proposedOrderReference: row.preview?.proposedOrderReference,
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
      orderDataStatus: eligibility.orderDataStatus,
      validationStatus: eligibility.validationStatus,
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
      serverRevalidationRequired: eligibility.serverRevalidationRequired,
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
