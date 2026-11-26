<template>
  <main class="inquiry-page" data-page-code="purchase-inquiry-acceptance" data-business-object="QuotePreparationContext"
    data-runtime-version="V1.14.2.8.18.7A" data-provider-code="SCM_QUOTE_PREPARATION_PROVIDER">
    <header class="page-heading"><div><h1>{{ pageName.pageTitle }}</h1><p>读取当前 QuotePreparationContext，不读取旧模拟核价数据。</p></div>
      <el-button @click="router.push('/scm/purchase-inquiry')">返回询价工作台</el-button></header>
    <section class="panel" data-acceptance-id="purchase-inquiry-acceptance-context">
      <template v-if="!isBatch && quotePreparationContext">
        <h2>当前报价准备事实</h2>
        <p data-acceptance-id="purchase-inquiry-next-action-region"><strong>当前节点：</strong>供应商报价准备　
          <strong>当前状态（流程状态）：</strong>quote_preparation_ready　<strong>下一步业务动作：</strong>进入供应商报价节点。</p>
        <el-descriptions :column="3" border>
          <el-descriptions-item label="报价准备编号">{{ quotePreparationContext.quotePreparationNo }}</el-descriptions-item>
          <el-descriptions-item label="询价编号">{{ quotePreparationContext.inquiryNo }}</el-descriptions-item>
          <el-descriptions-item label="来源采购申请">{{ quotePreparationContext.sourceRequestNo || '-' }}</el-descriptions-item>
        </el-descriptions>
      </template>
      <h2 v-else-if="isBatch">批量报价准备上下文</h2>
      <PceEnterpriseListTable
        ref="tableRef" :contract="enterpriseListContract" page-id="purchase-inquiry-acceptance"
        table-id="purchase-inquiry-acceptance-table" :rows="acceptanceRows" :table-rows="filteredRows"
        :filter-schema="filterSchema" :filters="filters" :quick-search="quickSearch"
        :advanced-visible="advancedVisible" :selected-count="selectedRows.length"
        :active-filter-count="activeFilterCount" :sort-text="sortText" primary-field="rowKey"
        primary-label="询价/供应商" :primary-width="210" min-width="1450px" action-width="120"
        @update:quick-search="quickSearch = $event" @search="applySearch"
        @toggle-advanced="advancedVisible = !advancedVisible" @clear-filters="clearFilters"
        @clear-sort="clearSort" @export-current="exportCurrent" @clear-selection="clearSelection"
        @update-filter="updateFilter" @selection-change="selectedRows = $event" @sort-change="handleSort"
      >
        <template #columns>
          <el-table-column prop="sourceRequestNo" label="来源采购申请" width="190" />
          <el-table-column prop="materialCode" label="物料编码" width="150" />
          <el-table-column prop="materialName" label="物料名称" width="180" />
          <el-table-column prop="supplierCode" label="供应商编码" width="150" />
          <el-table-column prop="supplierName" label="供应商名称" width="180" />
          <el-table-column prop="preparationStatus" label="准备状态" width="170" />
          <el-table-column prop="supplierStatus" label="供应商状态" width="150" />
          <el-table-column prop="source" label="来源" width="180" />
        </template>
        <template #actions><el-button size="small" plain disabled>只读</el-button></template>
      </PceEnterpriseListTable>
      <el-alert title="边界保持：尚未创建 SupplierQuote，未发送供应商，未创建采购订单。" type="info" :closable="false" show-icon />
    </section>
  </main>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import { createPceEnterpriseListContract, usePceEnterpriseListRuntime } from '@/meta/runtime/pceEnterpriseListContract.js'
import { SCM_7_GATE_LIST_CONTRACTS } from '@/meta/schema/scm/scm7GateListContracts.js'
import { loadPurchaseInquiryBatchRuntime } from '@/meta/runtime/purchaseInquiryBatchRuntime.js'
import { loadPurchaseInquiryBusinessBatchResult } from '@/meta/runtime/purchaseInquiryBusinessBatchAction.js'
import { quotePreparationProvider } from '@/meta/providers/quotePreparationProvider.js'
import { resolvePageNameConsumption } from '@/meta/governance/pageNameConsumer.js'

const route = useRoute()
const router = useRouter()
const pageName = resolvePageNameConsumption({ pageCode: 'purchase-inquiry-acceptance', route: route.path })
const inquiryNo = computed(() => String(route.params.inquiryNo || ''))
const isBatch = computed(() => inquiryNo.value === 'batch')
const batch = computed(() => isBatch.value ? loadPurchaseInquiryBatchRuntime() : null)
const businessBatch = computed(() => isBatch.value ? loadPurchaseInquiryBusinessBatchResult() : null)
const batchRows = computed(() => businessBatch.value?.quotePreparationContexts || batch.value?.inquiries || [])
const quotePreparationFacts = computed(() => quotePreparationProvider.load({ inquiryNo: inquiryNo.value }))
const quotePreparationContext = computed(() => quotePreparationFacts.value.current)
const listContract = SCM_7_GATE_LIST_CONTRACTS['purchase-inquiry-acceptance']
const filterSchema = listContract.filterSchema
const acceptanceRows = computed(() => {
  const contexts = isBatch.value ? batchRows.value : [quotePreparationContext.value].filter(Boolean)
  return contexts.flatMap((context, contextIndex) => {
    const candidates = context.materialSupplierCandidates || context.supplierCandidates || []
    const normalizedCandidates = candidates.length ? candidates : [{}]
    return normalizedCandidates.map((candidate, candidateIndex) => ({
      ...candidate,
      inquiryNo: context.inquiryNo || inquiryNo.value,
      sourceRequestNo: context.sourceRequestNo || context.sourceOrderNo || '',
      preparationStatus: context.preparationStatus || context.status || '',
      rowKey: [context.inquiryNo || inquiryNo.value, candidate.supplierCode || candidate.supplierName || contextIndex, candidate.materialCode || candidateIndex].join('::'),
    }))
  })
})
const enterpriseListContract = createPceEnterpriseListContract({
  pageCode: 'purchase-inquiry-acceptance', pageType: 'list', title: '询价下一流程验收', moduleCode: 'SCM',
})
const runtime = usePceEnterpriseListRuntime({
  rows: acceptanceRows, filterSchema, pageCode: 'purchase-inquiry-acceptance', searchFields: listContract.searchFields,
  exportFileName: 'purchase-inquiry-acceptance.csv',
  exportColumns: [
    { field: 'inquiryNo', label: '询价编号' }, { field: 'sourceRequestNo', label: '来源采购申请' },
    { field: 'materialCode', label: '物料编码' }, { field: 'supplierName', label: '供应商名称' },
    { field: 'preparationStatus', label: '准备状态' },
  ],
})
const { selectedRows, quickSearch, advancedVisible, filters, tableRef, activeFilterCount, sortText,
  filteredRows, applySearch, updateFilter, clearFilters, clearSort, clearSelection, handleSort, exportCurrent } = runtime
</script>

<style scoped>
.inquiry-page{display:grid;gap:16px;max-width:1200px;margin:0 auto}.page-heading{display:flex;align-items:center;justify-content:space-between}.page-heading h1,.panel h2{margin:0}.page-heading p{color:#64748b}.panel{display:grid;gap:16px;padding:20px;border:1px solid #dce4ed;border-radius:10px;background:#fff}
</style>
