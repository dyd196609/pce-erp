<template>
  <section class="raw-line-panel" :aria-label="title" :data-a07-mode="mode">
    <h2>{{ title }}</h2>
    <p v-if="mode==='receipt'">按采购单号找单。选中后选择准确采购行，核对当前可收量和单位。</p>
    <p v-if="mode==='inbound'">按采购单号、收货单号或检验单号找单。选中后核对本次检验的合格量、已入库量和当前额度。</p>
    <section v-if="supportsDirectory && !pending" aria-label="仓管授权单据目录">
      <form class="raw-lookup" @submit.prevent="searchDirectory()">
        <label>{{ directoryLabel }}
          <input v-model.trim="directoryInput" maxlength="100" :placeholder="directoryLabel" />
        </label>
        <button type="submit" :disabled="busy">查找单据</button>
      </form>
      <p v-if="directoryLoading" role="status">正在读取仓管授权单据。</p>
      <p v-else-if="directoryError" role="alert">{{ directoryError }}</p>
      <template v-else-if="directory">
        <p v-if="directory.count===0">查无匹配单据。</p>
        <template v-else>
          <p role="status">匹配 {{ directory.count }} 条 · 第 {{ directory.page }} 页</p>
          <ul class="raw-lookup-results">
            <li v-for="row in directory.results" :key="row.sourceId">
              <button type="button" :aria-pressed="row.sourceId===sourceId" :disabled="busy" @click="selectDirectoryRow(row)">
                {{ mode==='receipt' ? row.purchaseOrderNo : row.inspectionNo }}
              </button>
              <div>
                <span v-if="mode==='inbound'">收货单 {{ text(row.receiptNo) }} · 采购订单 {{ text(row.purchaseOrderNo) }} · </span>
                <strong>{{ text(row.statusLabel) }}</strong>
                <ul v-if="row.summary?.materials?.length">
                  <li v-for="(material,index) in row.summary.materials" :key="index">
                    {{ requestLine(material) }} · {{ text(material.materialName) }} · {{ text(material.materialCode) }} · {{ text(material.unit) }}
                  </li>
                </ul>
                <p v-else-if="row.summary?.materialName">{{ text(row.summary.materialName) }} · {{ text(row.summary.materialCode) }} · {{ text(row.summary.unit) }}</p>
                <p v-if="directoryBlockingReason(row)">{{ directoryBlockingReason(row) }}</p>
              </div>
            </li>
          </ul>
          <nav v-if="directory.count>directory.pageSize" class="raw-lookup-pages" aria-label="仓管单据分页">
            <button type="button" :disabled="directory.page<=1" @click="searchDirectory(directory.page-1)">上一页</button>
            <button type="button" :disabled="directory.page*directory.pageSize>=directory.count" @click="searchDirectory(directory.page+1)">下一页</button>
          </nav>
        </template>
      </template>
    </section>
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
const supportsDirectory = props.mode==='receipt' || props.mode==='inbound'
const directoryLabel = props.mode==='receipt' ? '采购单号' : '采购单号、收货单号或检验单号'
const directoryQuery = computed(()=>typeof route.query.a07Search==='string' ? route.query.a07Search : null)
const directoryPage = computed(()=>positiveId(route.query.a07Page) || 1)
const directoryInput = ref(''), directory = ref(null), directoryError = ref(''), directoryLoading = ref(false)
let directoryCycle = 0
let selectedContext = null
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
    selectedContext=null
    const next = {[keys[props.mode]]:undefined,a07Receipt:undefined,a07Line:undefined,[key]:String(id)}
    handoff.value=''
    if(sourceId.value===id&&(!lineId.value||props.mode!=='receipt')&&Boolean(creationSource.value)===(key==='a07Receipt'))return readContext()
    return router.replace({query:{...route.query,...next}})
  } catch { error.value='请选择本站原页面提供的准确单据交接链接。' }
}
function chooseLine(id){router.replace({query:{...route.query,a07Line:id||undefined}})}
function chooseInspection(id){router.replace({query:{...route.query,a07Inspection:id||undefined,a07Receipt:undefined}})}

function directoryBlockingReason(row){
  return row.summary?.blockingReason?.message ||
    (row.sourceStatus==='SOURCE_UNKNOWN' ? row.actionAuthorization?.blockingReason?.message : '')
}

function clearContext(){
  cycle++
  facts.value=null
  error.value=''
  loading.value=false
}

async function searchDirectory(requestedPage){
  if(!supportsDirectory || busy.value || pending.value || !currentOwner())return
  const page=requestedPage ?? 1
  const query=requestedPage==null ? directoryInput.value : directoryQuery.value
  const previousQuery=directoryQuery.value, previousPage=directoryPage.value
  clearContext()
  selectedContext=null
  await router.push({query:{...route.query,[keys[props.mode]]:undefined,a07Line:undefined,a07Search:query,a07Page:page>1 ? String(page) : undefined}})
  if(query===previousQuery && page===previousPage)await readDirectory()
}

async function readDirectory(){
  const ticket=++directoryCycle, query=directoryQuery.value, page=directoryPage.value
  directory.value=null
  directoryError.value=''
  directoryLoading.value=false
  if(!supportsDirectory || query===null || pending.value || !currentOwner())return
  directoryInput.value=query
  directoryLoading.value=true
  const kind=action.value
  const response=await read('/api/procurement/scm-runtime-actions/'+kind+'/sources/',{q:query,page,pageSize:20})
  if(ticket!==directoryCycle || !currentOwner())return
  directoryLoading.value=false
  const data=response?.data
  if(!response?.success || data?.contractVersion!=='PCE-WMS-SCOPED-SOURCE-DIRECTORY-V1' ||
    data.action!==kind || data.usagePurpose!==purpose || data.currentStateSource!=='server' || data.page!==page ||
    !Number.isSafeInteger(data.count) || data.count<0 || data.pageSize!==20 || !Array.isArray(data.results) ||
    data.results.some(row=>!Number.isSafeInteger(row.sourceId) || row.sourceId<=0 || row.sourceType!==sourceTypes[kind])){
    const status=response?.meta?.status
    const label=status===401?'请登录后读取单据':status===403?'无权读取仓管单据目录':'仓管单据目录读取失败'
    directoryError.value=response?.error?.message ? label+'：'+response.error.message : label
    return
  }
  directory.value=data
}

async function selectDirectoryRow(row){
  if(busy.value || pending.value || !currentOwner())return
  const same=sourceId.value===row.sourceId && !lineId.value
  clearContext()
  selectedContext=null
  // The catalogue provides a locator. Only accept the original same-origin action endpoint and purpose.
  if(row.contextUrl!==url(action.value,row.sourceId)+'?usagePurpose='+purpose){
    error.value='该目录记录的原单据链接无法核对。'
    return
  }
  selectedContext={id:row.sourceId,path:row.contextUrl}
  if(same)return readContext()
  await router.push({query:{...route.query,[keys[props.mode]]:String(row.sourceId),a07Line:undefined}})
}

function remember(value){
  pending.value=value
  if(cache){if(value)sessionStorage.setItem(cache,JSON.stringify(value));else sessionStorage.removeItem(cache)}
}
try {
  const original = cache&&JSON.parse(sessionStorage.getItem(cache)||'null')
  if(original && codes[original.action] && Number.isSafeInteger(original.id) && typeof original.key==='string')pending.value=original
} catch { /* An unreadable presentation record carries no result facts. */ }

function url(kind,id){return `/api/procurement/scm-runtime-actions/${kind}/${encodeURIComponent(id)}/`}
async function read(path,params){return request({url:path,params,meta:{module,readOnly:true,factLoad:true}}).catch(()=>null)}
async function get(kind,id,params){return read(url(kind,id),params)}
function parameters(line,key){return {usagePurpose:purpose,...(line?{purchaseOrderItemId:line}:{}),...(key?{idempotencyKey:key}:{})}}
function currentOwner(){return epoch===getTabAuthEpoch()}
function validResult(result,original){return result?.usagePurpose===purpose && result?.objectType===types[original.action] && Number.isSafeInteger(result.objectId) && (original.action!=='transition-inspection'||result.objectId===original.id)}

async function readContext(){
  const ticket=++cycle, id=sourceId.value, selected=lineId.value, kind=action.value
  facts.value=null;error.value='';loading.value=false;quantity.value='';inspectionAction.value='';reason.value=''
  if(!id||pending.value||!currentOwner())return
  loading.value=true
  const contextUrl=selectedContext?.id===id ? selectedContext.path : null
  const response=contextUrl ? await read(contextUrl,selected ? {purchaseOrderItemId:selected} : {}) : await get(kind,id,parameters(selected))
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
  return Promise.all([readContext(),readDirectory()])
}
watch([sourceId,lineId,action],readContext,{immediate:true})
if(supportsDirectory)watch([directoryQuery,directoryPage],readDirectory,{immediate:true})
onBeforeUnmount(()=>{cycle++;directoryCycle++})
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
.raw-lookup{display:flex;flex-wrap:wrap;align-items:end;gap:8px;margin-block:8px}
.raw-lookup label{flex:1 1 240px}
.raw-lookup-results{list-style:none;padding:0}
.raw-lookup-results>li{display:flex;flex-wrap:wrap;align-items:start;gap:8px;border-top:1px solid #d6e0ee;padding:8px 0}
.raw-lookup-results>li>div{flex:1 1 240px;min-width:0}
.raw-lookup-results p{margin:4px 0}
.raw-lookup-results button[aria-pressed=true]{font-weight:700}
.raw-lookup-pages{display:flex;gap:8px}
@media(max-width:600px){.raw-fields{grid-template-columns:1fr}.raw-facts{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
