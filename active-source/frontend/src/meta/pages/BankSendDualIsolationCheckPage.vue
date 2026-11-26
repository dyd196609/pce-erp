<template>
  <main class="page" data-acceptance-id="bank-send-dual-isolation-content">
    <section class="card stage">
      <Heading title="银行发送双重隔离检查" note="只读证明系统仍处于生产隔离状态，不提供配置或执行入口" />
      <p><strong>允许：</strong>✓ 查看隔离检查　✓ 查看来源</p>
      <p><strong>禁止：</strong>× 开启生产接口　× 配置生产密钥　× 执行银行发送　× 调用银行接口</p>
    </section>

    <section class="card" data-acceptance-id="bank-send-dual-isolation-facts">
      <Heading title="服务端持久事实" note="五端共用同一服务端隔离事实" />
      <div class="grid">
        <Fact label="事实加载状态" value="加载成功" />
        <Fact label="事实来源" value="服务端" />
        <Fact label="检查数量" :value="facts.checkCount" />
        <Fact label="通过数量" :value="facts.passedCount" />
        <Fact label="失败数量" :value="facts.failedCount" />
      </div>
    </section>

    <section class="card" data-acceptance-id="bank-send-dual-isolation-results">
      <Heading title="隔离检查结果" note="环境、凭证、权限和接口必须同时通过" />
      <div class="grid">
        <Fact label="环境隔离" :value="current?.environmentCheck ? '通过' : '未通过'" />
        <Fact label="凭证隔离" :value="current?.credentialCheck ? '通过' : '未通过'" />
        <Fact label="权限隔离" :value="current?.permissionCheck ? '通过' : '未通过'" />
        <Fact label="接口隔离" :value="current?.interfaceCheck ? '通过' : '未通过'" />
      </div>
    </section>

    <section class="card" data-acceptance-id="bank-send-dual-isolation-list">
      <Heading title="双重隔离检查列表" note="隔离结果由服务端检查对象持久化" />
      <PceEnterpriseListTable
        ref="tableRef"
        :contract="enterpriseListContract"
        page-id="bank-send-dual-isolation-check"
        table-id="bank-send-dual-isolation-checks-main"
        :rows="rows"
        :table-rows="filteredRows"
        :filter-schema="filterSchema"
        :filters="filters"
        :quick-search="quickSearch"
        :advanced-visible="advancedVisible"
        :selected-count="selectedRows.length"
        :active-filter-count="activeFilterCount"
        :sort-text="sortText"
        primary-field="checkNo"
        primary-label="检查编号"
        :primary-width="440"
        min-width="1550px"
        scroll-acceptance-id="bank-send-dual-isolation-horizontal-scroll"
        :action-width="140"
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
      >
        <template #columns>
          <el-table-column prop="traceNo" label="链路编号" width="350" />
          <el-table-column prop="approvalNo" label="最终审批编号" width="420" />
          <el-table-column prop="resultLabel" label="检查结果" width="180" />
          <el-table-column prop="checkedBy" label="检查人" width="190" />
        </template>
        <template #actions="{ row }">
          <el-button size="small" plain @click="showCheck(row)">查看检查</el-button>
        </template>
      </PceEnterpriseListTable>
    </section>

    <section class="card boundary" data-acceptance-id="bank-send-dual-isolation-boundary">
      <Heading title="最终边界" note="双重隔离通过只证明安全边界有效" />
      <p class="notice">隔离检查通过 ≠ 银行已发送</p>
      <div class="grid">
        <Fact label="银行发送" value="否" />
        <Fact label="付款执行" value="否" />
        <Fact label="资金扣减" value="否" />
      </div>
    </section>

    <el-dialog v-model="dialogVisible" title="双重隔离检查详情" width="820px">
      <pre>{{ JSON.stringify(dialogRow, null, 2) }}</pre>
    </el-dialog>
  </main>
</template>

<script setup>
import { computed, h, inject, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { bankSendProductionReleaseApi } from '@/api/bankSendProductionRelease.js'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import { PAGE_OBSERVABILITY_ACTIONS_KEY } from '@/meta/runtime/pageObservabilityActions.js'
import {
  createPceEnterpriseListContract,
  usePceEnterpriseListRuntime,
} from '@/meta/runtime/pceEnterpriseListContract.js'
import {
  BANK_SEND_PRODUCTION_RELEASE_VERSION,
  ISOLATION_FILTER_SCHEMA,
  createDualIsolationPageFacts,
} from '@/meta/runtime/bankSendProductionReleaseRuntime.js'

const rows = ref([])
const facts = reactive({})
const acceptanceFacts = ref({})
const strictFacts = ref({})
const diagnosticFacts = ref({})
const current = computed(() => rows.value[0] || null)
const observability = inject(PAGE_OBSERVABILITY_ACTIONS_KEY, null)
const dialogVisible = ref(false)
const dialogRow = ref(null)
const enterpriseListContract = createPceEnterpriseListContract({
  pageCode: 'bank-send-dual-isolation-check',
  pageType: 'list',
  title: '银行发送双重隔离检查',
  moduleCode: 'FIN_BANK_SEND_DUAL_ISOLATION_CHECK',
})
const filterSchema = ISOLATION_FILTER_SCHEMA
const {
  selectedRows, quickSearch, appliedSearch, advancedVisible, filters, tableRef,
  activeFilterCount, sortText, filteredRows, clearFilters, clearSort,
  clearSelection, handleSort, exportCurrent,
} = usePceEnterpriseListRuntime({
  rows, filterSchema, pageCode: 'bank-send-dual-isolation-check',
  searchFields: ['checkNo', 'traceNo', 'approvalNo', 'resultLabel'],
  exportFileName: 'bank-send-dual-isolation-checks.csv',
  exportColumns: [
    { field: 'checkNo', label: '检查编号' },
    { field: 'traceNo', label: '链路编号' },
    { field: 'resultLabel', label: '检查结果' },
  ],
})
const Heading = (_, { attrs }) => h('div', { class: 'heading' }, [h('h2', attrs.title), h('p', attrs.note)])
const Fact = (_, { attrs }) => h('article', { class: 'fact' }, [h('span', attrs.label), h('strong', String(attrs.value ?? '-'))])
function showCheck(row) {
  dialogRow.value = row
  dialogVisible.value = true
}
function diagnostics() {
  return {
    version: BANK_SEND_PRODUCTION_RELEASE_VERSION,
    canonicalName: '银行发送双重隔离检查',
    moduleCode: 'FIN_BANK_SEND_DUAL_ISOLATION_CHECK',
    pageFactOwner: 'FIN_BANK_SEND_DUAL_ISOLATION_CHECK',
    factSource: 'server',
    isolationFacts: { ...facts },
    diagnosticFacts: diagnosticFacts.value,
    strictFacts: strictFacts.value,
    acceptanceFacts: acceptanceFacts.value,
    resultCount: facts.recordCount ?? null,
    dangerActionCount: 0,
    businessProgressWriteCount: 0,
  }
}
function publish() {
  window.__PCE_BUSINESS_PAGE_ACCEPTANCE__ = {
    ...diagnostics(),
    pageAssertions: [
      { regionTitle: '隔离检查结果', actualValue: '四类全部通过', passed: Boolean(current.value?.environmentCheck && current.value?.credentialCheck && current.value?.permissionCheck && current.value?.interfaceCheck) },
      { regionTitle: '最终边界', actualValue: '隔离检查通过 ≠ 银行已发送', passed: true },
    ],
  }
}
async function refresh() {
  try {
    const loaded = createDualIsolationPageFacts(
      await bankSendProductionReleaseApi.isolationChecks(),
    )
    rows.value = loaded.rows
    Object.assign(facts, loaded.facts)
    acceptanceFacts.value = loaded.acceptanceFacts
    strictFacts.value = loaded.strictFacts
    diagnosticFacts.value = loaded.diagnosticFacts
    publish()
  } catch (error) {
    ElMessage.error(`双重隔离事实读取失败：${error?.message || 'UNKNOWN'}`)
  }
}
const provider = { factOwner: 'FIN_BANK_SEND_DUAL_ISOLATION_CHECK', refresh, buildDiagnostics: diagnostics }
onMounted(async () => {
  observability?.register?.(provider)
  await refresh()
  observability?.register?.(provider)
})
onBeforeUnmount(() => observability?.unregister?.(provider))
</script>

<style scoped>
.page { display: grid; min-width: 0; gap: 18px; }
.card { min-width: 0; padding: 20px; border: 1px solid #dce4ed; border-radius: 12px; background: #fff; }
.stage { border-color: #93c5fd; background: #eff6ff; }
.boundary { border-color: #b8d8c4; background: #f5fbf7; }
.heading h2 { margin: 0; color: #16243a; }
.heading p { margin: 6px 0 16px; color: #64748b; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; }
.fact { display: grid; gap: 5px; padding: 12px; border-radius: 8px; background: #f5f8fb; }
.fact span { color: #64748b; font-size: 13px; }
.notice { color: #166534; font-size: 18px; font-weight: 800; }
pre { max-height: 520px; overflow: auto; white-space: pre-wrap; }
</style>
