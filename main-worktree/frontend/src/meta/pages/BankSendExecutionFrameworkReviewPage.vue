<template>
  <main class="page" data-acceptance-id="bank-send-execution-framework-content">
    <section class="card stage" data-acceptance-id="bank-send-execution-framework-status">
      <Heading title="执行框架状态" note="框架仅描述未来发送能力，不是执行记录或发送记录" />
      <div class="grid">
        <Fact label="接口模式" :value="current?.interfaceModeLabel || '-'" />
        <Fact label="执行环境" :value="current?.environmentLabel || '-'" />
        <Fact label="生产连接" :value="current?.productionConnectionEnabled ? '开启' : '关闭'" />
        <Fact label="框架状态" :value="current?.statusLabel || '-'" />
      </div>
    </section>

    <section class="card">
      <Heading title="当前业务动作说明" note="本版本只允许查看设计、安全评审、签名和失败模型" />
      <p><strong>允许：</strong>✓ 查看执行框架　✓ 查看签名结果　✓ 查看失败模型</p>
      <p><strong>禁止：</strong>× 执行银行发送　× 调用银行接口　× 启用生产连接　× 上传生产密钥</p>
    </section>

    <section class="card" data-acceptance-id="bank-send-execution-framework-facts">
      <Heading title="服务端持久事实" note="五端复用同一服务端框架事实" />
      <div class="grid">
        <Fact label="事实加载状态" value="加载成功" />
        <Fact label="事实来源" value="服务端" />
        <Fact label="框架数量" :value="facts.frameworkCount" />
        <Fact label="安全评审通过" :value="facts.securityReviewedCount" />
        <Fact label="生产连接数量" :value="facts.productionConnectionCount" />
        <Fact label="真实发送能力" :value="facts.realSendCapabilityCount" />
      </div>
    </section>

    <section class="card" data-acceptance-id="bank-send-execution-framework-list">
      <Heading title="执行框架列表" note="只读展示框架设计状态" />
      <PceEnterpriseListTable
        ref="tableRef"
        :contract="enterpriseListContract"
        page-id="bank-send-execution-framework-review"
        table-id="bank-send-execution-framework-reviews-main"
        :rows="rows"
        :table-rows="filteredRows"
        :filter-schema="filterSchema"
        :filters="filters"
        :quick-search="quickSearch"
        :advanced-visible="advancedVisible"
        :selected-count="selectedRows.length"
        :active-filter-count="activeFilterCount"
        :sort-text="sortText"
        primary-field="frameworkNo"
        primary-label="框架编号"
        :primary-width="480"
        min-width="1650px"
        scroll-acceptance-id="bank-send-execution-framework-horizontal-scroll"
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
          <el-table-column prop="sourceReviewNo" label="来源生产评审" width="460" />
          <el-table-column prop="environmentLabel" label="执行环境" width="180" />
          <el-table-column prop="interfaceModeLabel" label="接口模式" width="160" />
          <el-table-column prop="statusLabel" label="框架状态" width="200" />
        </template>
        <template #actions="{ row }">
          <el-button size="small" plain @click="showRow(row)">查看框架</el-button>
        </template>
      </PceEnterpriseListTable>
    </section>

    <section class="card" data-acceptance-id="bank-send-execution-framework-safety">
      <Heading title="安全检查" note="生产接口、密钥和执行权限保持关闭" />
      <div class="grid">
        <Fact label="生产接口" :value="current?.productionConnectionEnabled ? '存在' : '不存在'" />
        <Fact label="生产密钥" :value="current?.productionSecretAvailable ? '存在' : '不存在'" />
        <Fact label="发送权限" :value="current?.sendPermissionEnabled ? '开启' : '关闭'" />
        <Fact label="付款权限" :value="current?.paymentPermissionEnabled ? '开启' : '关闭'" />
      </div>
    </section>

    <section class="card boundary" data-acceptance-id="bank-send-execution-framework-boundary">
      <Heading title="执行能力边界" note="框架设计完成不会产生真实发送能力" />
      <p class="notice">当前系统：具备发送框架设计能力</p>
      <p class="notice danger">当前系统：未开放真实发送能力</p>
      <p><strong>框架存在 ≠ 已经可以发送银行</strong></p>
    </section>

    <el-dialog v-model="dialogVisible" title="执行框架详情" width="820px">
      <pre>{{ JSON.stringify(dialogRow, null, 2) }}</pre>
    </el-dialog>
  </main>
</template>

<script setup>
import { computed, h, inject, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { bankSendExecutionFrameworkApi } from '@/api/bankSendExecutionFramework.js'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import { PAGE_OBSERVABILITY_ACTIONS_KEY } from '@/meta/runtime/pageObservabilityActions.js'
import { createPceEnterpriseListContract, usePceEnterpriseListRuntime } from '@/meta/runtime/pceEnterpriseListContract.js'
import {
  BANK_SEND_EXECUTION_FRAMEWORK_VERSION,
  FRAMEWORK_FILTER_SCHEMA,
  createFrameworkPageFacts,
} from '@/meta/runtime/bankSendExecutionFrameworkRuntime.js'

const rows = ref([])
const facts = reactive({})
const acceptanceFacts = ref({})
const strictFacts = ref({})
const diagnosticFacts = ref({})
const current = computed(() => rows.value[0] || null)
const observability = inject(PAGE_OBSERVABILITY_ACTIONS_KEY, null)
const dialogVisible = ref(false)
const dialogRow = ref(null)
const filterSchema = FRAMEWORK_FILTER_SCHEMA
const enterpriseListContract = createPceEnterpriseListContract({
  pageCode: 'bank-send-execution-framework-review',
  pageType: 'list',
  title: '银行发送执行框架评审',
  moduleCode: 'FIN_BANK_SEND_EXECUTION_FRAMEWORK_REVIEW',
})
const {
  selectedRows, quickSearch, appliedSearch, advancedVisible, filters, tableRef,
  activeFilterCount, sortText, filteredRows, clearFilters, clearSort,
  clearSelection, handleSort, exportCurrent,
} = usePceEnterpriseListRuntime({
  rows, filterSchema, pageCode: 'bank-send-execution-framework-review',
  searchFields: ['frameworkNo', 'sourceReviewNo', 'environmentLabel', 'statusLabel'],
  exportFileName: 'bank-send-execution-framework-reviews.csv',
  exportColumns: [
    { field: 'frameworkNo', label: '框架编号' },
    { field: 'environmentLabel', label: '执行环境' },
    { field: 'statusLabel', label: '框架状态' },
  ],
})
const Heading = (_, { attrs }) => h('div', { class: 'heading' }, [h('h2', attrs.title), h('p', attrs.note)])
const Fact = (_, { attrs }) => h('article', { class: 'fact' }, [h('span', attrs.label), h('strong', String(attrs.value ?? '-'))])
function showRow(row) { dialogRow.value = row; dialogVisible.value = true }
function diagnostics() {
  return {
    version: BANK_SEND_EXECUTION_FRAMEWORK_VERSION,
    canonicalName: '银行发送执行框架评审',
    moduleCode: 'FIN_BANK_SEND_EXECUTION_FRAMEWORK_REVIEW',
    pageFactOwner: 'FIN_BANK_SEND_EXECUTION_FRAMEWORK_REVIEW',
    factSource: 'server',
    frameworkFacts: { ...facts },
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
      { regionTitle: '执行框架状态', actualValue: '模拟/隔离/生产连接关闭', passed: current.value?.interfaceMode === 'simulated' && current.value?.productionConnectionEnabled === false },
      { regionTitle: '安全检查', actualValue: '生产接口与密钥不存在', passed: current.value?.productionSecretAvailable === false },
      { regionTitle: '执行能力边界', actualValue: '框架存在 ≠ 已经可以发送银行', passed: current.value?.realSendCapabilityOpen === false },
    ],
  }
}
async function refresh() {
  try {
    const loaded = createFrameworkPageFacts(await bankSendExecutionFrameworkApi.frameworks())
    rows.value = loaded.rows
    Object.assign(facts, loaded.facts)
    acceptanceFacts.value = loaded.acceptanceFacts
    strictFacts.value = loaded.strictFacts
    diagnosticFacts.value = loaded.diagnosticFacts
    publish()
  } catch (error) {
    ElMessage.error(`执行框架事实读取失败：${error?.message || 'UNKNOWN'}`)
  }
}
const provider = { factOwner: 'FIN_BANK_SEND_EXECUTION_FRAMEWORK_REVIEW', refresh, buildDiagnostics: diagnostics }
onMounted(async () => { observability?.register?.(provider); await refresh(); observability?.register?.(provider) })
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
.danger { color: #991b1b; }
pre { max-height: 520px; overflow: auto; white-space: pre-wrap; }
</style>
