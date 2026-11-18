<template>
  <section
    class="pce-strict-server-facts"
    data-acceptance-id="strict-server-facts"
    data-current-state-source="server"
    data-diagnostic-visibility="authorized-disclosure"
    :data-diagnostic-expanded="String(diagnosticExpanded)"
  >
    <div class="pce-strict-server-facts__heading">
      <div>
        <p>PCE-WEB-ACCEPTANCE-V1.1 strict</p>
        <h2>服务端持久事实</h2>
      </div>
      <button
        type="button"
        class="pce-strict-server-facts__toggle"
        data-acceptance-id="strict-diagnostic-toggle"
        :aria-expanded="diagnosticExpanded"
        @click="diagnosticExpanded = !diagnosticExpanded"
      >{{ diagnosticExpanded ? '收起诊断信息' : '查看诊断信息' }}</button>
    </div>
    <div v-show="diagnosticExpanded" data-acceptance-id="strict-diagnostic-content">
    <p v-if="loading">正在读取持久金丝雀服务端事实。</p>
    <p v-else-if="error" role="alert">{{ error }}</p>
    <template v-else>
      <div class="pce-strict-server-facts__summary">
        <span>租户：<strong>{{ context?.tenantId }}</strong></span>
        <span>批次：<strong>{{ context?.batchId }}</strong></span>
        <span>当前模块：<strong>{{ canonicalName }}</strong></span>
        <span>独立成功链：<strong data-acceptance-id="strict-server-row-count">{{ rows.length }}</strong></span>
      </div>
      <StandardListToolbar
        :page-id="pageCode"
        :table-id="tableId"
        :quick-search="quickSearch"
        :advanced-visible="advancedVisible"
        :result-count="filteredRows.length"
        :selected-count="selectedRows.length"
        :active-filter-count="activeFilterCount"
        :sort-text="sortText"
        placeholder="输入当前编号、来源编号、场景编码或状态"
        @update:quick-search="quickSearch = $event"
        @search="applySearch"
        @toggle-advanced="advancedVisible = !advancedVisible"
        @clear-filters="clearFilters"
        @clear-sort="clearSort"
        @export-current="exportCurrent"
        @clear-selection="clearSelection"
      />
      <div
        v-if="advancedVisible"
        class="pce-strict-server-facts__filters"
        data-acceptance-id="strict-advanced-filter"
        :data-filter-contract-version="filterContractVersion"
      >
        <PceAdvancedFilterField
          v-for="field in strictFilterSchema"
          :key="field.field"
          v-model="filters[field.field]"
          :field="field"
          :rows="rows"
        />
      </div>
      <BusinessTableScrollContainer
        :acceptance-id="`business-table-scroll-${tableId}`"
        :page-id="pageCode"
        :table-id="tableId"
        min-width="1500px"
      >
        <el-table
          ref="tableRef"
          :data="filteredRows"
          row-key="objectNo"
          data-acceptance-id="strict-server-facts-table"
          @selection-change="selectedRows = $event"
          @sort-change="sortChanged"
        >
          <el-table-column type="selection" width="56" fixed="left" class-name="business-table-selection-column" />
          <el-table-column type="index" label="序号" width="70" fixed="left" class-name="pce-fixed-index-column" />
          <el-table-column prop="scenarioCode" label="场景编码" width="260" sortable />
          <el-table-column prop="objectNo" label="当前业务编号" width="240" sortable />
          <el-table-column prop="sourceObjectNo" label="来源业务编号" width="240" sortable />
          <el-table-column prop="status" label="当前状态" width="180">
            <template #default="{ row }">{{ statusLabel(row.status) }}</template>
          </el-table-column>
          <el-table-column prop="currentStateSource" label="当前状态来源" width="180" />
          <el-table-column label="操作" width="180" fixed="right" class-name="payment-fixed-action-column">
            <template #default="{ row }">
              <el-button link type="primary" @click="copyObjectNo(row)">复制业务编号</el-button>
            </template>
          </el-table-column>
        </el-table>
      </BusinessTableScrollContainer>
    </template>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getPurchaseCanaryContext } from '@/api/purchaseCanary'
import { paymentOrderDraftApi } from '@/api/paymentOrderDraft.js'
import { createPaymentOrderDraftPageFacts } from '@/meta/runtime/paymentOrderDraftRuntime.js'
import { paymentRiskReviewApi } from '@/api/paymentRiskReview.js'
import { createPaymentRiskReviewPageFacts } from '@/meta/runtime/paymentRiskReviewRuntime.js'
import { formalPaymentOrderApi } from '@/api/formalPaymentOrder.js'
import { createFormalPaymentOrderPageFacts } from '@/meta/runtime/formalPaymentOrderRuntime.js'
import { bankSendPreparationApi } from '@/api/bankSendPreparation.js'
import { createBankSendPreparationPageFacts } from '@/meta/runtime/bankSendPreparationRuntime.js'
import { bankSendTaskApi } from '@/api/bankSendTask.js'
import { createBankSendTaskPageFacts } from '@/meta/runtime/bankSendTaskRuntime.js'
import {
  factLoadFailureFromError,
} from '@/meta/runtime/pceFactLoadContract.js'
import BusinessTableScrollContainer from './BusinessTableScrollContainer.vue'
import PceAdvancedFilterField from './PceAdvancedFilterField.vue'
import StandardListToolbar from './StandardListToolbar.vue'
import {
  PCE_ADVANCED_FILTER_CONTRACT_VERSION,
  createPceAdvancedFilterSchema,
  displayPceFilterValue,
} from '@/meta/runtime/pceAdvancedFilterContract.js'

const props = defineProps({
  pageCode: { type: String, required: true },
  canonicalName: { type: String, required: true },
})
const emit = defineEmits(['loaded', 'load-error'])
const diagnosticExpanded = ref(false)
const route = useRoute()
const context = ref(null)
const rows = ref([])
const quickSearch = ref('')
const appliedSearch = ref('')
const advancedVisible = ref(false)
const selectedRows = ref([])
const tableRef = ref(null)
const sort = reactive({ prop: '', order: '' })
const filters = reactive({ objectNo: '', sourceObjectNo: '', status: '', scenarioCode: '' })
const loading = ref(false)
const error = ref('')
const factLoadApiUrlByPage = Object.freeze({
  'payment-order-draft': '/api/finance/payment-order-drafts/',
  'formal-payment-order': '/api/finance/formal-payment-orders/',
  'bank-send-preparation': '/api/finance/bank-send-prepares/',
})

const filterContractVersion = PCE_ADVANCED_FILTER_CONTRACT_VERSION
const strictFilterSchema = createPceAdvancedFilterSchema([
  { field: 'objectNo', label: '当前编号', type: 'text', optionsProvider: 'none' },
  { field: 'sourceObjectNo', label: '来源编号', type: 'text', optionsProvider: 'none' },
  { field: 'status', label: '生命周期状态', type: 'select' },
  { field: 'scenarioCode', label: '金丝雀场景编码', type: 'text', optionsProvider: 'none' },
])
const statusLabel = value => displayPceFilterValue(value)
const tableId = computed(() => `${props.pageCode}-strict-server-main`)
const activeFilterCount = computed(() => (
  Number(Boolean(appliedSearch.value.trim()))
  + Object.values(filters).filter(value => String(value || '').trim()).length
))
const sortText = computed(() => sort.prop ? `${sort.prop} ${sort.order === 'ascending' ? '升序' : '降序'}` : '默认业务顺序')
const filteredRows = computed(() => {
  const keyword = appliedSearch.value.trim().toLowerCase()
  let result = rows.value.filter(row => {
    const searchable = [row.objectNo, row.sourceObjectNo, row.scenarioCode, row.status].join(' ').toLowerCase()
    return (!keyword || searchable.includes(keyword))
      && (!filters.objectNo || row.objectNo.includes(filters.objectNo.trim()))
      && (!filters.sourceObjectNo || row.sourceObjectNo.includes(filters.sourceObjectNo.trim()))
      && (!filters.status || row.status === filters.status)
      && (!filters.scenarioCode || row.scenarioCode.includes(filters.scenarioCode.trim()))
  })
  if (sort.prop && sort.order) {
    result = [...result].sort((left, right) => String(left[sort.prop] || '').localeCompare(String(right[sort.prop] || '')))
    if (sort.order === 'descending') result.reverse()
  }
  return result
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    if (props.pageCode === 'payment-order-draft') {
      const response = await paymentOrderDraftApi.list()
      const facts = createPaymentOrderDraftPageFacts(response)
      context.value = {
        tenantId: facts.tenantId,
        batchId: facts.canaryBatchId,
      }
      rows.value = facts.strictServerFacts.rows
      emit('loaded', facts.strictServerFacts)
      return
    }
    if (props.pageCode === 'payment-risk-review') {
      const response = await paymentRiskReviewApi.list()
      const facts = createPaymentRiskReviewPageFacts(response?.data || {})
      context.value = {
        tenantId: facts.tenantId,
        batchId: facts.canaryBatchId,
      }
      rows.value = facts.strictServerFacts.rows
      emit('loaded', facts.strictServerFacts)
      return
    }
    if (props.pageCode === 'formal-payment-order') {
      const response = await formalPaymentOrderApi.list()
      const facts = createFormalPaymentOrderPageFacts(response)
      context.value = {
        tenantId: facts.tenantId,
        batchId: facts.canaryBatchId,
      }
      rows.value = facts.strictServerFacts.rows
      emit('loaded', facts.strictServerFacts)
      return
    }
    if (props.pageCode === 'bank-send-preparation') {
      const response = await bankSendPreparationApi.list()
      const facts = createBankSendPreparationPageFacts(response)
      context.value = {
        tenantId: facts.strictServerFacts.tenantId,
        batchId: facts.strictServerFacts.batchId,
      }
      rows.value = facts.strictServerFacts.rows
      emit('loaded', facts.strictServerFacts)
      return
    }
    if (props.pageCode === 'bank-send-task') {
      const response = await bankSendTaskApi.list()
      const facts = createBankSendTaskPageFacts(response?.data || {})
      context.value = {
        tenantId: facts.strictServerFacts.tenantId,
        batchId: facts.strictServerFacts.batchId,
      }
      rows.value = facts.strictServerFacts.rows
      emit('loaded', facts.strictServerFacts)
      return
    }
    const response = await getPurchaseCanaryContext({
      scenarioCode: 'HAPPY_PATH',
      moduleCode: props.pageCode,
    })
    context.value = response?.success ? response.data : null
    rows.value = context.value?.strictSuccessfulPool || []
    if (rows.value.length < 8) throw new Error(`服务端独立成功链不足8条：${rows.value.length}`)
    emit('loaded', {
      currentStateSource: 'server',
      tenantId: context.value.tenantId,
      batchId: context.value.batchId,
      pageCode: props.pageCode,
      resultCount: rows.value.length,
      currentObject: rows.value[0],
      sourceObjects: rows.value.map(row => ({ objectNo: row.sourceObjectNo })),
      status: rows.value[0]?.status || '',
      rows: rows.value,
    })
  } catch (reason) {
    error.value = reason?.message || '读取服务端持久事实失败'
    const failed = factLoadFailureFromError(
      reason,
      factLoadApiUrlByPage[props.pageCode]
        || '/api/pce/purchase-canary/context',
      context.value,
    )
    context.value = {
      tenantId: failed.tenantId,
      batchId: failed.batchId,
    }
    rows.value = []
    emit('load-error', {
      currentStateSource: 'server',
      pageCode: props.pageCode,
      error: error.value,
      ...failed,
      factLoadFacts: failed,
      resultCount: null,
      rows: [],
      sourceObjects: [],
      passed: false,
    })
  } finally {
    loading.value = false
  }
}

function applySearch() {
  appliedSearch.value = quickSearch.value
}

function clearFilters() {
  quickSearch.value = ''
  appliedSearch.value = ''
  Object.assign(filters, { objectNo: '', sourceObjectNo: '', status: '', scenarioCode: '' })
}

function sortChanged(value) {
  sort.prop = value?.prop || ''
  sort.order = value?.order || ''
}

function clearSort() {
  Object.assign(sort, { prop: '', order: '' })
  tableRef.value?.clearSort()
}

function clearSelection() {
  tableRef.value?.clearSelection()
  selectedRows.value = []
}

async function copyObjectNo(row) {
  await navigator.clipboard.writeText(row.objectNo)
  ElMessage.success('业务编号已复制')
}

function exportCurrent() {
  const header = ['场景编码', '当前业务编号', '来源业务编号', '当前状态', '当前状态来源']
  const lines = filteredRows.value.map(row => [row.scenarioCode, row.objectNo, row.sourceObjectNo, statusLabel(row.status), 'server'])
  const csv = [header, ...lines].map(line => line.map(value => `"${String(value || '').replaceAll('"', '""')}"`).join(',')).join('\r\n')
  const link = document.createElement('a')
  link.href = URL.createObjectURL(new Blob([`\ufeff${csv}`], { type: 'text/csv;charset=utf-8' }))
  link.download = `${props.canonicalName}-当前结果.csv`
  link.click()
  URL.revokeObjectURL(link.href)
}

watch(() => route.fullPath, load)
onMounted(load)
</script>

<style scoped>
.pce-strict-server-facts {
  display: grid;
  gap: 12px;
  min-width: 0;
  padding: 16px;
  border: 1px solid #86b7a5;
  border-radius: 8px;
  background: #f5fbf8;
}
.pce-strict-server-facts__heading,
.pce-strict-server-facts__summary {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 12px;
}
.pce-strict-server-facts h2,
.pce-strict-server-facts p { margin: 0; }
.pce-strict-server-facts__toggle { padding:7px 12px; border:1px solid #94a3b8; border-radius:7px; background:#fff; color:#334155; cursor:pointer; white-space:nowrap; }
.pce-strict-server-facts__filters {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 10px;
}
.pce-strict-server-facts__filters label {
  display: grid;
  gap: 5px;
  color: #334155;
  font-weight: 700;
}
</style>
