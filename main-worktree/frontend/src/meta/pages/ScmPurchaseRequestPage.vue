<template>
  <main class="purchase-request-page" data-acceptance-id="purchase-request-business-page"
    data-page-code="purchase-request" data-business-object="PurchaseRequest"
    data-process-node="scm-purchase-request"
    data-module-code="SCM" data-fact-source="server"
    :data-canary-mode="String(isCanaryMode)" :data-list-data-mode="serverFacts.dataMode || 'normal'">
    <section class="card" data-acceptance-id="purchase-request-list-region">
      <header>
        <h2 data-acceptance-id="page-internal-subject-title">{{ pageName.pageTitle }}</h2>
        <p>业务区直接复用 ScmPage.vue / configs.request 原字段、主从明细、联动和状态动作；持久事实由 PurchaseRequest 服务端对象提供。</p>
      </header>
      <aside class="runtime-mode-card" data-acceptance-id="scm-business-runtime-mode" :data-mode="dataSourceMode">
        <span>运行模式：<strong>{{ dataSourceMode === 'production' ? '正式业务模式' : '金丝雀验收模式' }}</strong></span>
        <span>dataMode：<strong data-acceptance-id="scm-business-data-mode">{{ dataSourceMode }}</strong></span>
        <span>数据Provider：<strong>{{ runtimeProviderCode }}</strong></span>
      </aside>
      <PceEnterpriseListCanaryCard v-if="isCanaryMode" :facts="serverFacts" />
      <div v-if="!isCanaryMode" class="page-actions">
        <div class="procurement-mode-entries" data-acceptance-id="procurement-mode-entry-buttons">
          <el-button type="primary" data-purchase-mode="STANDARD" @click="businessRegionRef?.openCreate('STANDARD')">新增采购申请</el-button>
          <el-button type="warning" data-purchase-mode="AGREED_PRICE" @click="router.push('/scm/purchase-request/agreed-price')">既定价格采购</el-button>
          <el-button v-if="directPurchaseAuthorization.allowed" type="danger" data-purchase-mode="DIRECT"
            @click="router.push('/scm/purchase-order/create')">直接采购</el-button>
        </div>
        <el-button :disabled="!editableSelection" @click="businessRegionRef?.openEdit(editableSelection)">编辑</el-button>
        <el-button type="success" :disabled="!editableSelection" :data-process-action="purchaseRequestActionCodes.submit" @click="businessRegionRef?.runAction('submit',editableSelection)">提交审批</el-button>
        <el-button v-if="selectedRows.length>0" type="success" :data-process-action="purchaseRequestActionCodes.submit" @click="runBatchAction('submit')">批量提交（{{ selectedRows.length }}）</el-button>
        <el-button v-if="batchApproveVisible" type="primary" :data-process-action="purchaseRequestActionCodes.approve" @click="runBatchAction('approve')">批量审批（{{ selectedRows.length }}）</el-button>
        <el-button v-if="batchConvertVisible" type="primary" :data-process-action="purchaseRequestActionCodes.convert" @click="runBatchAction('convert')">批量生成询价准备（{{ selectedRows.length }}）</el-button>
      </div>

      <ScmPurchaseRequestOriginalBusinessRegion v-if="!isCanaryMode" ref="businessRegionRef" :operation-row="operationRow" @refreshed="handleBusinessRefresh" @authentication-required="handleAuthenticationRequired" @inquiry-preparation-created="handleInquiryPreparationCreated" @approval-required="handleApprovalRequired" @procurement-mode-routed="handleProcurementModeRouted" />

      <PceEnterpriseListTable ref="tableRef" :contract="enterpriseListContract"
        page-id="purchase-request" table-id="purchase-request-table" :rows="rows"
        row-key="requestNo"
        :table-rows="filteredRows" :filter-schema="filterSchema" :filters="filters"
        :quick-search="quickSearch" :advanced-visible="advancedVisible"
        :selected-count="selectedRows.length" :active-filter-count="activeFilterCount"
        :sort-text="sortText" primary-field="requestNo" primary-label="申请编号"
        :primary-width="190" min-width="2200px" action-width="330"
        :show-action-column="true"
        :data-source-mode="dataSourceMode"
        @update:quick-search="quickSearch = $event" @search="appliedSearch = quickSearch"
        @toggle-advanced="advancedVisible = !advancedVisible" @clear-filters="clearFilters"
        @clear-sort="clearSort" @export-current="exportCurrent" @clear-selection="clearSelection"
        @update-filter="(field, value) => filters[field] = value"
        @selection-change="handlePurchaseRequestSelectionChange" @sort-change="handleSort">
        <template #columns>
          <el-table-column prop="requestDate" label="申请日期" width="130" sortable />
          <el-table-column prop="requestTypeLabel" label="申请类型" width="130" />
          <el-table-column prop="projectName" label="项目" width="220" show-overflow-tooltip />
          <el-table-column prop="usageDepartment" label="使用部门" width="150" />
          <el-table-column prop="department" label="申请部门" width="150" />
          <el-table-column prop="requester" label="申请人" width="130" />
          <el-table-column prop="purchaseDepartment" label="采购部门" width="150" />
          <el-table-column prop="costCenterName" label="成本中心" width="190" />
          <el-table-column prop="materialSummary" label="物料摘要" width="260" show-overflow-tooltip />
          <el-table-column prop="totalQuantity" label="数量" width="120" sortable />
          <el-table-column prop="requiredDate" label="需求日期" width="130" sortable />
          <el-table-column label="状态" width="130">
            <template #default="{ row }"><PceBusinessStatus :status-code="row.approvalStatus" :status-label="row.approvalStatusLabel" source="server" /></template>
          </el-table-column>
          <el-table-column label="业务生命周期" width="170">
            <template #default="{ row }"><PceBusinessStatus :status-code="row.businessLifecycleStatus" :status-label="row.businessLifecycleStatusLabel" source="server" /></template>
          </el-table-column>
        </template>
        <template #actions="{ row }">
          <el-button size="small" @click="openRuntimeView(row)">查看</el-button>
          <template v-if="row.purchaseMode==='AGREED_PRICE'&&['waiting_agreed_price_confirmation','agreed_price_confirmation_ready'].includes(row.businessLifecycleStatus)">
            <el-button size="small" type="warning" data-process-action="CONFIRM_AGREED_PRICE"
              data-acceptance-id="agreed-price-confirmation-action"
              @click="router.push(`/scm/purchase-request/${row.objectId||row.id}/agreed-price-confirmation`)">既定价格确认</el-button>
          </template>
          <template v-else-if="!isCanaryMode&&row.statusCode==='draft'">
            <el-button size="small" @click="businessRegionRef?.openEdit(row)">编辑</el-button>
            <el-button size="small" type="success" :data-process-action="purchaseRequestActionCodes.submit" @click="businessRegionRef?.runAction('submit',row)">提交</el-button>
          </template>
          <template v-else-if="row.statusCode==='submitted'">
            <el-button size="small" type="primary" :data-process-action="purchaseRequestActionCodes.approve" @click="businessRegionRef?.runAction('approve',row)">审批</el-button>
          </template>
          <template v-else-if="row.purchaseMode==='AGREED_PRICE'&&row.businessLifecycleStatus==='purchase_order_created'">
            <PceBusinessStatus status-code="purchase_order_created"
              :status-label="`已生成采购订单：${(row.purchaseOrders||[]).map(item=>item.purchaseOrderNo).join('、')||'已关联'}`"
              source="server" />
          </template>
          <template v-else-if="row.purchaseMode==='DIRECT'&&row.statusCode==='approved'">
            <PceBusinessStatus status-code="DIRECT_AUTHORIZATION_COMPLETED" status-label="直接采购授权已完成" source="server" />
          </template>
          <template v-else-if="row.purchaseMode==='STANDARD'&&row.approvalStatus==='approved'&&['approved','inquiry_preparation_ready'].includes(row.businessLifecycleStatus)">
            <el-button size="small" type="primary" :data-process-action="purchaseRequestActionCodes.convert" @click="businessRegionRef?.runAction('convert',row)">生成询价准备</el-button>
          </template>
        </template>
      </PceEnterpriseListTable>
    </section>

    <el-dialog v-model="canaryDetailVisible" title="采购申请只读详情" width="860px" append-to-body>
      <PceBusinessDetailCard v-if="canaryDetail" :detail="canaryDetail" />
    </el-dialog>

    <section class="card boundary" data-acceptance-id="purchase-request-business-boundary">
      <h2>业务边界保护</h2>
      <div class="boundary-grid"><span>自动询价：<strong>否</strong></span><span>采购订单：<strong>否</strong></span><span>付款：<strong>否</strong></span><span>财务影响：<strong>否</strong></span></div>
    </section>
  </main>
</template>

<script setup>
import { computed, inject, onBeforeUnmount, onMounted, provide, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import PceBusinessStatus from '@/meta/components/PceBusinessStatus.vue'
import PceBusinessDetailCard from '@/meta/components/PceBusinessDetailCard.vue'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import PceEnterpriseListCanaryCard from '@/meta/components/PceEnterpriseListCanaryCard.vue'
import ScmPurchaseRequestOriginalBusinessRegion from '@/meta/components/ScmPurchaseRequestOriginalBusinessRegion.vue'
import { PAGE_OBSERVABILITY_ACTIONS_KEY } from '@/meta/runtime/pageObservabilityActions.js'
import { resolveEnterpriseListCanaryQuery } from '@/meta/runtime/enterpriseListCanaryDataProvider.js'
import { loadScmBusinessPageRuntimeFacts } from '@/meta/runtime/scmBusinessPageRuntimeProvider.js'
import { createPceEnterpriseListContract, usePceEnterpriseListRuntime } from '@/meta/runtime/pceEnterpriseListContract.js'
import { normalizePurchaseRequestSelection, PURCHASE_REQUEST_ROW_KEY } from '@/meta/runtime/purchaseRequestSubmitSelectionRuntime.js'
import { PURCHASE_REQUEST_PROVIDER_RUNTIME_KEY, initPurchaseRequestProviders, purchaseRequestProviders } from '@/meta/scm/purchaseRequestProviderRuntimeRegistry.js'
import { PURCHASE_REQUEST_BUTTON_ACTION_CODES } from '@/meta/process/scm/purchaseRequest/purchaseRequestActionContracts.js'
import { PURCHASE_REQUEST_PROCESS_ACCEPTANCE_VERSION } from '@/meta/process/scm/purchaseRequest/purchaseRequestProcessAcceptanceProfile.js'
import { purchaseRequestLifecycleProvider } from '@/meta/providers/purchaseRequestLifecycleProvider.js'
import { resolvePageNameConsumption } from '@/meta/governance/pageNameConsumer.js'
import { preparePurchaseOrderGateCreation } from '@/api/scmStandardPageFacts.js'

const rows=ref([]),serverFacts=ref({}),businessRegionRef=ref(null)
const directPurchaseAuthorization=ref({allowed:false,reason:'尚未校验直接采购权限'})
const runtimeProviderCode=ref('')
const canaryDetailVisible=ref(false),canaryDetailRow=ref(null)
const route=useRoute()
const router=useRouter()
const pageName=resolvePageNameConsumption({pageCode:'purchase-request',route:'/scm/purchase-request'})
const canaryQuery=computed(()=>resolveEnterpriseListCanaryQuery(route.query))
const isCanaryMode=computed(()=>canaryQuery.value.isCanaryMode)
const purchaseRequestActionCodes=PURCHASE_REQUEST_BUTTON_ACTION_CODES
const dataSourceMode=computed(()=>isCanaryMode.value?'canary_acceptance':'production')
const observability=inject(PAGE_OBSERVABILITY_ACTIONS_KEY,null)
provide(PURCHASE_REQUEST_PROVIDER_RUNTIME_KEY,purchaseRequestProviders)
const requestTypes=Object.freeze([{value:'production',label:'生产需求'},{value:'stock_replenishment',label:'库存补充'},{value:'engineering',label:'工程需求'},{value:'equipment',label:'设备需求'},{value:'other',label:'其他需求'}])
const enterpriseListContract=createPceEnterpriseListContract({pageCode:'purchase-request',pageType:'list',title:pageName.pageTitle,moduleCode:'SCM'})
const filterSchema=Object.freeze([{field:'requestNo',label:'申请编号',filterType:'text'},{field:'requestDate',label:'申请日期',filterType:'daterange'},{field:'requestType',label:'申请类型',filterType:'select',options:requestTypes},{field:'department',label:'申请部门',filterType:'text'},{field:'statusCode',label:'状态',filterType:'select',options:[{label:'草稿',value:'draft'},{label:'已提交',value:'submitted'},{label:'已审批',value:'approved'},{label:'已转询价',value:'converted'},{label:'已关闭',value:'closed'}]}])
const runtime=usePceEnterpriseListRuntime({rows,filterSchema,pageCode:'purchase-request',searchFields:['requestNo','requester','department','usageDepartment','purchaseDepartment','projectName','costCenterName','materialSummary'],exportFileName:'purchase-requests.csv',exportColumns:[{field:'requestNo',label:'申请编号'},{field:'requestDate',label:'申请日期'},{field:'requestTypeLabel',label:'申请类型'},{field:'projectName',label:'项目'},{field:'usageDepartment',label:'使用部门'},{field:'department',label:'申请部门'},{field:'requester',label:'申请人'},{field:'purchaseDepartment',label:'采购部门'},{field:'costCenterName',label:'成本中心'},{field:'materialSummary',label:'物料摘要'},{field:'totalQuantity',label:'数量'},{field:'requiredDate',label:'需求日期'},{field:'statusLabel',label:'状态'}]})
const {selectedRows,quickSearch,appliedSearch,advancedVisible,filters,tableRef,activeFilterCount,sortText,filteredRows,clearFilters,clearSort,clearSelection,handleSort,exportCurrent}=runtime
const editableSelection=computed(()=>selectedRows.value.length===1&&selectedRows.value[0].approvalStatus==='draft'?selectedRows.value[0]:null)
const batchApproveVisible=computed(()=>selectedRows.value.some(row=>row.approvalStatus==='submitted'))
const batchConvertVisible=computed(()=>selectedRows.value.length>0&&selectedRows.value.every(row=>row.purchaseMode==='STANDARD'&&row.approvalStatus==='approved'&&['approved','inquiry_preparation_ready'].includes(row.businessLifecycleStatus)))
const operationRow=computed(()=>selectedRows.value[0]||rows.value[0]||null)
function handlePurchaseRequestSelectionChange(selection){selectedRows.value=[...normalizePurchaseRequestSelection(selection)]}
async function runBatchAction(action){const result=await businessRegionRef.value?.runBatchAction(action,[...selectedRows.value]);if(result?.successCount)clearSelection();return result}
function handleAuthenticationRequired(){ElMessage.warning('请先登录企业账号，再执行采购申请业务动作');router.push({path:'/login',query:{redirect:route.fullPath}})}
function handleInquiryPreparationCreated(preparation){router.push({path:'/scm/purchase-inquiry',query:{inquiryPreparationNo:preparation?.inquiryPreparationNo,sourceRequestNo:preparation?.sourceRequestNo}})}
function handleApprovalRequired(payload){router.push({path:'/scm/purchase-approvals',query:{businessObjectId:payload?.businessObjectId,objectId:payload?.objectId}})}
function handleProcurementModeRouted(saved){
  if(saved?.purchaseMode==='DIRECT')router.push({path:'/scm/purchase-order/create',query:{purchaseRequestId:saved.id||saved.objectId}})
  else if(saved?.purchaseMode==='AGREED_PRICE')ElMessage.info('既定价格采购已登记，后续由简化准入批次承接。')
}
const canaryDetail=computed(()=>{
  const row=canaryDetailRow.value
  if(!row)return null
  return{sectionTitle:'采购申请与链路明细',fields:[
    {label:'业务编号',value:row.businessNo||row.requestNo},
    {label:'场景代码',value:row.scenarioCode},
    {label:'数据类型',value:row.dataType},
    {label:'当前节点',value:row.currentNode},
    {label:'来源对象',value:row.sourceObjectNo||'流程起点'},
    {label:'目标对象',value:row.targetObjectNo||'流程终点'},
    {label:'业务状态',value:row.statusLabel},
    {label:'只读模式',value:row.readOnly?'是':'否'},
  ]}
})

function openRuntimeView(row){
  if(!isCanaryMode.value){businessRegionRef.value?.openView(row);return}
  canaryDetailRow.value=row
  canaryDetailVisible.value=true
}

let loadGeneration=0
async function refresh(){
  const generation=++loadGeneration
  const querySnapshot={...route.query}
  const requestedMode=resolveEnterpriseListCanaryQuery(querySnapshot)
  const runtimeResult=await loadScmBusinessPageRuntimeFacts({pageCode:'purchase-request',query:querySnapshot})
  if(generation!==loadGeneration||resolveEnterpriseListCanaryQuery(route.query).isCanaryMode!==requestedMode.isCanaryMode)return
  runtimeProviderCode.value=runtimeResult.providerCode
  serverFacts.value=purchaseRequestLifecycleProvider.load(runtimeResult.facts)
  rows.value=serverFacts.value.objects
  publishDiagnostics()
}
async function handleBusinessRefresh(){await refresh();window.dispatchEvent(new CustomEvent('pce:scm-facts-changed'))}
function diagnostics(){return{version:'V1.14.2.8.7.9',processRuntimeVersion:PURCHASE_REQUEST_PROCESS_ACCEPTANCE_VERSION,processNodeCode:'scm-purchase-request',process006Required:true,moduleCode:'SCM',pageCode:'purchase-request',pageComponent:'ScmPurchaseRequestPage',pageFactOwner:'purchase-request',pageFactOwnerGuard:'instance-owned',factSource:'server',isCanaryMode:isCanaryMode.value,dataSourceMode:dataSourceMode.value,runtimeProviderCode:runtimeProviderCode.value,formalPurchaseRequestApiCallCount:isCanaryMode.value?0:1,canaryProviderCallCount:isCanaryMode.value?1:0,dataMode:serverFacts.value.dataMode||dataSourceMode.value,canaryBatchId:serverFacts.value.canaryBatchId||'',scenarioCode:serverFacts.value.scenarioCode||'',cleanupPolicy:serverFacts.value.cleanupPolicy||'',apiFacts:serverFacts.value,pageFacts:serverFacts.value,diagnosticFacts:serverFacts.value,strictFacts:serverFacts.value,acceptanceFacts:serverFacts.value,resultCount:serverFacts.value.recordCount??0,originalBusinessRegionComponent:'ScmPurchaseRequestOriginalBusinessRegion',originalSchemaSource:'ScmPage.vue/configs.request',providerRuntimeRegistered:true,providerRuntimeReady:isCanaryMode.value?true:purchaseRequestProviders.state.ready,providerHttpStatus:{...purchaseRequestProviders.httpStatus},providerCounts:Object.fromEntries(Object.entries(purchaseRequestProviders.providers).map(([code,items])=>[code,items.length])),directOriginalFunctions:['snapshotMaterial','preferredSupplierId','handleHeaderFieldChange','handleDetailFieldChange','startAddDetail','startEditDetail','saveDetail','deleteDetail'],pceBusinessMasterDataSelectorUsed:false,serverPersistenceAdaptation:true,purchaseRequestRowKey:PURCHASE_REQUEST_ROW_KEY,selectedCount:selectedRows.value.length,singleRowSelectionIsolated:true,submitPermission:'purchase_request.submit',approvePermission:'purchase_request.approve',batchSubmitAvailable:true,batchApproveAvailable:true,automaticSubmit:false,automaticApprove:false,draftDirectApprove:false,inquiryPreparationCreationEnabled:true,inquiryAutoCreate:false,quotationCreated:false,supplierSent:false,productionUserDataWritten:false}}
function publishDiagnostics(){window.__PCE_BUSINESS_PAGE_ACCEPTANCE__=diagnostics()}
const provider={factOwner:'purchase-request',refresh,buildDiagnostics:diagnostics}
async function loadCurrentMode(){
  if(!isCanaryMode.value){await initPurchaseRequestProviders();try{const response=await preparePurchaseOrderGateCreation();directPurchaseAuthorization.value=response?.data?.authorization||{allowed:false,reason:'权限事实缺失'}}catch(error){directPurchaseAuthorization.value={allowed:false,reason:error?.message||'权限校验失败'}}}
  await refresh()
}
watch(()=>[route.query.canaryBatchId,route.query.scenarioCode],async()=>{try{await loadCurrentMode()}catch(error){ElMessage.error(error?.message||'采购申请事实读取失败')}})
onMounted(async()=>{observability?.register?.(provider);try{await loadCurrentMode()}catch(error){ElMessage.error(error?.message||'采购申请事实读取失败')}})
onBeforeUnmount(()=>observability?.unregister?.(provider))
</script>

<style scoped>
.purchase-request-page{display:grid;gap:16px;min-width:0}.card{min-width:0;padding:18px;border:1px solid #dce4ed;border-radius:10px;background:#fff}.card h2{margin:0 0 8px}.card p{margin:0 0 14px;color:#64748b}.runtime-mode-card{display:flex;flex-wrap:wrap;gap:12px;margin:12px 0;padding:12px;border:1px solid #93c5fd;border-radius:9px;background:#eff6ff}.runtime-mode-card span{min-width:220px}.page-actions{display:flex;gap:10px;margin-bottom:12px}.boundary{border-color:#b8d8c4;background:#f5fbf7}.boundary-grid{display:grid;grid-template-columns:repeat(4,minmax(130px,1fr));gap:10px}.boundary-grid span{padding:12px;border-radius:8px;background:#fff}
.procurement-mode-entries{display:flex;gap:10px;padding-right:12px;border-right:1px solid #dbe4ee}
:global(.pce-list-page-shell:has(> .pce-list-page-content > .purchase-request-page) > .pce-list-page-header){order:-2}
:global(.pce-list-page-shell:has(> .pce-list-page-content > .purchase-request-page) > .pce-list-page-content){order:-1}
</style>
