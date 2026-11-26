<template>
  <main
    class="bank-send-preparation-page"
    data-acceptance-id="bank-send-preparation-business-content"
  >
    <section
      class="business-card"
      data-acceptance-id="bank-send-preparation-capacity"
    >
      <Heading
        title="金丝雀容量"
        note="全部读取服务端持久事实；本页不创建银行发送任务"
      />
      <div class="fact-grid">
        <Fact label="来源正式付款单" :value="capacity.sourceFormalPaymentOrderCount" />
        <Fact label="银行发送准备" :value="capacity.bankSendPreparationCount" />
        <Fact label="已准备" :value="capacity.preparedCount" />
        <Fact label="门禁通过" :value="capacity.eligibleCount" />
        <Fact label="仅预览对象" :value="capacity.previewCount" />
        <Fact label="下游已消费" :value="capacity.nextStageConsumedCount" />
      </div>
      <p class="ctrl-f">Ctrl+F：金丝雀容量</p>
    </section>

    <section
      class="business-card"
      data-acceptance-id="bank-send-preparation-source"
    >
      <Heading
        title="来源正式付款单"
        note="来源必须保持审批完成、执行冻结且 freezeHash 一致"
      />
      <div class="fact-grid">
        <Fact label="银行发送准备编号" :value="current?.prepareNo" />
        <Fact
          label="来源正式付款单编号"
          :value="current?.sourceFormalPaymentOrderNo"
        />
        <Fact label="来源状态" value="已冻结待执行" />
        <Fact label="来源版本" :value="current?.sourceFormalPaymentOrderVersion" />
        <Fact label="准备状态" :value="display(current?.status)" />
        <Fact label="服务端事实来源" :value="current?.currentStateSource" />
      </div>
      <p class="ctrl-f">Ctrl+F：来源正式付款单</p>
    </section>

    <PceBusinessActionBar
      current-module="bank-send-preparation"
      :current-status="current?.status || ''"
      :selected-rows="selectedRows"
      :eligibility="current?.gate?.eligible === true"
      :include-action-ids="[
        'view-bank-send-eligibility',
        'view-bank-send-gate',
        'generate-bank-message-preview',
      ]"
      @execute="handleBusinessAction"
    />

    <section
      id="bank-send-eligibility"
      class="business-card"
      data-acceptance-id="bank-send-preparation-eligibility"
    >
      <Heading
        title="银行发送资格"
        note="资格只允许进入预览；不代表已发送"
      />
      <div class="fact-grid">
        <Fact label="资格结论" :value="current?.gate?.eligible ? '允许生成发送预览' : '已阻断'" />
        <Fact label="正式付款单冻结" :value="current?.gate?.sourceStatusPassed" />
        <Fact label="审批通过" :value="current?.gate?.approvalPassed" />
        <Fact label="风险评审通过" :value="current?.gate?.riskReviewPassed" />
        <Fact label="资金可用" :value="current?.gate?.fundsAvailable" />
        <Fact label="职责分离有效" :value="current?.gate?.segregationValid" />
      </div>
      <p class="ctrl-f">Ctrl+F：银行发送资格</p>
    </section>

    <section
      id="bank-send-gate"
      class="business-card"
      data-acceptance-id="bank-send-preparation-gate"
    >
      <Heading
        title="最终门禁"
        note="当前服务端事实任何一项变化都必须阻断预览生成"
      />
      <div class="fact-grid">
        <Fact label="冻结快照哈希一致" :value="current?.gate?.freezeHashPassed" />
        <Fact label="银行接口可用" :value="current?.gate?.bankInterfaceAvailable" />
        <Fact label="签署能力就绪" :value="current?.gate?.signingCapabilityReady" />
        <Fact label="源 freezeHash" :value="shortHash(current?.gate?.sourceFreezeHash)" />
        <Fact label="当前 freezeHash" :value="shortHash(current?.gate?.currentFreezeHash)" />
        <Fact label="门禁哈希" :value="shortHash(current?.gate?.gateHash)" />
      </div>
      <p v-if="current?.gate?.blockingReasons?.length" class="blocked-reason">
        阻断原因：{{ current.gate.blockingReasons.join('；') }}
      </p>
      <p class="ctrl-f">Ctrl+F：最终门禁</p>
    </section>

    <section
      class="business-card"
      data-acceptance-id="bank-send-preparation-interface"
    >
      <Heading
        title="接口能力"
        note="仅返回接口标识和可用性，不返回密码、Token、证书私钥或签署凭据"
      />
      <div class="fact-grid">
        <Fact
          label="银行接口编码"
          :value="current?.bankInterface?.interfaceCode || '服务端受控接口'"
        />
        <Fact
          label="连接状态"
          :value="display(current?.bankInterface?.connectionStatus || 'available')"
        />
        <Fact label="接口可用" :value="current?.gate?.bankInterfaceAvailable" />
        <Fact label="签署能力" :value="current?.gate?.signingCapabilityReady" />
        <Fact label="银行密钥暴露" :value="current?.bankInterface?.secretExposed" />
      </div>
      <p class="ctrl-f">Ctrl+F：接口能力</p>
    </section>

    <section
      class="business-card"
      data-acceptance-id="bank-send-preparation-preview"
    >
      <Heading
        title="报文预览"
        note="BankMessagePreview 永远保持 preview_only，不能进入 sent"
      />
      <div class="fact-grid">
        <Fact label="预览是否存在" :value="current?.messagePreview?.exists" />
        <Fact label="预览编号" :value="current?.messagePreview?.previewNo" />
        <Fact label="预览状态" :value="display(current?.messagePreview?.status)" />
        <Fact label="只读" :value="current?.messagePreview?.readonly" />
        <Fact label="已发送" :value="current?.messagePreview?.sent" />
        <Fact label="付款执行" :value="writeIntentFacts.paymentExecuted" />
        <Fact label="敏感字段暴露" :value="current?.messagePreview?.bankSecretExposed" />
      </div>
      <pre v-if="current?.messagePreview?.exists" class="preview-json">{{
        JSON.stringify(current.messagePreview.payload, null, 2)
      }}</pre>
      <p class="ctrl-f">Ctrl+F：报文预览</p>
    </section>

    <section
      class="business-card"
      data-acceptance-id="bank-send-preparation-list"
    >
      <Heading
        title="银行发送准备列表"
        note="支持搜索、筛选、排序、多选、冻结列、横向滚动和导出当前结果"
      />
      <PceEnterpriseListTable
        ref="tableRef"
        :contract="enterpriseListContract"
        page-id="bank-send-preparation"
        table-id="bank-send-preparations-main"
        :rows="rows"
        :table-rows="filteredRows"
        :filter-schema="filterSchema"
        :filters="filters"
        :quick-search="quickSearch"
        :advanced-visible="advancedVisible"
        :selected-count="selectedRows.length"
        :active-filter-count="activeFilterCount"
        :sort-text="sortText"
        primary-field="prepareNo"
        primary-label="银行发送准备编号"
        :primary-width="210"
        min-width="1850px"
        :action-width="150"
        @update:quick-search="quickSearch = $event"
        @search="applySearch"
        @toggle-advanced="advancedVisible = !advancedVisible"
        @clear-filters="clearFilters"
        @clear-sort="clearSort"
        @export-current="exportCurrent"
        @clear-selection="clearSelection"
        @update-filter="(field, value) => filters[field] = value"
        @selection-change="selectedRows = $event"
        @sort-change="handleSort"
        @current-change="selectCurrent"
      >
        <template #columns>
          <el-table-column prop="sourceFormalPaymentOrderNo" label="来源正式付款单" width="210" />
          <el-table-column prop="supplierName" label="供应商" width="180" />
          <el-table-column prop="legalEntityId" label="法人" width="150" />
          <el-table-column prop="currency" label="币种" width="90" />
          <el-table-column prop="amount" label="金额" width="130" sortable />
          <el-table-column prop="plannedExecutionDate" label="计划执行日期" width="150" />
          <el-table-column prop="status" label="准备状态" width="120">
            <template #default="{ row }">
              <PceBusinessStatus
                :status-code="row.status"
                :status-label="display(row.status)"
                source="server"
              />
            </template>
          </el-table-column>
          <el-table-column label="发送资格" width="120">
            <template #default="{ row }">{{ display(row.gate?.eligible) }}</template>
          </el-table-column>
          <el-table-column label="接口能力" width="130">
            <template #default="{ row }">{{ display(row.gate?.bankInterfaceAvailable) }}</template>
          </el-table-column>
          <el-table-column label="预览状态" width="130">
            <template #default="{ row }">{{ display(row.messagePreview?.status) }}</template>
          </el-table-column>
        </template>
        <template #actions="{ row }">
          <el-button
            size="small"
            plain
            data-action-id="view-bank-send-preparation"
            @click.stop="selectCurrent(row)"
          >
            查看
          </el-button>
        </template>
      </PceEnterpriseListTable>
      <p class="ctrl-f">Ctrl+F：银行发送准备列表</p>
    </section>

    <section
      class="business-card zero-boundary"
      data-acceptance-id="bank-send-preparation-zero-boundary"
    >
      <Heading
        title="下游零对象保护"
        note="发送任务属于受控准备写入；银行发送、付款执行及财务影响对象必须为零"
      />
      <div class="fact-grid">
        <Fact
          v-for="(value, key) in downstreamCounts"
          :key="key"
          :label="downstreamLabel(key)"
          :value="value"
        />
      </div>
      <p>
        允许形成银行发送任务；未发送银行、未执行付款、未扣减资金、未生成银行流水、未生成凭证、未核销、未写总账、未过账。
      </p>
      <p class="ctrl-f">Ctrl+F：下游零对象保护</p>
    </section>
  </main>
</template>

<script setup>
import {
  h,
  inject,
  onBeforeUnmount,
  onMounted,
  reactive,
  ref,
} from 'vue'
import { ElMessage } from 'element-plus'
import { bankSendPreparationApi } from '@/api/bankSendPreparation.js'
import PceBusinessStatus from '@/meta/components/PceBusinessStatus.vue'
import PceBusinessActionBar from '@/meta/components/PceBusinessActionBar.vue'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import { PAGE_OBSERVABILITY_ACTIONS_KEY } from '@/meta/runtime/pageObservabilityActions.js'
import {
  createPceEnterpriseListContract,
  usePceEnterpriseListRuntime,
} from '@/meta/runtime/pceEnterpriseListContract.js'
import {
  BANK_SEND_PREPARATION_FILTER_SCHEMA,
  BANK_SEND_PREPARATION_VERSION,
  bankSendPreparationDisplayValue,
  createBankSendPreparationPageFacts,
} from '@/meta/runtime/bankSendPreparationRuntime.js'
import {
  factLoadFailureFromError,
  factLoadPassed,
  factLoadResultCount,
  readPceFactLoadEnvelope,
} from '@/meta/runtime/pceFactLoadContract.js'

const VERSION = BANK_SEND_PREPARATION_VERSION
const enterpriseListContract = createPceEnterpriseListContract({
  pageCode: 'bank-send-preparation',
  pageType: 'list',
  title: '银行发送准备',
  moduleCode: 'FIN_BANK_SEND_PREPARATION',
})
const FACT_LOAD_API_URL = '/api/finance/bank-send-prepares/'
const observability = inject(PAGE_OBSERVABILITY_ACTIONS_KEY, null)
const observabilityProvider = { refresh, buildDiagnostics }
const loading = ref(false)
const rows = ref([])
const capacity = reactive({
  sourceFormalPaymentOrderCount: 0,
  bankSendPreparationCount: 0,
  preparedCount: 0,
  eligibleCount: 0,
  previewCount: 0,
  nextStageConsumedCount: 0,
})
const downstreamCounts = reactive({})
const current = ref(null)
const filterSchema = BANK_SEND_PREPARATION_FILTER_SCHEMA
const strictServerFacts = ref({})
const factLoadFacts = ref(null)
const writeIntentFacts = reactive({})
const bankSendPreparationFacts = reactive({})
const {
  selectedRows,
  quickSearch,
  advancedVisible,
  filters,
  tableRef,
  activeFilterCount,
  sortText,
  filteredRows,
  applySearch,
  clearFilters,
  clearSort,
  clearSelection,
  handleSort,
  exportCurrent,
} = usePceEnterpriseListRuntime({
  rows,
  filterSchema,
  pageCode: 'bank-send-preparation',
  searchFields: [
    'prepareNo',
    'sourceFormalPaymentOrderNo',
    'supplierName',
    'legalEntityId',
  ],
  filterValueResolver(row, field) {
    return field.field === 'previewStatus'
      ? row.messagePreview?.status || 'not_generated'
      : row[field.sourceKey || field.field]
  },
  exportFileName: 'bank-send-preparations.csv',
  exportColumns: [
    { field: 'prepareNo', label: '银行发送准备编号' },
    { field: 'sourceFormalPaymentOrderNo', label: '来源正式付款单编号' },
    { field: 'supplierName', label: '供应商' },
    { field: 'legalEntityId', label: '法人' },
    { field: 'currency', label: '币种' },
    { field: 'amount', label: '金额' },
    { label: '状态', value: row => display(row.status) },
    { label: '资格', value: row => display(row.gate?.eligible) },
    { label: '预览状态', value: row => display(row.messagePreview?.status) },
  ],
})

const Heading = (_, { attrs }) => h('div', { class: 'section-heading' }, [
  h('div', {}, [
    h('h2', {}, attrs.title),
    h('p', {}, attrs.note),
  ]),
])
const Fact = (_, { attrs }) => h('article', { class: 'fact-item' }, [
  h('span', {}, attrs.label),
  h('strong', {}, display(attrs.value)),
])

function display(value) {
  return bankSendPreparationDisplayValue(value)
}

function shortHash(value) {
  const text = String(value || '')
  return text ? `${text.slice(0, 12)}…${text.slice(-8)}` : '-'
}

async function refresh() {
  loading.value = true
  try {
    const envelope = await bankSendPreparationApi.list()
    const loaded = readPceFactLoadEnvelope(
      envelope,
      FACT_LOAD_API_URL,
      'bank-send-preparation-page',
    )
    const response = loaded.payload
    if (response?.result !== 'passed') {
      throw new Error(response?.error?.message || '银行发送准备读取失败')
    }
    const facts = createBankSendPreparationPageFacts(response)
    factLoadFacts.value = loaded.factLoadFacts
    rows.value = facts.rows
    Object.assign(capacity, facts.capacity)
    Object.assign(downstreamCounts, facts.downstreamCounts)
    Object.assign(writeIntentFacts, facts.writeIntentFacts)
    Object.assign(
      bankSendPreparationFacts,
      facts.bankSendPreparationFacts,
    )
    const selectedId = current.value?.id
    current.value = rows.value.find(row => row.id === selectedId) || rows.value[0] || null
    strictServerFacts.value = facts.strictServerFacts
    publishAcceptance(facts)
  } catch (error) {
    const failed = factLoadFailureFromError(
      error,
      FACT_LOAD_API_URL,
      factLoadFacts.value,
    )
    factLoadFacts.value = failed
    strictServerFacts.value = {
      currentStateSource: 'server',
      pageCode: 'bank-send-preparation',
      ...failed,
      factLoadFacts: failed,
      resultCount: null,
      rows: [],
      sourceObjects: [],
      passed: false,
    }
    publishAcceptance({
      strictServerFacts: strictServerFacts.value,
    })
    ElMessage.error(error?.message || '银行发送准备读取失败')
  } finally {
    loading.value = false
  }
}

function selectCurrent(row) {
  current.value = row || null
  if (row && !selectedRows.value.some(item => item.id === row.id)) {
    tableRef.value?.clearSelection()
    tableRef.value?.toggleRowSelection(row, true)
  }
}

async function handleBusinessAction(action) {
  if (!current.value) {
    ElMessage.warning('请先选择一条银行发送准备记录')
    return
  }
  if (action.actionId === 'view-bank-send-eligibility') {
    document.getElementById('bank-send-eligibility')?.scrollIntoView({
      behavior: 'smooth',
      block: 'start',
    })
    return
  }
  if (action.actionId === 'view-bank-send-gate') {
    document.getElementById('bank-send-gate')?.scrollIntoView({
      behavior: 'smooth',
      block: 'start',
    })
    return
  }
  if (action.actionId === 'generate-bank-message-preview') {
    const row = current.value
    const envelope = await bankSendPreparationApi.generatePreview(row.id, {
      idempotencyKey: `V58-PREVIEW-${row.prepareNo}`,
      expectedVersion: row.version,
      explicitUserAction: true,
    })
    const result = envelope?.data?.result ? envelope.data : envelope
    if (result?.result !== 'passed') {
      ElMessage.error(result?.error?.message || '发送预览生成失败')
      return
    }
    ElMessage.success(
      result.classification === 'existing_result'
        ? '已读取现有只读发送预览'
        : '只读发送预览已生成；未发送银行',
    )
    await refresh()
  }
}

function downstreamLabel(key) {
  return {
    bankSendTasks: '银行发送任务',
    bankMessages: '银行报文发送',
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
    canonicalName: '银行发送准备',
    moduleCode: 'bank-send-preparation',
    sourceDocumentType: 'formalPaymentOrder',
    currentStateSource: 'server',
    ...factLoadFacts.value,
    factLoadFacts: factLoadFacts.value,
    factLoadStatusLabel: {
      loaded: '已加载',
      empty_valid: '有效空数据',
      read_failed: '读取失败',
    }[factLoadFacts.value?.factLoadStatus] || '未加载',
    resultCount: factLoadResultCount(factLoadFacts.value, rows.value.length),
    passed: factLoadPassed(
      factLoadFacts.value,
      bankSendPreparationFacts.passed === true,
    ),
    currentObject: current.value,
    selectedObject: current.value,
    sourceObjects: strictServerFacts.value.sourceObjects || [],
    status: current.value?.status || '',
    strictServerFacts: strictServerFacts.value,
    capacity: !factLoadFacts.value
      || factLoadFacts.value.factLoadStatus === 'read_failed'
      ? null
      : { ...capacity },
    downstreamCounts: { ...downstreamCounts },
    bankSendTaskCreated: writeIntentFacts.bankSendTaskCreated === true,
    bankSendCreated: false,
    bankMessageSent: false,
    paymentExecuted: false,
    fundsDebited: false,
    bankTransactionCreated: false,
    bankSecretExposed: false,
    writeIntentFacts: { ...writeIntentFacts },
    bankSendPreparationFacts: { ...bankSendPreparationFacts },
    writeIntentClassification: {
      previewPreparationWrite: {
        category: 'preview_preparation_write',
        label: '允许准备写入数量',
        count: writeIntentFacts.previewPreparationWriteCount,
      },
      auditWrite: {
        category: 'audit_write',
        label: '允许审计写入数量',
        count: writeIntentFacts.auditWriteCount,
      },
      forbiddenBusinessProgressWrite: {
        category: 'business_progress_write',
        label: '禁止业务推进写入数量',
        count: writeIntentFacts.forbiddenBusinessProgressWriteCount,
      },
    },
    previewPreparationWriteCount:
      writeIntentFacts.previewPreparationWriteCount,
    auditWriteCount: writeIntentFacts.auditWriteCount,
    forbiddenBusinessProgressWriteCount:
      writeIntentFacts.forbiddenBusinessProgressWriteCount,
  }
}

function publishAcceptance(facts) {
  window.__PCE_BUSINESS_PAGE_ACCEPTANCE__ = {
    ...buildDiagnostics(),
    strictServerFacts: facts.strictServerFacts,
    pageAssertions: [
      {
        fullUrl: window.location.href,
        regionTitle: '金丝雀容量',
        relativePosition: '页面动作栏之后第一个业务区域',
        fieldName: '来源正式付款单/银行发送准备/门禁通过',
        expectedValue: '8/8/8/8',
        actualValue: `${capacity.sourceFormalPaymentOrderCount}/${capacity.bankSendPreparationCount}/${capacity.preparedCount}/${capacity.eligibleCount}`,
        ctrlF: '金丝雀容量',
        passed:
          capacity.sourceFormalPaymentOrderCount >= 8
          && capacity.bankSendPreparationCount >= 8
          && capacity.preparedCount >= 8
          && capacity.eligibleCount >= 8,
      },
      {
        fullUrl: window.location.href,
        regionTitle: '报文预览',
        relativePosition: '接口能力之后',
        fieldName: '预览状态/已发送/付款执行/敏感字段暴露',
        expectedValue: 'preview_only/否/否/否',
        actualValue: `${current.value?.messagePreview?.status || 'not_generated'}/${display(current.value?.messagePreview?.sent)}/${display(writeIntentFacts.paymentExecuted)}/${display(current.value?.messagePreview?.bankSecretExposed)}`,
        ctrlF: '报文预览',
        passed:
          current.value?.messagePreview?.status === 'preview_only'
          && current.value?.messagePreview?.sent !== true
          && writeIntentFacts.paymentExecuted === false
          && current.value?.messagePreview?.bankSecretExposed !== true,
      },
      {
        fullUrl: window.location.href,
        regionTitle: '下游零对象保护',
        relativePosition: '页面最底部',
        fieldName: '发送/付款/资金/流水/凭证/总账',
        expectedValue: '全部为0',
        actualValue: JSON.stringify(downstreamCounts),
        ctrlF: '下游零对象保护',
        passed: Object.entries(downstreamCounts)
          .filter(([key]) => key !== 'bankSendTasks')
          .every(([, value]) => value === 0),
      },
    ],
  }
}

onMounted(() => {
  observability?.register(observabilityProvider)
  refresh()
})
onBeforeUnmount(() => observability?.unregister(observabilityProvider))
</script>

<style scoped>
.bank-send-preparation-page {
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

.section-heading p {
  margin-top: 5px;
  color: #64748b;
}

.fact-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 10px;
}

.fact-item {
  display: grid;
  gap: 5px;
  min-width: 0;
  padding: 11px;
  border: 1px solid #dbeafe;
  border-radius: 7px;
  background: #f8fbff;
}

.fact-item span {
  color: #64748b;
  font-size: 12px;
}

.fact-item strong {
  overflow-wrap: anywhere;
  color: #0f172a;
}

.advanced-filter-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 10px;
}

.table-scroll {
  width: 100%;
  min-width: 0;
  overflow-x: auto;
}

.bank-send-table {
  min-width: 1740px;
}

:deep(.bank-send-table .el-table-fixed-column--left),
:deep(.bank-send-table .el-table-fixed-column--right) {
  z-index: 4;
  background: #fff;
}

.preview-json {
  max-height: 280px;
  overflow: auto;
  padding: 12px;
  border-radius: 7px;
  background: #0f172a;
  color: #e2e8f0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.zero-boundary {
  border-color: #86efac;
  background: #f0fdf4;
}

.blocked-reason {
  color: #b91c1c;
  font-weight: 700;
}

.ctrl-f {
  color: #64748b;
  font-size: 12px;
}
</style>
