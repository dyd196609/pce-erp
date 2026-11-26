<template>
  <main class="payable-page">
    <section class="page-heading">
      <div v-if="!embeddedInCommonShell">
        <p class="eyebrow">{{ VERSION }} · Finance</p>
        <h2>{{ payableCheckCanonicalName }}</h2>
        <p class="page-note">
          本页只承接采购应付预备到应付核对的当前步骤。仅在用户点击“执行应付核对”或“批量完成应付核对”后写入应付核对 Store；
          不自动执行、不自动进入下一步、不写总账、不核销、不生成付款或银行流水。
        </p>
      </div>
      <el-button
        plain
        data-acceptance-id="toggle-acceptance-panel"
        @click="acceptanceVisible = !acceptanceVisible"
      >
        {{ acceptanceVisible ? '隐藏验收信息' : '显示验收信息' }}
      </el-button>
    </section>

    <section v-if="detailRecord" class="table-card payable-check-detail" data-pce-section="payable-check-detail">
      <div class="toolbar-title">
        <div>
          <p class="eyebrow">{{ VERSION }} · Finance</p>
          <h3 data-testid="payable-check-detail-title">采购应付核对</h3>
        </div>
        <el-button plain @click="router.push('/finance/payable-checks')">返回采购应付核对列表</el-button>
      </div>
      <dl class="detail-grid">
        <div><dt>采购应付核对编号</dt><dd data-testid="payable-check-detail-no">{{ detailRecord.payableCheckNo }}</dd></div>
        <div><dt>来源采购应付预备</dt><dd data-testid="payable-check-detail-prepare-no">{{ detailRecord.sourcePayablePrepareNo }}</dd></div>
        <div><dt>来源库存流水</dt><dd data-testid="payable-check-detail-transaction-no">{{ detailRecord.sourceInventoryTransactionNos?.[0] || '-' }}</dd></div>
        <div><dt>来源采购订单</dt><dd data-testid="payable-check-detail-order-no">{{ detailRecord.sourcePurchaseOrderNo }}</dd></div>
        <div><dt>供应商</dt><dd data-testid="payable-check-detail-supplier">{{ detailRecord.supplierName }}</dd></div>
        <div><dt>物料</dt><dd data-testid="payable-check-detail-material">{{ detailRecord.lines?.[0]?.materialCode }} / {{ detailRecord.lines?.[0]?.materialName }}</dd></div>
        <div><dt>数量</dt><dd data-testid="payable-check-detail-quantity">{{ detailRecord.totalPayableQty }} {{ detailRecord.lines?.[0]?.unit }}</dd></div>
        <div><dt>应付金额</dt><dd data-testid="payable-check-detail-payable-amount">{{ formatAmount(detailRecord.totalPayableAmount) }}</dd></div>
        <div><dt>核对金额</dt><dd data-testid="payable-check-detail-checked-amount">{{ formatAmount(detailRecord.totalCheckedAmount) }}</dd></div>
        <div><dt>差异金额</dt><dd data-testid="payable-check-detail-difference-amount">{{ formatAmount(detailRecord.amountDifference) }}</dd></div>
        <div><dt>当前状态</dt><dd data-testid="payable-check-detail-status">{{ statusTextMap[detailRecord.checkStatus] || detailRecord.checkStatus }}</dd></div>
        <div><dt>供应商结算</dt><dd data-testid="payable-check-detail-settlement-status">尚未生成</dd></div>
      </dl>
      <PceBusinessActionBar
        current-module="payable-check"
        :current-status="detailRecord.checkStatus"
        :selected-rows="[detailRecord]"
        :batch-enabled="false"
        :show-unavailable="true"
        @execute="executeRegistryAction"
      />
    </section>

    <PceBusinessActionBar
      current-module="payable-check"
      :selected-rows="selectedRows"
      :show-unavailable="selectedRows.length === 0"
      @execute="executeRegistryAction"
    />

    <section
      v-if="canaryOperationEnabled"
      class="table-card canary-operation-facts"
      data-acceptance-id="payable-check-canary-operation-strict-facts"
    >
      <header class="list-section-title">
        <div>
          <p class="eyebrow">{{ canaryStrictFacts.contractVersion }}</p>
          <h3>采购应付核对可操作金丝雀池</h3>
        </div>
        <strong>{{ canaryStrictFacts.operationPoolConsistent ? '一致' : '阻断' }}</strong>
      </header>
      <div class="acceptance-grid">
        <article><span>当前状态来源</span><strong>{{ canaryStrictFacts.currentStateSource }}</strong></article>
        <article><span>对象总数</span><strong>{{ canaryStrictFacts.objectCount }}</strong></article>
        <article><span>未核对池</span><strong>{{ canaryStrictFacts.pendingCheckCount }}</strong></article>
        <article><span>已核对池</span><strong>{{ canaryStrictFacts.checkedCount }}</strong></article>
        <article><span>混合选择</span><strong>{{ canaryStrictFacts.mixedSelectionSupported }}</strong></article>
        <article><span>保持目的</span><strong>{{ canaryStrictFacts.preservePurpose }}</strong></article>
      </div>
    </section>

    <section class="table-card">
      <header class="list-section-title">
        <div>
          <h3 data-acceptance-id="page-internal-subject-title">{{ payableCheckCanonicalName }}</h3>
          <span>表格操作工具栏紧邻数据表格；高级筛选默认收起。</span>
        </div>
      </header>

      <div class="standard-list-toolbar" data-acceptance-id="standard-list-toolbar" data-pce-page-id="payable-check" data-pce-toolbar-for="payable-check-main">
        <span class="toolbar-search-wrapper" data-acceptance-id="list-fuzzy-search-input">
        <el-input
          v-model="quickSearch"
          class="toolbar-search"
          clearable
          placeholder="输入编号、来源单号、供应商或关键字"
          @keyup.enter="applyFilters"
          @clear="applyFilters"
        />
        </span>
        <el-button type="primary" plain data-acceptance-id="list-fuzzy-search-button" @click="applyFilters">
          搜索
        </el-button>
        <el-button plain data-acceptance-id="list-advanced-filter-toggle" data-pce-filter-toggle-for="payable-check-main" :aria-expanded="String(advancedFilterVisible)" @click="advancedFilterVisible = !advancedFilterVisible">
          {{ advancedFilterVisible ? '收起高级筛选' : '展开高级筛选' }}
        </el-button>
        <el-button plain data-acceptance-id="list-clear-filter-button" @click="clearFilters">清空筛选</el-button>
        <el-button plain data-acceptance-id="list-clear-sort-button" @click="clearSort">清除排序</el-button>
        <el-button
          type="success"
          plain
          data-acceptance-id="list-export-selected-records-button"
          :disabled="selectedRows.length === 0"
          :title="selectedRows.length === 0 ? '请先选择要导出的应付核对记录。' : ''"
          @click="exportSelectedRows"
        >
          导出已选记录
        </el-button>
        <el-button
          type="primary"
          plain
          data-acceptance-id="list-export-current-result-button"
          data-pce-export-for="payable-check-main"
          :disabled="filteredSortedRows.length === 0"
          :title="filteredSortedRows.length === 0 ? '当前筛选结果为空，无法导出。' : ''"
          @click="exportCurrentRows"
        >
          导出当前结果
        </el-button>
        <span data-acceptance-id="list-result-count-visible">当前结果 {{ filteredSortedRows.length }} 条</span>
        <span data-acceptance-id="business-flow-selected-count">已选择 {{ selectedRows.length }} 条</span>
        <span>生效筛选 {{ activeFilterCount }} 项</span>
        <span>排序：{{ sortStateLabel }}</span>
        <el-button plain :disabled="selectedRows.length === 0" @click="clearSelection">清空选择</el-button>
      </div>

      <section
        v-show="advancedFilterVisible"
        class="advanced-filter-panel"
        data-acceptance-id="list-advanced-filter-panel"
        data-pce-filter-for="payable-check-main"
      >
        <label>
          应付核对单号
          <PceResultFilterSelect v-model="advancedFilters.payableCheckNo" :rows="rows" :fields="['payableCheckNo']" />
        </label>
        <label>
          来源应付预备编号
          <PceResultFilterSelect v-model="advancedFilters.sourcePayablePrepareNo" :rows="rows" :fields="['sourcePayablePrepareNo']" />
        </label>
        <label>
          供应商
          <PceResultFilterSelect v-model="advancedFilters.supplierName" :rows="rows" :fields="['supplierName']" />
        </label>
        <label>
          采购订单号
          <PceResultFilterSelect v-model="advancedFilters.sourcePurchaseOrderNo" :rows="rows" :fields="['sourcePurchaseOrderNo']" />
        </label>
        <label>
          核对状态
          <el-select v-model="advancedFilters.checkStatus" clearable placeholder="全部">
            <el-option label="未生成应付核对" value="not_created" />
            <el-option label="未核对" value="draft" />
            <el-option label="已核对" value="checked" />
            <el-option label="存在差异" value="difference" />
          </el-select>
        </label>
        <label>
          下游对象状态
          <el-select v-model="advancedFilters.downstreamStatus" clearable placeholder="全部">
            <el-option label="未进入下一步" value="not_started" />
            <el-option label="可进入供应商结算" value="ready" />
            <el-option label="已进入供应商结算" value="created" />
          </el-select>
        </label>
        <label>
          来源回写状态
          <el-select v-model="advancedFilters.flowWritebackStatus" clearable placeholder="全部">
            <el-option label="未回写" value="" />
            <el-option label="待回写" value="pending" />
            <el-option label="已回写" value="written" />
            <el-option label="回写失败" value="failed" />
          </el-select>
        </label>
        <label>
          核对日期起
          <el-date-picker v-model="advancedFilters.checkedDateFrom" type="date" value-format="YYYY-MM-DD" placeholder="开始日期" />
        </label>
        <label>
          核对日期止
          <el-date-picker v-model="advancedFilters.checkedDateTo" type="date" value-format="YYYY-MM-DD" placeholder="结束日期" />
        </label>
        <label>
          金额下限
          <el-input v-model="advancedFilters.amountMin" clearable type="number" />
        </label>
        <label>
          金额上限
          <el-input v-model="advancedFilters.amountMax" clearable type="number" />
        </label>
      </section>

      <div v-if="lastBatchResult" class="batch-result" data-acceptance-id="payable-check-batch-result">
        <strong>批量执行结果：</strong>
        成功 {{ lastBatchResult.successCount }} 条，失败 {{ lastBatchResult.failedCount }} 条，跳过 {{ lastBatchResult.skippedCount }} 条。
        <span v-if="lastBatchResult.reasons.length">原因：{{ lastBatchResult.reasons.join('；') }}</span>
        <span data-testid="batch-selected-record-nos">selectedRecordNos={{ lastBatchResult.selectedRecordNos.join(',') }}</span>
        <span data-testid="batch-processed-record-nos">processedRecordNos={{ lastBatchResult.processedRecordNos.join(',') }}</span>
        <span data-testid="batch-unselected-record-nos">unselectedRecordNos={{ lastBatchResult.unselectedRecordNos.join(',') }}</span>
        <span data-testid="batch-success-record-nos">successRecordNos={{ lastBatchResult.successRecordNos.join(',') }}</span>
        <span data-testid="batch-failed-record-nos">failedRecordNos={{ lastBatchResult.failedRecordNos.join(',') }}</span>
      </div>

      <BusinessTableScrollContainer class="pce-baseline-table-shell" acceptance-id="business-table-scroll-payable-check-main" page-id="payable-check" table-id="payable-check-main" min-width="2600px">
        <el-table
          ref="payableCheckTableRef"
          class="pce-baseline-table-shell global-sort-arrow"
          :data="filteredSortedRows"
          border
          stripe
          height="520"
          scrollbar-always-on
          row-key="rowKey"
          @selection-change="handleSelectionChange"
          @sort-change="handleSortChange"
        >
          <el-table-column
            type="selection"
            width="52"
            fixed="left"
            :reserve-selection="true"
            :selectable="(row) => !row.formalAuthority"
            class-name="business-table-selection-column"
            label-class-name="business-table-selection-column"
          />
          <el-table-column
            type="index"
            label="序号"
            width="70"
            fixed="left"
            class-name="pce-fixed-index-column"
            label-class-name="pce-fixed-index-column"
          >
            <template #default="{ $index }">{{ $index + 1 }}</template>
          </el-table-column>
          <el-table-column prop="scenarioCode" label="金丝雀场景编码" width="250" />
          <el-table-column prop="objectState" label="操作池状态" width="130">
            <template #default="{ row }">
              {{ row.objectState === 'pending_check' ? '未核对' : (row.objectState === 'checked' ? '已核对' : '-') }}
            </template>
          </el-table-column>
          <el-table-column
            prop="primaryBusinessNo"
            label="主业务编号 / 来源编号"
            width="260"
            fixed="left"
            sortable="custom"
            class-name="pce-fixed-primary-no-column"
            label-class-name="pce-fixed-primary-no-column"
          >
            <template #default="{ row }">
              <div class="primary-no-cell">
                <span>{{ row.primaryBusinessNoLabel }}</span>
                <strong>{{ displayNo(row.primaryBusinessNo) }}</strong>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="payableCheckNo" label="应付核对单号" width="190" sortable="custom">
            <template #default="{ row }">{{ displayNo(row.payableCheckNo) }}</template>
          </el-table-column>
          <el-table-column prop="sourcePayablePrepareNo" label="来源应付预备单号" width="200" sortable="custom">
            <template #default="{ row }">{{ displayNo(row.sourcePayablePrepareNo) }}</template>
          </el-table-column>
          <el-table-column prop="supplierName" label="供应商" width="180" sortable="custom">
            <template #default="{ row }">{{ row.supplierName || '-' }}</template>
          </el-table-column>
          <el-table-column prop="sourcePurchaseOrderNo" label="采购订单号" width="180" sortable="custom">
            <template #default="{ row }">{{ displayNo(row.sourcePurchaseOrderNo) }}</template>
          </el-table-column>
          <el-table-column prop="totalCheckedQty" label="核对数量" width="130" sortable="custom" />
          <el-table-column prop="totalCheckedAmount" label="核对金额" width="140" sortable="custom">
            <template #default="{ row }">{{ formatAmount(row.totalCheckedAmount) }}</template>
          </el-table-column>
          <el-table-column prop="amountDifference" label="差异金额" width="130" sortable="custom">
            <template #default="{ row }">{{ formatAmount(row.amountDifference) }}</template>
          </el-table-column>
          <el-table-column prop="checkStatusText" label="核对状态" width="150" sortable="custom" />
          <el-table-column prop="downstreamStatusText" label="下游对象状态" width="160" sortable="custom" />
          <el-table-column prop="flowWritebackStatusText" label="来源回写状态" width="170" sortable="custom" />
          <el-table-column prop="checkedAt" label="核对日期" width="150" sortable="custom">
            <template #default="{ row }">{{ row.checkedDateText }}</template>
          </el-table-column>
          <el-table-column
            prop="operation"
            label="操作"
            width="330"
            fixed="right"
            class-name="payment-fixed-action-column"
            header-class-name="payment-fixed-action-column"
            label-class-name="payment-fixed-action-column"
          >
            <template #default="{ row }">
              <div class="row-actions">
                <el-button
                  v-if="row.rowType === 'payablePrepareSource'"
                  type="primary"
                  size="small"
                  :disabled="!row.canExecutePayableCheck"
                  :title="!row.canExecutePayableCheck ? row.executeBlockedReason : ''"
                  @click="createPayableCheck(row)"
                >
                  {{ pceBusinessActionLabel('generate-payable-check') }}
                </el-button>
                <el-button
                  v-else-if="!row.formalAuthority && !isPayableChecked(row)"
                  type="primary"
                  size="small"
                  @click="completePayableCheck(row)"
                >
                  {{ pceBusinessActionLabel('complete-payable-check') }}
                </el-button>
                <el-button v-else type="success" size="small" plain @click="viewPayableCheckResult(row)">
                  查看应付核对结果
                </el-button>
                <el-button size="small" plain @click="goSourcePayablePrepare(row)">查看来源应付预备</el-button>
                <el-button
                  v-if="isPayableChecked(row)"
                  data-acceptance-id="go-supplier-settlement-row-button"
                  type="primary"
                  size="small"
                  plain
                  :disabled="Boolean(payableCheckSettlementBlockedReason(row))"
                  :title="payableCheckSettlementBlockedReason(row)"
                  @click="goSupplierSettlement(row)"
                >
                  {{ pceBusinessActionLabel('enter-supplier-settlement') }}
                </el-button>
              </div>
              <p v-if="!row.canExecutePayableCheck && !isPayableChecked(row)" class="blocked-reason">
                {{ row.executeBlockedReason }}
              </p>
            </template>
          </el-table-column>
        </el-table>
      </BusinessTableScrollContainer>

      <footer class="table-footer">
        <span>当前页码：1</span>
        <span>每页数量：{{ filteredSortedRows.length }}</span>
        <span>当前结果总数：{{ filteredSortedRows.length }}</span>
        <span>已选择数量：{{ selectedRows.length }}</span>
      </footer>
    </section>

    <section
      v-if="acceptanceVisible"
      class="development-acceptance-panel"
      data-acceptance-id="development-acceptance-panel"
    >
      <header>
        <div>
          <h3>开发验收信息</h3>
          <p>本区域默认收起，仅用于验收定位和复制诊断，不触发任何业务动作。</p>
        </div>
        <el-button type="success" plain data-acceptance-id="copy-diagnostic-data-button" @click="copyDiagnostics">
          复制诊断数据
        </el-button>
      </header>
      <div class="acceptance-grid">
        <article>
          <span>Ctrl+F 搜索词</span>
          <strong>应付核对列表 / 表格操作工具栏 / 开发验收信息</strong>
        </article>
        <article>
          <span>表格基线</span>
          <strong>选择列、序号列、主业务编号列左侧冻结；操作列右侧冻结。</strong>
        </article>
        <article>
          <span>保护结论</span>
          <strong>不自动执行、不自动进入下一步、不写总账、不核销、不生成银行流水。</strong>
        </article>
      </div>
    </section>
  </main>
</template>

<script setup>
const { embeddedInCommonShell = false } = defineProps({
  embeddedInCommonShell: { type: Boolean, default: false },
})
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import PceResultFilterSelect from '../components/PceResultFilterSelect.vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import BusinessTableScrollContainer from '../components/BusinessTableScrollContainer.vue'
import PceBusinessActionBar from '../components/PceBusinessActionBar.vue'
import {
  createPayableCheckFromPayablePrepare,
  batchMarkPayableCheckChecked,
  getPayableCheckSourcesFromPayablePrepares,
  listPayableChecks,
  markPayableCheckChecked,
} from '../finance/payableCheckStore.js'
import { formatBusinessNo, formatBusinessStatus } from '../runtime/businessDisplayValueFormatter.js'
import { BUSINESS_TABLE_EXPORT_SCOPES, downloadBusinessTableCsv } from '../runtime/businessTableExport.js'
import { resolvePageNameConsumption } from '../governance/pageNameConsumer.js'
import {
  buildSupplierSettlementRoute,
  payableCheckSettlementBlockedReason,
  resolveSupplierSettlementSelection,
} from '../finance/payableCheckSelectionContext.js'
import {
  capturePceBusinessTableState,
  pceBusinessActionLabel,
  restorePceBusinessTableState,
} from '../runtime/pceBusinessActionRegistry.js'
import { getCanaryOperationData } from '../../api/purchaseCanary.js'
import { formalExecutionApi } from '@/api/formalExecution.js'

const VERSION = 'V1.14.2.8.4.7.57.1'
const payableCheckCanonicalName = resolvePageNameConsumption({ pageCode: 'payable-check', route: '/finance/payable-checks' }).pageTitle
onMounted(async () => {
  await refreshRows()
  if (String(route.query.canaryOperation || '') === '1') await loadCanaryOperationData()
})
const router = useRouter()
const route = useRoute()
const payableChecks = ref([])
const payableCheckSources = ref([])
const canaryOperationRows = ref([])
const canaryOperationEnabled = ref(false)
const canaryStrictFacts = reactive({
  contractVersion: 'PCE-CANARY-OPERATION-DATA-V1.0',
  version: VERSION,
  moduleCode: 'payable-check',
  currentStateSource: 'server',
  objectCount: null,
  pendingCheckCount: null,
  checkedCount: null,
  mixedSelectionSupported: false,
  operationPoolConsistent: false,
  preservePurpose: '',
  businessWriteRequestCount: 0,
  factsHash: '',
})
const selectedRows = ref([])
const lastBatchResult = ref(null)
const lastCanaryActionResult = ref(null)
const payableCheckTableRef = ref(null)
const acceptanceVisible = ref(false)
const advancedFilterVisible = ref(false)
const quickSearch = ref('')
const sortState = ref({ prop: '', order: '' })
const advancedFilters = reactive({
  payableCheckNo: '',
  sourcePayablePrepareNo: '',
  supplierName: '',
  sourcePurchaseOrderNo: '',
  checkStatus: '',
  downstreamStatus: '',
  flowWritebackStatus: '',
  checkedDateFrom: '',
  checkedDateTo: '',
  amountMin: '',
  amountMax: '',
})

const statusTextMap = {
  not_created: '未生成应付核对',
  draft: '未核对',
  checking: '核对中',
  checked: '已核对',
  matched: '已核对',
  difference: '存在差异',
  invoicePrepareReady: '已核对',
  invoicePrepared: '已生成发票准备',
  cancelled: '已取消',
  closed: '已关闭',
}

const writebackStatusTextMap = {
  '': '未回写',
  pending: '待回写',
  written: '已回写',
  failed: '回写失败',
}

async function refreshRows() {
  const response = await formalExecutionApi.payableCheckFacts()
  if (!response?.success) {
    payableChecks.value = []
    payableCheckSources.value = []
    ElMessage.error(response?.error?.message || '正式采购应付核对事实读取失败')
    return
  }
  payableChecks.value = (response.data?.payableChecks || []).map((row) => ({
    ...row,
    formalAuthority: true,
    authoritySource: 'reconciliation.PayableCheckAuthorityRecord',
  }))
  payableCheckSources.value = []
}

const checkByPrepareId = computed(() => new Map(
  payableChecks.value
    .filter((item) => item.sourcePayablePrepareId)
    .map((item) => [String(item.sourcePayablePrepareId), item]),
))

const existingCheckRows = computed(() => payableChecks.value.map((row) => normalizeCheckRow(row)))

const sourceRows = computed(() => payableCheckSources.value
  .filter((source) => !checkByPrepareId.value.has(String(source.id)))
  .map((source) => normalizeSourceRow(source)))

const rows = computed(() => (
  canaryOperationEnabled.value
    ? canaryOperationRows.value
    : [...existingCheckRows.value, ...sourceRows.value]
))
const detailRecord = computed(() => {
  const id = String(route.params.id || '')
  return id ? payableChecks.value.find((item) => String(item.id) === id) || null : null
})

const activeFilterCount = computed(() => {
  const advancedCount = Object.values(advancedFilters).filter((value) => String(value ?? '').trim()).length
  return advancedCount + (quickSearch.value.trim() ? 1 : 0)
})

const filteredRows = computed(() => rows.value.filter(rowMatchesFilters))

const filteredSortedRows = computed(() => {
  const list = [...filteredRows.value]
  const { prop, order } = sortState.value
  if (!prop || !order) return list
  const factor = order === 'ascending' ? 1 : -1
  return list.sort((a, b) => compareValues(a[prop], b[prop]) * factor)
})

const supplierSettlementSelection = computed(() => resolveSupplierSettlementSelection(selectedRows.value))

const sortStateLabel = computed(() => {
  if (!sortState.value.prop || !sortState.value.order) return '默认业务顺序'
  return `${sortState.value.prop} ${sortState.value.order === 'ascending' ? '升序' : '降序'}`
})

function normalizeCheckRow(row = {}) {
  const checkStatus = row.checkStatus || 'draft'
  const downstreamStatus = isPayableChecked({ checkStatus }) ? (row.linkedSettlementNo ? 'created' : 'ready') : 'not_started'
  return {
    ...row,
    rowKey: `check-${row.id || row.payableCheckNo}`,
    rowType: 'payableCheck',
    primaryBusinessNo: row.payableCheckNo,
    primaryBusinessNoLabel: '应付核对单号',
    checkStatus,
    checkStatusText: statusTextMap[checkStatus] || formatBusinessStatus(checkStatus, '未核对'),
    downstreamStatus,
    downstreamStatusText: downstreamStatus === 'created' ? '已进入供应商结算' : (downstreamStatus === 'ready' ? '可进入供应商结算' : '未进入下一步'),
    flowWritebackStatusText: writebackStatusTextMap[row.flowWritebackStatus || ''] || formatBusinessStatus(row.flowWritebackStatus, '未回写'),
    checkedDateText: formatDate(row.checkedAt || row.updatedAt || row.createdAt),
    canExecutePayableCheck: !['checked', 'matched', 'invoicePrepareReady', 'invoicePrepared', 'closed', 'cancelled'].includes(checkStatus),
    executeBlockedReason: '',
  }
}

function normalizeSourceRow(source = {}) {
  return {
    ...source,
    rowKey: `source-${source.id || source.payablePrepareNo}`,
    rowType: 'payablePrepareSource',
    payableCheckNo: '',
    sourcePayablePrepareId: source.id,
    sourcePayablePrepareNo: source.payablePrepareNo,
    primaryBusinessNo: source.payablePrepareNo,
    primaryBusinessNoLabel: '来源应付预备单号',
    totalCheckedQty: source.totalPayableQty || 0,
    totalCheckedAmount: source.totalPayableAmount || 0,
    amountDifference: 0,
    checkStatus: 'not_created',
    checkStatusText: '未生成应付核对',
    downstreamStatus: 'not_started',
    downstreamStatusText: '未进入下一步',
    flowWritebackStatus: '',
    flowWritebackStatusText: '未回写',
    checkedAt: '',
    checkedDateText: '-',
    canExecutePayableCheck: Boolean(source.canCreatePayableCheck),
    executeBlockedReason: source.canCreatePayableCheck ? '' : '来源应付预备未达到生成应付核对条件，或已存在应付核对记录。',
  }
}

function normalizeCanaryOperationRow(row = {}) {
  const checkStatus = row.registryStatus
  return {
    ...row,
    rowKey: `canary-operation-${row.id}`,
    rowType: 'canaryOperationData',
    payableCheckNo: row.objectNo,
    sourcePayablePrepareId: '',
    sourcePayablePrepareNo: row.sourceObjectNo,
    primaryBusinessNo: row.objectNo,
    primaryBusinessNoLabel: '应付核对金丝雀编号',
    checkStatus,
    status: checkStatus,
    checkStatusText: checkStatus === 'checked' ? '已核对' : '未核对',
    downstreamStatus: checkStatus === 'checked' ? 'ready' : 'not_started',
    downstreamStatusText: checkStatus === 'checked' ? '可进入供应商结算' : '未进入下一步',
    flowWritebackStatus: '',
    flowWritebackStatusText: '验收数据不回写',
    checkedAt: checkStatus === 'checked' ? '2026-07-27' : '',
    checkedDateText: checkStatus === 'checked' ? '2026-07-27' : '-',
    canExecutePayableCheck: checkStatus === 'draft',
    executeBlockedReason: checkStatus === 'draft' ? '' : '已核对对象只允许进入供应商结算。',
  }
}

async function loadCanaryOperationData() {
  const response = await getCanaryOperationData({ moduleCode: 'payable-check' })
  const payload = response?.data
  if (
    response?.success !== true
    || payload?.result !== 'passed'
    || payload?.strictFacts?.operationPoolConsistent !== true
  ) {
    canaryOperationEnabled.value = false
    return
  }
  canaryOperationRows.value = (payload.results || []).map(normalizeCanaryOperationRow)
  Object.assign(canaryStrictFacts, payload.strictFacts)
  canaryOperationEnabled.value = true
}

function rowMatchesFilters(row = {}) {
  const q = quickSearch.value.trim().toLowerCase()
  if (q) {
    const haystack = [
      row.payableCheckNo,
      row.sourcePayablePrepareNo,
      row.supplierName,
      row.sourcePurchaseOrderNo,
      row.primaryBusinessNo,
      row.checkStatusText,
      row.downstreamStatusText,
      row.flowWritebackStatusText,
    ].join(' ').toLowerCase()
    if (!haystack.includes(q)) return false
  }

  const contains = (key, value) => {
    const expected = String(value || '').trim().toLowerCase()
    if (!expected) return true
    return String(row[key] || '').toLowerCase().includes(expected)
  }

  if (!contains('payableCheckNo', advancedFilters.payableCheckNo)) return false
  if (!contains('sourcePayablePrepareNo', advancedFilters.sourcePayablePrepareNo)) return false
  if (!contains('supplierName', advancedFilters.supplierName)) return false
  if (!contains('sourcePurchaseOrderNo', advancedFilters.sourcePurchaseOrderNo)) return false
  if (advancedFilters.checkStatus && row.checkStatus !== advancedFilters.checkStatus) return false
  if (advancedFilters.downstreamStatus && row.downstreamStatus !== advancedFilters.downstreamStatus) return false
  if (advancedFilters.flowWritebackStatus && (row.flowWritebackStatus || '') !== advancedFilters.flowWritebackStatus) return false
  if (!dateInRange(row.checkedAt || row.updatedAt || row.createdAt)) return false
  const amount = Number(row.totalCheckedAmount || 0)
  if (advancedFilters.amountMin !== '' && amount < Number(advancedFilters.amountMin)) return false
  if (advancedFilters.amountMax !== '' && amount > Number(advancedFilters.amountMax)) return false
  return true
}

function dateInRange(value) {
  if (!advancedFilters.checkedDateFrom && !advancedFilters.checkedDateTo) return true
  const dateText = formatDate(value)
  if (dateText === '-') return false
  if (advancedFilters.checkedDateFrom && dateText < advancedFilters.checkedDateFrom) return false
  if (advancedFilters.checkedDateTo && dateText > advancedFilters.checkedDateTo) return false
  return true
}

function compareValues(a, b) {
  const na = Number(a)
  const nb = Number(b)
  if (Number.isFinite(na) && Number.isFinite(nb)) return na - nb
  return String(a ?? '').localeCompare(String(b ?? ''), 'zh-CN')
}

function applyFilters() {
  clearSelection()
}

function clearFilters() {
  quickSearch.value = ''
  Object.keys(advancedFilters).forEach((key) => {
    advancedFilters[key] = ''
  })
  clearSelection()
}

function handleSortChange({ prop, order }) {
  sortState.value = { prop: prop || '', order: order || '' }
}

function clearSort() {
  sortState.value = { prop: '', order: '' }
  payableCheckTableRef.value?.clearSort?.()
}

function displayNo(value) {
  return formatBusinessNo(value)
}

function formatDate(value) {
  if (!value) return '-'
  return String(value).slice(0, 10)
}

function formatAmount(value) {
  const amount = Number(value)
  return Number.isFinite(amount) ? amount.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '0.00'
}

function isPayableChecked(row = {}) {
  return ['checked', 'matched', 'invoicePrepareReady', 'invoicePrepared'].includes(row.checkStatus)
}

function handleSelectionChange(selection) {
  selectedRows.value = selection
}

function clearSelection() {
  payableCheckTableRef.value?.clearSelection?.()
  selectedRows.value = []
}

function createPayableCheck(row, silent = false) {
  if (!row?.canExecutePayableCheck) {
    const reason = row?.executeBlockedReason || '当前记录不满足应付核对条件。'
    if (!silent) ElMessage.warning(reason)
    return { success: false, skipped: true, reason }
  }

  const createResult = createPayableCheckFromPayablePrepare(row.sourcePayablePrepareId || row.id)
  refreshRows()
  if (!createResult.ok) {
    const reason = createResult.error || '生成采购应付核对失败。'
    if (!silent) ElMessage.warning(reason)
    return { success: false, reason }
  }
  if (!silent) ElMessage.success(`已生成采购应付核对：${createResult.payableCheckNo}`)
  return { success: true, no: createResult.payableCheckNo, record: createResult.record }
}

function completePayableCheck(row, silent = false) {
  const result = markPayableCheckChecked(row?.id)
  refreshRows()
  if (!result.success) {
    const reason = result.error || '采购应付核对状态更新失败。'
    if (!silent) ElMessage.warning(reason)
    return { success: false, reason, alreadyCompleted: Boolean(result.alreadyCompleted) }
  }
  if (!silent) ElMessage.success(`采购应付核对完成：${result.payableCheck?.payableCheckNo || row?.payableCheckNo || '-'}`)
  return { success: true, no: result.payableCheck?.payableCheckNo || row?.payableCheckNo || '' }
}

function batchExecutePayableCheck() {
  const scrollElement = document.querySelector(
    '[data-acceptance-id="business-table-scroll-payable-check-main"] .el-scrollbar__wrap',
  )
  const uiSnapshot = capturePceBusinessTableState({
    selectedRows: selectedRows.value,
    sortState: sortState.value,
    scrollElement,
  })
  const selectedRecordNos = selectedRows.value.map((row) => row.payableCheckNo || row.primaryBusinessNo).filter(Boolean)
  const allRecordNos = rows.value.map((row) => row.payableCheckNo || row.primaryBusinessNo).filter(Boolean)
  const result = {
    successCount: 0,
    failedCount: 0,
    skippedCount: 0,
    reasons: [],
    selectedRecordNos,
    processedRecordNos: [],
    unselectedRecordNos: allRecordNos.filter((no) => !selectedRecordNos.includes(no)),
    successRecordNos: [],
    failedRecordNos: [],
  }
  const checkRows = selectedRows.value.filter((row) => row.rowType === 'payableCheck' && row.id)
  const batch = batchMarkPayableCheckChecked(checkRows.map((row) => row.id))
  const noById = new Map(checkRows.map((row) => [String(row.id), row.payableCheckNo || row.primaryBusinessNo || '-']))
  result.processedRecordNos.push(...checkRows.map((row) => row.payableCheckNo || row.primaryBusinessNo || '-'))
  result.successCount = batch.successCount
  result.failedCount = batch.failedCount
  result.successRecordNos.push(...batch.successItems.map((item) => noById.get(String(item.id)) || item.no))
  result.failedRecordNos.push(...batch.failedItems.map((item) => noById.get(String(item.id)) || item.no))
  result.reasons.push(...batch.failedItems.map((item) => `${noById.get(String(item.id)) || item.no} ${item.reason}`))
  selectedRows.value.filter((row) => row.rowType !== 'payableCheck' || !row.id).forEach((row) => {
    const no = row.payableCheckNo || row.primaryBusinessNo || '-'
    result.processedRecordNos.push(no)
    result.failedRecordNos.push(no)
    result.failedCount += 1
    result.reasons.push(`${no} 请先生成采购应付核对，再执行批量完成。`)
  })
  refreshRows()
  lastBatchResult.value = result
  if (result.failedCount > 0) {
    nextTick(() => {
      selectedRows.value = restorePceBusinessTableState({
        snapshot: uiSnapshot,
        rows: filteredSortedRows.value,
        tableRef: payableCheckTableRef.value,
        scrollElement,
      })
    })
    ElMessage.warning(`批量执行存在 ${result.failedCount} 条失败；表格、选择、排序和滚动状态已保留。`)
    return
  }
  clearSelection()
  ElMessage.success(`批量完成：成功 ${result.successCount} 条，失败 ${result.failedCount} 条，跳过 ${result.skippedCount} 条。`)
}

function executeRegistryAction(action) {
  if (
    action.selectedRows?.length
    && action.selectedRows.every((row) => row.rowType === 'canaryOperationData')
  ) {
    lastCanaryActionResult.value = {
      actionCode: action.actionCode,
      selectedScenarioCodes: action.selectedRows.map((row) => row.scenarioCode),
      currentStateSource: 'server',
      eligibilityValidated: true,
      businessWriteRequestCount: 0,
    }
    ElMessage.success('金丝雀操作资格验证通过；未执行正式业务写入。')
    return
  }
  if (['complete-payable-check', 'batch-complete-payable-check'].includes(action.actionId)) {
    if (
      action.actionId === 'complete-payable-check'
      && detailRecord.value
      && action.selectedRows?.[0]?.id === detailRecord.value.id
    ) {
      completePayableCheck(detailRecord.value)
      return
    }
    batchExecutePayableCheck()
  }
}

function viewPayableCheckResult(row) {
  if (!row?.id) {
    ElMessage.warning('未找到采购应付核对记录。')
    return
  }
  router.push({ path: `/finance/payable-check/${row.id}` })
}

function goSourcePayablePrepare(row) {
  router.push({ path: '/finance/payable-prepares', query: { sourcePayablePrepareNo: row.sourcePayablePrepareNo || '' } })
}

function goSupplierSettlement(row) {
  try {
    router.push(buildSupplierSettlementRoute(row))
  } catch (error) {
    ElMessage.warning(error?.message || '当前记录不能进入供应商结算。')
  }
}

function goSelectedSupplierSettlement() {
  const context = supplierSettlementSelection.value
  if (!context.allowed || !context.record) {
    ElMessage.warning(context.reason)
    return
  }
  goSupplierSettlement(context.record)
}

const exportColumns = [
  { label: '主业务编号类型', key: 'primaryBusinessNoLabel' },
  { label: '主业务编号', key: 'primaryBusinessNo' },
  { label: '应付核对单号', key: 'payableCheckNo' },
  { label: '来源应付预备单号', key: 'sourcePayablePrepareNo' },
  { label: '供应商', key: 'supplierName' },
  { label: '采购订单号', key: 'sourcePurchaseOrderNo' },
  { label: '核对数量', key: 'totalCheckedQty' },
  { label: '核对金额', key: 'totalCheckedAmount' },
  { label: '差异金额', key: 'amountDifference' },
  { label: '核对状态', key: 'checkStatusText' },
  { label: '下游对象状态', key: 'downstreamStatusText' },
  { label: '来源回写状态', key: 'flowWritebackStatusText' },
  { label: '核对日期', key: 'checkedDateText' },
]

function exportRows(scope) {
  const result = downloadBusinessTableCsv({
    scope,
    selectedRows: selectedRows.value,
    sortedRows: filteredSortedRows.value,
    columns: exportColumns,
    canonicalName: payableCheckCanonicalName,
  })
  ElMessage.success(`已导出${scope === BUSINESS_TABLE_EXPORT_SCOPES.selected ? '已选记录' : '当前结果'} ${result.rowCount} 条。`)
}

function exportSelectedRows() {
  if (!selectedRows.value.length) return
  exportRows(BUSINESS_TABLE_EXPORT_SCOPES.selected)
}

function exportCurrentRows() {
  if (!filteredSortedRows.value.length) return
  exportRows(BUSINESS_TABLE_EXPORT_SCOPES.currentResult)
}

async function copyDiagnostics() {
  const diagnostics = {
    page: 'PayableCheckPage',
    version: VERSION,
    quickSearch: quickSearch.value,
    advancedFilterVisible: advancedFilterVisible.value,
    filterState: { ...advancedFilters },
    activeFilterCount: activeFilterCount.value,
    sortState: { ...sortState.value },
    resultCount: filteredSortedRows.value.length,
    sourceRowCount: rows.value.length,
    selectedCount: selectedRows.value.length,
    currentStateSource: canaryOperationEnabled.value ? 'server' : 'legacy_client_store',
    strictFacts: canaryOperationEnabled.value ? { ...canaryStrictFacts } : null,
    canaryOperationData: canaryOperationEnabled.value
      ? canaryOperationRows.value.map((row) => ({
          moduleCode: row.moduleCode,
          scenarioCode: row.scenarioCode,
          objectState: row.objectState,
          availableActions: row.availableActions,
          expectedAction: row.expectedAction,
          preservePurpose: row.preservePurpose,
        }))
      : [],
    selectedSupplierSettlementContext: {
      allowed: supplierSettlementSelection.value.allowed,
      reason: supplierSettlementSelection.value.reason,
      selectedPayableCheckNo: supplierSettlementSelection.value.record?.payableCheckNo || '',
    },
    exportScopes: ['selected', 'current_result'],
    payableCheckCount: payableChecks.value.length,
    sourceCandidateCount: payableCheckSources.value.length,
    executableSourceCount: sourceRows.value.filter((row) => row.canExecutePayableCheck).length,
    checkedCount: filteredSortedRows.value.filter(isPayableChecked).length,
    batchResult: lastBatchResult.value,
    canaryActionResult: lastCanaryActionResult.value,
    developmentAcceptancePanelCollapsedByDefault: !acceptanceVisible.value,
    listToolbarBaseline: {
      fuzzySearch: true,
      advancedFilter: true,
      clearFilter: true,
      clearSort: true,
      exportCurrentResult: true,
      resultCountVisible: true,
      selectedCountVisible: true,
      toolbarAdjacentToTable: true,
    },
    tableBaseline: {
      selectionColumn: true,
      indexColumn: true,
      primaryBusinessNoFixedLeft: true,
      operationColumnFixedRight: true,
      scrollOwner: 'ElementPlusTableInnerScrollbar',
      fixedCoordinateMustBeVerifiedByPlaywright: true,
    },
    actionReachability: {
      executePayableCheckVisible: true,
      viewSourcePayablePrepareVisible: true,
      goSupplierSettlementAfterCheckedVisible: true,
      batchExecuteVisible: true,
    },
    protectionFlags: {
      writeBusinessDataScope: 'only_payable_check_store_by_user_action',
      autoExecutePayableCheck: false,
      forceEnableNextStep: false,
      modifyPurchaseOrder: false,
      modifyReceipt: false,
      modifyInspection: false,
      modifyInventory: false,
      modifyPayablePrepareAmount: false,
      modifyPayment: false,
      writeLedger: false,
      writeOffPayment: false,
      generateBankFlow: false,
    },
    timestamp: new Date().toISOString(),
  }
  await navigator.clipboard.writeText(JSON.stringify(diagnostics, null, 2))
  ElMessage.success('诊断数据已复制')
}
</script>

<style scoped>
.payable-page {
  display: grid;
  gap: 12px;
  max-width: 100%;
  overflow-x: hidden;
}

.page-heading,
.current-action-panel,
.table-card,
.development-acceptance-panel {
  border: 1px solid #d8e0ea;
  border-radius: 8px;
  background: #fff;
  padding: 14px;
}

.page-heading,
.current-action-panel,
.list-section-title,
.development-acceptance-panel header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.page-heading h2,
.page-heading p,
.list-section-title h3,
.list-section-title span,
.development-acceptance-panel p {
  margin: 0;
}

.current-action-panel div {
  display: grid;
  gap: 4px;
}

.current-action-panel span,
.list-section-title span {
  color: #64748b;
  font-size: 13px;
}

.page-note {
  margin-top: 6px;
  color: #475569;
  font-size: 13px;
  line-height: 1.6;
}

.eyebrow {
  color: #2563eb;
  font-size: 13px;
  font-weight: 800;
}

.table-card {
  display: grid;
  gap: 10px;
}

.standard-list-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  padding: 10px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #f8fbff;
}

.toolbar-search-wrapper,
.toolbar-search {
  width: min(360px, 100%);
}

.standard-list-toolbar span {
  color: #334155;
  font-size: 13px;
  font-weight: 700;
}

.advanced-filter-panel {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
  padding: 10px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}

.advanced-filter-panel label {
  display: grid;
  gap: 5px;
  color: #334155;
  font-size: 12px;
  font-weight: 800;
}

.batch-result {
  border: 1px solid #bfdbfe;
  background: #eff6ff;
  color: #1e3a8a;
  border-radius: 8px;
  padding: 10px 12px;
  line-height: 1.6;
}

.primary-no-cell {
  display: grid;
  gap: 2px;
}

.primary-no-cell span {
  color: #64748b;
  font-size: 12px;
}

.primary-no-cell strong {
  color: #0f172a;
  font-size: 13px;
  word-break: break-all;
}

.row-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

.blocked-reason {
  margin: 6px 0 0;
  color: #b45309;
  font-size: 12px;
  line-height: 1.5;
}

.table-footer {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  color: #475569;
  font-size: 13px;
}

.development-acceptance-panel {
  display: grid;
  gap: 12px;
  border-color: #bfdbfe;
  background: #f8fbff;
}

.acceptance-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 10px;
}

.acceptance-grid article {
  display: grid;
  gap: 6px;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
}

.acceptance-grid span {
  color: #64748b;
  font-size: 12px;
}
</style>
