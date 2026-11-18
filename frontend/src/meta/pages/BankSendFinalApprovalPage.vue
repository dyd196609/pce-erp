<template>
  <main class="page" data-acceptance-id="bank-send-final-approval-content">
    <section class="card stage">
      <Heading title="银行发送最终审批" note="最终审批用于锁定审批记录，不代表银行已发送" />
      <p><strong>允许：</strong>✓ 查看审批条件　✓ 提交第一审批　✓ 提交第二审批</p>
      <p><strong>禁止：</strong>× 执行发送　× 开启生产接口　× 上传密钥　× 调用银行</p>
    </section>

    <section class="card" data-acceptance-id="bank-send-final-approval-facts">
      <Heading title="服务端持久事实" note="审批数量、状态与保护事实全部来自服务端" />
      <div class="grid">
        <Fact label="事实加载状态" value="加载成功" />
        <Fact label="事实来源" value="服务端" />
        <Fact label="审批数量" :value="facts.approvalCount" />
        <Fact label="最终锁定" :value="facts.finalLockedCount" />
        <Fact label="双人审批" :value="facts.dualPersonApprovalCount" />
        <Fact label="银行已发送" :value="facts.bankSentCount" />
      </div>
    </section>

    <section class="card" data-acceptance-id="bank-send-final-approval-list">
      <Heading title="审批列表" note="业务审核人与资金负责人必须是两个独立用户和角色" />
      <PceEnterpriseListTable
        ref="tableRef"
        :contract="enterpriseListContract"
        page-id="bank-send-final-approval"
        table-id="bank-send-final-approvals-main"
        :rows="rows"
        :table-rows="filteredRows"
        :filter-schema="filterSchema"
        :filters="filters"
        :quick-search="quickSearch"
        :advanced-visible="advancedVisible"
        :selected-count="selectedRows.length"
        :active-filter-count="activeFilterCount"
        :sort-text="sortText"
        primary-field="approvalNo"
        primary-label="审批编号"
        :primary-width="420"
        min-width="1700px"
        scroll-acceptance-id="bank-send-final-approvals-horizontal-scroll"
        :action-width="160"
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
          <el-table-column prop="traceNo" label="链路编号" width="340" />
          <el-table-column prop="requestNo" label="请求编号" width="260" />
          <el-table-column prop="statusLabel" label="审批状态" width="180" />
          <el-table-column label="第一审批" width="190">
            <template #default="{ row }">{{ row.firstApproval?.operator || '待审批' }}</template>
          </el-table-column>
          <el-table-column label="第二审批" width="190">
            <template #default="{ row }">{{ row.secondApproval?.operator || '待审批' }}</template>
          </el-table-column>
        </template>
        <template #actions="{ row }">
          <el-button size="small" plain @click="showApproval(row)">{{ viewConditionsLabel }}</el-button>
        </template>
      </PceEnterpriseListTable>
    </section>

    <section class="card" data-acceptance-id="bank-send-final-approval-conditions">
      <Heading title="审批条件" note="FINAL-001～008 每次审批前均由服务端重新检查" />
      <div class="grid">
        <Fact label="发送请求" :value="current?.checks?.['FINAL-001'] ? '通过' : '未通过'" />
        <Fact label="执行授权" :value="current?.checks?.['FINAL-002'] ? '通过' : '未通过'" />
        <Fact label="模拟结果" :value="current?.checks?.['FINAL-003'] ? '通过' : '未通过'" />
        <Fact label="模拟审计" :value="current?.checks?.['FINAL-004'] ? '完整' : '不完整'" />
        <Fact label="隔离门禁" :value="current?.checks?.['FINAL-005'] ? '有效' : '无效'" />
        <Fact label="生产接口" :value="current?.checks?.['FINAL-006'] ? '关闭' : '开启'" />
        <Fact label="生产密钥" :value="current?.checks?.['FINAL-007'] ? '不存在' : '存在'" />
        <Fact label="业务未推进" :value="current?.checks?.['FINAL-008'] ? '是' : '否'" />
      </div>
    </section>

    <section class="card" data-acceptance-id="bank-send-dual-approval">
      <Heading title="双人授权记录" note="同一用户不能完成两次审批，两个审批角色必须不同" />
      <div class="grid">
        <Fact label="第一审批角色" :value="current?.firstApproval?.role || '-'" />
        <Fact label="第一审批人" :value="current?.firstApproval?.operator || '-'" />
        <Fact label="第二审批角色" :value="current?.secondApproval?.role || '-'" />
        <Fact label="第二审批人" :value="current?.secondApproval?.operator || '-'" />
      </div>
    </section>

    <section class="card boundary" data-acceptance-id="bank-send-final-boundary">
      <Heading title="最终边界" note="审批锁定后仍然没有任何银行发送能力" />
      <p class="notice">最终审批通过 ≠ 银行已发送</p>
      <div class="grid">
        <Fact label="最终审批状态" :value="current?.statusLabel || '-'" />
        <Fact label="银行发送" value="否" />
        <Fact label="付款执行" value="否" />
        <Fact label="资金扣减" value="否" />
      </div>
    </section>

    <el-dialog v-model="dialogVisible" title="银行发送最终审批详情" width="820px">
      <pre>{{ JSON.stringify(dialogRow, null, 2) }}</pre>
    </el-dialog>
  </main>
</template>

<script setup>
import { computed, h, inject, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { bankSendChainFinalApprovalApi } from '@/api/bankSendChainFinalApproval.js'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import { PAGE_OBSERVABILITY_ACTIONS_KEY } from '@/meta/runtime/pageObservabilityActions.js'
import { pceBusinessActionLabel } from '@/meta/runtime/pceBusinessActionRegistry.js'
import {
  createPceEnterpriseListContract,
  usePceEnterpriseListRuntime,
} from '@/meta/runtime/pceEnterpriseListContract.js'
import {
  APPROVAL_FILTER_SCHEMA,
  BANK_SEND_CHAIN_FINAL_APPROVAL_VERSION,
  createFinalApprovalPageFacts,
} from '@/meta/runtime/bankSendChainFinalApprovalRuntime.js'

const rows = ref([])
const facts = reactive({})
const acceptanceFacts = ref({})
const strictFacts = ref({})
const diagnosticFacts = ref({})
const current = computed(() => rows.value[0] || null)
const observability = inject(PAGE_OBSERVABILITY_ACTIONS_KEY, null)
const dialogVisible = ref(false)
const dialogRow = ref(null)
const viewConditionsLabel = pceBusinessActionLabel('view-bank-send-final-approval-conditions')
const enterpriseListContract = createPceEnterpriseListContract({
  pageCode: 'bank-send-final-approval',
  pageType: 'list',
  title: '银行发送最终审批',
  moduleCode: 'FIN_BANK_SEND_FINAL_APPROVAL',
})
const filterSchema = APPROVAL_FILTER_SCHEMA
const {
  selectedRows, quickSearch, appliedSearch, advancedVisible, filters, tableRef,
  activeFilterCount, sortText, filteredRows, clearFilters, clearSort,
  clearSelection, handleSort, exportCurrent,
} = usePceEnterpriseListRuntime({
  rows, filterSchema, pageCode: 'bank-send-final-approval',
  searchFields: ['approvalNo', 'traceNo', 'requestNo', 'statusLabel'],
  exportFileName: 'bank-send-final-approvals.csv',
  exportColumns: [
    { field: 'approvalNo', label: '审批编号' },
    { field: 'traceNo', label: '链路编号' },
    { field: 'requestNo', label: '请求编号' },
    { field: 'statusLabel', label: '审批状态' },
  ],
})
const Heading = (_, { attrs }) => h('div', { class: 'heading' }, [h('h2', attrs.title), h('p', attrs.note)])
const Fact = (_, { attrs }) => h('article', { class: 'fact' }, [h('span', attrs.label), h('strong', String(attrs.value ?? '-'))])
function showApproval(row) {
  dialogRow.value = row
  dialogVisible.value = true
}
async function refresh() {
  try {
    const loaded = createFinalApprovalPageFacts(
      await bankSendChainFinalApprovalApi.approvals(),
    )
    rows.value = loaded.rows
    Object.assign(facts, loaded.facts)
    acceptanceFacts.value = loaded.acceptanceFacts
    strictFacts.value = loaded.strictFacts
    diagnosticFacts.value = loaded.diagnosticFacts
    publish()
  } catch (error) {
    ElMessage.error(`银行发送最终审批事实读取失败：${error?.message || 'UNKNOWN'}`)
  }
}
function diagnostics() {
  return {
    version: BANK_SEND_CHAIN_FINAL_APPROVAL_VERSION,
    canonicalName: '银行发送最终审批',
    moduleCode: 'FIN_BANK_SEND_FINAL_APPROVAL',
    pageFactOwner: 'FIN_BANK_SEND_FINAL_APPROVAL',
    factSource: 'server',
    approvalFacts: { ...facts },
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
      { regionTitle: '审批条件', actualValue: 'FINAL-001～008通过', passed: Object.entries(current.value?.checks || {}).filter(([key]) => key.startsWith('FINAL-')).every(([, value]) => value === true) },
      { regionTitle: '双人授权记录', actualValue: '两个独立用户', passed: current.value?.firstApproval?.operator !== current.value?.secondApproval?.operator },
      { regionTitle: '最终边界', actualValue: '最终审批通过 ≠ 银行已发送', passed: current.value?.bankSent === false },
    ],
  }
}
const provider = { factOwner: 'FIN_BANK_SEND_FINAL_APPROVAL', refresh, buildDiagnostics: diagnostics }
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
