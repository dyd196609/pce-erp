<template>
  <main class="ap-page">
    <header class="page-header">
      <div v-if="!embeddedInCommonShell">
        <p class="eyebrow">{{ VERSION }} · 多成功金丝雀继承池</p>
        <h2 data-acceptance-id="page-internal-subject-title"><PceBusinessNameConsumer page-code="account-payable-draft" /></h2>
        <p>当前数据源：服务端采购应付账款草稿持久化读模型</p>
      </div>
      <div class="button-row">
        <el-button @click="goProcessCenter">返回业务流程中心</el-button>
        <el-button :loading="loading" @click="refresh">刷新</el-button>
        <el-button type="success" plain @click="copyDiagnostics">复制验收报告</el-button>
      </div>
    </header>

    <section class="business-card capacity-card" data-acceptance-id="purchase-canary-capacity">
      <div class="section-heading">
        <div>
          <h3>金丝雀群测试容量</h3>
          <p class="ctrl-f">下游可继承成功链数量</p>
        </div>
        <el-tag :type="capacity.passed ? 'success' : 'danger'">
          {{ capacity.passed ? '容量门禁通过' : '容量不足' }}
        </el-tag>
      </div>
      <div class="facts">
        <Fact label="金丝雀批次" :value="capacity.canaryBatchId || '-'" />
        <Fact label="成功继承链数量" :value="capacity.successLineageCount || 0" />
        <Fact label="下游可继承成功链数量" :value="capacity.downstreamEligibleLineageCount || 0" />
        <Fact label="正式采购应付账款草稿数量" :value="capacity.formalDraftCount || 0" />
        <Fact label="阻断场景数量" :value="capacity.blockedScenarioCount || 0" />
        <Fact label="为下一模块保留数量" :value="capacity.reservedForNextModuleCount || 0" />
        <Fact label="下一阶段已消费数量" :value="capacity.nextStageConsumedCount || 0" />
        <Fact label="未消费可用数量" :value="capacity.unconsumedAvailableCount || 0" />
        <Fact label="保留给下一模块" :value="capacity.nextModule || 'payable_confirmation_prepare'" />
      </div>
    </section>

    <section class="business-card" data-acceptance-id="purchase-canary-scenario-overview">
      <div class="section-heading">
        <div>
          <h3>金丝雀业务场景</h3>
          <p class="ctrl-f">成功场景与阻断场景</p>
        </div>
        <label class="scenario-filter">
          只读场景筛选
          <el-select v-model="scenarioFilter" filterable @change="refresh">
            <el-option label="全部场景" value="all" />
            <el-option label="全部成功场景" value="success" />
            <el-option label="全部阻断场景" value="blocked" />
            <el-option
              v-for="option in scenarioOptions"
              :key="option.scenarioCode"
              :label="option.scenarioCode"
              :value="option.scenarioCode"
            />
          </el-select>
        </label>
      </div>
      <el-table :data="scenarioOverview" border stripe max-height="360" row-key="scenarioCode">
        <el-table-column prop="scenarioCode" label="场景编码" min-width="250" fixed="left" />
        <el-table-column prop="scenarioClass" label="场景分类" width="130" />
        <el-table-column prop="scenarioRole" label="场景角色" min-width="190" />
        <el-table-column prop="currentModuleCode" label="当前模块" min-width="190" />
        <el-table-column prop="currentObjectNo" label="当前对象编号" min-width="200" />
        <el-table-column prop="currentStatus" label="当前状态" width="130"><template #default="{ row }">{{ display(row.currentStatus) }}</template></el-table-column>
        <el-table-column label="是否形成 AP 草稿" width="150">
          <template #default="{ row }">{{ row.formalApDraftCreated ? '是' : '否' }}</template>
        </el-table-column>
        <el-table-column label="下游资格" width="120">
          <template #default="{ row }">{{ row.downstreamEligible ? '可继承' : '阻断' }}</template>
        </el-table-column>
        <el-table-column prop="reservedForNextModule" label="保留测试角色" min-width="220" />
        <el-table-column prop="blockingReason" label="阻断原因" min-width="260" />
      </el-table>
    </section>

    <PceBusinessActionBar
      current-module="accounts-payable-draft"
      :current-status="actionBarStatus"
      :selected-rows="actionBarRows"
      :eligibility="Boolean(draft.id) || generationButtonVisible"
      :show-unavailable="true"
      :include-action-ids="draft.id
        ? [
            'enter-payable-confirmation-prepare',
            'batch-enter-payable-confirmation-prepare',
          ]
        : ['generate-purchase-accounts-payable-draft']"
      @execute="executeRegistryAction"
    />

    <section class="business-card" data-acceptance-id="purchase-ap-draft-strict-facts">
      <div class="section-heading"><h3>服务端状态机事实</h3></div>
      <div class="facts">
        <Fact label="当前状态来源" :value="strictFacts.currentStateSource" />
        <Fact label="对象数量" :value="strictFacts.objectCount" />
        <Fact label="状态迁移数量" :value="strictFacts.statusTransitionCount" />
        <Fact label="状态机一致" :value="strictFacts.stateMachineConsistent" />
      </div>
    </section>

    <template v-if="rows.length === 1">
      <section class="business-card" data-acceptance-id="purchase-ap-draft-source">
        <div class="section-heading">
          <div><h3>采购应付账款草稿来源</h3><p class="ctrl-f">来源采购发票准备</p></div>
          <el-button v-if="source.id" plain @click="viewSource">查看来源采购发票准备</el-button>
        </div>
        <div class="facts">
          <Fact label="来源采购发票准备编号" :value="source.prepareNo || draft.sourcePurchaseInvoicePrepareNo || '-'" />
          <Fact label="来源采购对账编号" :value="source.sourcePurchaseReconciliationNo || draft.sourcePurchaseReconciliationNo || '-'" />
          <Fact label="资料状态" :value="source.invoiceDataStatus || '-'" />
          <Fact label="校验状态" :value="source.validationStatus || '-'" />
          <Fact label="发票身份状态" :value="source.invoiceIdentityStatus || '-'" />
          <Fact label="当前状态来源" value="server" />
        </div>
      </section>

      <section class="business-card" data-acceptance-id="purchase-ap-draft-business-gate">
        <div class="section-heading">
          <div><h3>采购应付账款草稿业务门禁</h3><p class="ctrl-f">业务门禁</p></div>
          <strong>当前结论：{{ currentBusinessStatus }}</strong>
        </div>
        <div class="facts">
          <Fact label="动作前业务门禁快照" :value="preActionGate.passed ? '通过' : '阻断'" />
          <Fact label="当前目标数量" :value="currentState.targetCount ?? rows.length" />
          <Fact label="幂等状态" :value="currentState.idempotencyStatus || 'committed'" />
          <Fact label="编号状态" :value="currentState.numberReservationStatus || 'consumed'" />
          <Fact label="事务状态" :value="currentState.transactionStatus || 'committed'" />
          <Fact label="审计状态" :value="currentState.auditStatus || 'committed'" />
        </div>
        <div v-if="currentState.testTenant && rows.length === 1" class="button-row">
          <el-button plain @click="scrollToObject">查看已有采购应付账款草稿</el-button>
          <el-button plain @click="retryGeneration">测试租户执行幂等重试</el-button>
          <el-button plain @click="queryGenerationResult">测试租户查询生成结果</el-button>
          <el-button plain @click="recoverCommittedResult">测试租户执行提交结果恢复</el-button>
        </div>
      </section>

      <section ref="objectRegion" class="business-card" data-acceptance-id="purchase-ap-draft-object">
        <div class="section-heading">
          <div><h3>采购应付账款草稿对象</h3><p class="ctrl-f">采购应付账款草稿编号</p></div>
        </div>
        <div class="facts">
          <Fact label="采购应付账款草稿编号" :value="draft.draftNo || '-'" />
          <Fact label="场景编码" :value="draft.scenarioCode || '-'" />
          <Fact label="供应商" :value="draft.supplierName || '-'" />
          <Fact label="发票号码" :value="draft.invoiceNumber || '-'" />
          <Fact label="含税金额" :value="draft.amountIncludingTax || '0.00'" />
          <Fact label="幂等键" :value="draft.idempotencyKey || '-'" />
          <Fact label="事务标识" :value="draft.transactionId || '-'" />
          <Fact label="审计记录标识" :value="draft.auditRecordId || '-'" />
          <Fact label="来源关系哈希" :value="draft.sourceRelationHash || '-'" />
        </div>
      </section>
    </template>

    <section class="business-card table-card" data-acceptance-id="purchase-ap-draft-formal-list">
      <div class="section-heading">
        <div>
          <h3>正式采购应付账款草稿列表</h3>
          <p class="ctrl-f">APD20260700000001</p>
        </div>
      </div>
      <StandardListToolbar
        page-id="account-payable-draft"
        table-id="account-payable-draft-main"
        v-model:quick-search="quickSearch"
        :advanced-visible="advancedFilterVisible"
        :result-count="filteredRows.length"
        :selected-count="selectedRows.length"
        :active-filter-count="activeFilterCount"
        sort-text="默认业务顺序"
        :export-disabled="filteredRows.length === 0"
        @search="clearSelection"
        @toggle-advanced="advancedFilterVisible = !advancedFilterVisible"
        @clear-filters="clearFilters"
        @clear-sort="clearSort"
        @export-current="exportCurrentRows"
        @clear-selection="clearSelection"
      />
      <section
        v-show="advancedFilterVisible"
        class="advanced-filter-panel"
        data-acceptance-id="list-advanced-filter-panel"
        data-pce-filter-for="account-payable-draft-main"
      >
        <label>草稿编号<PceResultFilterSelect v-model="filters.draftNo" :rows="rows" :fields="['draftNo']" /></label>
        <label>场景编码<PceResultFilterSelect v-model="filters.scenarioCode" :rows="rows" :fields="['scenarioCode']" /></label>
        <label>供应商<PceResultFilterSelect v-model="filters.supplierName" :rows="rows" :fields="['supplierName']" /></label>
        <label>状态<PceResultFilterSelect v-model="filters.status" :rows="rows" :fields="['status']" /></label>
      </section>
      <BusinessTableScrollContainer acceptance-id="business-table-scroll-account-payable-draft-main" page-id="account-payable-draft" table-id="account-payable-draft-main" min-width="2450px">
        <el-table ref="tableRef" :data="filteredRows" border stripe height="480" scrollbar-always-on row-key="id" @selection-change="selectedRows = $event || []">
          <el-table-column type="selection" width="52" fixed="left" class-name="business-table-selection-column" />
          <el-table-column type="index" label="序号" width="70" fixed="left" class-name="pce-fixed-index-column" />
          <el-table-column prop="draftNo" label="采购应付账款草稿编号" min-width="220" fixed="left" sortable />
          <el-table-column prop="scenarioCode" label="场景编码" min-width="250" sortable />
          <el-table-column label="下游资格" width="120">
            <template #default="{ row }">{{ row.downstreamEligible ? '可继承' : '阻断' }}</template>
          </el-table-column>
          <el-table-column prop="scenarioRole" label="保留测试角色" min-width="210" />
          <el-table-column prop="sourcePurchaseInvoicePrepareNo" label="来源采购发票准备" min-width="200" />
          <el-table-column prop="supplierName" label="供应商" min-width="170" />
          <el-table-column prop="invoiceNumber" label="发票号码" min-width="170" />
          <el-table-column prop="currency" label="币种" width="90" />
          <el-table-column prop="quantity" label="数量" width="110" />
          <el-table-column prop="amountIncludingTax" label="含税金额" width="130" sortable />
          <el-table-column prop="payableAmount" label="应付金额" width="130" sortable />
          <el-table-column prop="status" label="应付草稿状态" width="120"><template #default="{ row }">{{ display(row.status) }}</template></el-table-column>
          <el-table-column label="操作" fixed="right" width="150" class-name="payment-fixed-action-column">
            <template #default="{ row }">
              <el-button size="small" plain @click="selectLineage(row)">查看</el-button>
            </template>
          </el-table-column>
        </el-table>
      </BusinessTableScrollContainer>
    </section>

    <section class="business-card" data-acceptance-id="purchase-ap-draft-downstream-zero">
      <h3>业务流程与后续边界</h3>
      <p class="ctrl-f">后续边界</p>
      <div class="facts">
        <Fact label="应付确认准备数量" :value="downstream.confirmationPrepares || 0" />
        <Fact label="是否已创建应付确认准备" value="否" />
        <Fact label="付款申请数量" :value="downstream.paymentApplications || 0" />
        <Fact label="付款对象数量" :value="downstream.payments || 0" />
        <Fact label="付款凭证数量" :value="downstream.paymentVouchers || 0" />
        <Fact label="核销数量" :value="downstream.writeoffs || 0" />
        <Fact label="总账数量" :value="downstream.ledgerEntries || 0" />
        <Fact label="过账数量" :value="downstream.postings || 0" />
        <Fact label="银行流水数量" :value="downstream.bankTransactions || 0" />
        <Fact label="用户 localStorage 业务写入数量" :value="downstream.localStorageBusinessWrites || 0" />
        <Fact label="生产租户网络写入数量" :value="downstream.productionNetworkWrites || 0" />
      </div>
      <p class="boundary">本版本只形成下游测试容量，不创建应付确认准备或任何更下游对象。</p>
    </section>
  </main>
</template>

<script setup>
import PceBusinessNameConsumer from '../components/PceBusinessNameConsumer.vue'
const { embeddedInCommonShell = false } = defineProps({
  embeddedInCommonShell: { type: Boolean, default: false },
})
import { computed, defineComponent, h, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { displayPceFilterValue } from '@/meta/runtime/pceAdvancedFilterContract.js'
import { purchaseAccountsPayableDraftApi } from '@/api/purchaseAccountsPayableDraft.js'
import BusinessTableScrollContainer from '../components/BusinessTableScrollContainer.vue'
import PceResultFilterSelect from '../components/PceResultFilterSelect.vue'
import StandardListToolbar from '../components/StandardListToolbar.vue'
import PceBusinessActionBar from '../components/PceBusinessActionBar.vue'

const VERSION = 'V1.14.2.8.4.7.45.3'
const display = displayPceFilterValue
const route = useRoute()
const router = useRouter()
const sourcePrepareId = computed(() => Number(route.query.sourcePurchaseInvoicePrepareId || 0))
const loading = ref(false)
const generating = ref(false)
const rows = ref([])
const selectedRows = ref([])
const scenarioOverview = ref([])
const scenarioOptions = ref([])
const scenarioFilter = ref('all')
const quickSearch = ref('')
const advancedFilterVisible = ref(false)
const tableRef = ref(null)
const objectRegion = ref(null)
const filters = reactive({ draftNo: '', scenarioCode: '', supplierName: '', status: '' })
const capacity = reactive({})
const source = reactive({})
const preActionGate = reactive({ passed: false, ruleCount: 0, rules: [], label: '动作前业务门禁快照' })
const currentState = reactive({
  targetCount: 0, generationAllowed: false, currentStateSource: 'server',
  testTenant: false, purchaseAccountsPayableDraft: null,
})
const strictFacts = reactive({
  currentStateSource: 'server',
  objectCount: null,
  statusTransitionHistory: null,
  statusTransitionCount: null,
  stateMachineConsistent: false,
})
const downstream = reactive({})

const Fact = defineComponent({
  props: { label: { type: String, required: true }, value: { type: [String, Number, Boolean], default: '-' } },
  setup(props) {
    return () => h('div', { class: 'fact' }, [h('span', props.label), h('strong', String(props.value ?? '-'))])
  },
})

function unwrap(response) {
  const envelope = response?.data || {}
  return envelope?.data || envelope
}

const draft = computed(() => currentState.purchaseAccountsPayableDraft || rows.value[0] || {})
const actionBarStatus = computed(() => (
  draft.value.id ? draft.value.status : (source.status || '')
))
const actionBarRows = computed(() => {
  if (selectedRows.value.length) return selectedRows.value
  if (draft.value.id) return [draft.value]
  if (source.id) return [source]
  return []
})
const generationButtonVisible = computed(() => (
  currentState.currentStateSource === 'server'
  && currentState.testTenant
  && currentState.generationAllowed
  && currentState.targetCount === 0
))
const currentBusinessStatus = computed(() => (
  rows.value.length === 1 ? '已存在采购应付账款草稿，不允许重复生成' : '当前条件阻断'
))
const activeFilterCount = computed(() => (
  Object.values(filters).filter(Boolean).length + (quickSearch.value.trim() ? 1 : 0)
))
const filteredRows = computed(() => rows.value.filter((row) => {
  const q = quickSearch.value.trim().toLowerCase()
  if (q && !Object.values(row).join(' ').toLowerCase().includes(q)) return false
  return Object.entries(filters).every(([field, value]) => !value || row[field] === value)
}))
const idempotencyKey = computed(() => [
  'papd-v45', sourcePrepareId.value, source.prepareVersion, source.invoiceDataVersion,
  source.validationVersion, source.sourceReconciliationVersion, source.sourceCheckVersion,
].join('-'))

function queryForScenario() {
  if (['all', 'success', 'blocked'].includes(scenarioFilter.value)) {
    return { scenarioClass: scenarioFilter.value }
  }
  return { scenarioCode: scenarioFilter.value }
}

async function refresh() {
  loading.value = true
  try {
    const list = unwrap(await purchaseAccountsPayableDraftApi.list({
      canaryBatchId: route.query.canaryBatchId || undefined,
      ...queryForScenario(),
    }))
    rows.value = list.results || []
    Object.assign(strictFacts, list.strictFacts || {})
    scenarioOverview.value = list.scenarioOverview || []
    if (!scenarioOptions.value.length || scenarioFilter.value === 'all') {
      scenarioOptions.value = [...(list.scenarioOverview || [])]
    }
    Object.assign(capacity, list.capacity || {})
    Object.assign(downstream, list.downstreamCounts || {})
    Object.keys(source).forEach((key) => delete source[key])
    if (list.source) Object.assign(source, list.source)
    Object.assign(currentState, {
      targetCount: rows.value.length,
      currentStateSource: 'server',
      purchaseAccountsPayableDraft: rows.value.length === 1 ? rows.value[0] : null,
      ...(list.currentState || {}),
    })
    Object.assign(preActionGate, list.preActionBusinessGate || { passed: false, rules: [] })
    if (sourcePrepareId.value) {
      const state = unwrap(await purchaseAccountsPayableDraftApi.bySource(sourcePrepareId.value))
      rows.value = state.results || []
      Object.assign(source, state.source || {})
      Object.assign(preActionGate, state.preActionBusinessGate || {})
      Object.assign(currentState, state)
    }
  } catch (error) {
    ElMessage.error(error?.message || '服务端金丝雀继承池读取失败')
  } finally {
    loading.value = false
  }
}

async function generate() {
  generating.value = true
  try {
    await purchaseAccountsPayableDraftApi.generate({
      sourcePurchaseInvoicePrepareId: sourcePrepareId.value,
      idempotencyKey: idempotencyKey.value,
      expectedPrepareVersion: source.prepareVersion,
      expectedInvoiceDataVersion: source.invoiceDataVersion,
      expectedValidationVersion: source.validationVersion,
      expectedReconciliationVersion: source.sourceReconciliationVersion,
      expectedCheckVersion: source.sourceCheckVersion,
      explicitUserAction: true,
    })
    await refresh()
  } catch (error) {
    ElMessage.error(error?.message || '测试租户受控生成失败')
  } finally {
    generating.value = false
  }
}

function executeRegistryAction(action) {
  if (action.actionId === 'generate-purchase-accounts-payable-draft') {
    generate()
  }
}

async function selectLineage(row) {
  scenarioFilter.value = row.scenarioCode
  await refresh()
  objectRegion.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function scrollToObject() {
  objectRegion.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

async function retryGeneration() {
  await generate()
}

async function queryGenerationResult() {
  try {
    const result = unwrap(await purchaseAccountsPayableDraftApi.generationResult(draft.value.idempotencyKey))
    if (result?.currentState) Object.assign(currentState, result.currentState)
    ElMessage.success(`生成结果：${result?.classification || 'existing_result'}`)
  } catch (error) {
    ElMessage.error(error?.message || '生成结果查询失败')
  }
}

async function recoverCommittedResult() {
  await queryGenerationResult()
}

function clearSelection() {
  tableRef.value?.clearSelection?.()
  selectedRows.value = []
}
function clearSort() { tableRef.value?.clearSort?.(); clearSelection() }
function clearFilters() {
  quickSearch.value = ''
  Object.keys(filters).forEach((key) => { filters[key] = '' })
  clearSelection()
}
function viewSource() {
  router.push({ path: '/finance/purchase-invoice-prepares', query: { sourcePurchaseReconciliationId: source.sourcePurchaseReconciliationId } })
}
function goProcessCenter() { router.push('/process-center') }
function exportCurrentRows() {
  const fields = ['draftNo', 'scenarioCode', 'scenarioRole', 'sourcePurchaseInvoicePrepareNo', 'supplierName', 'invoiceNumber', 'payableAmount', 'status']
  const csv = [fields.join(',')].concat(filteredRows.value.map((row) => fields
    .map((field) => `"${String(row[field] ?? '').replaceAll('"', '""')}"`).join(','))).join('\n')
  const blob = new Blob([`\ufeff${csv}`], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = 'purchase-accounts-payable-draft-canary-pool.csv'
  link.click()
  URL.revokeObjectURL(link.href)
}
async function copyDiagnostics() {
  await navigator.clipboard.writeText(JSON.stringify({
    version: VERSION, fullUrl: window.location.href, pageStandardName: '采购应付账款草稿',
    currentStateSource: 'server', capacity, scenarioOverview: scenarioOverview.value,
    formalDrafts: rows.value, strictFacts: { ...strictFacts }, downstream, nextStageWrites: 0,
  }, null, 2))
  ElMessage.success('验收报告已复制')
}

onMounted(refresh)
watch(() => [route.query.canaryBatchId, route.query.sourcePurchaseInvoicePrepareId], refresh)
</script>

<style scoped>
.ap-page { display: grid; gap: 16px; max-width: 100%; overflow-x: hidden; }
.page-header, .section-heading, .button-row { display: flex; justify-content: space-between; gap: 12px; align-items: center; flex-wrap: wrap; }
.page-header h2, .page-header p, .business-card h3, .ctrl-f { margin: 0; }
.eyebrow, .ctrl-f { color: #2563eb; font-size: 13px; font-weight: 800; }
.business-card { display: grid; gap: 14px; padding: 18px; border: 1px solid #dbe3ef; border-radius: 12px; background: #fff; }
.capacity-card { border-color: #86efac; background: linear-gradient(135deg, #f0fdf4, #fff); }
.facts { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; }
:deep(.fact) { display: grid; gap: 5px; padding: 11px; border-radius: 8px; background: #f8fafc; }
:deep(.fact span) { color: #64748b; font-size: 12px; }
:deep(.fact strong) { color: #0f172a; overflow-wrap: anywhere; }
.scenario-filter { display: grid; gap: 5px; min-width: 260px; color: #334155; font-size: 12px; font-weight: 800; }
.boundary { margin: 0; color: #92400e; font-weight: 700; line-height: 1.6; }
.advanced-filter-panel { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; padding: 10px; border: 1px solid #e2e8f0; border-radius: 8px; background: #f8fafc; }
.advanced-filter-panel label { display: grid; gap: 5px; color: #334155; font-size: 12px; font-weight: 800; }
</style>
