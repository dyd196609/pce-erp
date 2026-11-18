<template>
  <main class="node-page" data-page-code="inquiry-preparation" :data-page-name="pageName.pageTitle"
    data-module-code="SCM" data-business-object="InquiryPreparationContext">
    <header class="page-heading"><div><p>SCM · 采购询价</p><h1>{{ pageName.pageTitle }}</h1>
      <span>承接采购申请审批结果，确认物料和供应商候选后人工启动询价。</span></div>
      <el-button @click="refresh">刷新</el-button></header>
    <section class="panel" data-acceptance-region="inquiry-preparation-list">
      <PceEnterpriseListTable ref="tableRef" :contract="enterpriseListContract"
        page-id="inquiry-preparation" table-id="inquiry-preparation-main"
        :rows="rows" :table-rows="filteredRows" :filter-schema="filterSchema" :filters="filters"
        :quick-search="quickSearch" :advanced-visible="advancedVisible" :selected-count="selectedRows.length"
        :active-filter-count="activeFilterCount" :sort-text="sortText" primary-field="inquiryPreparationNo"
        primary-label="询价准备编号" :primary-width="220" min-width="1500px"
        scroll-acceptance-id="inquiry-preparation-horizontal-scroll" :action-width="150"
        @update:quick-search="quickSearch=$event" @search="appliedSearch=quickSearch"
        @toggle-advanced="advancedVisible=!advancedVisible" @clear-filters="clearFilters"
        @clear-sort="clearSort" @export-current="exportCurrent" @clear-selection="clearSelection"
        @update-filter="(field,value)=>filters[field]=value" @selection-change="selectedRows=$event"
        @sort-change="handleSort">
        <template #columns>
          <el-table-column prop="sourceRequestNo" label="来源采购申请" width="190" />
          <el-table-column prop="materialLineCount" label="物料项数" width="110" />
          <el-table-column prop="materialQuantity" label="物料数量" width="110" />
          <el-table-column prop="supplierCandidateCount" label="供应商候选" width="130" />
          <el-table-column prop="requiredDate" label="需求日期" width="140" />
          <el-table-column label="当前状态" width="160"><template #default="{row}">
            <PceBusinessStatus :status-code="row.preparationStatus" :status-label="row.statusLabel" source="provider" />
          </template></el-table-column>
        </template>
        <template #actions="{row}"><el-button link type="primary"
          data-process-action="START_PURCHASE_INQUIRY" @click="startInquiry(row)">启动询价</el-button></template>
      </PceEnterpriseListTable>
    </section>
    <section class="panel detail" data-acceptance-region="preparation-detail">
      <h2>准备明细</h2><el-empty v-if="!current" description="请选择询价准备记录" />
      <template v-else><div class="facts"><article><span>来源申请</span><strong>{{current.sourceRequestNo}}</strong></article>
        <article><span>物料</span><strong>{{current.materialLineCount}} 项</strong></article>
        <article><span>供应商候选</span><strong>{{current.supplierCandidateCount}} 家</strong></article>
        <article><span>下一动作</span><strong>启动询价</strong></article></div>
        <el-table :data="current.inquiryLines" border><el-table-column prop="materialCode" label="物料编码" />
          <el-table-column prop="materialName" label="物料名称" /><el-table-column prop="quantity" label="数量" />
          <el-table-column prop="requiredDate" label="需求日期" /></el-table></template>
    </section>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import PceBusinessStatus from '@/meta/components/PceBusinessStatus.vue'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import { createPceEnterpriseListContract, usePceEnterpriseListRuntime } from '@/meta/runtime/pceEnterpriseListContract.js'
import { inquiryPreparationProvider } from '@/meta/providers/inquiryPreparationProvider.js'
import { activatePurchaseInquiryFromPreparation } from '@/meta/runtime/purchaseInquiryRuntime.js'
import { resolvePageNameConsumption } from '@/meta/governance/pageNameConsumer.js'

const router=useRouter(); const providerFacts=ref({objects:[],recordCount:0}); const rows=computed(()=>providerFacts.value.objects||[])
const current=computed(()=>selectedRows.value.at(-1)||rows.value.at(-1)||null)
const filterSchema=Object.freeze([{field:'sourceRequestNo',label:'来源采购申请',filterType:'text'},
  {field:'preparationStatus',label:'准备状态',filterType:'select',options:[{label:'询价准备就绪',value:'ready_for_inquiry'}]}])
const pageName=resolvePageNameConsumption({pageCode:'inquiry-preparation',route:'/scm/inquiry-preparations'})
const enterpriseListContract=createPceEnterpriseListContract({pageCode:'inquiry-preparation',pageType:'list',title:pageName.pageTitle,moduleCode:'SCM_INQUIRY_PREPARATION'})
const {selectedRows,quickSearch,appliedSearch,advancedVisible,filters,tableRef,activeFilterCount,sortText,
  filteredRows,clearFilters,clearSort,clearSelection,handleSort,exportCurrent}=usePceEnterpriseListRuntime({rows,filterSchema,
  pageCode:'inquiry-preparation',searchFields:['inquiryPreparationNo','sourceRequestNo'],exportFileName:'inquiry-preparations.csv',
  exportColumns:[{field:'inquiryPreparationNo',label:'询价准备编号'},{field:'sourceRequestNo',label:'来源采购申请'}]})
function refresh(){providerFacts.value=inquiryPreparationProvider.load()}
function startInquiry(row){const result=activatePurchaseInquiryFromPreparation(row);if(result.result!=='PASS')return ElMessage.warning('当前询价准备不满足启动条件。');ElMessage.success(result.idempotent?'询价已存在':'询价已启动');router.push({path:'/scm/purchase-inquiry',query:{inquiryNo:result.object.inquiryNo}})}
onMounted(refresh)
</script>

<style scoped>
.node-page{display:grid;gap:18px;padding:20px}.page-heading{display:flex;justify-content:space-between;align-items:center}.page-heading h1{margin:4px 0}.page-heading p,.page-heading span,.facts span{color:#64748b}.panel{padding:18px;border:1px solid #dbe4ee;border-radius:12px;background:#fff}.facts{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px}.facts article{display:grid;gap:5px}@media(max-width:800px){.facts{grid-template-columns:1fr}.page-heading{align-items:flex-start;flex-direction:column}}
</style>
