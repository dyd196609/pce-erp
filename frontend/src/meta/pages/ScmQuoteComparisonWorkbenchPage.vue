<template>
  <section v-if="nativeMode"><ScmNativeQuoteRegistrationPanel mode="comparison" /><router-link :to="{path:route.path,query:{preview:'local'}}">查看本地预览（未正式登记）</router-link></section>
  <main v-else class="quote-comparison-page" data-page-code="quote-comparison-workbench"
    :data-page-name="businessName.pageTitle" data-module-code="SCM" data-business-object="QuoteComparison"
    :data-mode="dataMode" :data-source="route.query.preview==='local'?'local_preview':(providerFacts.source || '')"
    :data-fact-load-status="providerFacts.factLoadStatus || 'loading'"
    :data-production-consistency="dataMode==='production' && productionAcceptance.productionDataConsistent ? 'pass' : 'blocked'">
    <header class="page-heading"><div><p class="eyebrow">SCM · 采购报价</p><h1>{{ businessName.pageTitle }}</h1>
      <p>按物料并列展示供应商报价和最低报价，不做供应商推荐、智能分析或复杂评分。</p></div>
      <el-button @click="refreshFacts">刷新</el-button></header>
    <section class="panel mode-banner" data-acceptance-region="runtime-mode">
      <strong>运行模式：{{ dataMode }}</strong>
      <span v-if="dataMode==='canary_acceptance'">批次 {{ providerFacts.canaryBatchId }} · 场景 {{ providerFacts.scenarioCode }}</span>
      <span v-else>本地预览，未正式登记；当前预览 {{ providerFacts.resultCount || 0 }} 条 · 状态 {{ providerFacts.factLoadStatus || 'loading' }}</span>
    </section>
    <el-alert v-if="providerFacts.loadError" type="error" :closable="false" show-icon
      title="报价比较事实读取失败" :description="providerFacts.loadError" />
    <section class="panel" data-acceptance-region="page-operation-guide" data-guide-contract="GUIDE-001..010">
      <h2>页面操作指引</h2>
      <ol>
        <li><b>用途：</b>比较供应商报价，为后续核价准备依据。</li>
        <li><b>第一步：</b>查看报价来源。</li>
        <li><b>第二步：</b>确认供应商报价。</li>
        <li><b>第三步：</b>比较价格。</li>
        <li><b>第四步：</b>确认比较结果。</li>
        <li><b>第五步：</b>进入核价准备。</li>
      </ol>
      <p>“进入核价准备”只提供页面入口，不创建 PriceApproval、不推荐最终供应商、不生成采购订单。</p>
    </section>
    <section class="panel chain-panel" data-acceptance-region="business-chain">
      <h2>业务链信息</h2>
      <div><span>来源询价</span><strong>{{ currentRow?.sourceInquiryNo || currentRow?.sourceInquiryId || '—' }}</strong></div>
      <div><span>来源报价</span><strong>{{ sourceQuotationText }}</strong></div>
      <div><span>当前比较</span><strong>{{ currentRow?.quoteComparisonId || '—' }}</strong></div>
      <div><span>数据连续性</span><strong>{{ dataMode==='production' ? '本地预览，非正式事实' : '金丝雀只读隔离' }}</strong></div>
    </section>
    <section class="panel" data-acceptance-region="quote-comparison-list">
      <div class="section-heading"><div><h2>报价比较列表</h2><p>数据来源：已完成收集的供应商报价。</p></div></div>
      <PceEnterpriseListTable ref="tableRef" :contract="enterpriseListContract"
        page-id="quote-comparison-workbench" table-id="quote-comparison-main"
        :rows="displayRows" :table-rows="filteredRows" :filter-schema="filterSchema" :filters="filters"
        :quick-search="quickSearch" :advanced-visible="advancedVisible" :selected-count="selectedRows.length"
        :active-filter-count="activeFilterCount" :sort-text="sortText" primary-field="materialName"
        primary-label="物料" :primary-width="190" :min-width="columnRuntime.minWidth"
        scroll-acceptance-id="quote-comparison-horizontal-scroll"
        :action-contracts="SCM_QUOTE_COMPARISON_LIST_ACTIONS" action-state-field="comparisonStatus"
        @row-action="handleRowAction"
        @update:quick-search="quickSearch=$event" @search="appliedSearch=quickSearch"
        @toggle-advanced="advancedVisible=!advancedVisible" @clear-filters="clearFilters"
        @clear-sort="clearSort" @export-current="exportCurrent" @clear-selection="clearSelection"
        @update-filter="(field,value)=>filters[field]=value" @selection-change="selectedRows=$event"
        @sort-change="handleSort">
        <template #columns>
          <el-table-column prop="materialCode" label="物料编码" min-width="150" />
          <el-table-column prop="quantity" label="数量" width="110" />
          <el-table-column v-for="column in columnRuntime.dynamicGroups.flatMap(group=>group.columns)"
            :key="column.field" :prop="column.field" :label="column.label"
            :width="column.width" :min-width="column.minWidth" />
          <el-table-column prop="lowestQuoteLabel" label="最低报价" width="130" />
          <el-table-column prop="comparisonStatusLabel" label="比较状态" min-width="140" />
        </template>
      </PceEnterpriseListTable>
    </section>
    <section class="panel next-panel" data-acceptance-region="next-action">
      <div><span>当前节点</span><strong>报价比较</strong></div><div><span>当前状态</span><strong>{{ providerFacts.recordCount ? '比较完成' : '等待供应商报价' }}</strong></div>
      <div><span>下一节点</span><strong>采购核价准备</strong></div>
      <el-button type="primary" :disabled="!providerFacts.recordCount||dataMode!=='production'"
        title="仅进入采购核价准备页面，不创建核价对象" @click="router.push('/scm/price-approval')">进入采购核价准备</el-button>
    </section>
  </main>
</template>
<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import ScmNativeQuoteRegistrationPanel from '../components/ScmNativeQuoteRegistrationPanel.vue'
import { useRoute, useRouter } from 'vue-router'
import { resolveBusinessName } from '@/meta/governance/businessNameRegistry.js'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import { createPceEnterpriseListContract, usePceEnterpriseListRuntime } from '@/meta/runtime/pceEnterpriseListContract.js'
import { quoteComparisonSimpleProvider } from '@/meta/providers/quoteComparisonSimpleProviderV11428121.js'
import { SCM_QUOTE_COMPARISON_LIST_ACTIONS } from '@/meta/process/scm/scmUnifiedListActionContractsV1142813.js'
import { createUnifiedFilterSchema } from '@/meta/runtime/unifiedFilterSchema.js'
import { createRemoteSelectOptionsProvider } from '@/meta/runtime/remoteSelectOptionsProvider.js'
import { createPceTableColumnRuntime, createSupplierComparisonColumnGroups } from '@/meta/runtime/pceTableColumnRuntime.js'
import { adaptQuoteComparisonProductionFacts } from '@/meta/acceptance/quoteComparisonProductionAcceptanceAdapterV11428423R2.js'
const businessName=resolveBusinessName('quote-comparison'); const router=useRouter(); const route=useRoute()
const nativeMode=computed(()=>!(route.query.canaryBatchId&&route.query.scenarioCode)&&route.query.preview!=='local')
const providerFacts=ref({records:[],recordCount:0,dataMode:'production'})
const dataMode=computed(()=>route.query.preview==='local'?'local_preview_not_registered':(providerFacts.value.dataMode||'production'))
const productionAcceptance=computed(()=>adaptQuoteComparisonProductionFacts(providerFacts.value))
const currentRow=computed(()=>providerFacts.value.current||providerFacts.value.records?.at(-1)||null)
const sourceQuotationText=computed(()=>{const row=currentRow.value||{};const values=row.sourceQuotationNos
  ||row.supplierQuotes?.map(item=>item.quotationNo).filter(Boolean)||[];return values.length?values.join('、'):'—'})
const supplierColumnCount=computed(()=>Math.max(3,...(providerFacts.value.records||[]).map(row=>row.supplierQuotes?.length||0)))
const columnRuntime=computed(()=>createPceTableColumnRuntime({baseReservedWidth:850,
  dynamicGroups:createSupplierComparisonColumnGroups(supplierColumnCount.value),widthPolicy:'wide'}))
const displayRows=computed(()=>(providerFacts.value.records||[]).map(row=>{const projected={...row,
  supplierCodes:(row.supplierQuotes||[]).map(item=>item.supplierCode),lowestQuoteLabel:Number(row.lowestQuote).toFixed(2),
  comparisonStatusLabel:row.comparisonStatusLabel||'比较完成'}
  ;(row.supplierQuotes||[]).forEach((item,index)=>{projected[`supplierName${index+1}`]=`${item.supplierName}（${item.supplierCode}）`;projected[`supplierPrice${index+1}`]=Number(item.quotePrice).toFixed(2)})
  return projected}))
const optionsProvider=createRemoteSelectOptionsProvider({providerCode:'SCM_QUOTE_COMPARISON_FILTER_OPTIONS'})
const filterFields=Object.freeze([{field:'sourceInquiryId',label:'询价编号',type:'remote-select',optionsProvider},
  {field:'materialCode',label:'物料编码',type:'remote-select',optionsProvider},
  {field:'supplierCodes',label:'供应商',type:'remote-select',optionsProvider},
  {field:'comparisonStatus',label:'比较状态',type:'select',optionsSource:'QuoteComparisonStateContract',options:[{label:'比较完成',value:'comparison_completed'}]}])
const filterSchema=createUnifiedFilterSchema({filterFields,optionsProvider})
const enterpriseListContract=createPceEnterpriseListContract({pageCode:'quote-comparison-workbench',pageType:'list',title:businessName.pageTitle,moduleCode:'SCM_QUOTE_COMPARISON'})
const supplierSearchFields=columnRuntime.value.dynamicGroups.flatMap(group=>group.columns.map(column=>column.field))
const {selectedRows,quickSearch,appliedSearch,advancedVisible,filters,tableRef,activeFilterCount,sortText,filteredRows,clearFilters,clearSort,clearSelection,handleSort,exportCurrent}=usePceEnterpriseListRuntime({rows:displayRows,filterSchema,pageCode:'quote-comparison-workbench',searchFields:['sourceInquiryId','materialCode','materialName',...supplierSearchFields],exportFileName:'quote-comparisons.csv',exportColumns:[{field:'sourceInquiryId',label:'询价编号'},{field:'materialCode',label:'物料编码'},{field:'materialName',label:'物料名称'},...columnRuntime.value.dynamicGroups.flatMap(group=>group.columns.map(column=>({field:column.field,label:column.label}))),{field:'lowestQuoteLabel',label:'最低报价'},{field:'comparisonStatusLabel',label:'比较状态'}]})
async function refreshFacts(){if(nativeMode.value)return;const query={...route.query};const isCanary=Boolean(query.canaryBatchId&&query.scenarioCode)
  try{providerFacts.value=await quoteComparisonSimpleProvider.loadRuntime({query})}
  catch(error){providerFacts.value={records:[],recordCount:0,dataMode:isCanary?'canary_acceptance':'production',
    rows:[],resultCount:0,source:isCanary?'canary':'production',
    canaryBatchId:query.canaryBatchId||'',scenarioCode:query.scenarioCode||'',loadError:error?.message||String(error),
    factLoadStatus:'read_failed',
    productionUserDataWritten:false,priceApprovalCreated:false,purchaseOrderCreated:false}}
} onMounted(refreshFacts)
function handleRowAction(action){if(action.actionCode==='OPEN_PRICE_APPROVAL_PREPARATION'&&dataMode.value==='production')router.push('/scm/price-approval')}
watch(()=>[route.query.canaryBatchId,route.query.scenarioCode,route.query.preview],refreshFacts)
</script>
<style scoped>
.quote-comparison-page{display:grid;gap:18px;padding:20px;width:100%;min-width:0;max-width:100%}.page-heading,.section-heading{display:flex;align-items:center;justify-content:space-between;gap:18px;min-width:0}.page-heading h1,.section-heading h2{margin:0}.page-heading p,.section-heading p{margin:6px 0 0;color:#64748b}.eyebrow{font-weight:700;color:#2563eb!important}.panel{padding:18px;border:1px solid #dbe4ee;border-radius:12px;background:#fff;min-width:0;max-width:100%}.next-panel{display:grid;grid-template-columns:repeat(3,minmax(0,1fr)) auto;align-items:center;gap:14px}.next-panel div{display:grid;gap:6px}.next-panel span{font-size:12px;color:#64748b}@media(max-width:800px){.page-heading,.section-heading{align-items:flex-start;flex-direction:column}.next-panel{grid-template-columns:1fr}}
.mode-banner{display:flex;align-items:center;justify-content:space-between;gap:18px}.chain-panel{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.chain-panel h2{grid-column:1/-1;margin:0}.chain-panel div{display:grid;gap:5px;padding:12px;background:#f8fafc;border-radius:8px}.chain-panel span{font-size:12px;color:#64748b}@media(max-width:800px){.chain-panel{grid-template-columns:1fr}.mode-banner{align-items:flex-start;flex-direction:column}}
</style>
