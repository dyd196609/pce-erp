<template>
  <main class="confirmation-page" data-acceptance-id="payable-confirmation-prepare-page">
    <header class="page-header">
      <div v-if="!embeddedInCommonShell">
        <p class="eyebrow">V1.14.2.8.4.7.46 · Finance</p>
        <h2 data-acceptance-id="page-internal-subject-title"><PceBusinessNameConsumer page-code="account-payable-confirm" /></h2>
        <p>唯一直接来源：采购应付账款草稿；当前状态和放行资格均来自服务端。</p>
      </div>
      <el-button type="success" plain @click="copyDiagnostics">复制验收报告</el-button>
    </header>

    <section class="business-card capacity-card" data-acceptance-id="payable-confirmation-capacity">
      <div class="section-heading">
        <h3>应付确认准备金丝雀容量</h3>
        <span :class="capacity.passed ? 'passed' : 'blocked'">
          {{ capacity.passed ? '容量门禁：通过' : '容量门禁：阻断' }}
        </span>
      </div>
      <div class="facts">
        <Fact label="持久批次编号" :value="capacity.canaryBatchId" />
        <Fact label="成功业务链数量" :value="capacity.passThroughLineageCount" />
        <Fact label="阻断场景数量" :value="capacity.blockedScenarioCount" />
        <Fact label="正式应付确认准备数量" :value="capacity.formalPayableConfirmationPrepareCount" />
        <Fact label="下游可继承来源数量" :value="capacity.downstreamEligibleSourceCount" />
        <Fact label="已被下一模块消费数量" :value="capacity.nextStageConsumedCount" />
        <Fact label="未消费可用数量" :value="capacity.unconsumedAvailableCount" />
        <Fact label="下一模块" value="付款申请准备" />
      </div>
      <p class="ctrl-f">Ctrl+F：应付确认准备金丝雀容量</p>
    </section>

    <section class="business-card" data-acceptance-id="payable-confirmation-strict-facts">
      <div class="section-heading"><h3>服务端状态机事实</h3></div>
      <div class="facts">
        <Fact label="当前状态来源" :value="strictFacts.currentStateSource" />
        <Fact label="对象数量" :value="strictFacts.objectCount" />
        <Fact label="状态迁移数量" :value="strictFacts.statusTransitionCount" />
        <Fact label="状态机一致" :value="strictFacts.stateMachineConsistent" />
      </div>
    </section>

    <section class="business-card" data-acceptance-id="payable-confirmation-source">
      <div class="section-heading">
        <h3>应付确认准备来源</h3>
        <strong>sourceDocumentType=purchaseAccountsPayableDraft</strong>
      </div>
      <div class="facts">
        <Fact label="来源模块" value="采购应付账款草稿" />
        <Fact label="来源对象数量" :value="capacity.formalPayableConfirmationPrepareCount" />
        <Fact label="当前状态来源" value="server" />
        <Fact label="一源一目标" value="服务端硬唯一约束" />
      </div>
      <p class="ctrl-f">Ctrl+F：应付确认准备来源</p>
    </section>

    <section class="business-card" data-acceptance-id="payable-confirmation-scenarios">
      <div class="section-heading">
        <div>
          <h3>应付确认准备业务场景</h3>
          <p>成功场景与独立阻断场景分开展示；场景切换只执行服务端查询。</p>
        </div>
        <label class="scenario-filter">
          场景筛选
          <el-select v-model="scenarioFilter" @change="refresh">
            <el-option label="全部场景" value="all" />
            <el-option label="全部成功链" value="success" />
            <el-option label="全部阻断场景" value="blocked" />
            <el-option
              v-for="item in scenarioOptions"
              :key="item.scenarioCode"
              :label="item.scenarioCode"
              :value="item.scenarioCode"
            />
          </el-select>
        </label>
      </div>
      <BusinessTableScrollContainer acceptance-id="business-table-scroll-payable-confirmation-scenarios" min-width="1400px">
        <el-table :data="scenarioOverview" border stripe height="360" scrollbar-always-on>
          <el-table-column prop="scenarioCode" label="场景编码" width="270" fixed="left" />
          <el-table-column prop="scenarioClass" label="场景类型" width="130" />
          <el-table-column prop="scenarioRole" label="场景目的" min-width="240" />
          <el-table-column prop="currentModuleCode" label="当前到达模块" min-width="220" />
          <el-table-column prop="currentObjectNo" label="当前对象编号" min-width="210" />
          <el-table-column prop="currentStatus" label="当前状态" width="130"><template #default="{ row }">{{ display(row.currentStatus) }}</template></el-table-column>
          <el-table-column prop="formalPayableConfirmationPrepareCreated" label="形成正式对象" width="140">
            <template #default="{ row }">{{ row.formalPayableConfirmationPrepareCreated ? '是' : '否' }}</template>
          </el-table-column>
          <el-table-column prop="downstreamEligible" label="下游继承资格" width="140">
            <template #default="{ row }">{{ row.downstreamEligible ? '允许' : '阻断' }}</template>
          </el-table-column>
          <el-table-column prop="blockingRuleCode" label="阻断规则" min-width="230" />
          <el-table-column prop="blockingReason" label="阻断原因" min-width="240" />
        </el-table>
      </BusinessTableScrollContainer>
      <p class="ctrl-f">Ctrl+F：应付确认准备业务场景</p>
    </section>

    <section class="business-card" data-acceptance-id="accounting-validation-evidence">
      <div class="section-heading">
        <div>
          <h3>会计资料与借贷预检查</h3>
          <p>会计科目、辅助核算、组织维度、付款条件、到期日、开放期间及 Decimal 借贷平衡均由服务端校验。</p>
        </div>
      </div>
      <div class="facts">
        <Fact label="资料快照" value="版本化且不可变" />
        <Fact label="校验执行" value="服务端持久化" />
        <Fact label="借贷算法" value="Decimal" />
        <Fact label="放行状态" value="prepared" />
        <Fact label="唯一放行资格" value="ready_for_payment_request_prepare" />
        <Fact label="下一模块重验" value="必须服务端重新验证" />
      </div>
      <p class="ctrl-f">Ctrl+F：会计资料与借贷预检查</p>
    </section>

    <section class="business-card" data-acceptance-id="payable-confirmation-formal-list" data-search-alias="快速搜索" aria-label="搜索">
      <div class="section-heading">
        <div>
          <h3>应付确认准备列表</h3>
          <p>仅展示真实存在于服务端正式领域表的对象。</p>
        </div>
      </div>

      <div class="business-flow-action-toolbar" data-acceptance-id="business-flow-action-toolbar">
        <PceBusinessActionBar
          current-module="payable-confirmation-prepare"
          :current-status="selectedRows[0]?.status || rows[0]?.status || ''"
          :selected-rows="selectedRows"
          :eligibility="selectedRows.length ? selectedRows.every(row => row.eligibility?.eligible) : null"
          :show-unavailable="selectedRows.length === 0"
        />
        <div class="business-flow-secondary-actions" data-acceptance-id="business-flow-secondary-actions">
          <strong>辅助操作</strong>
          <el-button type="primary" plain @click="exportCurrentRows">导出当前结果</el-button>
        </div>
      </div>

      <StandardListToolbar
        page-id="account-payable-confirm"
        table-id="account-payable-confirm-main"
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

      <section v-show="advancedFilterVisible" class="advanced-filter-panel" data-acceptance-id="list-advanced-filter-panel" data-pce-filter-for="account-payable-confirm-main">
        <label>应付确认准备编号<PceResultFilterSelect v-model="filters.prepareNo" :rows="rows" :fields="['prepareNo']" /></label>
        <label>来源AP草稿<PceResultFilterSelect v-model="filters.sourceDraftNo" :rows="rows" :fields="['sourceDraftNo']" /></label>
        <label>供应商<PceResultFilterSelect v-model="filters.supplierName" :rows="rows" :fields="['supplierName']" /></label>
        <label>状态<PceResultFilterSelect v-model="filters.status" :rows="rows" :fields="['status']" /></label>
        <label>场景编码<PceResultFilterSelect v-model="filters.scenarioCode" :rows="rows" :fields="['scenarioCode']" /></label>
        <label>会计期间<PceResultFilterSelect v-model="filters.accountingPeriod" :rows="rows" :fields="['accountingPeriod']" /></label>
        <label>付款条件<PceResultFilterSelect v-model="filters.paymentTermsCode" :rows="rows" :fields="['paymentTermsCode']" /></label>
        <label>校验状态<PceResultFilterSelect v-model="filters.validationStatus" :rows="rows" :fields="['validationStatus']" /></label>
        <label>币种<PceResultFilterSelect v-model="filters.currency" :rows="rows" :fields="['currency']" /></label>
      </section>

      <BusinessTableScrollContainer class="pce-baseline-table-shell" acceptance-id="business-table-scroll-account-payable-confirm-main" min-width="2350px">
        <el-table
          ref="tableRef"
          v-loading="loading"
          class="global-sort-arrow"
          :data="filteredRows"
          border
          stripe
          height="560"
          style="width:100%"
          scrollbar-always-on
          @selection-change="selectedRows = $event"
        >
          <el-table-column type="selection" width="48" fixed="left" class-name="business-table-selection-column" header-class-name="business-table-selection-column" />
          <el-table-column type="index" label="序号" width="64" fixed="left" class-name="pce-fixed-index-column" header-class-name="pce-fixed-index-column" />
          <el-table-column prop="prepareNo" label="应付确认准备编号" min-width="210" fixed="left" sortable class-name="pce-fixed-primary-no-column" header-class-name="pce-fixed-primary-no-column" />
          <el-table-column prop="scenarioCode" label="场景编码" min-width="250" sortable />
          <el-table-column prop="sourceDraftNo" label="来源采购应付账款草稿" min-width="220" sortable />
          <el-table-column prop="supplierName" label="供应商" min-width="180" sortable />
          <el-table-column prop="currency" label="币种" width="90" sortable />
          <el-table-column prop="payableAmount" label="应付金额" width="130" sortable />
          <el-table-column prop="accountingPeriod" label="会计期间" width="120" sortable />
          <el-table-column prop="dueDate" label="到期日" width="130" sortable />
          <el-table-column prop="debitTotal" label="借方合计" width="130" sortable />
          <el-table-column prop="creditTotal" label="贷方合计" width="130" sortable />
          <el-table-column prop="validationStatus" label="校验状态" width="120" sortable><template #default="{ row }">{{ display(row.validationStatus) }}</template></el-table-column>
          <el-table-column prop="status" label="准备状态" width="110" sortable><template #default="{ row }">{{ display(row.status) }}</template></el-table-column>
          <el-table-column label="付款申请准备资格" min-width="230">
            <template #default="{ row }">{{ display(row.eligibility?.nextStepReadiness || 'blocked') }}</template>
          </el-table-column>
          <el-table-column prop="scenarioRole" label="预留测试角色" min-width="250" />
          <el-table-column label="操作" fixed="right" width="170" class-name="payment-fixed-action-column" header-class-name="payment-fixed-action-column">
            <template #default="{ row }">
              <div class="row-actions">
                <el-button size="small" plain @click="viewSource(row)">查看来源草稿</el-button>
                <el-button size="small" type="primary" plain @click="viewServerDetail(row)">查看服务端详情</el-button>
                <el-button size="small" plain @click="viewAccountingSnapshot(row)">查看会计快照</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </BusinessTableScrollContainer>
      <p class="ctrl-f">Ctrl+F：{{ rows[0]?.prepareNo || '应付确认准备编号' }}</p>
    </section>

    <section class="business-card boundary-card" data-acceptance-id="payment-request-prepare-zero-boundary">
      <div class="section-heading">
        <h3>付款申请准备放行与下游零对象保护</h3>
        <strong>仅形成导航资格，不执行下游写入</strong>
      </div>
      <div class="facts">
        <Fact label="付款申请准备数量" :value="downstream.paymentRequestPrepares || 0" />
        <Fact label="付款申请数量" :value="downstream.paymentApplications || 0" />
        <Fact label="付款数量" :value="downstream.payments || 0" />
        <Fact label="付款凭证数量" :value="downstream.paymentVouchers || 0" />
        <Fact label="核销数量" :value="downstream.writeoffs || 0" />
        <Fact label="总账分录数量" :value="downstream.ledgerEntries || 0" />
        <Fact label="过账数量" :value="downstream.postings || 0" />
        <Fact label="银行流水数量" :value="downstream.bankTransactions || 0" />
      </div>
      <p class="boundary">paymentRequestPrepareCreated=false。本轮不创建付款申请准备及任何更下游对象。</p>
      <p class="ctrl-f">Ctrl+F：付款申请准备放行与下游零对象保护</p>
    </section>
  </main>
</template>

<script setup>
import PceBusinessNameConsumer from '../components/PceBusinessNameConsumer.vue'
const { embeddedInCommonShell = false } = defineProps({
  embeddedInCommonShell: { type: Boolean, default: false },
})
import { computed, defineComponent, h, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { displayPceFilterValue } from '@/meta/runtime/pceAdvancedFilterContract.js'
import { payableConfirmationPrepareApi } from '@/api/payableConfirmationPrepare.js'
import BusinessTableScrollContainer from '../components/BusinessTableScrollContainer.vue'
import PceResultFilterSelect from '../components/PceResultFilterSelect.vue'
import StandardListToolbar from '../components/StandardListToolbar.vue'
import PceBusinessActionBar from '../components/PceBusinessActionBar.vue'

const VERSION = 'V1.14.2.8.4.7.46'
const display = displayPceFilterValue
const router = useRouter()
const loading = ref(false)
const rows = ref([])
const scenarioOverview = ref([])
const scenarioOptions = ref([])
const scenarioFilter = ref('all')
const quickSearch = ref('')
const advancedFilterVisible = ref(false)
const selectedRows = ref([])
const tableRef = ref(null)
const capacity = reactive({})
const downstream = reactive({})
const strictFacts = reactive({
  currentStateSource: 'server',
  objectCount: null,
  statusTransitionHistory: null,
  statusTransitionCount: null,
  stateMachineConsistent: false,
})
const filters = reactive({
  prepareNo: '',
  sourceDraftNo: '',
  supplierName: '',
  status: '',
  scenarioCode: '',
  accountingPeriod: '',
  paymentTermsCode: '',
  validationStatus: '',
  currency: '',
})

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

function queryForScenario() {
  if (['all', 'success', 'blocked'].includes(scenarioFilter.value)) {
    return { scenarioClass: scenarioFilter.value }
  }
  return { scenarioCode: scenarioFilter.value }
}

async function refresh() {
  loading.value = true
  try {
    const data = unwrap(await payableConfirmationPrepareApi.list(queryForScenario()))
    rows.value = data.results || []
    scenarioOverview.value = data.scenarioOverview || []
    if (!scenarioOptions.value.length || scenarioFilter.value === 'all') {
      scenarioOptions.value = [...(data.scenarioOverview || [])]
    }
    Object.assign(capacity, data.capacity || {})
    Object.assign(downstream, data.downstreamCounts || {})
    Object.assign(strictFacts, data.strictFacts || {})
  } catch (error) {
    ElMessage.error(error?.message || '服务端应付确认准备读取失败')
  } finally {
    loading.value = false
  }
}

const activeFilterCount = computed(() => (
  Object.values(filters).filter(Boolean).length + (quickSearch.value.trim() ? 1 : 0)
))
const filteredRows = computed(() => rows.value.filter((row) => {
  const q = quickSearch.value.trim().toLowerCase()
  if (q && !Object.values(row).join(' ').toLowerCase().includes(q)) return false
  return Object.entries(filters).every(([field, value]) => !value || row[field] === value)
}))

function clearSelection() {
  tableRef.value?.clearSelection?.()
  selectedRows.value = []
}
function clearSort() {
  tableRef.value?.clearSort?.()
  clearSelection()
}
function clearFilters() {
  quickSearch.value = ''
  Object.keys(filters).forEach((key) => { filters[key] = '' })
  clearSelection()
}
function viewSource(row) {
  router.push({ path: '/finance/ap-drafts', query: { apDraftNo: row.sourceDraftNo } })
}
async function viewServerDetail(row) {
  const detail = unwrap(await payableConfirmationPrepareApi.detail(row.id))
  ElMessage.success(`服务端对象：${detail.prepareNo || row.prepareNo}`)
}
function viewAccountingSnapshot(row) {
  ElMessage.success(`会计快照：${row.accountingSnapshot?.snapshotHash || '未找到'}`)
}
function exportCurrentRows() {
  const fields = ['prepareNo', 'scenarioCode', 'sourceDraftNo', 'supplierName', 'currency', 'payableAmount', 'accountingPeriod', 'dueDate', 'validationStatus', 'status']
  const csv = [fields.join(',')].concat(filteredRows.value.map((row) => fields
    .map((field) => `"${String(row[field] ?? '').replaceAll('"', '""')}"`).join(','))).join('\n')
  const blob = new Blob([`\ufeff${csv}`], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = 'payable-confirmation-prepares.csv'
  link.click()
  URL.revokeObjectURL(link.href)
}
async function copyDiagnostics() {
  await navigator.clipboard.writeText(JSON.stringify({
    version: VERSION,
    canonicalName: '应付确认准备',
    sourceDocumentType: 'purchaseAccountsPayableDraft',
    currentStateSource: 'server',
    fullUrl: window.location.href,
    capacity,
    formalRows: rows.value,
    strictFacts: { ...strictFacts },
    scenarioOverview: scenarioOverview.value,
    downstream,
    paymentRequestPrepareCreated: false,
  }, null, 2))
  ElMessage.success('V46验收报告已复制')
}

onMounted(refresh)
</script>

<style scoped>
.confirmation-page { display: grid; gap: 16px; max-width: 100%; overflow-x: hidden; }
.page-header, .section-heading { display: flex; justify-content: space-between; gap: 12px; align-items: center; flex-wrap: wrap; }
.page-header h2, .page-header p, .business-card h3, .business-card p { margin: 0; }
.eyebrow, .ctrl-f { color: #2563eb; font-size: 13px; font-weight: 800; }
.business-card { display: grid; gap: 14px; padding: 18px; border: 1px solid #dbe3ef; border-radius: 12px; background: #fff; }
.capacity-card { border-color: #86efac; background: linear-gradient(135deg, #f0fdf4, #fff); }
.boundary-card { border-color: #fdba74; background: #fffaf0; }
.facts { display: grid; grid-template-columns: repeat(auto-fit, minmax(215px, 1fr)); gap: 10px; }
:deep(.fact) { display: grid; gap: 5px; padding: 11px; border-radius: 8px; background: #f8fafc; }
:deep(.fact span) { color: #64748b; font-size: 12px; }
:deep(.fact strong) { color: #0f172a; overflow-wrap: anywhere; }
.scenario-filter { display: grid; gap: 5px; min-width: 280px; color: #334155; font-size: 12px; font-weight: 800; }
.business-flow-action-toolbar { display: flex; justify-content: space-between; gap: 12px; align-items: center; flex-wrap: wrap; }
.business-flow-primary-actions, .business-flow-secondary-actions, .row-actions { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.business-flow-primary-actions small { flex-basis: 100%; color: #b45309; font-weight: 700; }
.advanced-filter-panel { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; padding: 10px; border: 1px solid #e2e8f0; border-radius: 8px; background: #f8fafc; }
.advanced-filter-panel label { display: grid; gap: 5px; color: #334155; font-size: 12px; font-weight: 800; }
.passed { color: #15803d; font-weight: 800; }
.blocked, .boundary { color: #b45309; font-weight: 800; }
</style>
