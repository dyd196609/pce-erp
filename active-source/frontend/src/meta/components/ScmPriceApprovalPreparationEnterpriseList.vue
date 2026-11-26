<template>
  <PceEnterpriseListTable ref="tableRef" :contract="enterpriseListContract"
    page-id="price-approval" table-id="price-approval-preparation-main"
    :rows="rows" :table-rows="filteredRows" :filter-schema="filterSchema" :filters="filters"
    :quick-search="quickSearch" :advanced-visible="advancedVisible" :selected-count="selectedRows.length"
    :active-filter-count="activeFilterCount" :sort-text="sortText" primary-field="inquiryNo"
    primary-label="询价编号" :primary-width="190" min-width="1420px"
    scroll-acceptance-id="price-approval-horizontal-scroll"
    :action-contracts="SCM_PRICE_APPROVAL_LIST_ACTIONS" action-state-field="preparationStatus"
    @row-action="handleRowAction"
    @update:quick-search="quickSearch=$event" @search="appliedSearch=quickSearch"
    @toggle-advanced="advancedVisible=!advancedVisible" @clear-filters="clearFilters"
    @clear-sort="clearSort" @export-current="exportCurrent" @clear-selection="clearSelection"
    @update-filter="(field,value)=>filters[field]=value" @selection-change="selectedRows=$event"
    @sort-change="handleSort">
    <template #columns>
      <el-table-column prop="sourceRequestNo" label="来源采购申请" min-width="180" />
      <el-table-column prop="materialCode" label="物料编码" min-width="150" />
      <el-table-column prop="materialName" label="物料名称" min-width="180" />
      <el-table-column prop="supplierCode" label="供应商编码" min-width="150" />
      <el-table-column prop="supplierName" label="供应商" min-width="180" />
      <el-table-column prop="materialPriceContextTypeLabel" label="物料核价类型" min-width="140" />
      <el-table-column prop="historicalLowestPurchasePriceLabel" label="历史最低采购价" min-width="150" />
      <el-table-column prop="historicalPurchasePriceLabel" label="历史采购价（最近）" min-width="160" />
      <el-table-column prop="lastPurchaseDateLabel" label="最近采购日期" min-width="150" />
      <el-table-column prop="historicalPurchaseCountLabel" label="历史采购次数" min-width="140" />
      <el-table-column prop="currentQuoteLabel" label="当前报价" min-width="130" />
      <el-table-column prop="priceChangeRatioLabel" label="价格变化比例" min-width="150" />
      <el-table-column prop="preparationStatusLabel" label="核价准备状态" min-width="190" />
    </template>
  </PceEnterpriseListTable>
  <section class="batch-recommendation-action" data-acceptance-id="supplier-recommendation-batch-entry">
    <div>
      <h3>供应商推荐任务交接</h3>
      <p>已选择 {{ selectedRows.length }} 条核价记录；本次选择统一形成一个推荐决策批次，并按物料编码生成独立决策项。</p>
    </div>
    <el-button type="primary" data-process-action="BATCH_OPEN_SUPPLIER_RECOMMENDATION"
      :disabled="!selectedRows.length" @click="openBatchSupplierRecommendation">
      批量进入供应商推荐
    </el-button>
  </section>
  <section class="material-price-reference" data-acceptance-id="material-price-reference-region"
    data-read-only="true">
    <h3>价格参考信息</h3>
    <el-alert title="价格参考仅提供采购证据，最终核价决策由采购人员完成。"
      type="info" :closable="false" show-icon />
    <el-empty v-if="!sourceRows.length" description="暂无核价参考数据" />
    <el-collapse v-else>
      <el-collapse-item v-for="(row,index) in sourceRows"
        :key="`${row.inquiryNo}-${row.materialCode}-${row.supplierCode}-${index}`"
        :name="`${row.materialCode}-${row.supplierCode}-${index}`">
        <template #title>
          <span>{{ row.materialName }}（{{ row.materialCode }}） · {{ row.supplierName || row.supplierCode }}</span>
          <el-tag class="material-price-reference__tag" size="small" effect="plain">
            {{ row.materialPriceContextTypeLabel }}
          </el-tag>
        </template>
        <template v-if="row.materialPriceContextType === 'new_material'">
          <el-alert title="暂无历史价格参考" type="warning" :closable="false" show-icon />
          <el-descriptions :column="2" border>
            <el-descriptions-item label="供应商报价">{{ row.currentQuoteLabel }}</el-descriptions-item>
            <el-descriptions-item label="报价比较结果">{{ formatComparisonResult(row.comparisonResult) }}</el-descriptions-item>
            <el-descriptions-item label="供应商基本信息">{{ row.supplierName || row.supplierCode || '-' }}</el-descriptions-item>
            <el-descriptions-item label="采购人员核价意见">{{ row.manualAssessment || '待采购人员填写' }}</el-descriptions-item>
          </el-descriptions>
        </template>
        <template v-else>
          <el-descriptions :column="3" border>
            <el-descriptions-item label="历史最低采购价">{{ row.historicalLowestPurchasePriceLabel }}</el-descriptions-item>
            <el-descriptions-item label="最近采购价格">{{ row.historicalPurchasePriceLabel }}</el-descriptions-item>
            <el-descriptions-item label="最近采购日期">{{ row.lastPurchaseDateLabel }}</el-descriptions-item>
            <el-descriptions-item label="历史采购次数">{{ row.historicalPurchaseCountLabel }}</el-descriptions-item>
            <el-descriptions-item label="当前报价">{{ row.currentQuoteLabel }}</el-descriptions-item>
            <el-descriptions-item label="价格变化比例">{{ row.priceChangeRatioLabel }}</el-descriptions-item>
            <el-descriptions-item label="证据来源">{{ row.priceChangeEvidence?.evidenceSource || 'PurchaseOrderHistory' }}</el-descriptions-item>
          </el-descriptions>
          <el-table :data="row.historicalPriceList" size="small" border>
            <el-table-column prop="purchaseDate" label="采购日期" min-width="150" />
            <el-table-column prop="purchasePrice" label="采购价格" min-width="130" />
            <el-table-column prop="supplierCode" label="供应商编码" min-width="150" />
            <el-table-column prop="supplierName" label="供应商" min-width="180" />
            <el-table-column prop="evidenceSource" label="证据来源" min-width="180" />
          </el-table>
        </template>
      </el-collapse-item>
    </el-collapse>
  </section>
  <el-dialog v-model="evidenceVisible" title="报价依据" width="560px">
    <el-descriptions v-if="selectedEvidence" :column="1" border>
      <el-descriptions-item label="询价编号">{{ selectedEvidence.inquiryNo }}</el-descriptions-item>
      <el-descriptions-item label="物料">{{ selectedEvidence.materialName }}（{{ selectedEvidence.materialCode }}）</el-descriptions-item>
      <el-descriptions-item label="供应商">{{ selectedEvidence.supplierName }}</el-descriptions-item>
      <el-descriptions-item label="报价金额">{{ selectedEvidence.quotePrice }}</el-descriptions-item>
    </el-descriptions>
  </el-dialog>
</template>
<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import { createPceEnterpriseListContract, usePceEnterpriseListRuntime } from '@/meta/runtime/pceEnterpriseListContract.js'
import { SCM_PRICE_APPROVAL_LIST_ACTIONS } from '@/meta/process/scm/scmUnifiedListActionContractsV1142813.js'
import { createUnifiedFilterSchema } from '@/meta/runtime/unifiedFilterSchema.js'
import { createRemoteSelectOptionsProvider } from '@/meta/runtime/remoteSelectOptionsProvider.js'
import { priceReferenceProvider } from '@/meta/providers/priceReferenceProvider.js'
import { executeSupplierRecommendationDecisionBatchEntryV11428169 } from '@/meta/process/scm/supplierRecommendation/supplierRecommendationDecisionBatchV11428169.js'
import { supplierRecommendationRouteContextResolverV11428171 } from '@/meta/process/scm/supplierRecommendation/supplierRecommendationRouteContextResolverV11428171.js'
const props=defineProps({rows:{type:Array,default:()=>[]}})
const sourceRows=computed(()=>priceReferenceProvider.load({currentQuotes:props.rows||[]}).records.map(row=>({ ...row,
  id:`${row.priceApprovalId||row.priceApprovalNo}::${row.quoteComparisonId}::${row.materialCode}::${row.supplierCode}`,
  materialPriceContextTypeLabel:row.materialPriceContextType==='existing_material'?'老物料':'新物料',
  historicalLowestPurchasePriceLabel:row.historicalLowestPurchasePrice==null?'暂无参考':Number(row.historicalLowestPurchasePrice).toFixed(2),
  historicalPurchasePriceLabel:row.historicalPurchasePrice==null?'暂无参考':Number(row.historicalPurchasePrice).toFixed(2),
  historicalPurchaseCountLabel:row.historicalPurchaseCount?String(row.historicalPurchaseCount):'0',
  lastPurchaseDateLabel:row.lastPurchaseDate||'暂无参考', currentQuoteLabel:row.currentQuote==null?'-':Number(row.currentQuote).toFixed(2),
  priceChangeRatioLabel:row.priceChangeRatio==null?'暂无参考':`${(row.priceChangeRatio*100).toFixed(2)}%` })))
const router=useRouter()
const optionsProvider=createRemoteSelectOptionsProvider({providerCode:'SCM_PRICE_APPROVAL_FILTER_OPTIONS'})
const filterFields=Object.freeze([{field:'inquiryNo',label:'询价编号',type:'remote-select',optionsProvider},
  {field:'sourceRequestNo',label:'来源采购申请',type:'remote-select',optionsProvider},
  {field:'materialCode',label:'物料编码',type:'select',optionsSource:'current_result'},
  {field:'preparationStatus',label:'核价准备状态',type:'select',optionsSource:'PriceApprovalStateContract',options:[{label:'已进入采购核价准备',value:'price_approval_preparation_ready'}]}])
const filterSchema=createUnifiedFilterSchema({filterFields,optionsProvider})
const enterpriseListContract=createPceEnterpriseListContract({pageCode:'price-approval',pageType:'list',title:'核价准备',moduleCode:'SCM_PRICE_APPROVAL'})
const {selectedRows,quickSearch,appliedSearch,advancedVisible,filters,tableRef,activeFilterCount,sortText,filteredRows,clearFilters,clearSort,clearSelection,handleSort,exportCurrent}=usePceEnterpriseListRuntime({rows:sourceRows,filterSchema,pageCode:'price-approval',searchFields:['inquiryNo','sourceRequestNo','materialCode','materialName','supplierCode','supplierName'],exportFileName:'price-approval-preparations.csv',exportColumns:[{field:'inquiryNo',label:'询价编号'},{field:'sourceRequestNo',label:'来源采购申请'},{field:'materialCode',label:'物料编码'},{field:'supplierCode',label:'供应商编码'},{field:'quotePrice',label:'报价金额'},{field:'preparationStatusLabel',label:'核价准备状态'}]})
const evidenceVisible=ref(false); const selectedEvidence=ref(null)
function createHandoffInput(row){
  const candidates=sourceRows.value.filter(item=>item.priceApprovalId===row.priceApprovalId
    && item.quoteComparisonId===row.quoteComparisonId && item.materialCode===row.materialCode)
  return {
    priceApprovalId:row.priceApprovalId,priceApprovalNo:row.priceApprovalNo||row.priceApprovalId,
    quoteComparisonId:row.quoteComparisonId,
    sourceInquiryNo:row.inquiryNo,sourceRequestNo:row.sourceRequestNo,
    materialCode:row.materialCode,materialName:row.materialName,
    supplierCandidates:candidates.map(item=>({supplierCode:item.supplierCode,supplierName:item.supplierName,
      quotePrice:item.currentQuote,priceRank:item.priceRank,comparisonResult:item.comparisonResult})),
    priceEvidence:candidates.map(item=>({supplierCode:item.supplierCode,currentPrice:item.currentQuote,
      priceRank:item.priceRank,evidenceSource:'QuoteComparison'})),
    historicalPriceEvidence:candidates.map(item=>({supplierCode:item.supplierCode,
      priceReferenceContext:item.priceReferenceContext,priceChangeEvidence:item.priceChangeEvidence})),
    priceReferenceRecords:candidates,
  }
}
function handleRowAction(action,row){
  if(action.actionCode==='VIEW_PRICE_APPROVAL'){selectedEvidence.value=row;evidenceVisible.value=true}
  if(action.actionCode==='OPEN_SUPPLIER_RECOMMENDATION'){
    // V16.1 persistence contract remains inside executePriceApprovalSupplierRecommendationHandoffV11428161,
    // which is invoked by the V16.7 task entry service before navigation.
    const result=executeSupplierRecommendationDecisionBatchEntryV11428169([createHandoffInput(row)])
    if(result.result!=='PASS')return ElMessage.error(result.error||'核价事实未完成，不能进入供应商推荐')
    ElMessage.success('核价与价格证据已交接至供应商推荐')
    // V16.3/V16.6 compatibility trace: priceApprovalId:row.priceApprovalId,
    // quoteComparisonId:row.quoteComparisonId, materialCode:row.materialCode,
    // runtimeContextId:result.handoff.runtimeContext.runtimeContextNo.
    // V16.7 compatibility trace: taskId:result.task.taskId remains an internal item binding.
    const context=supplierRecommendationRouteContextResolverV11428171.activate(result.activeBatch.batchId)
    if(context.result!=='PASS')return ElMessage.error(context.error||'供应商推荐上下文恢复失败')
    router.push(context.pageRoute)
  }
}
function openBatchSupplierRecommendation(){
  // V16.4 compatibility trace: executeSupplierRecommendationBatchHandoffV11428164
  // was superseded; navigation formerly used runtimeContextId:firstBatch.runtimeContextIds[0].
  // V16.5 compatibility trace: executeSupplierRecommendationBatchSplitV11428165.
  const result=executeSupplierRecommendationDecisionBatchEntryV11428169(
    selectedRows.value.map(createHandoffInput))
  if(result.result!=='PASS')return ElMessage.error(result.error||'批量核价交接未完成')
  const firstBatch=result.decisionBatches[0]
  ElMessage.success(`已形成 ${result.decisionBatches.length} 个采购推荐决策批次、${result.taskCount} 个物料项`)
  // V16.5 navigation was firstBatch.tasks[0].runtimeContextId; V16.7 routes by TaskId only.
  // V16.7 compatibility trace: taskId:result.recommendationTasks[0].taskId is no longer a page entry.
  const context=supplierRecommendationRouteContextResolverV11428171.activate(firstBatch.batchId)
  if(context.result!=='PASS')return ElMessage.error(context.error||'供应商推荐上下文恢复失败')
  router.push(context.pageRoute)
}
function formatComparisonResult(value){
  if(value==null||value==='')return '暂无比较结论'
  if(typeof value==='object')return value.summary||value.label||JSON.stringify(value)
  return String(value)
}
</script>
<style scoped>
.batch-recommendation-action{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-top:16px;padding:16px;border:1px solid #dbe4ee;border-radius:10px;background:#fff}
.batch-recommendation-action h3{margin:0 0 6px}.batch-recommendation-action p{margin:0;color:#64748b}
.material-price-reference{margin-top:16px}.material-price-reference h3{margin:0 0 12px}
.material-price-reference .el-alert{margin-bottom:12px}.material-price-reference__tag{margin-left:10px}
</style>
