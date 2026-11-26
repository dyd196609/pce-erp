<template>
  <main
    class="bank-send-task-page"
    data-acceptance-id="bank-send-task-business-content"
  >
    <section
      class="business-card"
      data-acceptance-id="bank-send-task-server-facts"
    >
      <Heading
        title="服务端持久事实"
        note="PCE-FACT-LOAD-CONTRACT-V1.0；页面、诊断与 strictFacts 共用同一服务端事实"
      />
      <div class="fact-grid">
        <Fact label="事实加载状态" :value="factLoadStatusLabel" />
        <Fact label="事实来源" value="服务端" />
        <Fact label="API" :value="factLoadFacts?.apiUrl" />
        <Fact label="HTTP状态" :value="factLoadFacts?.httpStatus" />
        <Fact label="租户" :value="factLoadFacts?.tenantId" />
        <Fact label="批次" :value="factLoadFacts?.batchId" />
      </div>
      <p v-if="factLoadFailed" class="fact-load-error">
        银行发送任务事实读取失败
      </p>
      <p class="ctrl-f">Ctrl+F：服务端持久事实</p>
    </section>

    <section class="business-card" data-acceptance-id="bank-send-task-capacity">
      <Heading
        title="银行发送任务容量"
        note="全部来自服务端；任务就绪不代表已发送银行"
      />
      <div class="fact-grid">
        <Fact label="来源银行发送准备数量" :value="capacity.sourceBankSendPreparationCount" />
        <Fact label="任务数量" :value="capacity.bankSendTaskCount" />
        <Fact label="已准备任务数量" :value="capacity.preparedCount" />
        <Fact label="队列中任务数量" :value="capacity.queuedCount" />
        <Fact label="发送前就绪数量" :value="capacity.readyToSendCount" />
        <Fact label="测试任务池充足状态" :value="canaryPoolFacts.poolSufficient" />
      </div>
      <div class="fact-grid canary-pool-facts">
        <Fact label="正常任务池" :value="canaryPoolFacts.normalPoolCount" />
        <Fact label="阻断任务池" :value="canaryPoolFacts.blockedPoolCount" />
        <Fact label="补充任务池" :value="canaryPoolFacts.reservePoolCount" />
        <Fact label="已创建任务数量" :value="canaryPoolFacts.createdTaskCount" />
        <Fact label="已阻断任务数量" :value="canaryPoolFacts.blockedTaskCount" />
        <Fact label="可用任务" :value="canaryPoolFacts.availablePoolCount" />
      </div>
      <p class="ctrl-f">Ctrl+F：银行发送任务容量</p>
    </section>

    <section
      class="business-card"
      data-acceptance-id="bank-send-task-source"
    >
      <Heading
        title="来源银行发送准备"
        note="创建时由服务端重新验证冻结、审批、风险、预览和写入边界"
      />
      <div class="source-select">
        <label for="bank-send-task-source-select">选择来源</label>
        <select
          id="bank-send-task-source-select"
          v-model="selectedSourceId"
          data-acceptance-id="bank-send-task-source-select"
        >
          <option
            v-for="source in sources"
            :key="source.id"
            :value="String(source.id)"
          >
            {{ source.prepareNo }} / {{ display(source.taskEligibility?.eligible) }}
          </option>
        </select>
      </div>
      <div class="fact-grid">
        <Fact label="来源准备编号" :value="currentSource?.prepareNo" />
        <Fact label="来源正式付款单" :value="currentSource?.sourceFormalPaymentOrderNo" />
        <Fact label="来源状态" :value="display(currentSource?.status)" />
        <Fact label="只读预览" :value="display(currentSource?.messagePreview?.status)" />
        <Fact label="任务创建资格" :value="currentSource?.taskEligibility?.eligible" />
        <Fact label="目标是否存在" :value="currentSource?.targetExists" />
      </div>
      <p
        v-if="currentSource?.taskEligibility?.blockingReasons?.length"
        class="blocked-reason"
      >
        阻断原因：{{ currentSource.taskEligibility.blockingReasons.join('；') }}
      </p>
      <p class="ctrl-f">Ctrl+F：来源银行发送准备</p>
    </section>

    <PceBusinessActionBar
      current-module="bank-send-task"
      :current-status="actionStatus"
      :selected-rows="actionRows"
      :eligibility="actionEligibility"
      :include-action-ids="[
        'view-bank-send-task',
        'view-bank-send-task-status',
        'view-bank-message-binding',
        'create-bank-send-task',
      ]"
      @execute="handleBusinessAction"
    />

    <section
      id="bank-send-task-status"
      class="business-card"
      data-acceptance-id="bank-send-task-status"
    >
      <Heading
        title="状态转换历史"
        note="已准备 → 已进入发送队列 → 发送前就绪"
      />
      <div class="fact-grid">
        <Fact label="任务编号" :value="currentTask?.taskNo" />
        <Fact label="业务状态" :value="currentTask?.statusLabel" />
        <Fact label="状态转换数量" :value="currentTask?.statusTransitionCount" />
        <Fact label="状态机一致" :value="currentTask?.stateMachineConsistent" />
        <Fact label="幂等状态" :value="display(currentTask?.idempotencyStatus)" />
        <Fact label="编号状态" :value="display(currentTask?.numberReservationStatus)" />
        <Fact label="事务状态" :value="display(currentTask?.transactionStatus)" />
        <Fact label="服务端事实来源" :value="currentTask?.currentStateSource" />
      </div>
      <ol class="transition-history">
        <li data-state="prepared">已准备</li>
        <li
          v-for="transition in currentTask?.statusTransitionHistory || []"
          :key="transition.id"
          :data-state="transition.targetState"
        >
          → {{ display(transition.targetState) }}
          （{{ transition.operator?.name }} / {{ transition.reason }}）
        </li>
      </ol>
      <p class="ctrl-f">Ctrl+F：状态转换历史</p>
    </section>

    <section
      id="bank-message-binding"
      class="business-card"
      data-acceptance-id="bank-send-task-preview-binding"
    >
      <Heading
        title="报文绑定"
        note="绑定 preview_only 快照，不创建银行报文发送对象"
      />
      <div class="fact-grid">
        <Fact label="预览编号" :value="currentTask?.messagePreview?.previewNo" />
        <Fact label="预览状态" :value="display(currentTask?.messagePreview?.status)" />
        <Fact label="只读" :value="currentTask?.messagePreview?.readonly" />
        <Fact label="已发送" :value="currentTask?.messagePreview?.sent" />
        <Fact label="预览哈希" :value="shortHash(currentTask?.messagePreview?.payloadHash)" />
        <Fact label="任务验证哈希" :value="shortHash(currentTask?.validationHash)" />
      </div>
      <p class="ctrl-f">Ctrl+F：报文绑定</p>
    </section>

    <section class="business-card" data-acceptance-id="bank-send-task-list">
      <Heading
        title="银行发送任务列表"
        note="支持搜索、筛选、排序、多选、冻结列、横向滚动和导出"
      />
      <p v-if="factLoadFailed" class="fact-load-error">
        银行发送任务事实读取失败
      </p>
      <PceEnterpriseListTable
        v-if="!factLoadFailed"
        ref="tableRef"
        :contract="enterpriseListContract"
        page-id="bank-send-task"
        table-id="bank-send-tasks-main"
        :rows="rows"
        :table-rows="filteredRows"
        :filter-schema="filterSchema"
        :filters="filters"
        :quick-search="quickSearch"
        :advanced-visible="advancedVisible"
        :selected-count="selectedRows.length"
        :active-filter-count="activeFilterCount"
        :sort-text="sortText"
        primary-field="taskNo"
        primary-label="任务编号"
        :primary-width="210"
        min-width="1700px"
        :action-width="180"
        @update:quick-search="quickSearch = $event"
        @search="appliedSearch = quickSearch"
        @toggle-advanced="advancedVisible = !advancedVisible"
        @clear-filters="clearFilters"
        @clear-sort="clearSort"
        @export-current="exportCurrent"
        @clear-selection="clearSelection"
        @update-filter="(field, value) => filters[field] = value"
        @selection-change="selectedRows = $event"
        @sort-change="handleSort"
        @current-change="selectTask"
      >
        <template #columns>
          <el-table-column prop="sourcePreparationNo" label="来源准备编号" width="210" />
          <el-table-column prop="sourceFormalPaymentOrderNo" label="正式付款单" width="210" />
          <el-table-column prop="supplierName" label="供应商" width="180" />
          <el-table-column prop="legalEntityId" label="法人" width="150" />
          <el-table-column prop="currency" label="币种" width="90" />
          <el-table-column prop="amount" label="金额" width="120" sortable />
          <el-table-column prop="plannedExecutionDate" label="计划执行日期" width="150" />
          <el-table-column prop="statusLabel" label="业务状态" width="160">
            <template #default="{ row }">
              <PceBusinessStatus
                :status-code="row.statusCode || row.status"
                :status-label="row.statusLabel"
                :source="row.currentStateSource"
              />
            </template>
          </el-table-column>
          <el-table-column prop="currentStateSource" label="状态来源" width="120">
            <template #default="{ row }">{{ display(row.currentStateSource) }}</template>
          </el-table-column>
          <el-table-column label="预览绑定" width="140">
            <template #default="{ row }">{{ display(row.messagePreview?.status) }}</template>
          </el-table-column>
        </template>
        <template #actions="{ row }">
          <el-button
            size="small"
            plain
            data-ui-control="select-bank-send-task-row"
            @click.stop="selectTask(row)"
          >
            选择
          </el-button>
        </template>
      </PceEnterpriseListTable>
      <p class="ctrl-f">Ctrl+F：银行发送任务列表</p>
    </section>

    <section
      class="business-card zero-boundary"
      data-acceptance-id="bank-send-task-zero-boundary"
    >
      <Heading
        title="发送前保护"
        note="本版本仅创建发送前任务，禁止真实发送和付款执行"
      />
      <p><strong>当前阶段：银行发送前准备阶段</strong></p>
      <div class="protection-rules">
        <p>允许：✓ 创建银行发送任务　✓ 状态跟踪　✓ 审计查询</p>
        <p>禁止：× 发送银行　× 执行付款　× 资金扣减　× 生成银行流水　× 生成付款凭证　× 写总账</p>
      </div>
      <div class="fact-grid">
        <Fact label="银行发送" :value="false" />
        <Fact label="付款执行" :value="false" />
        <Fact label="资金扣减" :value="false" />
        <Fact label="银行流水" :value="false" />
      </div>
      <div class="fact-grid">
        <Fact
          v-for="(value, key) in downstreamCounts"
          :key="key"
          :label="downstreamLabel(key)"
          :value="value"
        />
      </div>
      <p>银行报文、付款执行、资金扣减、银行流水、凭证、总账和过账全部为0。</p>
      <p class="ctrl-f">Ctrl+F：发送前保护</p>
    </section>
  </main>
</template>

<script setup>
import {
  computed,
  h,
  inject,
  onBeforeUnmount,
  onMounted,
  reactive,
  ref,
  watch,
} from 'vue'
import { ElMessage } from 'element-plus'
import { bankSendTaskApi } from '@/api/bankSendTask.js'
import PceBusinessStatus from '@/meta/components/PceBusinessStatus.vue'
import PceBusinessActionBar from '@/meta/components/PceBusinessActionBar.vue'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import { PAGE_OBSERVABILITY_ACTIONS_KEY } from '@/meta/runtime/pageObservabilityActions.js'
import {
  createPceEnterpriseListContract,
  usePceEnterpriseListRuntime,
} from '@/meta/runtime/pceEnterpriseListContract.js'
import {
  BANK_SEND_TASK_FILTER_SCHEMA,
  BANK_SEND_TASK_VERSION,
  bankSendTaskDisplayValue,
  createBankSendTaskPageFacts,
} from '@/meta/runtime/bankSendTaskRuntime.js'
import {
  factLoadFailureFromError,
  factLoadPassed,
  factLoadResultCount,
} from '@/meta/runtime/pceFactLoadContract.js'

const VERSION = BANK_SEND_TASK_VERSION
const FACT_LOAD_API_URL = '/api/finance/bank-send-tasks/'
const enterpriseListContract = createPceEnterpriseListContract({
  pageCode: 'bank-send-task',
  pageType: 'list',
  title: '银行发送任务',
  moduleCode: 'FIN_BANK_SEND_TASK',
})
const observability = inject(PAGE_OBSERVABILITY_ACTIONS_KEY, null)
const observabilityProvider = {
  factOwner: 'FIN_BANK_SEND_TASK',
  refresh,
  buildDiagnostics,
}
const rows = ref([])
const sources = ref([])
const currentTask = ref(null)
const selectedSourceId = ref('')
const capacity = reactive({
  sourceBankSendPreparationCount: 0,
  previewReadySourceCount: 0,
  bankSendTaskCount: 0,
  taskCount: 0,
  preparedCount: 0,
  queuedCount: 0,
  readyToSendCount: 0,
  sentCount: 0,
  executionCount: 0,
})
const downstreamCounts = reactive({})
const writeIntentFacts = reactive({})
const bankSendTaskFacts = reactive({})
const canaryPoolFacts = reactive({})
const strictServerFacts = ref({})
const factLoadFacts = ref(null)
const filterSchema = BANK_SEND_TASK_FILTER_SCHEMA
const {
  selectedRows,
  quickSearch,
  appliedSearch,
  advancedVisible,
  filters,
  tableRef,
  activeFilterCount,
  sortText,
  filteredRows,
  clearFilters,
  clearSort,
  clearSelection,
  handleSort,
  exportCurrent,
} = usePceEnterpriseListRuntime({
  rows,
  filterSchema,
  pageCode: 'bank-send-task',
  searchFields: [
    'taskNo',
    'sourcePreparationNo',
    'sourceFormalPaymentOrderNo',
    'supplierName',
  ],
  exportFileName: 'bank-send-tasks.csv',
  exportColumns: [
    { field: 'taskNo', label: '任务编号' },
    { field: 'sourcePreparationNo', label: '来源准备编号' },
    { field: 'sourceFormalPaymentOrderNo', label: '正式付款单' },
    { field: 'supplierName', label: '供应商' },
    { field: 'legalEntityId', label: '法人' },
    { field: 'currency', label: '币种' },
    { field: 'amount', label: '金额' },
    { field: 'plannedExecutionDate', label: '计划执行日期' },
    { field: 'statusLabel', label: '任务状态' },
  ],
})
const factLoadFailed = computed(() => (
  factLoadFacts.value?.factLoadStatus === 'read_failed'
))
const factLoadStatusLabel = computed(() => ({
  success: '加载成功',
  loaded: '加载成功',
  empty_valid: '加载成功',
  read_failed: '读取失败',
}[factLoadFacts.value?.factLoadStatus] || '加载中'))

const currentSource = computed(() => sources.value.find(
  source => String(source.id) === selectedSourceId.value,
) || null)
const actionStatus = computed(() => (
  currentTask.value?.status || currentSource.value?.status || ''
))
const actionRows = computed(() => (
  currentTask.value ? [currentTask.value]
    : currentSource.value ? [currentSource.value] : []
))
const actionEligibility = computed(() => (
  currentTask.value
    ? true
    : currentSource.value?.taskEligibility?.eligible === true
))
const Heading = (_, { attrs }) => h('div', { class: 'section-heading' }, [
  h('div', {}, [h('h2', {}, attrs.title), h('p', {}, attrs.note)]),
])
const Fact = (_, { attrs }) => h('article', { class: 'fact-item' }, [
  h('span', {}, attrs.label),
  h('strong', {}, display(attrs.value)),
])

function display(value) {
  return bankSendTaskDisplayValue(value)
}

function shortHash(value) {
  const text = String(value || '')
  return text ? `${text.slice(0, 12)}…${text.slice(-8)}` : '-'
}

async function refresh() {
  try {
    const envelope = await bankSendTaskApi.list()
    const facts = createBankSendTaskPageFacts(envelope)
    factLoadFacts.value = facts.factLoadFacts
    rows.value = facts.rows
    sources.value = facts.sources
    Object.assign(capacity, facts.capacity)
    Object.assign(downstreamCounts, facts.downstreamCounts)
    Object.assign(writeIntentFacts, facts.writeIntentFacts)
    Object.assign(bankSendTaskFacts, facts.bankSendTaskFacts)
    Object.assign(canaryPoolFacts, facts.canaryPoolFacts)
    strictServerFacts.value = facts.strictServerFacts
    currentTask.value = rows.value[0] || null
    const eligible = sources.value.find(
      source => source.taskEligibility?.eligible && !source.targetExists,
    )
    const linked = currentTask.value
      ? sources.value.find(
          source => source.id === currentTask.value.sourcePreparationId,
        )
      : null
    selectedSourceId.value = String(
      (eligible || linked || sources.value[0])?.id || '',
    )
    publishAcceptance()
  } catch (error) {
    const failed = factLoadFailureFromError(
      error,
      FACT_LOAD_API_URL,
      factLoadFacts.value,
    )
    factLoadFacts.value = failed
    rows.value = []
    sources.value = []
    currentTask.value = null
    selectedSourceId.value = ''
    for (const key of Object.keys(capacity)) capacity[key] = null
    for (const key of Object.keys(canaryPoolFacts)) {
      delete canaryPoolFacts[key]
    }
    strictServerFacts.value = {
      ...failed,
      factLoadFacts: failed,
      currentStateSource: 'server',
      pageCode: 'bank-send-task',
      moduleCode: 'FIN_BANK_SEND_TASK',
      pageFactOwner: 'FIN_BANK_SEND_TASK',
      pageFactOwnerGuard: 'page_fact_owner_unique',
      resultCount: null,
      rows: [],
      sourceObjects: [],
      passed: false,
    }
    publishAcceptance()
    ElMessage.error('银行发送任务事实读取失败')
  }
}

async function handleBusinessAction(action) {
  if (action.actionId === 'view-bank-send-task') {
    document
      .querySelector('[data-acceptance-id="bank-send-task-list"]')
      ?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    return
  }
  if (action.actionId === 'view-bank-send-task-status') {
    document.getElementById('bank-send-task-status')?.scrollIntoView({
      behavior: 'smooth',
      block: 'start',
    })
    return
  }
  if (action.actionId === 'view-bank-message-binding') {
    document.getElementById('bank-message-binding')?.scrollIntoView({
      behavior: 'smooth',
      block: 'start',
    })
    return
  }
  if (action.actionId === 'create-bank-send-task') {
    const source = currentSource.value
    if (!source) {
      ElMessage.warning('请选择银行发送准备来源')
      return
    }
    const envelope = await bankSendTaskApi.createFromPreparation(source.id, {
      idempotencyKey: `V59-CREATE-${source.prepareNo}`,
      expectedSourceVersion: source.version,
      explicitUserAction: true,
    })
    const result = envelope?.data?.result ? envelope.data : envelope
    if (result?.result !== 'passed') {
      ElMessage.error(result?.error?.message || '银行发送任务创建失败')
      return
    }
    ElMessage.success(
      result.classification === 'existing_result'
        ? '已读取现有银行发送任务；未重复创建'
        : '银行发送任务已创建并进入发送前就绪；尚未发送银行',
    )
    await refresh()
  }
}

function selectTask(row) {
  currentTask.value = row || null
}

function downstreamLabel(key) {
  return {
    bankMessages: '银行报文',
    paymentExecutions: '付款执行',
    fundsDebits: '资金扣减',
    bankTransactions: '银行流水',
    paymentVouchers: '付款凭证',
    writeoffs: '核销',
    ledgerEntries: '总账分录',
    postings: '过账',
  }[key] || key
}

function buildDiagnostics() {
  return {
    version: VERSION,
    canonicalName: '银行发送任务',
    moduleCode: 'FIN_BANK_SEND_TASK',
    pageFactOwner: 'FIN_BANK_SEND_TASK',
    pageFactOwnerGuard: 'page_fact_owner_unique',
    sourceDocumentType: 'bankSendPreparation',
    currentStateSource: 'server',
    ...factLoadFacts.value,
    factLoadFacts: factLoadFacts.value,
    factLoadStatusLabel: factLoadStatusLabel.value,
    resultCount: factLoadResultCount(
      factLoadFacts.value,
      bankSendTaskFacts.taskCount,
    ),
    passed: factLoadPassed(
      factLoadFacts.value,
      bankSendTaskFacts.passed === true,
    ),
    currentObject: currentTask.value,
    selectedSource: currentSource.value,
    sourceObjects: strictServerFacts.value.sourceObjects || [],
    status: currentTask.value?.status || '',
    capacity: factLoadFailed.value ? null : { ...capacity },
    downstreamCounts: { ...downstreamCounts },
    writeIntentFacts: { ...writeIntentFacts },
    bankSendTaskFacts: { ...bankSendTaskFacts },
    canaryPoolFacts: { ...canaryPoolFacts },
    strictServerFacts: strictServerFacts.value,
    sendTaskPreparationWriteCount:
      writeIntentFacts.sendTaskPreparationWriteCount,
    bankSendExecutionWriteCount:
      writeIntentFacts.bankSendExecutionWriteCount,
    auditWriteCount: writeIntentFacts.auditWriteCount,
    bankMessageSent: false,
    paymentExecuted: false,
    fundsDebited: false,
    bankTransactionCreated: false,
  }
}

function publishAcceptance() {
  window.__PCE_BUSINESS_PAGE_ACCEPTANCE__ = {
    ...buildDiagnostics(),
    pageAssertions: [
      {
        fullUrl: window.location.href,
        regionTitle: '银行发送任务容量',
        relativePosition: '页面标题下方第一个业务区域',
        fieldName: '正常/阻断/补充/任务/发送前就绪',
        expectedValue: '8/5/20/8/8',
        actualValue:
          `${canaryPoolFacts.normalPoolCount}/`
          + `${canaryPoolFacts.blockedPoolCount}/`
          + `${canaryPoolFacts.reservePoolCount}/`
          + `${capacity.bankSendTaskCount}/`
          + `${capacity.readyToSendCount}`,
        ctrlF: '银行发送任务容量',
        passed:
          canaryPoolFacts.normalPoolCount >= 8
          && canaryPoolFacts.blockedPoolCount >= 5
          && canaryPoolFacts.reservePoolCount >= 20
          && capacity.bankSendTaskCount >= 8
          && capacity.readyToSendCount === capacity.bankSendTaskCount,
      },
      {
        fullUrl: window.location.href,
        regionTitle: '状态转换历史',
        relativePosition: '业务动作栏之后',
        fieldName: '状态编码/业务状态/转换数量/状态机一致',
        expectedValue: 'ready_to_send/发送前就绪/2/是',
        actualValue:
          `${currentTask.value?.statusCode || '-'}/`
          + `${currentTask.value?.statusLabel || '-'}/`
          + `${currentTask.value?.statusTransitionCount ?? 0}/`
          + `${display(currentTask.value?.stateMachineConsistent)}`,
        ctrlF: '状态转换历史',
        passed:
          currentTask.value?.statusCode === 'ready_to_send'
          && currentTask.value?.statusLabel === '发送前就绪'
          && currentTask.value?.statusTransitionCount === 2
          && currentTask.value?.stateMachineConsistent === true,
      },
      {
        fullUrl: window.location.href,
        regionTitle: '发送前保护',
        relativePosition: '页面最底部',
        fieldName: '银行报文/付款执行/资金扣减/银行流水',
        expectedValue: '全部为0',
        actualValue: JSON.stringify(downstreamCounts),
        ctrlF: '发送前保护',
        passed: Object.values(downstreamCounts).every(value => value === 0),
      },
    ],
  }
}

watch(selectedSourceId, () => {
  if (!currentSource.value?.targetExists) currentTask.value = null
})

onMounted(async () => {
  observability?.register(observabilityProvider)
  await refresh()
})
onBeforeUnmount(() => observability?.unregister(observabilityProvider))
</script>

<style scoped>
.bank-send-task-page {
  display: grid;
  gap: 14px;
  min-width: 0;
}

.business-card {
  display: grid;
  gap: 12px;
  min-width: 0;
  padding: 16px;
  border: 1px solid #d8e0ea;
  border-radius: 8px;
  background: #fff;
}

.section-heading h2,
.section-heading p,
.business-card p {
  margin: 0;
}

.section-heading p,
.ctrl-f {
  color: #64748b;
}

.fact-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
}

.fact-item {
  display: grid;
  gap: 6px;
  min-width: 0;
  padding: 10px 12px;
  border-radius: 7px;
  background: #f8fafc;
}

.fact-item span {
  color: #64748b;
  font-size: 13px;
}

.fact-item strong {
  overflow-wrap: anywhere;
}

.source-select {
  display: flex;
  align-items: center;
  gap: 12px;
}

.source-select select {
  min-width: 360px;
  max-width: 100%;
  padding: 8px 10px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
}

.advanced-filter-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 10px;
}

.blocked-reason {
  color: #b91c1c;
}

.fact-load-error {
  color: #b91c1c;
  font-weight: 800;
}

.zero-boundary {
  border-color: #86efac;
  background: #f0fdf4;
}
</style>
