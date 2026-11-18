<template>
  <section class="operation-resource-admission" data-section="operation-resource-selection-and-precise-receipt"
    data-fact-source="server" :data-load-status="state.readState" :data-strict-facts="JSON.stringify(state.facts)">
    <h4>正式执行资源选择与逐工序接收</h4>
    <p>没有预先选择工作中心的工序，在此由有职责的责任人明确选择，再办理本工序精确接收。目录默认工作中心、资源能力配置和原整组接收均不自动构成本工序已接收证明。</p>
    <details><summary>操作说明</summary><ol>
      <li>在本页选择已下达工单，再明确选择本次工序并读取事实。</li>
      <li>尚未正式选择资源时，从本次服务返回的有效候选中明确选择工作中心，在“本次资源选择原因”填写真实选择依据，再点击“正式选择执行资源”。</li>
      <li>独立回读显示“已选择资源”后，不再重复选择；在同一位置的“本次精确接收原因”另填本次真实接收原因，再点击“确认本工序精确接收”。资源选择原因不代替接收原因。</li>
      <li>显示“已精确接收”后只核对证明及审计，不再提交。精确接收不扩大原整组接收范围，不派工、开工或登记产量。</li>
      <li>已有冻结资源、归属变化和已有任务迁移分别核对。下方原“资源归属承接”继续处理其正式范围；未支持的任务迁移保持阻止。</li>
      <li>下方“归属承接原因”仅用于已有归属真实变更，不能用于首次资源选择或精确接收；显示“无需归属承接”时不用填写或提交下方动作。</li>
      <li>结果待核实时只点“仅重新读取资源操作结果”。处理中读取按钮暂禁用；请求结束或读取失败后可以再次只读核查。刷新或重新进入仍只回查原意图，不自动重发。</li>
    </ol></details>
    <p v-if="!workOrderId">请先明确选择已下达工单；不会自动选择工序或工作中心。</p>
    <label v-if="workOrderId">资源与接收的正式工序<select :value="state.operationId" :disabled="locked||externalLocked"
      aria-label="资源与接收的正式工序" @change="selectViewedOperation($event.target.value)">
      <option value="">请选择本工单工序</option><option v-for="row in operationOptions" :key="row.operationId"
        :value="String(row.operationId)">{{ row.sequence }} · {{ row.operationName }} · {{ row.statusLabel }}</option>
    </select></label>
    <button v-if="workOrderId" type="button" :disabled="writing||state.readState==='loading'" @click="controller.load()">
      {{ pending?'仅重新读取资源操作结果':'重新读取资源选择与接收事实' }}</button>
    <p v-if="state.readState==='loading'" role="status">正在读取本次正式资源、接收及责任事实，当前资格未知。</p>
    <p v-if="state.error" role="alert">{{ state.error }}</p><p v-if="state.message" role="status">{{ state.message }}</p>
    <p v-if="state.recoveryJournalError" role="alert">{{ state.recoveryJournalError }}</p>
    <p v-if="state.pendingActionLabel" role="status">本次待核实动作：{{ state.pendingActionLabel }}；工单ID {{ state.pendingIntent.workOrderId }}，工序ID {{ state.pendingIntent.operationId }}，资源选择版本 {{ state.pendingIntent.selectionVersion }}。只读核查对应原请求，不创建新提交。</p>
    <p v-if="!state.facts&&state.lastDisplayFacts" role="alert">以下为同账号、公司和工单上次只读展示；当前准入与操作结果未知，不能据此提交。</p>
    <p v-if="displayFacts">{{ displayFacts.statusLabel }}；本次后台账号：{{ displayFacts.currentActorEvidence.username }}；责任岗位：{{ displayFacts.currentActorEvidence.positionName||'未核实正式岗位' }}</p>
    <template v-if="selected">
      <p v-if="selected.preciseReceiptProof" class="completed-receipt" role="status">{{ selected.receiptStatusLabel }}。正式证明及审计如下；本次只读核对，无需重新选择资源或填写接收原因。</p>
      <section v-for="entry in proofEntries" :key="entry.key"><h5>{{ entry.title }}</h5>
        <p v-if="entry.proof">{{ entry.proof.statusLabel }}；责任人：{{ entry.proof.actorLabel }}；时间：{{ entry.proof.timeLabel }}；原因：{{ entry.proof.reason }}；审计：{{ entry.proof.auditReference }}</p>
        <details v-if="entry.proof?.statusTransitionHistory?.length"><summary>本笔正式追溯（{{ entry.proof.statusTransitionCount }}）</summary>
          <p v-for="event in entry.proof.statusTransitionHistory" :key="event.id">{{ event.statusLabel||event.targetStateLabel }}；{{ event.timestampLabel||event.timeLabel }}；{{ event.reason }}；{{ event.auditReference }}</p>
        </details>
      </section>
      <dl><div><dt>工单／工序</dt><dd>{{ selected.workOrderNo }}／{{ selected.operationName }}</dd></div>
        <div><dt>资源选择进度</dt><dd>{{ selected.selectionStatusLabel }}</dd></div>
        <div><dt>精确接收进度</dt><dd>{{ selected.receiptStatusLabel }}</dd></div>
        <div><dt>正式资源依据</dt><dd>{{ selected.sourceBasisLabel }}</dd></div>
        <div><dt>{{ selected.selectionFact?.proofType==='FROZEN_ORDER_RESOURCE'?'原工单冻结工作中心':'正式选择的工作中心' }}</dt><dd>{{ selected.selectionFact?.workCenterName||'尚未正式选定' }}</dd></div>
        <div><dt>{{ selected.selectionFact?.proofType==='FROZEN_ORDER_RESOURCE'?'冻结工作中心的当前所属车间':'正式选择时的车间' }}</dt><dd>{{ selected.selectionFact?.workshopName||'尚未取得正式选择证明' }}</dd></div>
        <div><dt>当前工作中心所属车间</dt><dd>{{ selected.currentResourceFacts?.effectiveWorkshop?.name||'当前资源归属事实待核实' }}</dd></div>
        <div v-if="selected.currentResourceFacts?.originalReceiptWorkshop"><dt>原冻结接收车间</dt><dd>{{ selected.currentResourceFacts.originalReceiptWorkshop.name }}</dd></div></dl>
      <p v-if="selected.currentResourceFacts?.frozenResourceBasisLabel">{{ selected.currentResourceFacts.frozenResourceBasisLabel }}</p>
      <p v-if="selected.currentResourceFacts?.currentResourceBasisLabel">{{ selected.currentResourceFacts.currentResourceBasisLabel }}</p>
      <PceBusinessStatus :status-label="selected.statusLabel" />
      <ul v-if="selected.blockingReasons.length"><li v-for="reason in selected.blockingReasons" :key="reason">{{ reason }}</li></ul>
      <label v-if="!selected.selectionFact">本次正式候选工作中心<select :value="state.workCenterId" :disabled="locked||externalLocked"
        aria-label="本次正式候选工作中心" @change="controller.selectWorkCenter($event.target.value)">
        <option value="">请明确选择工作中心</option><option v-for="option in selected.candidateWorkCenters" :key="option.id"
          :value="String(option.id)" :disabled="!option.enabled">{{ option.name }} · {{ option.workshopName }}</option>
      </select></label>
      <p v-if="!selected.selectionFact&&!selected.candidateWorkCenters.length">本次正式服务未返回候选工作中心。请由有职责的资源维护人员核对当前工序能力、有效车间及本人责任范围；目录默认中心不能替代正式选择。</p>
      <p v-for="option in selected.selectionFact?[]:selected.candidateWorkCenters.filter(row=>!row.enabled)" :key="`blocked-${option.id}`">{{ option.name }}：{{ option.blockingReasons.join('；')||option.qualification?.statusLabel }}</p>
      <p v-if="candidate">{{ candidate.qualification?.statusLabel }}</p>
      <ul v-if="candidate?.blockingReasons?.length"><li v-for="reason in candidate.blockingReasons" :key="reason">{{ reason }}</li></ul>
      <label v-if="!selected.preciseReceiptProof&&!selected.originalMembershipProven">{{ selected.selectionFact?'本次精确接收原因':'本次资源选择原因' }}<textarea v-model="state.reason" aria-label="本次资源选择或接收原因" rows="2"
        :disabled="locked||externalLocked||!!selected.preciseReceiptProof" :placeholder="selected.selectionFact?'填写本次真实精确接收原因；2至240字':'填写本次真实资源选择原因；2至240字'" /></label>
      <p v-if="selected.preciseReceiptProof">本工序已精确接收。请核对下方正式证明与审计，并只读刷新；无需重新填写原因或重复提交。</p>
      <div class="operation-resource-actions"><template v-for="key in actionKeys" :key="key">
        <button v-if="assessments[key].action" type="button" :data-action-id="assessments[key].action.actionId"
          :data-action-code="assessments[key].action.actionCode" :disabled="!assessments[key].enabled"
          @click="controller.execute(key)">{{ assessments[key].action.displayName }}</button>
        <p v-if="!assessments[key].enabled" role="status">{{ assessments[key].disabledReason }}</p>
      </template></div>
    </template>
  </section>
</template>
<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, watch } from 'vue'
import { operationResourcesApi } from '@/api/operationResources.js'
import { getTabAuthEpoch, readTabIdentity } from '@/meta/runtime/tabAuthenticationContext.js'
import { createOperationResourceState, createOperationResourceController } from '@/meta/runtime/operationResourceAdmission.js'
import PceBusinessStatus from './PceBusinessStatus.vue'
const props=defineProps({workOrderId:{type:[Number,String],default:null},operationId:{type:[Number,String],default:''},locationControlled:{type:Boolean,default:false},allowLatestFormalLocation:{type:Boolean,default:false},externalLocked:{type:Boolean,default:false}})
const emit=defineEmits(['lock-change','facts-changed','location-change','view-selection-confirmed']),state=reactive(createOperationResourceState())
const owner=()=>JSON.stringify([getTabAuthEpoch(),readTabIdentity()?.userId,readTabIdentity()?.companyId])
const controller=createOperationResourceController({state,api:operationResourcesApi,owner,
  companyId:()=>readTabIdentity()?.companyId,userId:()=>readTabIdentity()?.userId,externalLocked:()=>props.externalLocked,
  onFactsChanged:detail=>emit('facts-changed',detail)})
const displayFacts=computed(()=>state.facts||state.lastDisplayFacts),selected=computed(()=>displayFacts.value?.selectedOperation||null)
const operationOptions=computed(()=>displayFacts.value?.operationOptions||displayFacts.value?.operations||[])
const pending=computed(()=>state.writeState==='readback_pending'),writing=computed(()=>state.writeState==='writing')
const locked=computed(()=>writing.value||pending.value)
const actionKeys=Object.freeze(['selectResource','receiveOperation'])
const assessments=computed(()=>Object.fromEntries(actionKeys.map(key=>[key,controller.assessment(key)])))
const candidate=computed(()=>selected.value?.candidateWorkCenters.find(row=>row.id===Number(state.workCenterId))||null)
const proofEntries=computed(()=>selected.value?[{key:'selection',title:'本次正式资源选择证明',proof:selected.value.resourceSelectionProof},
  {key:'receipt',title:'本工序精确接收证明',proof:selected.value.preciseReceiptProof}].filter(row=>row.proof):[])
watch(locked,value=>emit('lock-change',value),{immediate:true,flush:'sync'})
watch([()=>props.workOrderId,()=>props.operationId],([order,operation])=>{if(!order){controller.invalidate();return}
  if(String(order)!==state.workOrderId)controller.selectWorkOrder(String(order),{operationId:operation,allowLatestFormalLocation:props.allowLatestFormalLocation})
  else if(String(operation||'')!==state.operationId)controller.selectOperation(String(operation||''))},{immediate:true})
watch(()=>state.readState,value=>{if(value==='loaded')emit('location-change',state.operationId)})
async function selectViewedOperation(value){if(await controller.selectOperation(value))emit('view-selection-confirmed',state.operationId)}
function authenticationChanged(){controller.invalidate();if(!props.locationControlled&&props.workOrderId)controller.selectWorkOrder(String(props.workOrderId),{operationId:props.operationId,allowLatestFormalLocation:props.allowLatestFormalLocation})}
function buildDiagnostics(){return{factSource:'server',operationResourceFacts:state.facts,strictServerFacts:state.facts,
  factLoadFacts:state.factLoadFacts,readState:state.readState,executionReadbackState:state.writeState,
  pendingActionLabel:state.pendingActionLabel,pendingIntent:state.pendingIntent,recoveryJournalError:state.recoveryJournalError||null,
  submissionChecks:Object.fromEntries(actionKeys.map(key=>[key,assessments.value[key].checks])),errorMessage:state.error||null}}
defineExpose({refresh:options=>controller.load(options),buildDiagnostics})
onMounted(()=>globalThis.window?.addEventListener?.('pce:authentication-changed',authenticationChanged))
onBeforeUnmount(()=>{controller.invalidate();emit('lock-change',false);globalThis.window?.removeEventListener?.('pce:authentication-changed',authenticationChanged)})
</script>
<style scoped>
.operation-resource-admission{border-top:2px solid #cbd5e1;margin-top:24px;padding-top:16px;min-width:0}.operation-resource-admission p,.operation-resource-admission li{line-height:1.6;overflow-wrap:anywhere}.operation-resource-admission label{display:block;max-width:780px;margin:12px 0}.operation-resource-admission select,.operation-resource-admission textarea{display:block;box-sizing:border-box;width:100%;padding:9px;margin-top:6px;border:1px solid #cbd5e1;border-radius:7px;font:inherit}.operation-resource-admission button{padding:9px 12px;background:#3568dc;color:#fff;border:1px solid #3568dc;border-radius:7px;cursor:pointer}.operation-resource-admission button:disabled{opacity:.55;cursor:not-allowed}.operation-resource-admission dl{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.operation-resource-admission dt{color:#64748b;font-size:12px}.operation-resource-admission dd{margin:4px 0;overflow-wrap:anywhere}@media(max-width:540px){.operation-resource-admission dl{grid-template-columns:1fr}}
</style>
