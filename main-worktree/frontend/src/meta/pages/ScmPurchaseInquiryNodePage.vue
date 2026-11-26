<template>
  <main class="node-page" data-page-code="purchase-inquiry" :data-page-name="pageName.pageTitle"
    data-module-code="SCM" data-business-object="PurchaseInquiry" :data-mode="dataMode">
    <header class="page-heading"><div><p>SCM · 采购询价</p><h1>{{ pageName.pageTitle }}</h1>
      <span>承接已审批采购申请，维护询价对象、物料明细与供应商候选。</span></div><el-button :loading="loading" @click="refresh">刷新</el-button></header>
    <section class="mode-banner" data-acceptance-region="runtime-mode" :data-runtime-mode="dataMode">
      <strong>运行模式：{{ dataMode }}</strong>
      <span v-if="dataMode==='canary_acceptance'">批次 {{ facts.canaryBatchId }} · 场景 {{ facts.scenarioCode }}</span>
      <span v-else>正式业务事实 · 只读加载</span>
      <span v-if="loadError" role="alert">{{ loadError }}</span>
    </section>
    <section class="panel guide" data-acceptance-region="page-operation-guide" data-guide-contract="GUIDE-001..010">
      <h2>页面操作指引</h2>
      <ol class="r1-guide-steps" data-guide-version="V1.14.2.8.4.21-R1">
        <li><b>页面用途：</b>由采购申请生成供应商询价。</li>
        <li><b>第一步：</b>选择来源采购申请。</li>
        <li><b>第二步：</b>确认供应商候选。</li>
        <li><b>第三步：</b>发送询价。</li>
        <li><b>第四步：</b>接收报价。</li>
        <li><b>第五步：</b>进入核价。</li>
      </ol>
      <div class="guide-grid">
        <p><b>用途与角色</b><span>采购员核对采购申请来源并开展供应商询价。</span></p>
        <p><b>进入与区域</b><span>从 SCM 采购流程进入；依次查看来源、询价列表、物料与供应商。</span></p>
        <p><b>第一步</b><span>选择一条询价记录，确认来源采购申请、物料和数量一致。</span></p>
        <p><b>关键按钮</b><span>“刷新”重新读取当前模式事实；“进入核价”仅在报价已接收时可用。</span></p>
        <p><b>字段填写</b><span>当前页面为业务事实承接与查询区域，不在金丝雀模式写入字段。</span></p>
        <p><b>异常处理</b><span>来源缺失或报价未接收时停止流转，并按阻断信息返回上游处理。</span></p>
        <p><b>完成标准</b><span>询价编号、来源申请、物料、供应商与报价接收状态完整可追踪。</span></p>
        <p><b>下一步</b><span>报价接收完成后，由采购人员人工进入采购核价。</span></p>
      </div>
    </section>
    <section class="panel source-context" data-acceptance-region="source-purchase-request">
      <h2>来源采购申请</h2>
      <p class="source-help">选择已完成审批的采购申请，确认物料与供应商候选后，由采购人员显式生成询价。</p>
      <el-table v-if="dataMode==='production' && sourceRequests.length" :data="sourceRequests" size="small" border>
        <el-table-column prop="requestNo" label="来源申请编号" min-width="180" />
        <el-table-column prop="demandDepartment" label="需求部门" min-width="140" />
        <el-table-column prop="purchaseDepartment" label="采购部门" min-width="140" />
        <el-table-column prop="materialCount" label="物料数量" width="100" />
        <el-table-column prop="supplierCandidateCount" label="供应商数量" width="110" />
        <el-table-column prop="statusLabel" label="申请状态" width="110" />
        <el-table-column label="操作" fixed="right" width="130">
          <template #default="{row}"><el-button type="primary" link :loading="creatingRequestId===row.requestId"
            @click="createInquiry(row)">生成询价</el-button></template>
        </el-table-column>
      </el-table>
      <div v-if="current" class="facts-grid">
        <span>采购申请编号<strong>{{ current.sourceRequestNo || '未提供' }}</strong></span>
        <span>询价对象编号<strong>{{ current.inquiryNo || '未提供' }}</strong></span>
        <span>来源证据<strong>{{ evidenceLabel }}</strong></span>
        <span>数据来源<strong>server</strong></span>
      </div><el-empty v-else description="暂无可显示的来源采购申请" />
    </section>
    <section class="panel" data-acceptance-region="purchase-inquiry-list">
      <PceEnterpriseListTable ref="tableRef" :contract="enterpriseListContract" page-id="purchase-inquiry"
        table-id="purchase-inquiry-node-main" :rows="rows" :table-rows="filteredRows" :filter-schema="filterSchema"
        :filters="filters" :quick-search="quickSearch" :advanced-visible="advancedVisible"
        :selected-count="selectedRows.length" :active-filter-count="activeFilterCount" :sort-text="sortText"
        primary-field="inquiryNo" primary-label="询价编号" :primary-width="210" min-width="1450px"
        scroll-acceptance-id="purchase-inquiry-node-horizontal-scroll" :action-width="150"
        :action-contracts="SCM_PURCHASE_INQUIRY_LIST_ACTIONS" action-state-field="businessStatusCode"
        @row-action="handleRowAction"
        @update:quick-search="quickSearch=$event" @search="appliedSearch=quickSearch"
        @toggle-advanced="advancedVisible=!advancedVisible" @clear-filters="clearFilters" @clear-sort="clearSort"
        @export-current="exportCurrent" @clear-selection="clearSelection" @update-filter="(field,value)=>filters[field]=value"
        @selection-change="selectedRows=$event" @sort-change="handleSort">
        <template #columns><el-table-column prop="sourceRequestNo" label="来源采购申请" width="190" />
          <el-table-column prop="buyerName" label="采购员" width="140" /><el-table-column prop="lineCount" label="物料项数" width="110" />
          <el-table-column prop="supplierCount" label="供应商数量" width="120" />
          <el-table-column prop="supplierSendStatusLabel" label="供应商发送状态" width="150" />
          <el-table-column prop="quoteReceiveStatusLabel" label="报价接收状态" width="150" />
          <el-table-column label="业务状态" width="130"><template #default="{row}"><PceBusinessStatus
            :status-code="row.businessStatusCode" :status-label="row.businessStatusLabel" source="provider" /></template></el-table-column>
          <el-table-column label="流程状态" width="190"><template #default="{row}">{{row.processStatusLabel}}</template></el-table-column></template>
      </PceEnterpriseListTable>
    </section>
    <section class="panel" data-acceptance-region="material-supplier-decision"><h2>物料与供应商决策</h2>
      <el-empty v-if="!current" description="暂无询价对象" /><div v-else class="line-grid"><article v-for="line in current.lines||[]" :key="line.materialCode">
        <strong>{{line.materialCode}} · {{line.materialName}}</strong><p>数量：{{line.quantity}}　需求日期：{{line.requiredDate||'未提供'}}</p>
        <p>供应商候选：{{(line.supplierCandidates||current.suppliers||[]).map(item=>item.supplierName||item.name).join('、')||'未选择'}}</p></article></div>
    </section>
    <section class="panel next" data-acceptance-region="next-action"><div><span>当前节点</span><strong>采购询价</strong></div>
      <div><span>下一节点</span><strong>核价</strong></div><el-button type="primary" :disabled="!priceApprovalEntryAllowed"
        :title="priceApprovalEntryAllowed?'进入采购核价':'必须先完成询价审批并接收报价'" @click="enterPriceApproval">进入核价</el-button></section>
  </main>
</template>

<script setup>
import { computed,onMounted,ref,watch } from 'vue';import { useRoute,useRouter } from 'vue-router';import { ElMessage } from 'element-plus'
import PceBusinessStatus from '@/meta/components/PceBusinessStatus.vue';import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import { createPceEnterpriseListContract,usePceEnterpriseListRuntime } from '@/meta/runtime/pceEnterpriseListContract.js';import { purchaseInquiryProvider } from '@/meta/providers/purchaseInquiryProvider.js'
import { resolvePageNameConsumption } from '@/meta/governance/pageNameConsumer.js'
import { createUnifiedFilterSchema } from '@/meta/runtime/unifiedFilterSchema.js'
import { createRemoteSelectOptionsProvider } from '@/meta/runtime/remoteSelectOptionsProvider.js'
import { SCM_PURCHASE_INQUIRY_LIST_ACTIONS } from '@/meta/process/scm/scmUnifiedListActionContractsV1142813.js'
const route=useRoute();const router=useRouter();const facts=ref({existingInquiryList:[],dataMode:'production'});const loading=ref(false);const loadError=ref('');let loadGeneration=0
const rows=computed(()=>facts.value.existingInquiryList||[]);const sourceRequests=computed(()=>facts.value.eligibleSourceRequests||[]);const current=computed(()=>selectedRows.value.at(-1)||rows.value.at(-1)||null);const creatingRequestId=ref(null)
const dataMode=computed(()=>facts.value.dataMode||'production')
const evidenceLabel=computed(()=>current.value?.sourceEvidence?.sourceEvidenceHash||current.value?.sourceEvidence?.sourceRequestNo||'未提供')
const priceApprovalEntryAllowed=computed(()=>current.value?.quoteReceiveStatus==='received'&&current.value?.supplierSendStatus==='sent')
const pageName=resolvePageNameConsumption({pageCode:'purchase-inquiry',route:'/scm/purchase-inquiry'})
const optionsProvider=createRemoteSelectOptionsProvider({providerCode:'SCM_PURCHASE_INQUIRY_FILTER_OPTIONS'})
const filterFields=Object.freeze([
  {field:'inquiryNo',label:'询价编号',type:'remote-select',optionsProvider},
  {field:'sourceRequestNo',label:'采购申请编号',type:'remote-select',optionsProvider},
  {field:'buyerName',label:'采购员',type:'select',optionsSource:'current_result'},
  {field:'businessStatusCode',label:'业务状态',type:'select',options:[{label:'草稿',value:'draft'}]},
  {field:'processStatusCode',label:'流程状态',type:'select',options:[{label:'询价草稿',value:'inquiry_draft'},{label:'已进入供应商报价准备',value:'quote_preparation_ready'}]},
])
const filterSchema=createUnifiedFilterSchema({filterFields,optionsProvider})
const enterpriseListContract=createPceEnterpriseListContract({pageCode:'purchase-inquiry',pageType:'list',title:pageName.pageTitle,moduleCode:'SCM_PURCHASE_INQUIRY'})
const {selectedRows,quickSearch,appliedSearch,advancedVisible,filters,tableRef,activeFilterCount,sortText,filteredRows,clearFilters,clearSort,clearSelection,handleSort,exportCurrent}=usePceEnterpriseListRuntime({rows,filterSchema,pageCode:'purchase-inquiry',searchFields:['inquiryNo','sourceRequestNo','buyerName'],exportFileName:'purchase-inquiries.csv',exportColumns:[{field:'inquiryNo',label:'询价编号'},{field:'sourceRequestNo',label:'来源采购申请'}]})
async function refresh(){
  const generation=++loadGeneration;loading.value=true;loadError.value=''
  try{const result=await purchaseInquiryProvider.loadRuntime({query:{...route.query}});if(generation===loadGeneration)facts.value=result}
  catch(error){if(generation===loadGeneration){facts.value={existingInquiryList:[],dataMode:route.query.canaryBatchId?'canary_acceptance':'production'};loadError.value=error?.message||'采购询价读取失败'}}
  finally{if(generation===loadGeneration)loading.value=false}
}
async function createInquiry(row){
  if(dataMode.value!=='production'||creatingRequestId.value)return
  creatingRequestId.value=row.requestId
  try{const result=await purchaseInquiryProvider.createFromApprovedRequest(row.requestId);ElMessage.success(result.created?'询价已生成':'该采购申请已存在询价');await refresh()}
  catch(error){ElMessage.error(error?.message||'采购询价生成失败')}
  finally{creatingRequestId.value=null}
}
function enterPriceApproval(){if(priceApprovalEntryAllowed.value)router.push('/scm/price-approvals')}
function diagnostics(){return{version:'V1.14.2.8.4.21-R1',pageCode:'purchase-inquiry',pageComponent:'ScmPurchaseInquiryNodePage',businessObject:'PurchaseInquiry',dataMode:dataMode.value,providerCode:facts.value.providerCode||'',productionApiCallCount:facts.value.productionApiCallCount||0,canaryApiCallCount:facts.value.canaryApiCallCount||0,recordCount:rows.value.length,eligibleSourceRequestCount:sourceRequests.value.length,sourceRequestNo:current.value?.sourceRequestNo||'',inquiryNo:current.value?.inquiryNo||'',productionUserDataWritten:false,purchaseOrderCreated:false}}
defineExpose({diagnostics,refresh})
watch(()=>[route.query.canaryBatchId,route.query.scenarioCode],refresh)
onMounted(refresh)
function handleRowAction(action,row){
  if(action.actionCode==='VIEW_PURCHASE_INQUIRY')router.push(`/scm/purchase-inquiry/detail/${row.inquiryNo}`)
  if(action.actionCode==='EDIT_PURCHASE_INQUIRY')router.push(`/scm/purchase-inquiry/edit/${row.inquiryNo}`)
}
</script>
<style scoped>.node-page{display:grid;gap:18px;padding:20px}.page-heading,.next,.mode-banner{display:flex;align-items:center;justify-content:space-between;gap:16px}.page-heading h1{margin:4px 0}.page-heading p,.page-heading span,.next span{color:#64748b}.mode-banner{padding:12px 16px;border:1px solid #bfdbfe;border-radius:10px;background:#eff6ff;color:#1e3a8a}.panel{padding:18px;border:1px solid #dbe4ee;border-radius:12px;background:#fff}.guide-grid,.facts-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px}.guide-grid p,.facts-grid span{display:grid;gap:5px;margin:0;padding:12px;border-radius:9px;background:#f8fafc}.guide-grid span{color:#475569}.facts-grid strong{color:#0f172a;overflow-wrap:anywhere}.line-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}.line-grid article{padding:14px;border:1px solid #e2e8f0;border-radius:10px}.next div{display:grid;gap:5px}@media(max-width:800px){.page-heading,.next,.mode-banner{align-items:flex-start;flex-direction:column}}</style>
