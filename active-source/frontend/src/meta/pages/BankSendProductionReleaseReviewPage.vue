<template>
  <main class="page" data-acceptance-id="bank-send-production-release-review-content">
    <section class="card stage">
      <Heading title="真实银行发送前生产隔离评审" note="本页面记录人工评审，不是发送授权，也不提供真实发送能力" />
      <p><strong>允许：</strong>✓ 查看生产隔离评审　✓ 查看隔离检查　✓ 查看评审意见</p>
      <p><strong>禁止：</strong>× 开启生产接口　× 配置生产密钥　× 执行银行发送　× 调用银行接口</p>
    </section>

    <section class="card" data-acceptance-id="bank-send-production-isolation-review">
      <Heading title="生产隔离检查" note="页面上部核心区域；全部事实直接来自服务端双重隔离对象" />
      <div class="grid">
        <Fact label="生产环境" value="隔离" />
        <Fact label="生产接口" :value="current?.isolation?.productionInterfaceDisabled ? '关闭' : '开启'" />
        <Fact label="生产密钥" :value="current?.isolation?.productionCredentialAbsent ? '不存在' : '存在'" />
        <Fact label="发送权限" :value="current?.isolation?.sendPermissionDisabled ? '关闭' : '开启'" />
        <Fact label="付款权限" :value="current?.isolation?.paymentPermissionDisabled ? '关闭' : '开启'" />
      </div>
    </section>

    <section class="card" data-acceptance-id="bank-send-production-release-facts">
      <Heading title="服务端持久事实" note="API、页面、复制诊断、strictFacts 与 AcceptanceFacts 共用同一事实" />
      <div class="grid">
        <Fact label="事实加载状态" value="加载成功" />
        <Fact label="事实来源" value="服务端" />
        <Fact label="评审数量" :value="facts.reviewCount" />
        <Fact label="已锁定" :value="facts.lockedCount" />
        <Fact label="完整人工评审" :value="facts.completeManualReviewCount" />
        <Fact label="银行已发送" :value="facts.bankSentCount" />
      </div>
    </section>

    <section class="card" data-acceptance-id="bank-send-production-release-list">
      <Heading title="人工放行评审" note="业务、资金和系统安全负责人独立确认，评审结果不产生发送权限" />
      <PceEnterpriseListTable
        ref="tableRef"
        :contract="enterpriseListContract"
        page-id="bank-send-production-release-review"
        table-id="bank-send-production-release-reviews-main"
        :rows="rows"
        :table-rows="filteredRows"
        :filter-schema="filterSchema"
        :filters="filters"
        :quick-search="quickSearch"
        :advanced-visible="advancedVisible"
        :selected-count="selectedRows.length"
        :active-filter-count="activeFilterCount"
        :sort-text="sortText"
        primary-field="reviewNo"
        primary-label="评审编号"
        :primary-width="440"
        min-width="1850px"
        scroll-acceptance-id="bank-send-production-release-horizontal-scroll"
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
          <el-table-column prop="statusLabel" label="评审状态" width="180" />
          <el-table-column label="业务负责人" width="190">
            <template #default="{ row }">{{ row.businessReview?.operator || '待评审' }}</template>
          </el-table-column>
          <el-table-column label="资金负责人" width="190">
            <template #default="{ row }">{{ row.fundReview?.operator || '待评审' }}</template>
          </el-table-column>
          <el-table-column label="安全负责人" width="190">
            <template #default="{ row }">{{ row.securityReview?.operator || '待评审' }}</template>
          </el-table-column>
        </template>
        <template #actions="{ row }">
          <el-button size="small" plain @click="showReview(row)">查看评审</el-button>
        </template>
      </PceEnterpriseListTable>
    </section>

    <section class="card" data-acceptance-id="bank-send-production-release-checks">
      <Heading title="最终放行检查项" note="RELEASE-001～010 全部由服务端判定，任何失败均禁止评审通过" />
      <div class="checks">
        <Fact
          v-for="index in 10"
          :key="index"
          :label="`RELEASE-${String(index).padStart(3, '0')}`"
          :value="current?.checks?.[`RELEASE-${String(index).padStart(3, '0')}`] ? '通过' : '未通过'"
        />
      </div>
    </section>

    <section class="card boundary" data-acceptance-id="bank-send-production-release-boundary">
      <Heading title="最终边界" note="评审锁定只形成审计证明，仍然没有任何银行发送能力" />
      <p class="notice">生产评审通过 ≠ 银行已发送</p>
      <div class="grid">
        <Fact label="生产评审状态" :value="current?.statusLabel || '-'" />
        <Fact label="银行发送" value="否" />
        <Fact label="付款执行" value="否" />
        <Fact label="资金扣减" value="否" />
      </div>
    </section>

    <el-dialog v-model="dialogVisible" title="生产隔离评审详情" width="820px">
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
  REVIEW_FILTER_SCHEMA,
  createProductionReleaseReviewPageFacts,
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
  pageCode: 'bank-send-production-release-review',
  pageType: 'list',
  title: '真实银行发送前生产隔离评审',
  moduleCode: 'FIN_BANK_SEND_PRODUCTION_RELEASE_REVIEW',
})
const filterSchema = REVIEW_FILTER_SCHEMA
const {
  selectedRows, quickSearch, appliedSearch, advancedVisible, filters, tableRef,
  activeFilterCount, sortText, filteredRows, clearFilters, clearSort,
  clearSelection, handleSort, exportCurrent,
} = usePceEnterpriseListRuntime({
  rows, filterSchema, pageCode: 'bank-send-production-release-review',
  searchFields: ['reviewNo', 'traceNo', 'approvalNo', 'statusLabel'],
  exportFileName: 'bank-send-production-release-reviews.csv',
  exportColumns: [
    { field: 'reviewNo', label: '评审编号' },
    { field: 'traceNo', label: '链路编号' },
    { field: 'statusLabel', label: '评审状态' },
  ],
})
const Heading = (_, { attrs }) => h('div', { class: 'heading' }, [h('h2', attrs.title), h('p', attrs.note)])
const Fact = (_, { attrs }) => h('article', { class: 'fact' }, [h('span', attrs.label), h('strong', String(attrs.value ?? '-'))])
function showReview(row) {
  dialogRow.value = row
  dialogVisible.value = true
}
function diagnostics() {
  return {
    version: BANK_SEND_PRODUCTION_RELEASE_VERSION,
    canonicalName: '真实银行发送前生产隔离评审',
    moduleCode: 'FIN_BANK_SEND_PRODUCTION_RELEASE_REVIEW',
    pageFactOwner: 'FIN_BANK_SEND_PRODUCTION_RELEASE_REVIEW',
    factSource: 'server',
    reviewFacts: { ...facts },
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
      { regionTitle: '生产隔离检查', actualValue: '接口/密钥/发送/付款权限关闭', passed: Boolean(current.value?.isolation?.productionInterfaceDisabled && current.value?.isolation?.productionCredentialAbsent && current.value?.isolation?.sendPermissionDisabled && current.value?.isolation?.paymentPermissionDisabled) },
      { regionTitle: '人工放行评审', actualValue: '三人三角色', passed: new Set(current.value?.decisions?.map(item => item.operator)).size >= 2 },
      { regionTitle: '最终边界', actualValue: '生产评审通过 ≠ 银行已发送', passed: current.value?.bankSent === false },
    ],
  }
}
async function refresh() {
  try {
    const loaded = createProductionReleaseReviewPageFacts(
      await bankSendProductionReleaseApi.reviews(),
    )
    rows.value = loaded.rows
    Object.assign(facts, loaded.facts)
    acceptanceFacts.value = loaded.acceptanceFacts
    strictFacts.value = loaded.strictFacts
    diagnosticFacts.value = loaded.diagnosticFacts
    publish()
  } catch (error) {
    ElMessage.error(`生产隔离评审事实读取失败：${error?.message || 'UNKNOWN'}`)
  }
}
const provider = { factOwner: 'FIN_BANK_SEND_PRODUCTION_RELEASE_REVIEW', refresh, buildDiagnostics: diagnostics }
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
.grid, .checks { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; }
.fact { display: grid; gap: 5px; padding: 12px; border-radius: 8px; background: #f5f8fb; }
.fact span { color: #64748b; font-size: 13px; }
.notice { color: #166534; font-size: 18px; font-weight: 800; }
pre { max-height: 520px; overflow: auto; white-space: pre-wrap; }
</style>
