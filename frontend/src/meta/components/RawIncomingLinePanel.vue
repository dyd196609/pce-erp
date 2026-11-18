<template>
  <section class="raw-line-panel" :aria-label="title" :data-a07-mode="mode">
    <h2>{{ title }}</h2>
    <p v-if="mode==='receipt'">使用原采购订单的收货交接入口。选择服务端提供的采购行后，读取本次收货资格。</p>
    <p v-if="mode==='inbound'">使用原来料检验记录的仓管入库入口。按本张检验单核对合格、已入库和当前额度。</p>
    <form v-if="mode!=='quality' || !sourceId" class="raw-fields" @submit.prevent="openHandoff">
      <label>原单据交接链接<input v-model.trim="handoff" placeholder="粘贴原页面提供的交接链接" :disabled="Boolean(pending)" /></label>
      <button type="submit" :disabled="!handoff || Boolean(pending)">打开交接单据</button>
    </form>
    <label v-if="mode==='quality' && qualityRows.length">选取本次收货对应的检验单
      <select :value="action==='transition-inspection'?sourceId:''" :disabled="Boolean(pending)" @change="chooseInspection($event.target.value)">
        <option value="">请选择授权目录中的检验单</option>
        <option v-for="row in qualityRows" :key="row.id" :value="row.id">{{ row.inspectionNo }} · {{ row.receiptNo }} · {{ row.purchaseOrderNo }}</option>
      </select>
    </label>
    <button v-if="sourceId && !pending" type="button" :disabled="busy || loading" @click="readContext">刷新当前原记录</button>
    <p v-if="loading" role="status">正在读取当前原记录和办理资格。</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <template v-if="!pending">
      <p v-if="qualityRow?.lineReleaseStatus==='SOURCE_UNKNOWN'">来源待核：{{ text(qualityRow.lineReleaseBlockingReason?.message) }}</p>
      <template v-if="facts">
        <h3>采购订单 {{ text(facts.source.orderNo) }}</h3>
        <label v-if="mode==='receipt'">本次采购行
          <select :value="lineId" :disabled="busy" @change="chooseLine($event.target.value)">
            <option value="">请选择本次准确采购行</option>
            <option v-for="row in facts.source.lineCandidates" :key="row.purchaseOrderItemId" :value="row.purchaseOrderItemId">
              {{ requestLine(row) }} · {{ text(row.materialName) }} · {{ text(row.materialCode) }}{{ row.sourceStatus==='SOURCE_UNKNOWN' ? ' · 来源待核' : '' }}
            </option>
          </select>
        </label>
        <p v-if="mode==='receipt' && !facts.source.lineCandidates.length">服务端本次未提供采购行候选。</p>
        <template v-if="line">
          <dl class="raw-facts">
            <div><dt>来源采购申请及行号</dt><dd>{{ requestLine(line) }}</dd></div>
            <div><dt>采购行独立业务号</dt><dd>{{ text(line.purchaseOrderLineNo) }}</dd></div>
            <div><dt>物料</dt><dd>{{ text(line.materialName) }} · {{ text(line.materialCode) }}</dd></div>
            <template v-if="mode==='receipt'">
              <div><dt>本行原批准量</dt><dd>{{ qty(line.orderedQuantity,line.unit) }}</dd></div>
              <div><dt>本行累计正式实收</dt><dd>{{ qty(line.registeredReceivedQuantity,line.unit) }}</dd></div>
              <div><dt>本行当前可收</dt><dd>{{ qty(line.remainingReceivableQuantity,line.unit) }}</dd></div>
            </template>
          </dl>
          <p v-if="line.blockingReason">{{ line.blockingReason.message }}</p>
        </template>

        <article v-for="row in releases" :key="row.inspectionId" class="raw-release" :data-a07-inspection="row.inspectionNo">
          <h4>检验单 {{ text(row.inspectionNo) }} · 收货单 {{ text(row.receiptNo) }}</h4>
          <p>{{ text(row.qualityReleaseStatusLabel) }}</p>
          <dl class="raw-facts">
            <div v-for="[field,label] in releaseFields" :key="field"><dt>{{ label }}</dt><dd :data-a07-field="field">{{ qty(row[field],row.unit) }}</dd></div>
          </dl>
          <p v-if="row.blockingReason">{{ row.blockingReason.message }}</p>
          <details v-if="row.inboundRecords?.length"><summary>逐笔入库和库存流水</summary>
            <ul><li v-for="record in row.inboundRecords" :key="record.inboundId">{{ record.inboundNo }} · {{ record.transactionNo }} · {{ qty(record.quantity,row.unit) }}</li></ul>
          </details>
          <a v-if="mode==='quality'" :href="handoffUrl('inbound',row.inspectionId)">本张检验单的仓管入库入口</a>
        </article>

        <template v-if="!authorized">
          <p v-if="!releases.some(row=>row.blockingReason?.message===facts.actionAuthorization?.blockingReason?.message && row.blockingReason?.message)">{{ mode==='receipt'&&!lineId ? '请选择本次采购行，再读取收货资格。' : text(facts.actionAuthorization?.blockingReason?.message || facts.selectionStatusLabel) }}</p>
        </template>
        <form v-else class="raw-fields" @submit.prevent="submit">
          <label v-if="action==='transition-inspection'">本次检验动作
            <select v-model="inspectionAction" required><option value="">请选择本次动作</option>
              <option v-if="facts.source.state?.status==='pending'" value="START">开始检验</option>
              <template v-if="facts.source.state?.status==='inspecting'"><option value="QUALIFY">登记正式合格量</option><option value="REJECT">判定不合格</option></template>
            </select>
          </label>
          <label v-if="needsQuantity">{{ quantityLabel }}（{{ text(facts.source.unit) }}）
            <input v-model.trim="quantity" inputmode="decimal" required :aria-label="quantityLabel" />
          </label>
          <template v-if="mode==='inbound'">
            <label>正式仓库<select v-model="warehouse" required @change="location=''">
              <option value="">请选择</option><option v-for="row in warehouseChoices" :key="row.id" :value="row.code">{{ row.name }} · {{ row.code }}</option>
            </select></label>
            <label>正式库位<select v-model="location" required>
              <option value="">请选择</option><option v-for="row in locations" :key="row.id" :value="row.code">{{ row.name }} · {{ row.code }}</option>
            </select></label>
            <label>本次入库批号<input v-model.trim="lot" required maxlength="120" /></label>
          </template>
          <label>本次办理依据<textarea v-model.trim="reason" maxlength="300" required /></label>
          <button type="submit" :disabled="!canSubmit">{{ submitLabel }}</button>
        </form>
      </template>
    </template>
    <section v-else class="raw-release" aria-label="本次原动作回执">
      <p v-if="receipt">本次原回执：{{ text(receipt.objectNo) }}。</p>
      <p v-else role="status">本次结果尚未核实。原动作标识 {{ pending.key }}。</p>
      <button type="button" :disabled="busy" @click="queryOriginal">仅查询同一次提交</button>
      <a v-if="receipt && pending.action==='confirm-receipt'" :href="handoffUrl('quality',receipt.objectId,'a07Receipt')">本次收货的质检办理入口</a>
      <button v-if="receipt" type="button" :disabled="busy" @click="acknowledge">查看当前办理事实</button>
    </section>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import request from '@/api/request.js'
import { getTabAuthEpoch, readTabIdentity } from '@/meta/runtime/tabAuthenticationContext.js'

const props = defineProps({mode:{type:String,required:true},qualityRows:{type:Array,default:()=>[]},inventoryFacts:{type:Object,default:()=>({})},initialSourceId:{type:Number,default:null}})
const emit = defineEmits(['changed'])
const route = useRoute(), router = useRouter()
const paths = { receipt:'/wms/purchase-receive-preview', quality:'/qms/incoming-inspections', inbound:'/wms/inventory-balances' }
const keys = { receipt:'a07Order', quality:'a07Inspection', inbound:'a07Inspection' }
const titles = { receipt:'生产用原料正式收货', quality:'来料检验逐行放行', inbound:'生产用原料合格入库' }
const codes = {'confirm-receipt':'procurement.receipt.receive','create-inspection':'quality.purchase.inspect','transition-inspection':'quality.purchase.inspect','confirm-inbound':'warehouse.purchase.putaway'}
const types = {'confirm-receipt':'PurchaseReceipt','create-inspection':'PurchaseInspection','transition-inspection':'PurchaseInspection','confirm-inbound':'WarehouseInbound'}
const sourceTypes = {'confirm-receipt':'PurchaseOrder','create-inspection':'PurchaseReceipt','transition-inspection':'PurchaseInspection','confirm-inbound':'PurchaseInspection'}
const releaseFields = [['registeredReceivedQuantity','本次正式实收量'],['inspectionScopeQuantity','检验范围'],['actualInspectedQuantity','实际已检件数'],['qualifiedQuantity','正式合格量'],['rejectedQuantity','不合格量'],['successfullyInboundQuantity','本检验已入库量'],['currentInboundEligibleQuantity','当前最多可入量']]
const purpose = 'PRODUCTION_USE'
const title = titles[props.mode]
const module = props.mode==='quality'?'QMS':'WMS'
const epoch = getTabAuthEpoch()
const identity = readTabIdentity()
const actor = identity?.username || identity?.userId || identity?.id
const cache = actor ? `pce-a07-original-action:${props.mode}:${actor}` : null
const facts = ref(null), error = ref(''), loading = ref(false), busy = ref(false), receipt = ref(null), pending = ref(null)
const handoff = ref(''), quantity = ref(''), reason = ref(''), warehouse = ref(''), location = ref(''), lot = ref(''), inspectionAction = ref('')
const positiveId = value => typeof value === 'string' && /^[1-9]\d{0,14}$/.test(value) && Number.isSafeInteger(Number(value)) ? Number(value) : null
const creationSource = computed(()=>props.mode==='quality'?positiveId(route.query.a07Receipt):null)
const sourceId = computed(()=>creationSource.value||positiveId(route.query[keys[props.mode]])||props.initialSourceId)
const lineId = computed(()=>props.mode==='receipt'?positiveId(route.query.a07Line):null)
const action = computed(()=>props.mode==='receipt'?'confirm-receipt':props.mode==='inbound'?'confirm-inbound':creationSource.value?'create-inspection':'transition-inspection')
const qualityRow = computed(()=>props.mode==='quality'&&!creationSource.value?props.qualityRows.find(row=>row.id===sourceId.value):null)
const line = computed(()=>facts.value?.source.lineCandidates.find(row=>row.purchaseOrderItemId===facts.value.source.lineId))
const releases = computed(()=>props.mode==='receipt' ? line.value?.inspectionScopes||[] : facts.value?.source.lineReleaseFacts ? [facts.value.source.lineReleaseFacts] : [])
const authorized = computed(()=>facts.value?.actionAuthorization?.allowed===true && (props.mode!=='receipt'||lineId.value===facts.value?.source.lineId))
const warehouseChoices = computed(()=>(props.inventoryFacts?.warehouses||[]).filter(row=>row.isActive!==false))
const locations = computed(()=>(props.inventoryFacts?.locations||[]).filter(row=>row.warehouseCode===warehouse.value&&row.isActive!==false))
const needsQuantity = computed(()=>props.mode!=='quality'||inspectionAction.value==='QUALIFY')
const quantityLabel = computed(()=>props.mode==='receipt'?'本次实际收货量':props.mode==='inbound'?'本次实际入库量':'本次正式合格量')
const submitLabel = computed(()=>({'confirm-receipt':'确认本行收货','create-inspection':'建立本次收货检验单','transition-inspection':'提交本次检验动作','confirm-inbound':'确认本张检验单入库'})[action.value])
const canSubmit = computed(()=>authorized.value && !busy.value && !loading.value && !pending.value && Boolean(reason.value) &&
  (!needsQuantity.value || /^\d+(\.\d+)?$/.test(quantity.value)) &&
  (action.value!=='transition-inspection'||Boolean(inspectionAction.value)) &&
  (props.mode!=='inbound'||locations.value.some(row=>row.code===location.value)&&Boolean(lot.value)))
let cycle = 0

function text(value){return value==null||value===''?'未提供':String(value)}
function qty(value,unit){return value==null||value===''?'未提供':`${value} ${unit||'（单位未提供）'}`}
function requestLine(row){return row.sourcePurchaseRequestNo && row.sourcePurchaseRequestLineNo!=null ? `${row.sourcePurchaseRequestNo} · 申请第 ${row.sourcePurchaseRequestLineNo} 行` : '来源申请或行号未提供'}
function handoffUrl(target,id,key=keys[target]){return router.resolve({path:paths[target],query:{[key]:String(id)}}).href}
function openHandoff(){
  try {
    const url = new URL(handoff.value,window.location.href)
    const [path,query] = url.hash.slice(1).split('?')
    const params = new URLSearchParams(query)
    const acceptedPath = path===paths[props.mode] || props.mode==='receipt'&&path==='/wms/purchase-receives'
    if(url.origin!==window.location.origin||!acceptedPath)throw Error()
    const key = props.mode==='quality'&&params.has('a07Receipt')?'a07Receipt':keys[props.mode]
    const id = positiveId(params.get(key))
    if(!id)throw Error()
    const next = {[keys[props.mode]]:undefined,a07Receipt:undefined,a07Line:undefined,[key]:String(id)}
    handoff.value=''
    if(sourceId.value===id&&(!lineId.value||props.mode!=='receipt')&&Boolean(creationSource.value)===(key==='a07Receipt'))return readContext()
    return router.replace({query:{...route.query,...next}})
  } catch { error.value='请选择本站原页面提供的准确单据交接链接。' }
}
function chooseLine(id){router.replace({query:{...route.query,a07Line:id||undefined}})}
function chooseInspection(id){router.replace({query:{...route.query,a07Inspection:id||undefined,a07Receipt:undefined}})}

function remember(value){
  pending.value=value
  if(cache){if(value)sessionStorage.setItem(cache,JSON.stringify(value));else sessionStorage.removeItem(cache)}
}
try {
  const original = cache&&JSON.parse(sessionStorage.getItem(cache)||'null')
  if(original && codes[original.action] && Number.isSafeInteger(original.id) && typeof original.key==='string')pending.value=original
} catch { /* An unreadable presentation record carries no result facts. */ }

function url(kind,id){return `/api/procurement/scm-runtime-actions/${kind}/${encodeURIComponent(id)}/`}
async function get(kind,id,params){return request({url:url(kind,id),params,meta:{module,readOnly:true,factLoad:true}}).catch(()=>null)}
function parameters(line,key){return {usagePurpose:purpose,...(line?{purchaseOrderItemId:line}:{}),...(key?{idempotencyKey:key}:{})}}
function currentOwner(){return epoch===getTabAuthEpoch()}
function validResult(result,original){return result?.usagePurpose===purpose && result?.objectType===types[original.action] && Number.isSafeInteger(result.objectId) && (original.action!=='transition-inspection'||result.objectId===original.id)}

async function readContext(){
  const ticket=++cycle, id=sourceId.value, selected=lineId.value, kind=action.value
  facts.value=null;error.value='';loading.value=false;quantity.value='';inspectionAction.value='';reason.value=''
  if(!id||pending.value||!currentOwner())return
  loading.value=true
  const response=await get(kind,id,parameters(selected))
  if(ticket!==cycle||!currentOwner())return
  loading.value=false
  const data=response?.data, source=data?.source
  if(!response?.success || data?.usagePurpose!==purpose || data?.currentStateSource!=='server' || source?.sourceId!==id || source?.sourceType!==sourceTypes[kind] ||
    !Array.isArray(source?.lineCandidates) || selected&&source.lineId!==selected ||
    (kind==='confirm-inbound'||kind==='transition-inspection')&&source.lineReleaseFacts?.inspectionId!==id){
    error.value=response?.error?.message||'未取得当前单据一致的逐行来源，办理资格未知。'
    return
  }
  facts.value=data
}
async function submit(){
  if(!canSubmit.value||!currentOwner())return
  const current=facts.value, original={action:action.value,id:sourceId.value,line:lineId.value,key:crypto.randomUUID()}
  remember(original);busy.value=true;error.value='';receipt.value=null
  const input={usagePurpose:purpose,expectedSourceFingerprint:current.sourceFingerprint,idempotencyKey:original.key,reason:reason.value}
  if(original.action==='confirm-receipt')Object.assign(input,{purchaseOrderItemId:original.line,quantity:quantity.value})
  if(original.action==='transition-inspection')Object.assign(input,{inspectionAction:inspectionAction.value,qualifiedQuantity:inspectionAction.value==='QUALIFY'?quantity.value:null})
  if(original.action==='confirm-inbound')Object.assign(input,{quantity:quantity.value,warehouseCode:warehouse.value,locationCode:location.value,lotNumbers:{[current.source.materialId]:lot.value}})
  try {
    const response=await request({method:'POST',url:url(original.action,original.id),data:input,meta:{module,actionCode:codes[original.action],explicitBusinessAction:true}})
    if(!currentOwner())return
    if(response?.success&&validResult(response.data,original))receipt.value=response.data
    else {
      error.value=response?.error?.message||'未取得同次回执，请查询原动作。'
      if([400,401,403,404].includes(response?.meta?.status)){remember(null);facts.value=null}
    }
  } catch { if(currentOwner())error.value='未取得同次回执，请查询原动作。' }
  finally { busy.value=false }
}
async function queryOriginal(){
  if(busy.value||!pending.value||!currentOwner())return
  const original=pending.value
  busy.value=true;error.value=''
  const response=await get(original.action,original.id,parameters(original.line,original.key))
  busy.value=false
  if(!currentOwner())return
  const data=response?.data
  if(response?.success && data?.historicalReceiptOnly===true && data.automaticReplayAllowed===false && data.executionAuthorizedByResult===false && data.resultState==='COMMITTED' && validResult(data.result,original))receipt.value=data.result
  else if(response?.success && data?.resultState==='UNKNOWN')error.value='服务端尚未取得本次原动作回执。'
  else error.value=response?.error?.message||'同次回执读取失败。'
}
async function acknowledge(){
  if(!receipt.value)return
  const original=pending.value, result=receipt.value
  remember(null);receipt.value=null;emit('changed')
  if(original.action==='create-inspection')return chooseInspection(String(result.objectId))
  return readContext()
}
watch([sourceId,lineId,action],readContext,{immediate:true})
onBeforeUnmount(()=>{cycle++})
</script>

<style scoped>
.raw-line-panel,.raw-release{min-width:0;overflow-wrap:anywhere;border:1px solid #d6e0ee;border-radius:9px;padding:12px;margin-block:12px}
.raw-line-panel h2,.raw-line-panel h3,.raw-line-panel h4{margin:0 0 8px}
.raw-facts,.raw-fields{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}
.raw-facts dt{color:#41546a}.raw-facts dd{margin:0;font-weight:600;font-variant-numeric:tabular-nums}
.raw-line-panel label{display:grid;grid-template-columns:minmax(0,1fr);gap:4px;min-width:0}
.raw-line-panel input,.raw-line-panel select,.raw-line-panel textarea,.raw-line-panel button,.raw-release a{min-height:44px;max-width:100%;padding:6px 8px}
.raw-line-panel input,.raw-line-panel select,.raw-line-panel textarea{box-sizing:border-box;width:100%;min-width:0}
.raw-release a{display:inline-flex;align-items:center}
@media(max-width:600px){.raw-fields{grid-template-columns:1fr}.raw-facts{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
