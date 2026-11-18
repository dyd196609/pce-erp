<template>
  <section class="native-quote-panel" :data-native-quote-mode="mode" :data-fact-load-status="loadState">
    <div class="native-heading"><h2>{{ title }}</h2><el-button :loading="loadState==='loading'" @click="reload">刷新正式事实</el-button>
      <el-button :data-process-action="navigation.actionCode" @click="router.push(navigation.nextRoute)">{{ navigation.actionName }}</el-button></div>
    <details><summary>操作说明</summary><p v-if="mode==='comparison'">先核对原询价和申请行，再读取登记依据。只有服务端确认具备原采购员登记资格时，才能明确登记并生成待核价准备。本地预览不是正式登记。</p>
      <p v-else>此处读取原授权范围的核价准备及其准确比较版本。采购员的登记回执不授予准备列表读取权。</p>
      <p>登记不选择供应商、不批准价格或采购订单。初始回执与当前状态分别查看；准备审核只采用服务端对当前准确版本提供的动作。</p></details>
    <p v-if="loadState==='loading'" role="status">正在读取正式事实，数量尚未取得。</p>
    <el-alert v-if="loadError" :title="loadError.message" type="error" :closable="false" show-icon />
    <p v-if="count!==null">本授权范围服务端总量 {{ count }} 条；本次提供 {{ records.length }} 条，各版本分别保留。<span v-if="count>records.length">原接口有返回上限，未返回的记录不计为本页已展示。</span></p>
    <p v-if="mode==='preparation'">历史来源证明未建立的准备仍为来源待核，未补造关联。本次登记不提供核价审核资格。</p>
    <PceEnterpriseListTable v-if="records!==null" ref="tableRef" :contract="listContract" :page-id="pageId" :table-id="`${pageId}-native`"
      :rows="rows" :table-rows="filteredRows" :filter-schema="filterSchema" :filters="filters" :quick-search="quickSearch"
      :advanced-visible="advancedVisible" :selected-count="selectedRows.length" :active-filter-count="activeFilterCount" :sort-text="sortText"
      primary-field="displayNo" :primary-label="mode==='comparison'?'正式比较编号':'核价准备编号'" :primary-width="230" min-width="1500px"
      :action-contracts="NATIVE_QUOTE_VIEW_ACTIONS" action-state-field="statusCode" data-source-mode="production"
      @row-action="(_action,row)=>selected=row" @update:quick-search="quickSearch=$event" @search="appliedSearch=quickSearch"
      @toggle-advanced="advancedVisible=!advancedVisible" @clear-filters="clearFilters" @clear-sort="clearSort" @export-current="exportCurrent"
      @clear-selection="clearSelection" @update-filter="(field,value)=>filters[field]=value" @selection-change="selectedRows=$event" @sort-change="handleSort">
      <template #columns>
        <el-table-column prop="displayVersion" label="比较版本" width="115" />
        <el-table-column prop="sourceInquiryNo" label="来源询价编号" min-width="190" />
        <el-table-column v-if="mode==='comparison'" prop="sourcePurchaseRequestNo" label="来源采购申请" min-width="190" />
        <el-table-column v-if="mode==='comparison'" prop="materialName" label="物料名称" min-width="180" />
        <el-table-column v-if="mode==='comparison'" prop="quantity" label="申请行数量" width="130" />
        <el-table-column v-if="mode==='comparison'" prop="unit" label="单位" width="95" />
        <el-table-column v-if="mode==='preparation'" prop="sourceComparisonNo" label="绑定比较编号" min-width="230" />
        <el-table-column prop="statusLabel" label="服务端当前状态" min-width="180" />
      </template>
    </PceEnterpriseListTable>
    <section v-if="selected" class="native-detail" data-native-detail>
      <h3>来源、范围与准确版本</h3><el-button @click="selected=null">关闭来源查看</el-button>
      <p>{{ selected.displayNo }} · 比较版本 {{ selected.displayVersion }} · {{ shown(selected.statusLabel) }}</p>
      <p>{{ mode==='comparison'?'正式登记时间':'准备创建时间' }}：{{ shown(mode==='comparison'?selected.registeredAt:selected.createdAt) }}；当前准备资格不从登记时间推断。</p>
      <p>来源询价 {{ shown(selected.sourceInquiryNo) }}；绑定比较 {{ shown(selected.sourceComparisonNo || selected.quoteComparisonNo) }}。</p>
      <p>税费：{{ shown(basisOf(selected).tax) }}；运费：{{ shown(basisOf(selected).freight) }}；交期：{{ shown(basisOf(selected).deliveryTerms) }}；有效期：{{ shown(basisOf(selected).validUntil) }}。</p>
      <p>比较依据：{{ shown(basisOf(selected).note) }}。未自动选定最低价供应商，登记不等于价格批准。</p>
      <div v-for="(quote,index) in quotesOf(selected)" :key="quote.quotationId || index" class="native-quote-row">
        {{ shown(quote.quotationNo) }} · {{ shown(quote.supplierName || quote.supplierCode) }} · 数量 {{ shown(quote.quantity) }} {{ shown(quote.unit) }} · 单价 {{ shown(quote.unitPrice) }} {{ shown(quote.currency) }} · 接收时间 {{ shown(quote.receivedAt) }}
      </div>
      <details><summary>完整来源及版本追溯</summary><pre>{{ JSON.stringify(selected,null,2) }}</pre></details>
    </section>
    <ScmNativePreparationReviewPanel v-if="mode==='preparation'" :preparation="selected || {}" @current-facts="updateReviewFacts" />
    <section v-if="mode==='comparison'" class="native-registration" data-native-registration>
      <h3>原生来源及正式登记</h3>
      <el-button :disabled="Boolean(pending)" @click="loadInquiries">读取本人可用询价来源</el-button>
      <el-alert v-if="sourceError" type="error" :title="sourceError.message" :closable="false" />
      <p v-if="inquiries!==null && !inquiries.length">已读取授权询价，当前没有可用记录。</p>
      <label>原询价
        <select v-model="inquiryKey" aria-label="原询价" :disabled="Boolean(pending)||requestBusy" @change="changeInquiry">
          <option value="">请选择原询价</option><option v-for="item in inquiries || []" :key="item.objectId" :value="String(item.objectId)">{{ item.inquiryNo }} ／ {{ item.sourcePurchaseRequestNo || '申请编号未提供' }}</option>
        </select></label>
      <p v-if="requestBusy" role="status">正在读取原采购申请行。</p>
      <p v-if="requestLines!==null && !sourceOptions.length">原申请未提供准确行ID，不能据物料猜配登记。</p>
      <label>原询价／原采购申请行
        <select v-model="sourceKey" aria-label="原询价／原采购申请行" :disabled="Boolean(pending)||contextBusy" @change="context=null">
          <option value="">请选择原来源行</option><option v-for="item in sourceOptions" :key="item.key" :value="item.key">{{ item.label }}</option>
        </select></label>
      <el-button :loading="contextBusy" :disabled="!chosenSource || Boolean(pending)" @click="loadContext(chosenSource.inquiryId,chosenSource.requestItemId)">核对本次登记依据</el-button>
      <el-alert v-if="actionError" type="error" :title="actionError.message" :closable="false" />
      <details v-if="rejectedAction"><summary>上次明确拒绝及原动作追溯</summary><p>原动作已被服务明确拒绝，未自动重放。先读取原正式事实或重新核对依据，再决定是否明确提交新动作。</p><pre>{{ JSON.stringify(rejectedAction,null,2) }}</pre></details>
      <section v-if="context" data-native-source-context>
        <p>来源已核对，尚非登记结果。{{ shown(context.sourceSnapshot?.inquiry?.no) }} ／ {{ shown(context.sourceSnapshot?.request?.no) }}，原申请行ID {{ context.sourceSnapshot?.requestItem?.id }}。</p>
        <p>本次候选供应商 {{ context.sourceSnapshot?.supplierCandidates?.map(v=>v.name || v.code).join('、') || '未提供' }}；参与范围及已接收报价见追溯。</p>
        <p>服务端前版：{{ context.expectedPreviousVersion }}；登记时按准确前版及来源指纹校验，新版不会覆盖旧版。</p>
        <p v-if="context.canRegister!==true">当前身份没有本次登记执行资格；读取不等于执行授权。</p>
        <label>比较依据<el-input v-model="basisNote" aria-label="比较依据" type="textarea" maxlength="1000" :disabled="Boolean(pending)" /></label>
        <label>本次登记原因<el-input v-model="reason" aria-label="本次登记原因" maxlength="240" :disabled="Boolean(pending)" /></label>
        <el-button type="primary" :data-process-action="NATIVE_QUOTE_ACTIONS.register.actionCode" :loading="actionBusy"
          :disabled="context.canRegister!==true || Boolean(pending) || !basisNote.trim() || !reason.trim()" @click="register(basisNote,reason)">{{ NATIVE_QUOTE_ACTIONS.register.actionName }}</el-button>
        <details><summary>原始来源、完整参与范围及版本核验</summary><pre>{{ JSON.stringify(context,null,2) }}</pre></details>
      </section>
      <section v-if="pending" data-native-action-result role="status">
        <h3>{{ receipt?.resultState==='COMMITTED'?'原动作已正式登记':'原动作结果尚未确认' }}</h3>
        <p>保留原动作标识，只查询同一次动作，不自动重放提交。</p>
        <el-button :loading="actionBusy" @click="queryOriginal">查询原动作结果</el-button>
        <template v-if="receipt?.resultState==='COMMITTED'">
          <p>正式比较 {{ receipt.comparisonNo }} · 版本 {{ receipt.factVersion }}；准备 {{ receipt.approvalPrepareNo }}。</p>
          <p>登记时初始状态：{{ shown(receipt.statusLabel) }}。这是历史回执，当前准备状态及办理资格须由原授权服务另读。</p>
          <p>原提交时间：{{ shown(receipt.receiptAsOf) }}；未选供应商、未批准价格。</p>
          <el-button @click="acknowledgeCommitted">已查看回执，重新核对下一次依据</el-button>
        </template>
        <p v-else>未知结果不代表登记失败，也不代表可以再次提交。</p>
        <details><summary>同次动作与回执追溯</summary><pre>{{ JSON.stringify({originalAction:pending,receipt},null,2) }}</pre></details>
      </section>
    </section>
    <details v-if="loadError || sourceError || actionError"><summary>读取／动作诊断</summary><pre>{{ JSON.stringify({loadError,sourceError,actionError},null,2) }}</pre></details>
  </section>
</template>
<script setup>
import { computed, inject, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import PceEnterpriseListTable from './PceEnterpriseListTable.vue'
import ScmNativePreparationReviewPanel from './ScmNativePreparationReviewPanel.vue'
import { createPceEnterpriseListContract, usePceEnterpriseListRuntime } from '../runtime/pceEnterpriseListContract.js'
import { createNativeQuoteRegistration } from '../runtime/nativeQuoteRegistration.js'
import { NATIVE_QUOTE_ACTIONS, NATIVE_QUOTE_VIEW_ACTIONS } from '../process/scm/nativeQuoteRegistrationActions.js'
import { PAGE_OBSERVABILITY_ACTIONS_KEY } from '../runtime/pageObservabilityActions.js'
const props=defineProps({mode:{type:String,default:'comparison'}}), router=useRouter()
const {records,count,loadState,loadError,inquiries,requestLines,requestBusy,sourceError,context,contextBusy,pending,receipt,rejectedAction,actionError,actionBusy,
  load,loadInquiries,loadRequest,loadContext,register,queryOriginal,acknowledgeCommitted}=createNativeQuoteRegistration()
const title=computed(()=>props.mode==='comparison'?'正式报价比较':'核价准备')
const pageId=props.mode==='comparison'?'quote-comparison-workbench':'price-approval'
const navigation=computed(()=>NATIVE_QUOTE_ACTIONS[props.mode==='comparison'?'preparation':'comparison'])
const shown=value=>value===null || value===undefined || value===''?'未提供':String(value)
const basisOf=row=>row.basis || row.comparisonBasis?.basis || {}
const quotesOf=row=>row.comparisonRows || row.sourceQuotationEvidence || []
const selected=ref(null),inquiryKey=ref(''),sourceKey=ref(''),basisNote=ref(''),reason=ref('')
const chosenInquiry=computed(()=>(inquiries.value || []).find(v=>String(v.objectId)===inquiryKey.value))
async function changeInquiry(){sourceKey.value='';await loadRequest(chosenInquiry.value)}
const sourceOptions=computed(()=>(requestLines.value || []).filter(line=>line.id!=null).map(line=>({
  key:`${chosenInquiry.value?.objectId}:${line.id}`,inquiryId:chosenInquiry.value?.objectId,requestItemId:line.id,
  label:`申请行ID ${line.id} ／ ${line.materialName || line.materialCode || '名称未提供'}` })))
const chosenSource=computed(()=>sourceOptions.value.find(v=>v.key===sourceKey.value))
const rows=computed(()=>(records.value || []).map(row=>({...row,displayNo:row.quoteComparisonNo || row.approvalPrepareNo,
  displayVersion:row.factVersion ?? row.sourceComparisonVersion ?? '未提供'})))
const filterSchema=[{field:'displayNo',label:'单据编号',filterType:'text',type:'text'}, {field:'sourceInquiryNo',label:'来源询价',filterType:'text',type:'text'}, {field:'statusLabel',label:'当前状态',filterType:'text',type:'text'}]
const listContract=createPceEnterpriseListContract({pageCode:pageId,pageType:'list',title:title.value,moduleCode:'SCM'})
const {selectedRows,quickSearch,appliedSearch,advancedVisible,filters,tableRef,activeFilterCount,sortText,filteredRows,
  clearFilters,clearSort,clearSelection,handleSort,exportCurrent}=usePceEnterpriseListRuntime({rows,filterSchema,pageCode:pageId,
  searchFields:['displayNo','sourceInquiryNo','materialName','statusLabel'],exportFileName:`${pageId}-native.csv`,
  exportColumns:[{field:'displayNo',label:'单据编号'},{field:'displayVersion',label:'比较版本'},{field:'sourceInquiryNo',label:'来源询价'},{field:'statusLabel',label:'服务端当前状态'}]})
async function reload(){selected.value=null;await load(props.mode)}
function updateReviewFacts(facts){
  const matches=row=>(row.preparationId ?? row.id)===facts.preparationId
  const apply=row=>({...row,statusCode:facts.statusCode,statusLabel:facts.statusLabel,reviewFacts:facts})
  if(selected.value && matches(selected.value))selected.value=apply(selected.value)
  else if(!selected.value){const row=(records.value || []).find(matches);if(row)selected.value=apply(row)}
  if(records.value)records.value=records.value.map(row=>matches(row)?apply(row):row)
}
const observability=inject(PAGE_OBSERVABILITY_ACTIONS_KEY,null)
const ownedProvider={factOwner:'SCM_NATIVE_QUOTE_REGISTRATION',refresh:reload,buildDiagnostics:()=>({
  pageCode:pageId,currentStateSource:'server',factLoadStatus:loadState.value,resultCount:count.value,
  records:records.value,loadError:loadError.value,sourceError:sourceError.value,actionError:actionError.value,
  originalAction:pending.value,receipt:receipt.value,rejectedAction:rejectedAction.value,readFactsBusinessWriteCount:0,
  latestActionCallBusinessWriteCount:receipt.value?.businessWriteCount ?? null,
  writeCountMeaning:'服务端最近一次回执调用的写入数；同次查询的0不否定原登记写入',
  qualificationSource:'Original server context only; receipt conveys initial state, not current preparation eligibility'})}
onBeforeUnmount(()=>observability?.unregister(ownedProvider))
onMounted(()=>{observability?.register(ownedProvider);void reload()})
</script>
<style scoped>
.native-quote-panel{display:grid;gap:16px;padding:18px;min-width:0;max-width:100%}.native-heading{display:flex;align-items:center;gap:12px;flex-wrap:wrap}.native-heading h2{margin:0 auto 0 0}.native-registration,.native-detail{border:1px solid #dbe4ee;border-radius:10px;padding:16px;display:grid;gap:12px;min-width:0}.native-quote-panel p{margin:6px 0;line-height:1.65}.native-quote-panel label{display:grid;gap:8px}.native-quote-panel select{width:100%;min-height:44px;max-width:100%;border:1px solid #cbd5e1;border-radius:5px;background:white;padding:8px}.native-quote-panel pre{white-space:pre-wrap;overflow-wrap:anywhere;max-width:100%;font-size:12px}.native-quote-row{padding:10px;background:#f8fafc;overflow-wrap:anywhere}.native-quote-panel summary{cursor:pointer}.native-quote-panel :deep(.el-button){white-space:normal;height:auto;min-height:40px;line-height:1.5;max-width:100%}
@media(max-width:600px){.native-quote-panel{padding:12px;gap:12px}.native-registration,.native-detail{padding:12px}.native-heading{align-items:stretch}.native-heading h2{flex-basis:100%}}
</style>
