<template>
  <section class="workshop-receipt panel block" data-section="production-work-order-workshop-receipt" data-fact-source="server"
    :data-load-status="state.readState" :data-strict-facts="JSON.stringify(state.facts)">
    <h3>车间接收已下达工单</h3>
    <ProductionMaterialDeliveryPanel mode="receive" />
    <p>本区展示原工单冻结的整组接收范围。新增正式资源选择及逐工序精确接收另见下方；原冻结未归属清单不代表当前有效资源仍未选定。接收不代表派工、开工或报工。</p>
    <section class="receipt-scope" data-section="workshop-receipt-instructions" aria-label="车间接收操作说明">
      <h4>操作说明</h4>
      <ol>
        <li>页面恢复本账号已保存的查看定位并重新读取；没有查看定位时，可依据本人最近正式办理记录定位。</li>
        <li>下方已有本工序精确接收证明时，只核对证明，不填写新原因或重复提交。</li>
        <li>需要查看其他工单或原冻结车间范围时，再明确选择；“重新读取”只核查正式事实。</li>
        <li>首次办理时先核对本人、岗位、工序范围及准入结果，再按下方对应动作说明提交。</li>
      </ol>
      <p>原整组接收、下方资源选择、精确接收和归属承接是不同动作。已有资源选择证明时，在下方填写精确接收原因；已精确接收时只核对证明，不重复原整组接收或归属承接。</p>
    </section>
    <div class="receipt-controls">
      <label>已下达生产工单<select :value="state.selectedPlanId" :disabled="busy||pending" aria-label="车间接收已下达工单" @change="selectPlan($event.target.value)">
        <option value="">请选择工单</option><option v-for="row in displayFacts?.workOrderOptions||[]" :key="row.workOrderId" :value="String(row.productionPlanId)">{{ row.workOrderNo }} · {{ row.productionPlanNo }} · {{ row.quantityLabel }}</option>
      </select></label>
      <button type="button" :disabled="receiptBusy" @click="refresh()">重新读取车间接收事实</button>
    </div>
    <p v-if="state.readState==='loading'" role="status">正在读取本次后台身份、可见工单和车间接收事实，当前资格未知。</p>
    <p v-if="state.error" class="receipt-warning" role="alert">{{ state.error }}</p>
    <p v-if="!state.facts&&state.lastReadDisplay" class="receipt-warning" role="alert">以下仅为同一账号、公司和工单的上次只读展示；本次资格、接收数量和执行结果尚未核实，不能据此提交。</p>
    <p v-if="state.message" class="receipt-warning" role="status">{{ state.message }}</p>
    <button v-if="state.executionState==='readback_pending'" type="button" :disabled="receiptBusy" @click="refresh()">仅重新读取接收结果</button>
    <template v-if="displayFacts">
      <dl class="receipt-facts">
        <div><dt>本次后台账号</dt><dd>{{ displayFacts.currentActorEvidence.username }}</dd></div>
        <div><dt>本次公司</dt><dd>{{ displayFacts.currentActorEvidence.companyName }}（{{ displayFacts.currentActorEvidence.companyCode }}）</dd></div>
        <div><dt>正式员工 / 岗位</dt><dd>{{ displayFacts.currentActorEvidence.employeeName||'未建立正式员工关系' }} / {{ displayFacts.currentActorEvidence.positionName||'正式岗位未核实' }}</dd></div>
        <div><dt>岗位所属车间</dt><dd>{{ displayFacts.currentActorEvidence.workshopName||'岗位尚未关联车间' }}</dd></div>
      </dl>
      <p v-if="!displayFacts.workOrder">请从本次服务端返回的已下达工单中明确选择；不默认第一张工单或第一个车间。</p>
      <template v-else>
        <dl class="receipt-facts">
          <div><dt>正式工单</dt><dd>{{ displayFacts.workOrder.no }} · <PceBusinessStatus :status-label="displayFacts.workOrder.statusLabel" /></dd></div>
          <div><dt>工单数量 / 单位</dt><dd>{{ displayFacts.workOrder.quantityLabel }}</dd></div>
          <div><dt>生产对象</dt><dd>{{ displayFacts.workOrder.materialName }}（{{ displayFacts.workOrder.materialCode }}）</dd></div>
          <div><dt>正式工单工序总数 / 当前可见行</dt><dd>{{ displayFacts.workOrder.operationCount }} / {{ displayFacts.visibleOperationCount }}</dd></div>
          <div><dt>本次读取范围</dt><dd>{{ displayFacts.scopeVisibilityLabel }}</dd></div>
          <div><dt>{{ state.facts?'车间范围':'上次读取的车间范围' }}</dt><dd>{{ displayFacts.scopeSummary.statusLabel }}</dd></div>
          <div><dt>范围数 / 已接收范围数</dt><dd>{{ displayFacts.scopeSummary.scopeCount }} / {{ displayFacts.scopeSummary.receivedScopeCount }}</dd></div>
          <div><dt>原冻结已归属工序行 / 原冻结未归属工序行</dt><dd>{{ displayFacts.scopeSummary.assignedOperationCount }} / {{ displayFacts.scopeSummary.unassignedOperationCount }}</dd></div>
          <div><dt>未归属中的依赖行</dt><dd>{{ displayFacts.scopeSummary.dependencyOnlyUnassignedCount }}；不算作产品数量或额外资源占用</dd></div>
        </dl>
        <label>本次接收车间<select :value="state.selectedWorkshopId" :disabled="busy||pending" aria-label="本次接收车间" @change="selectWorkshop($event.target.value)">
          <option value="">请明确选择车间范围</option><option v-for="row in displayFacts.scopes" :key="row.workshopId" :value="String(row.workshopId)">{{ row.workshopName }} · {{ row.operationCount }}条工序 · {{ row.receipt.statusLabel }}</option>
        </select></label>
        <section v-if="selectedScope" class="receipt-scope">
          <h4>{{ selectedScope.workshopName }}：{{ selectedScope.operationCount }}条正式工序</h4>
          <p><PceBusinessStatus :status-label="selectedScope.receipt.statusLabel" />；接收人：{{ selectedScope.receipt.receivedByLabel||'尚未接收' }}；接收时间：{{ selectedScope.receipt.receivedAtLabel||'尚未接收' }}<span v-if="selectedScope.receipt.received">（{{ selectedScope.receipt.timezoneLabel }}）</span></p>
          <p>本区域保留原整组冻结接收校验。当前单个工序的有效资源、正式选择及精确接收证明见下方“正式执行资源选择与逐工序接收”；真实归属变更见“资源归属承接”。两者均不回填或扩大原冻结整组范围。</p>
          <p v-if="displayFacts.frozenScopeBasisLabel">{{ displayFacts.frozenScopeBasisLabel }}</p>
          <template v-if="currentScope">
            <p>{{ currentScope.qualification.statusLabel }}</p>
            <ul v-if="currentScope.qualification.issues.length"><li v-for="issue in currentScope.qualification.issues" :key="issue.code">
              {{ issue.categoryLabel }}：{{ issue.statusLabel }}。{{ issue.remediation.statusLabel }}
              <router-link v-if="issue.remediation.path" :to="{path:issue.remediation.path,query:issue.remediation.query}">{{ issue.remediation.pathLabel }}</router-link><span v-else>{{ issue.remediation.pathLabel }}</span>
            </li></ul>
            <label v-if="!currentScope.receipt.received">本次原冻结整组接收原因<textarea v-model="state.reason" rows="2" :disabled="busy||pending" placeholder="必填；只接收明确选择的原冻结车间范围" /></label>
            <button v-if="action" type="button" :data-action-id="action.actionId" :data-action-code="action.actionCode"
              :disabled="busy||pending||!action.enabled||!state.reason.trim()" @click="controller.receive()">{{ action.displayName }}</button>
            <p v-if="action&&!action.enabled">{{ action.disabledReason }}</p>
          </template>
          <PceEnterpriseListTable :ref="element=>operationsTable.tableRef=element" :contract="operationsContract" page-id="work-order-workshop-operations" table-id="work-order-workshop-operations-table"
            :rows="operationRows" :table-rows="operationsTable.filteredRows" :filter-schema="operationFilters" :filters="operationsTable.filters" :quick-search="operationsTable.quickSearch"
            :advanced-visible="operationsTable.advancedVisible" :selected-count="operationsTable.selectedRows.length" :active-filter-count="operationsTable.activeFilterCount" :sort-text="operationsTable.sortText"
            row-key="id" primary-field="sequence" primary-label="工序顺序" :primary-width="110" min-width="1300px" :action-width="100"
            @update:quick-search="operationsTable.quickSearch=$event" @search="operationsTable.appliedSearch=operationsTable.quickSearch" @toggle-advanced="operationsTable.advancedVisible=!operationsTable.advancedVisible"
            @clear-filters="operationsTable.clearFilters" @clear-sort="operationsTable.handleSort()" @clear-selection="operationsTable.selectedRows=[]" @update-filter="operationsTable.updateFilter"
            @selection-change="operationsTable.selectedRows=$event" @sort-change="operationsTable.handleSort" @export-current="operationsTable.exportCurrent">
            <template #columns><el-table-column prop="operationName" label="正式工序" min-width="160" /><el-table-column prop="workCenterName" label="工作中心" min-width="160" />
              <el-table-column prop="workloadLabel" label="正式作业量 / 单位" min-width="200" /><el-table-column prop="startLabel" label="计划开始" min-width="180" /><el-table-column prop="endLabel" label="计划完成" min-width="180" />
              <el-table-column prop="rootRoutingVersionId" label="根路线版本" width="120" /><el-table-column prop="effectiveRoutingVersionId" label="生效路线版本" width="130" /></template>
            <template #actions>仅查看来源</template>
          </PceEnterpriseListTable>
          <details v-if="selectedScope.receipt.stateTransitionHistory.length"><summary>接收状态与审计历史（{{ selectedScope.receipt.statusTransitionCount }}）</summary>
            <p v-for="event in selectedScope.receipt.stateTransitionHistory" :key="event.id">{{ event.actionLabel }}：{{ event.sourceStateLabel }} → {{ event.targetStateLabel }}；{{ event.timestampLabel }}；操作人ID {{ event.operatorId }}；版本 {{ event.version }}；原因：{{ event.reason }}</p>
          </details>
        </section>
        <section v-if="displayFacts.unassignedOperations.length" class="receipt-scope"><h4>原工单冻结时未归属整组接收范围的正式工序</h4>
          <p>此清单描述原冻结历史；新增正式选择不会移除此处原始记录。当前有效资源及精确接收进度以同页下方正式证明为准；依赖行不自动归入任一车间，不自动接收。</p>
          <ul><li v-for="row in displayFacts.unassignedOperations" :key="row.id">{{ row.sequence }} · {{ row.operationName }} · {{ row.workloadLabel }} · {{ row.statusLabel }}</li></ul>
        </section>
      </template>
    </template>
    <p v-if="locationWarning" role="alert">{{ locationWarning }}</p>
    <p v-if="pendingNavigationIntent" role="status">本页优先按本账号原待核实资源操作定位；正式结果以下方原工序、动作及原请求的只读核查为准，不会重新提交。</p>
    <ProductionOperationResourceAdmissionPanel ref="resourceAdmissionPanel" :work-order-id="displayFacts?.workOrder?.id||null"
      :operation-id="workOrderLocationMatches?location.resourceOperationId:''" :location-controlled="true" :allow-latest-formal-location="canLocateLatest"
      :external-locked="receiptBusy||pending||handoffLocked" @lock-change="resourceAdmissionLocked=$event"
      @facts-changed="refreshRelated('resource',{force:true})" @location-change="updateLocation({resourceOperationId:$event})"
      @view-selection-confirmed="explicitLocation({resourceOperationId:$event})" />
    <ProductionOperationResourceHandoffPanel ref="handoffPanel" :work-order-id="displayFacts?.workOrder?.id||null"
      :operation-id="workOrderLocationMatches?location.handoffOperationId:''" :location-controlled="true" :allow-latest-formal-location="canLocateLatest"
      :external-locked="receiptBusy||pending||resourceAdmissionLocked" @lock-change="handoffLocked=$event"
      @facts-changed="refreshRelated('handoff',{force:true})" @location-change="updateLocation({handoffOperationId:$event})"
      @view-selection-confirmed="explicitLocation({handoffOperationId:$event})" />
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { planningApi } from '@/api/planning.js'
import PceBusinessStatus from './PceBusinessStatus.vue'
import ProductionMaterialDeliveryPanel from './ProductionMaterialDeliveryPanel.vue'
import PceEnterpriseListTable from './PceEnterpriseListTable.vue'
import ProductionOperationResourceHandoffPanel from './ProductionOperationResourceHandoffPanel.vue'
import ProductionOperationResourceAdmissionPanel from './ProductionOperationResourceAdmissionPanel.vue'
import { createPceEnterpriseListContract, usePceEnterpriseListRuntime } from '@/meta/runtime/pceEnterpriseListContract.js'
import { getTabAuthEpoch, readTabIdentity } from '@/meta/runtime/tabAuthenticationContext.js'
import { createWorkshopReceptionState, createWorkshopReceptionController, projectWorkshopReceiptAction } from '@/meta/runtime/productionWorkOrderWorkshopReceipt.js'
import { readWorkshopReceptionLocation, workshopReceptionLocationQuery, WORKSHOP_RECEPTION_LOCATION_KEYS,createWorkshopReceptionLocationStore } from '@/meta/runtime/workshopReceptionLocation.js'
import { createOperationResourcePendingStore } from '@/meta/runtime/operationResourcePendingIntent.js'

const route=useRoute(),router=useRouter(),state=reactive(createWorkshopReceptionState())
const owner=()=>JSON.stringify([getTabAuthEpoch(),readTabIdentity()?.userId,readTabIdentity()?.companyId])
const handoffPanel=ref(null),handoffLocked=ref(false),resourceAdmissionPanel=ref(null),resourceAdmissionLocked=ref(false)
const controller=createWorkshopReceptionController({state,api:planningApi,owner,companyId:()=>readTabIdentity()?.companyId,
  userId:()=>readTabIdentity()?.userId,allowLatestFormalLocation:()=>canLocateLatest.value,
  externalLocked:()=>handoffLocked.value||resourceAdmissionLocked.value})
const displayFacts=computed(()=>state.facts||state.lastReadDisplay)
const navigationStore=createWorkshopReceptionLocationStore(),restoredLocation=ref(null),navigationRestoreError=ref('')
const pendingNavigationStore=createOperationResourcePendingStore(),pendingNavigationIntent=ref(null)
const locationContext=()=>({companyId:readTabIdentity()?.companyId,userId:readTabIdentity()?.userId,planId:route.query.productionPlanId||state.selectedPlanId})
const routeLocation=computed(()=>readWorkshopReceptionLocation(route.query,locationContext()))
const location=computed(()=>routeLocation.value.hasContext?routeLocation.value:restoredLocation.value||routeLocation.value)
const canLocateLatest=computed(()=>!navigationRestoreError.value&&!pendingNavigationIntent.value&&!routeLocation.value.hasContext&&!restoredLocation.value)
const workOrderLocationMatches=computed(()=>!location.value.workOrderId||location.value.workOrderId===String(displayFacts.value?.workOrder?.id||''))
const locationWarning=computed(()=>navigationRestoreError.value|| (location.value.hasContext&&!location.value.ownerMatches?'本次账号、公司或计划与原定位不一致；未恢复原车间或工序，需重新明确选择。'
  :!workOrderLocationMatches.value&&state.readState==='loaded'?'原定位工单与本次服务端正式工单不一致；未恢复原工序。':location.value.workshopId&&state.facts
    &&!state.facts.scopes.some(row=>String(row.workshopId)===location.value.workshopId)?'原定位车间不在本次服务端可见范围；未默认选择其他车间。':''))
const receiptBusy=computed(()=>state.readState==='loading'||['writing','reading'].includes(state.executionState))
const busy=computed(()=>receiptBusy.value||handoffLocked.value||resourceAdmissionLocked.value)
const pending=computed(()=>state.executionState==='readback_pending')
const selectedScope=computed(()=>displayFacts.value?.scopes.find(row=>String(row.workshopId)===state.selectedWorkshopId)||null)
const currentScope=computed(()=>state.facts?.scopes.find(row=>String(row.workshopId)===state.selectedWorkshopId)||null)
const action=computed(()=>projectWorkshopReceiptAction(state.facts,state.selectedWorkshopId))
const operationRows=computed(()=>selectedScope.value?.operations||[])
const operationsContract=createPceEnterpriseListContract({pageCode:'work-order-workshop-operations',pageType:'list',title:'所选车间正式工序',moduleCode:'MES'})
const operationFilters=Object.freeze([{field:'operationName',label:'工序',filterType:'text'},{field:'workCenterName',label:'工作中心',filterType:'text'}])
const operationsTable=reactive(usePceEnterpriseListRuntime({rows:operationRows,filterSchema:operationFilters,pageCode:'work-order-workshop-operations',
  searchFields:['operationName','workCenterName'],exportFileName:'work-order-workshop-operations.csv',exportColumns:[{field:'sequence',label:'工序顺序'},{field:'operationName',label:'正式工序'},{field:'workCenterName',label:'工作中心'},{field:'workloadLabel',label:'正式作业量 / 单位'}]}))
let locationQueue=Promise.resolve(),locationEpoch=0,explicitNavigationRepair=false
function updateLocation(patch){const identity=owner(),epoch=locationEpoch,plan=String(route.query.productionPlanId||'')
  const selectedPlan=plan||state.selectedPlanId
  locationQueue=locationQueue.then(async()=>{if(identity!==owner()||epoch!==locationEpoch||selectedPlan!==String(route.query.productionPlanId||state.selectedPlanId))return
    const context=locationContext(),base={...route.query,section:'work-order-reception',productionPlanId:selectedPlan||undefined}
    const next=workshopReceptionLocationQuery(base,context,{...location.value,workOrderId:state.facts?.workOrder?.id,...patch})
    if(JSON.stringify(next)!==JSON.stringify(route.query))await router.replace({query:next})
    const saved=readWorkshopReceptionLocation(next,context)
    if(saved.ownerMatches){navigationStore.save({...saved,companyId:String(context.companyId),userId:String(context.userId)},{replaceInvalid:explicitNavigationRepair})
      explicitNavigationRepair=false;navigationRestoreError.value=''}
  }).catch(()=>{navigationRestoreError.value='本次查看定位未保存；正式证明与业务记录未改变。请保留本页只读核对。'})
  return locationQueue}
async function selectPlan(value){if(busy.value||pending.value)return;locationEpoch++
  explicitNavigationRepair=true
  restoredLocation.value=null;navigationRestoreError.value=''
  const query={...route.query,section:'work-order-reception',productionPlanId:value||undefined};for(const key of WORKSHOP_RECEPTION_LOCATION_KEYS)delete query[key]
  await router.replace({query})}
async function explicitLocation(patch){explicitNavigationRepair=true;return updateLocation(patch)}
async function selectWorkshop(value){if(controller.selectWorkshop(value))await explicitLocation({workshopId:value})}
function restoreWorkshopLocation(){if(!state.facts||!workOrderLocationMatches.value)return
  const desired=location.value.workshopId
  if(desired!==state.selectedWorkshopId&&(!desired||state.facts.scopes.some(row=>String(row.workshopId)===desired))){state.selectedWorkshopId=desired;state.reason=''}}
async function authenticationChanged(){locationEpoch++;controller.invalidate();const hadPlan=!!route.query.productionPlanId,query={...route.query}
  explicitNavigationRepair=false
  restoredLocation.value=null;pendingNavigationIntent.value=null;navigationRestoreError.value=''
  delete query.productionPlanId;for(const key of WORKSHOP_RECEPTION_LOCATION_KEYS)delete query[key]
  await router.replace({query});if(!hadPlan)synchronizePlan('')}
async function synchronizePlan(value){const requested=String(value||''),identity=owner(),epoch=locationEpoch
  if(requested&&requested===state.selectedPlanId&&state.facts?.productionPlanId===Number(requested))return
  restoredLocation.value=null
  if(!routeLocation.value.hasContext){try{const saved=navigationStore.read({...locationContext(),planId:requested})
    if(saved){restoredLocation.value={...saved,ownerMatches:true,hasContext:true}
      const query=workshopReceptionLocationQuery({...route.query,section:'work-order-reception',productionPlanId:saved.planId},{...locationContext(),planId:saved.planId},saved)
      if(identity!==owner()||epoch!==locationEpoch)return
      await router.replace({query});if(requested!==saved.planId)return
    }}catch(error){navigationRestoreError.value=error.message}}
  // A transport recovery intent precedes optional latest-action navigation.
  // With no saved view, use the authorized group directory to resolve its plan;
  // only the resource reader may verify the exact action/hash/key afterwards.
  if(!requested&&!routeLocation.value.hasContext&&!restoredLocation.value&&!navigationRestoreError.value){
    try{const actor=readTabIdentity(),rows=pendingNavigationStore.readOwn(JSON.stringify([Number(actor?.companyId),Number(actor?.userId)]))
      if(rows.length>1)throw new Error('本账号存在多项原待核实资源操作；已停止自动定位，请保留原技术标识进行只读核查。')
      if(rows.length){const intent=rows[0]
        if(intent.actorId!==Number(actor?.userId))throw new Error('原待核实操作的账号身份不一致；已停止恢复。')
        pendingNavigationIntent.value=intent
        await controller.selectPlan('')
        if(identity!==owner()||epoch!==locationEpoch)return
        const order=state.facts?.workOrderOptions.find(row=>row.workOrderId===intent.workOrderId)
        if(!order){navigationRestoreError.value='原待核实操作的工单未通过本次服务端可见范围核对；未换用其他工单。';return}
        restoredLocation.value={ownerMatches:true,hasContext:true,planId:String(order.productionPlanId),workOrderId:String(order.workOrderId),
          workshopId:'',resourceOperationId:String(intent.operationId),handoffOperationId:''}
        await router.replace({query:workshopReceptionLocationQuery({...route.query,section:'work-order-reception',productionPlanId:String(order.productionPlanId)},
          {...locationContext(),planId:order.productionPlanId},restoredLocation.value)})
        return
      }
    }catch(error){navigationRestoreError.value=error.message}}
  if(identity===owner()&&epoch===locationEpoch)return controller.selectPlan(requested)}
watch(()=>route.query.productionPlanId,synchronizePlan,{immediate:true})
watch(()=>state.facts,facts=>{if(facts?.viewLocationSuggestion&&canLocateLatest.value){const value=facts.viewLocationSuggestion
  restoredLocation.value={ownerMatches:true,hasContext:true,planId:String(value.productionPlanId),workOrderId:String(value.workOrderId),workshopId:'',
    resourceOperationId:String(value.operationId),handoffOperationId:String(value.operationId)}
  updateLocation(restoredLocation.value)}},{flush:'sync'})
watch([()=>state.facts,()=>location.value.workshopId],restoreWorkshopLocation)
watch(()=>state.selectedPlanId,()=>operationsTable.clearSelection())
watch(()=>state.selectedWorkshopId,()=>operationsTable.clearSelection())
watch(()=>state.executionState,value=>{if(value==='verified')refreshRelated('receipt')})
function buildDiagnostics(){return{factSource:'server',pageFactOwner:'production-work-order-workshop-receipt',
  workshopReceptionFacts:state.facts,strictFacts:state.facts||{passed:false,workOrder:null,scopeSummary:null},strictServerFacts:state.facts,
  factLoadFacts:state.factLoadFacts,readState:state.readState,executionReadbackState:state.executionState,errorMessage:state.error||null,
  viewLocation:{...location.value},navigationRestoreError:navigationRestoreError.value||null,
  resourceHandoff:handoffPanel.value?.buildDiagnostics?.()||null,
  operationResource:resourceAdmissionPanel.value?.buildDiagnostics?.()||null}}
// Every read is independent and zero-write. Keep the active order stable while
// a parent GET clears current eligibility, so child recovery intent survives.
async function refreshRelated(origin,options={}){return Promise.all([
  origin==='receipt'?true:controller.load(options),
  origin==='resource'?true:resourceAdmissionPanel.value?.refresh?.(options),
  origin==='handoff'?true:handoffPanel.value?.refresh?.(options),
])}
async function refresh(){return refreshRelated(null)}
defineExpose({refresh,buildDiagnostics})
onMounted(()=>globalThis.window?.addEventListener?.('pce:authentication-changed',authenticationChanged))
onBeforeUnmount(()=>{controller.invalidate();globalThis.window?.removeEventListener?.('pce:authentication-changed',authenticationChanged)})
</script>

<style scoped>
.workshop-receipt{min-width:0;margin-top:24px;border-top:2px solid #cbd5e1;padding-top:18px}.workshop-receipt p,.workshop-receipt li{line-height:1.6;overflow-wrap:anywhere}.receipt-controls{display:flex;align-items:end;gap:12px;flex-wrap:wrap}.workshop-receipt label{display:block;margin:12px 0;max-width:680px}.workshop-receipt select,.workshop-receipt textarea{display:block;box-sizing:border-box;width:100%;margin-top:6px;padding:9px;border:1px solid #cbd5e1;border-radius:7px;font:inherit}.workshop-receipt textarea{resize:vertical}.workshop-receipt button{padding:9px 12px;border:1px solid #3568dc;border-radius:7px;background:#3568dc;color:#fff;cursor:pointer}.workshop-receipt button:disabled{opacity:.55;cursor:not-allowed}.receipt-facts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px 20px}.receipt-facts dt{font-size:12px;color:#64748b}.receipt-facts dd{margin:4px 0;font-weight:600;overflow-wrap:anywhere}.receipt-scope{margin-top:16px;padding-top:12px;border-top:1px solid #dce4ef;min-width:0}.receipt-warning{padding:10px;background:#fff7e6;color:#7c4b00;border-radius:7px}@media(max-width:540px){.receipt-facts{grid-template-columns:1fr}.receipt-controls{display:block}}
</style>
