<template>
  <section v-if="inspectionId || pending" class="exception-panel" :aria-label="title">
    <h3>{{ title }}</h3>
    <p v-if="error" role="alert">{{ error }}</p>
    <template v-if="pending">
      <p v-if="confirmed" role="status">{{ confirmed.statusLabel }} · {{ count(confirmed.quantity) }}</p>
      <p v-else role="status">本次提交结果待核。可查询同一次回执。</p>
      <button v-if="!confirmed" type="button" :disabled="busy" @click="queryResult">查询同一次回执</button>
      <button v-else type="button" :disabled="busy" @click="acknowledge">返回当前事实</button>
    </template>
    <template v-else>
      <button type="button" :disabled="loading" @click="readContext">刷新异常与保管事实</button>
      <p v-if="loading" role="status">正在读取本次检验的异常事实。</p>
      <template v-if="context">
        <dl class="exception-facts">
          <div><dt>采购订单</dt><dd>{{ shown(context.inspection.purchaseOrderNo) }}</dd></div>
          <div><dt>来源采购申请行</dt><dd>{{ requestLine(context.inspection) }}</dd></div>
          <div><dt>收货单与检验单</dt><dd>{{ shown(context.inspection.receiptNo) }} · {{ shown(context.inspection.inspectionNo) }}</dd></div>
          <div><dt>物料与单位</dt><dd>{{ shown(context.inspection.materialName) }} · {{ shown(context.inspection.unit) }}</dd></div>
          <div><dt>本次实收与正式合格</dt><dd>{{ count(context.inspection.registeredReceivedQuantity) }}／{{ count(context.inspection.qualifiedQuantity) }}</dd></div>
          <div><dt>检验判定依据</dt><dd>本次正式检验 {{ shown(context.inspection.inspectionNo) }} · {{ shown(context.inspection.qualityReleaseStatusLabel) }}</dd></div>
          <div><dt>正式不合格量</dt><dd>{{ count(context.inspection.rejectedQuantity) }}</dd></div>
          <div v-if="kind==='register'"><dt>本次最多可登记</dt><dd>{{ count(context.remainingRegistrableQuantity) }}</dd></div>
        </dl>
        <template v-if="kind==='register'">
          <p v-if="!context.registrations.length">本次检验尚无异常登记。</p>
          <ul v-else class="exception-history">
            <li v-for="row in context.registrations" :key="row.id">
              <p>{{ count(row.quantity) }} · {{ shown(row.source?.employeeName) }} · {{ shown(row.occurredAt) }}</p>
              <p>{{ shown(row.payload?.basis) }}</p>
              <router-link :to="custodyLink(row)">查看本笔登记的仓管保管入口</router-link>
            </li>
          </ul>
          <p v-if="!context.actionAuthorization.allowed">本次正式不合格范围已登记完毕。</p>
        </template>
        <template v-else>
          <p v-if="!context.registrations.length">本次检验尚无异常登记，待质检登记后核对。</p>
          <template v-else>
            <label>本次异常登记
              <select :value="registrationId || ''" @change="selectRegistration($event.target.value)">
                <option value="">请选择服务端提供的异常登记</option>
                <option v-for="row in context.registrations" :key="row.id" :value="row.id">
                  {{ row.occurredAt }} · {{ count(row.quantity) }} · {{ shown(row.source?.employeeName) }} · {{ shown(row.payload?.basis) }}
                </option>
              </select>
            </label>
            <template v-if="registrationId">
              <p role="status">{{ shown(context.custodyStatusLabel) }}</p>
              <dl class="exception-facts">
                <div><dt>本笔登记量</dt><dd>{{ count(root?.quantity) }}</dd></div>
                <div><dt>最近登记的实点量</dt><dd>{{ count(latest?.payload?.actualQuantity) }}</dd></div>
                <div><dt>当前确认保管量</dt><dd>{{ count(latest?.payload?.confirmedCustodyQuantity) }}</dd></div>
                <div><dt>本次差异待核</dt><dd>{{ count(latest?.payload?.differenceQuantity) }}</dd></div>
                <div><dt>实物位置</dt><dd>{{ locationText(latest) }}</dd></div>
                <div><dt>隔离情况</dt><dd>{{ isolatedText(latest?.payload?.isolated) }}</dd></div>
                <div><dt>确认保管人</dt><dd>{{ custodian(latest) }}</dd></div>
                <div v-if="latest?.payload?.pendingReason"><dt>待核原因</dt><dd>{{ latest.payload.pendingReason }}</dd></div>
              </dl>
              <details v-if="context.custodyFacts.length">
                <summary>逐次实物核对记录（{{ context.custodyFacts.length }}）</summary>
                <ol class="exception-history">
                  <li v-for="row in context.custodyFacts" :key="row.id">
                    <p>发生 {{ shown(row.occurredAt) }} · 登记 {{ shown(row.registeredAt) }}</p>
                    <p>实点 {{ count(row.payload.actualQuantity) }} · 确认保管 {{ count(row.payload.confirmedCustodyQuantity) }} · 差异 {{ count(row.payload.differenceQuantity) }}</p>
                    <p>实物位置 {{ locationText(row) }} · {{ isolatedText(row.payload.isolated) }}</p>
                    <p>核对人 {{ shown(row.source?.employeeName) }} · 确认保管人 {{ custodian(row) }}</p>
                    <p>{{ shown(row.payload.basis) }}</p>
                    <p v-if="row.payload.pendingReason">{{ row.payload.pendingReason }}</p>
                  </li>
                </ol>
              </details>
            </template>
          </template>
        </template>
        <form v-if="context.actionAuthorization.allowed" class="exception-form" @submit.prevent="submit">
          <label>实际发生时间（业务当地时间）
            <input v-model="form.occurredAt" type="datetime-local" step="1" required />
          </label>
          <label v-if="kind==='register'">本次登记不合格量（{{ unit }})
            <input v-model.trim="form.quantity" inputmode="decimal" required />
          </label>
          <template v-else>
            <label>本人实点数量（{{ unit }}，未知留空）
              <input v-model.trim="form.quantity" inputmode="decimal" />
            </label>
            <label class="exception-check"><input v-model="form.verified" type="checkbox" /> 本人已现场实点核实</label>
            <label>实际所在仓库
              <select v-model="form.warehouseId" @change="form.locationId=null">
                <option :value="null">未提供</option>
                <option v-for="row in warehouses" :key="row.id" :value="row.id">{{ row.name }} · {{ row.code }}</option>
              </select>
            </label>
            <label>实际所在库位
              <select v-model="form.locationId" :disabled="!form.warehouseId">
                <option :value="null">未提供</option>
                <option v-for="row in locations" :key="row.id" :value="row.id">{{ row.name }} · {{ row.code }}</option>
              </select>
            </label>
            <label>实际现场位置说明<input v-model.trim="form.description" maxlength="1000" /></label>
            <label>现场隔离情况
              <select v-model="form.isolated">
                <option :value="null">未提供</option>
                <option :value="true">已隔离</option>
                <option :value="false">未隔离</option>
              </select>
            </label>
            <label>待核原因（有差异或无法核实时填写）<textarea v-model.trim="form.pendingReason" maxlength="1000" /></label>
          </template>
          <label>本次办理依据<textarea v-model.trim="form.basis" maxlength="300" required /></label>
          <button type="submit" :disabled="busy">{{ kind==='register' ? '登记本次不合格范围' : '提交本人保管核对' }}</button>
        </form>
      </template>
    </template>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import request from '@/api/request.js'
import { getTabAuthEpoch, readTabIdentity } from '@/meta/runtime/tabAuthenticationContext.js'

const props = defineProps({kind:{type:String,required:true},inspectionId:{type:Number,default:null},inventoryFacts:{type:Object,default:()=>({})}})
const route=useRoute(), router=useRouter()
const title=props.kind==='register'?'来料不合格登记':'来料不合格保管核对'
const permission=props.kind==='register'?'quality.incoming_exception.register':'warehouse.incoming_exception.custody'
const identity=readTabIdentity()
const epoch=getTabAuthEpoch()
const storageKey=identity?.username ? 'pce-a10-action:'+identity.username+':'+props.kind : null
const context=ref(null), error=ref(''), loading=ref(false), busy=ref(false), pending=ref(null), confirmed=ref(null)
const defaults=()=>({occurredAt:'',quantity:'',verified:false,warehouseId:null,locationId:null,description:'',isolated:null,pendingReason:'',basis:''})
const form=reactive(defaults())
const registrationId=computed(()=>{
  if(props.kind!=='custody'||!props.inspectionId||route.query.a10Inspection!==String(props.inspectionId))return null
  const id=route.query.a10Registration
  return typeof id==='string' && /^[1-9]\d*$/.test(id) && Number.isSafeInteger(Number(id)) ? Number(id) : null
})
const root=computed(()=>context.value?.registrations.find(row=>row.id===registrationId.value))
// The service returns observations in registration order. Show the last stored observation and the full history.
const latest=computed(()=>context.value?.custodyFacts.at(-1))
const unit=computed(()=>context.value?.inspection.unit || confirmed.value?.source?.lineFacts?.unit)
const warehouses=computed(()=>(props.inventoryFacts.warehouses || []).filter(row=>row.isActive!==false))
const locations=computed(()=>(props.inventoryFacts.locations || []).filter(row=>row.isActive!==false&&row.warehouseId===form.warehouseId))
let readCycle=0

function shown(value){return value==null||value===''?'未提供':String(value)}
function count(value){return value==null?'未提供':String(value)+' '+shown(unit.value)}
function isolatedText(value){return value==null?'未提供':value?'已隔离':'未隔离'}
function custodian(row){return row?.payload?.confirmedCustodianId!=null ? shown(row.source?.employeeName) : '未提供'}
function requestLine(row){return row.sourcePurchaseRequestNo && row.sourcePurchaseRequestLineNo!=null ? row.sourcePurchaseRequestNo+' · 申请第 '+row.sourcePurchaseRequestLineNo+' 行' : '未提供'}
function locationText(row){
  const details=row?.payload
  if(!details)return '未提供'
  const warehouse=(props.inventoryFacts.warehouses || []).find(x=>x.id===details.warehouseId)
  const location=(props.inventoryFacts.locations || []).find(x=>x.id===details.locationId)
  return [warehouse?.name,location?.name,details.locationDescription].filter(Boolean).join(' · ') || '未提供'
}
function custodyLink(row){
  return {path:'/wms/inventory-balances',query:{a07Inspection:String(row.inspectionId),a10Inspection:String(row.inspectionId),a10Registration:String(row.id)}}
}
function selectRegistration(id){
  context.value=null
  return router.push({query:{...route.query,a10Inspection:id ? String(props.inspectionId) : undefined,a10Registration:id || undefined}})
}
function owned(){return getTabAuthEpoch()===epoch}
function url(id){return '/api/procurement/incoming-exceptions/'+id+'/'+props.kind+'/'}
function read(id,params){
  return request({url:url(id),params,meta:{module:props.kind==='register'?'QMS':'WMS',readOnly:true,factLoad:true}}).catch(()=>null)
}
function remember(value){
  if(!storageKey)throw Error('Missing tab identity')
  if(value)sessionStorage.setItem(storageKey,JSON.stringify(value))
  else sessionStorage.removeItem(storageKey)
  pending.value=value
}
try {
  const original=storageKey && JSON.parse(sessionStorage.getItem(storageKey) || 'null')
  if(original?.kind===props.kind && Number.isSafeInteger(original.id) && original.id>0 &&
     typeof original.key==='string' && typeof original.intent==='string')pending.value=original
} catch { /* The local record contains only action keys and cannot supply business facts. */ }

async function readContext(){
  const ticket=++readCycle,id=props.inspectionId,target=registrationId.value
  context.value=null
  error.value=''
  loading.value=false
  Object.assign(form,defaults())
  if(!id || pending.value || !owned())return
  loading.value=true
  const response=await read(id,target ? {registrationId:target} : {})
  if(ticket!==readCycle||!owned())return
  loading.value=false
  const value=response?.data
  if(!response?.success || value?.currentStateSource!=='server' || value.inspection?.inspectionId!==id ||
    value.registrationId!==target || !Array.isArray(value.registrations) || !Array.isArray(value.custodyFacts) ||
    typeof value.collectionVersion!=='string' || typeof value.actionAuthorization?.allowed!=='boolean' ||
    value.actionAuthorization.permission!==permission){
    error.value=response?.error?.message || '未取得本次检验一致的异常事实和办理资格。'
    return
  }
  context.value=value
}

function exactReceipt(value,original){
  return value?.inspectionId===original.id && value.kind===props.kind &&
    value.registrationId===original.registrationId && value.intentId===original.intent &&
    value.historicalFactOnly===true && value.inventoryEffect==='NONE' && Number.isSafeInteger(value.id)
}

async function submit(){
  const value=context.value
  if(busy.value || pending.value || !owned() || !value?.actionAuthorization.allowed)return
  const qty=form.quantity
  if(qty && !/^\d+(\.\d+)?$/.test(qty)){
    error.value='请按原单位填写十进制数量。'
    return
  }
  const original={kind:props.kind,id:props.inspectionId,registrationId:registrationId.value,key:crypto.randomUUID(),intent:crypto.randomUUID()}
  const details=props.kind==='register' ? {quantity:qty,basis:form.basis} : {
    actualQuantity:qty || null,warehouseId:form.warehouseId,locationId:form.locationId,
    locationDescription:form.description,isolated:form.isolated,quantityVerified:form.verified,
    pendingReason:form.pendingReason,basis:form.basis,
  }
  const payload={idempotencyKey:original.key,intentId:original.intent,expectedCollectionVersion:value.collectionVersion,
    reason:form.basis,occurredAt:form.occurredAt,registrationId:original.registrationId,details}
  try { remember(original) } catch {
    error.value='无法保存同次提交标识，请恢复浏览器会话存储后再提交。'
    return
  }
  busy.value=true
  context.value=null
  error.value=''
  try {
    const response=await request({method:'POST',url:url(original.id),data:payload,
      meta:{module:props.kind==='register'?'QMS':'WMS',actionCode:permission,explicitBusinessAction:true}})
    if(!owned())return
    if(response?.success && exactReceipt(response.data,original))confirmed.value=response.data
    else if([400,401,403,404,409].includes(response?.meta?.status) && response?.error?.code!=='MATERIAL_CONCURRENCY_CONFLICT'){
      remember(null)
      await readContext()
      error.value=response?.error?.message || '本次提交被拒绝。'
    } else error.value=response?.error?.message || '未取得准确回执，请查询同一次提交。'
  } catch {
    if(owned())error.value='未取得准确回执，请查询同一次提交。'
  } finally { busy.value=false }
}

async function queryResult(){
  if(!pending.value || busy.value || !owned())return
  const original=pending.value
  busy.value=true
  error.value=''
  try {
    const response=await read(original.id,{resultKey:original.key,intentId:original.intent})
    if(!owned())return
    const value=response?.data
    if(response?.success && value?.historicalReceiptOnly===true && value.automaticReplayAllowed===false && value.resultState==='COMMITTED' &&
      exactReceipt(value.result,original))confirmed.value=value.result
    else error.value=response?.error?.message || '服务端尚未取得本次原动作回执。'
  } finally { busy.value=false }
}

function acknowledge(){
  if(!confirmed.value)return
  remember(null)
  confirmed.value=null
  return readContext()
}
watch([()=>props.inspectionId,registrationId],readContext,{immediate:true})
onBeforeUnmount(()=>{readCycle++})
</script>

<style scoped>
.exception-panel{margin-top:12px;padding:12px;border:1px solid #d6e0ee;border-radius:9px;min-width:0;overflow-wrap:anywhere}
.exception-facts,.exception-form{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}
.exception-facts dd{margin:0;font-weight:600;font-variant-numeric:tabular-nums}
.exception-form label,.exception-panel>label{display:grid;gap:4px;min-width:0}
.exception-panel input,.exception-panel select,.exception-panel textarea,.exception-panel button{min-height:44px;max-width:100%;padding:6px 8px;box-sizing:border-box}
.exception-panel select,.exception-panel textarea,.exception-form input:not([type=checkbox]){width:100%;min-width:0}
.exception-form .exception-check{display:flex;align-items:center}
.exception-history{padding-inline-start:22px}
.exception-history p{margin-block:4px}
.exception-panel details{margin-block:12px}
.exception-form{margin-top:12px;align-items:end}
@media(max-width:600px){.exception-form{grid-template-columns:1fr}.exception-facts{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
