<template>
  <section class="resource-handoff" data-section="production-operation-resource-handoff" data-fact-source="server" :data-load-status="state.readState">
    <h4>资源归属承接</h4>
    <p>逐工序核对原冻结接收、当前资源归属及正式承接。某一工序归属变化不等于其他工序失去接收依据；各工序执行条件仍以正式服务判断为准。</p>
    <details><summary>操作说明</summary>
      <ol><li>在本页选择已下达工单，再明确选择需要核对的工序。</li>
        <li>核对原冻结来源、当前有效资源、正式证明及承接是否适用。原冻结工作中心为空不等于当前主数据错误；首次正式资源选择后按上方办理精确接收。</li>
        <li>只有正式事实显示真实归属变更且存在主数据冲突时，才由有职责的维护人校正；“无需归属承接”时不用填写本区原因。</li>
        <li>有权限的目标车间接收责任人填写2至240字原因，确认本工序归属承接。此动作保留原接收，不重收整单，不派工或开工。</li>
        <li>显示“已承接”以独立回读的正式记录为依据。结果待核实时仅重新读取，不重复操作。每笔历史均可查看人员、时间、原因及审计。</li></ol>
    </details>
    <p v-if="!workOrderId">请先明确选择已下达工单；不自动选择工序或执行承接。</p>
    <label v-if="workOrderId">核对归属的正式工序<select :value="state.operationId" :disabled="locked||externalLocked" aria-label="核对归属的正式工序" @change="selectViewedOperation($event.target.value)">
      <option value="">请选择工序</option><option v-for="row in operationOptions" :key="row.operationId" :value="String(row.operationId)">{{ row.sequence }} · {{ row.operationName }} · {{ row.statusLabel }}</option>
    </select></label>
    <button v-if="workOrderId" type="button" :disabled="state.writeState==='writing'||state.readState==='loading'" @click="controller.load()">{{ pending?'仅重新读取承接结果':'重新读取归属及承接事实' }}</button>
    <p v-if="state.readState==='loading'" role="status">正在读取正式归属及承接事实，当前资格未知。</p>
    <p v-if="state.error" role="alert">{{ state.error }}</p><p v-if="state.message" role="status">{{ state.message }}</p>
    <p v-if="!state.facts&&state.lastDisplayFacts" role="alert">以下是同一账号及工单的上次只读展示；当前归属、资格及操作结果尚未核实，不能据此提交。</p>
    <p v-if="displayFacts">{{ displayFacts.statusLabel }}；本次后台账号：{{ displayFacts.currentActorEvidence.username }}；正式岗位：{{ displayFacts.currentActorEvidence.positionName||'尚未核实岗位' }}；岗位所属车间：{{ displayFacts.currentActorEvidence.workshopName||'尚未核实车间' }}</p>
    <template v-if="selected">
      <dl><div><dt>工单 / 工序</dt><dd>{{ selected.workOrderNo }} / {{ selected.operationName }}</dd></div>
        <div><dt>工作中心</dt><dd>{{ selected.workCenterName||'正式来源未关联工作中心' }}</dd></div>
        <div><dt>原冻结接收车间</dt><dd>{{ selected.originalWorkshopName||selected.frozenResourceBasisLabel||'原冻结接收来源待核实' }}</dd></div>
        <div><dt>当前工作中心车间</dt><dd>{{ selected.currentWorkshopName||'未核实当前车间' }}</dd></div>
        <div><dt>正式工序声明车间</dt><dd>{{ selected.formalProcessWorkshopName===undefined?'正式工序车间事实尚未读取':selected.formalProcessWorkshopName||'正式工序未指定车间' }}</dd></div>
        <div><dt>当前动作有效归属</dt><dd>{{ selected.effectiveWorkshopName||selected.handoffStatusLabel||'有效归属事实待核实' }}</dd></div>
        <div><dt>归属及接收依据</dt><dd>{{ selected.sourceBasisLabel }}</dd></div></dl>
      <p><PceBusinessStatus :status-label="selected.statusLabel" /></p>
      <p v-if="selected.frozenResourceBasisLabel">{{ selected.frozenResourceBasisLabel }}</p>
      <p v-if="selected.currentResourceBasisLabel">{{ selected.currentResourceBasisLabel }}</p>
      <p v-if="selected.resourceSelectionStatusLabel">资源选择：{{ selected.resourceSelectionStatusLabel }}；精确接收：{{ selected.receiptStatusLabel }}；{{ selected.handoffStatusLabel }}</p>
      <p v-if="selected.resourceSelectionReference">资源选择证明：{{ selected.resourceSelectionReference.ref }}；{{ selected.resourceSelectionReference.actorLabel }}；{{ selected.resourceSelectionReference.timeLabel }}；审计：{{ selected.resourceSelectionReference.auditReference }}</p>
      <p v-if="selected.preciseReceiptReference">本工序精确接收证明：{{ selected.preciseReceiptReference.ref }}；{{ selected.preciseReceiptReference.actorLabel }}；{{ selected.preciseReceiptReference.timeLabel }}；审计：{{ selected.preciseReceiptReference.auditReference }}</p>
      <p v-if="selected.receiptBaselineLabel">{{ selected.receiptBaselineLabel }}</p>
      <p v-if="frozenReceipt">原冻结接收：{{ frozenReceipt.id }}；原接收人：{{ frozenReceipt.receivedByLabel }}；时间：{{ frozenReceipt.receivedAtLabel }}</p>
      <p v-if="selected.receiptAnchor&&!frozenReceipt">历史接收关联锚点：{{ selected.receiptAnchor.id }}；仅用于证明关联，不表示原整组范围包含本工序。</p>
      <p>{{ selected.qualification.statusLabel }}</p>
      <ul v-if="selected.blockingReasons.length"><li v-for="reason in selected.blockingReasons" :key="reason">{{ reason }}</li></ul>
      <template v-if="selected.resourceHandoff"><p>承接人：{{ selected.resourceHandoff.actorLabel }}；时间：{{ selected.resourceHandoff.timeLabel }}；原因：{{ selected.resourceHandoff.reason }}；审计：{{ selected.resourceHandoff.auditReference }}</p></template>
      <p v-if="selected.handoffApplicable===false||selected.resourceHandoff" role="status">本区无需重新填写归属承接原因；请核对上方正式状态及证明。</p>
      <label v-else>本工序归属承接原因<textarea v-model="state.reason" rows="2" aria-label="本工序归属承接原因" :disabled="locked||externalLocked" placeholder="仅真实归属变更需要填写；不用于上方资源选择或精确接收" /></label>
      <button v-if="assessment.action" type="button" :data-action-id="assessment.action.actionId" :data-action-code="assessment.action.actionCode" :disabled="!assessment.enabled" @click="controller.confirm()">{{ assessment.action.displayName }}</button>
      <p v-if="!assessment.enabled" role="status">{{ assessment.disabledReason }}</p>
      <details v-if="selected.statusTransitionHistory?.length"><summary>本工序正式承接历史（{{ selected.statusTransitionCount }}）</summary>
        <p v-for="proof in selected.statusTransitionHistory" :key="proof.id">{{ proof.statusLabel }}；{{ proof.actorLabel }}；{{ proof.timeLabel }}；原因：{{ proof.reason }}；审计：{{ proof.auditReference }}</p>
      </details>
    </template>
  </section>
</template>
<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, watch } from 'vue'
import { resourceHandoffsApi } from '@/api/resourceHandoffs.js'
import { getTabAuthEpoch, readTabIdentity } from '@/meta/runtime/tabAuthenticationContext.js'
import { createResourceHandoffState, createResourceHandoffController } from '@/meta/runtime/operationResourceHandoff.js'
import PceBusinessStatus from './PceBusinessStatus.vue'
const props=defineProps({workOrderId:{type:[Number,String],default:null},operationId:{type:[Number,String],default:''},locationControlled:{type:Boolean,default:false},allowLatestFormalLocation:{type:Boolean,default:false},externalLocked:{type:Boolean,default:false}})
const emit=defineEmits(['lock-change','facts-changed','location-change','view-selection-confirmed'])
const state=reactive(createResourceHandoffState())
const owner=()=>JSON.stringify([getTabAuthEpoch(),readTabIdentity()?.userId,readTabIdentity()?.companyId])
const controller=createResourceHandoffController({state,api:resourceHandoffsApi,owner,
  companyId:()=>readTabIdentity()?.companyId,userId:()=>readTabIdentity()?.userId,externalLocked:()=>props.externalLocked})
const displayFacts=computed(()=>state.facts||state.lastDisplayFacts)
const operationOptions=computed(()=>displayFacts.value?.operationOptions||displayFacts.value?.operations||[])
const selected=computed(()=>displayFacts.value?.selectedOperation||null)
const frozenReceipt=computed(()=>{const fact=selected.value&&('originalFrozenReceipt' in selected.value?selected.value.originalFrozenReceipt:selected.value.originalReceipt)
  return fact?.id?fact:null})
const pending=computed(()=>state.writeState==='readback_pending')
const locked=computed(()=>state.writeState==='writing'||pending.value)
const assessment=computed(()=>controller.submission())
watch(locked,value=>emit('lock-change',value),{immediate:true,flush:'sync'})
watch(()=>state.writeState,value=>{if(value==='verified')emit('facts-changed',{phase:'verified',action:'resourceHandoff'})})
watch([()=>props.workOrderId,()=>props.operationId],([order,operation])=>{if(!order){controller.invalidate();return}
  if(String(order)!==state.workOrderId)controller.selectWorkOrder(String(order),{operationId:operation,allowLatestFormalLocation:props.allowLatestFormalLocation})
  else if(String(operation||'')!==state.operationId)controller.selectOperation(String(operation||''))},{immediate:true})
watch(()=>state.readState,value=>{if(value==='loaded')emit('location-change',state.operationId)})
async function selectViewedOperation(value){if(await controller.selectOperation(value))emit('view-selection-confirmed',state.operationId)}
function authenticationChanged(){controller.invalidate();if(!props.locationControlled&&props.workOrderId)controller.selectWorkOrder(String(props.workOrderId),{operationId:props.operationId,allowLatestFormalLocation:props.allowLatestFormalLocation})}
function buildDiagnostics(){return {factSource:'server',resourceHandoffFacts:state.facts,strictServerFacts:state.facts,
  factLoadFacts:state.factLoadFacts,readState:state.readState,executionReadbackState:state.writeState,
  submissionChecks:assessment.value.checks,errorMessage:state.error||null}}
defineExpose({refresh:options=>controller.load(options),buildDiagnostics})
onMounted(()=>globalThis.window?.addEventListener?.('pce:authentication-changed',authenticationChanged))
onBeforeUnmount(()=>{controller.invalidate();emit('lock-change',false);globalThis.window?.removeEventListener?.('pce:authentication-changed',authenticationChanged)})
</script>
<style scoped>
.resource-handoff{border-top:2px solid #cbd5e1;margin-top:24px;padding-top:16px}.resource-handoff p,.resource-handoff li{line-height:1.6;overflow-wrap:anywhere}.resource-handoff label{display:block;max-width:780px;margin:12px 0}.resource-handoff select,.resource-handoff textarea{display:block;box-sizing:border-box;width:100%;padding:9px;margin-top:6px;border:1px solid #cbd5e1;border-radius:7px;font:inherit}.resource-handoff button{padding:9px 12px;background:#3568dc;color:#fff;border:1px solid #3568dc;border-radius:7px;cursor:pointer}.resource-handoff button:disabled{opacity:.55;cursor:not-allowed}.resource-handoff dl{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.resource-handoff dt{color:#64748b;font-size:12px}.resource-handoff dd{margin:4px 0;overflow-wrap:anywhere}@media(max-width:540px){.resource-handoff dl{grid-template-columns:1fr}}
</style>
