<template>
  <section v-if="inspectionId && registrationId" class="return-panel" :aria-label="title">
    <h4>{{ title }}</h4>
    <button type="button" :aria-expanded="open" @click="toggle">
      {{ open ? '收起退供信息' : title }}
    </button>
    <template v-if="open">
      <p v-if="error" role="alert">{{ error }}</p>
      <template v-if="pending">
        <p v-if="receipt" role="status">{{ receipt.statusLabel }} · {{ amount(receipt.quantity, receipt.source?.lineFacts?.unit) }}</p>
        <p v-else role="status">本次提交结果待核，可以查询同一次回执。</p>
        <button v-if="receipt" type="button" @click="acknowledge">返回当前退供事实</button>
        <button v-else type="button" :disabled="busy" @click="queryResult">查询同一次退供回执</button>
      </template>
      <template v-else>
        <button type="button" :disabled="loading || busy" @click="load">刷新本笔退供</button>
        <p v-if="loading" role="status">正在读取本笔退供事实和办理资格。</p>
        <template v-if="context">
          <p>{{ context.inspection.purchaseOrderNo }} · {{ context.inspection.receiptNo }} · {{ context.inspection.inspectionNo }}</p>
          <p>{{ context.inspection.materialName }} · {{ unit }} · 采购来源 {{ sourceLine }}</p>
          <p role="status">{{ summary.statusLabel }}</p>
          <dl class="return-grid">
            <div v-for="[key,label] in quantityFields" :key="key">
              <dt>{{ label }}</dt><dd>{{ amount(summary[key]) }}</dd>
            </div>
          </dl>
          <h5>供应商历次回复及附加条件</h5>
          <p v-if="!context.supplierOpinions.length">当前没有供应商回复。</p>
          <ol v-else class="return-list">
            <li v-for="opinion in context.supplierOpinions" :key="opinion.id">
              <p class="reply">{{ opinion.payload.replyContent }}</p>
              <p>实际回复 {{ shown(opinion.occurredAt) }} · 登记 {{ shown(opinion.registeredAt) }} · {{ shown(opinion.source?.employeeName) }}</p>
              <ul v-if="opinion.payload.evidenceReferences?.length">
                <li v-for="reference in opinion.payload.evidenceReferences" :key="reference">{{ reference }}</li>
              </ul>
            </li>
          </ol>
          <h5>企业申请与决定</h5>
          <p v-if="!summary.requests.length">本笔异常尚无企业退供申请。</p>
          <ul v-else class="return-list">
            <li v-for="application in summary.requests" :key="application.requestId">
              <strong>{{ application.statusLabel }}</strong>
              <p>{{ applicationLabel(application) }}</p>
              <p>批准 {{ amount(application.approvedQuantity) }} · 已交 {{ amount(application.handedQuantity) }} · 批准未交 {{ amount(application.remainingApprovedQuantity) }}</p>
              <p>到场授权代表 {{ shown(application.proposal.receiverName) }} · 接收授权依据 {{ shown(application.proposal.receiverAuthorizationReference) }}</p>
              <p>申请依据 {{ shown(application.proposal.returnBasis) }}</p>
            </li>
          </ul>
          <label v-if="choosesRequest && summary.requests.length">
            <span :id="kind+'-request-label'">选择本次退供申请</span>
            <select :aria-labelledby="kind+'-request-label'" :value="requestId || ''" @change="selectRequest">
              <option value="">请选择本次退供申请</option>
              <option v-for="application in summary.requests" :key="application.requestId" :value="application.requestId">
                {{ applicationLabel(application) }} · {{ application.statusLabel }}
              </option>
            </select>
          </label>
          <details v-if="returnHistory.length">
            <summary>历次申请、企业决定及现场签收</summary>
            <ol class="return-list">
              <li v-for="item in returnHistory" :key="item.id">
                <p>{{ item.statusLabel }} · {{ amount(item.quantity) }} · {{ shown(item.source?.employeeName) }}</p>
                <p>实际发生 {{ shown(item.occurredAt) }} · 登记 {{ shown(item.registeredAt) }}</p>
                <template v-if="item.kind==='return_decide'">
                  <p>企业决定 {{ item.payload.decisionValue.decision==='approve' ? '同意退供' : '不同意退供' }}</p>
                  <p>决定依据 {{ shown(item.payload.decisionValue.reason) }}</p>
                  <p>供应商条件核对 {{ shown(item.payload.decisionValue.supplierConditionsAssessment) }}</p>
                </template>
                <template v-if="item.kind==='return_handover'">
                  <p>代表 {{ shown(item.payload.receiver?.name) }} · 本次转移责任量 {{ amount(item.payload.responsibilityTransferredQuantity) }}</p>
                  <p>签收凭据 {{ shown(item.payload.signedReceipt?.reference) }} · 收方签收依据 {{ shown(item.payload.signedReceipt?.signatureReference) }}</p>
                </template>
              </li>
            </ol>
          </details>
          <p v-if="context.actionAuthorization.blockingReason?.message" role="status">{{ context.actionAuthorization.blockingReason.message }}</p>
          <form v-if="canAct" class="return-form" @submit.prevent="submit">
            <template v-if="kind==='return_request'">
              <label>本次申请数量（{{ unit }}）<input v-model.trim="form.quantity" inputmode="decimal" :pattern="decimalPattern" required /></label>
              <label>到场供应商授权代表姓名<input v-model.trim="form.receiverName" maxlength="500" required /></label>
              <label>接收授权原始依据引用<textarea v-model.trim="form.authorizationReference" maxlength="500" required /></label>
              <label>本笔异常的退供申请依据<textarea v-model.trim="form.returnBasis" maxlength="500" required /></label>
            </template>
            <template v-else-if="kind==='return_decide'">
              <label>企业决定
                <select v-model="form.decision" required>
                  <option value="">请选择企业决定</option>
                  <option value="approve">同意退供</option>
                  <option value="reject">不同意退供</option>
                </select>
              </label>
              <label>本人对全部供应商回复及附加条件的核对意见<textarea v-model.trim="form.assessment" maxlength="1000" required /></label>
              <label class="return-check"><input v-model="form.reviewed" type="checkbox" required />本人已核对上列全部回复及附加条件</label>
            </template>
            <template v-else>
              <p>本笔批准代表 {{ chosen.proposal.receiverName }} · 授权依据 {{ chosen.proposal.receiverAuthorizationReference }}</p>
              <label>本次本人实点可交量（{{ unit }}）<input v-model.trim="form.verifiedQuantity" inputmode="decimal" :pattern="decimalPattern" required /></label>
              <label>本次现场签收实交量（{{ unit }}）<input v-model.trim="form.quantity" inputmode="decimal" :pattern="decimalPattern" required /></label>
              <label>原始签收交接凭据引用<textarea v-model.trim="form.receiptReference" maxlength="500" required /></label>
              <label>授权代表对本次数量签收的原始依据引用<textarea v-model.trim="form.signatureReference" maxlength="500" required /></label>
              <label class="return-check"><input v-model="form.verifiedOriginal" type="checkbox" required />本人已核对到场授权代表和原始签收</label>
            </template>
            <label>本动作实际发生时间（业务当地时间）<input v-model="form.occurredAt" type="datetime-local" step="1" required /></label>
            <label>本人办理理由<textarea v-model.trim="form.reason" maxlength="240" required /></label>
            <button type="submit" :disabled="busy">{{ title }}</button>
          </form>
          <p>签收仅转移有据实交量的保管责任。本页办理以原退供申请、企业决定或现场签收为限。</p>
        </template>
      </template>
    </template>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import request from '@/api/request.js'
import { getTabAuthEpoch, readTabIdentity } from '@/meta/runtime/tabAuthenticationContext.js'

const props = defineProps({
  kind: { type: String, required: true },
  inspectionId: { type: Number, required: true },
  registrationId: { type: Number, required: true },
  orderId: { type: Number, default: null },
})
const emit = defineEmits(['changed'])
const route = useRoute(), router = useRouter(), epoch = getTabAuthEpoch()
const kinds = {
  return_request: ['申请企业退供','procurement','SCM'],
  return_decide: ['企业退供决定','procurement','SCM'],
  return_handover: ['现场签收交付确认','warehouse','WMS'],
}
const [title, permissionModule, module] = kinds[props.kind]
const permission = permissionModule + '.incoming_exception.' + props.kind
const queryPrefix = {return_request:'a10ReturnApply',return_decide:'a10ReturnDecide',return_handover:'a10ReturnHandover'}[props.kind]
const choosesRequest = props.kind!=='return_request'
const identity = readTabIdentity()
const storage = identity?.username ? 'pce-a10-return:'+identity.username+':'+props.kind : null
const context = ref(null), error = ref(''), loading = ref(false), busy = ref(false), pending = ref(null), receipt = ref(null)
const defaults = () => ({
  quantity:'', receiverName:'', authorizationReference:'', returnBasis:'', decision:'', assessment:'', reviewed:false,
  verifiedQuantity:'', receiptReference:'', signatureReference:'', verifiedOriginal:false, occurredAt:'', reason:'',
})
const form = reactive(defaults())
const decimalPattern = '[0-9]+(\\.[0-9]+)?'
const quantityFields = [
  ['registeredRejectedQuantity','本笔异常登记量'],
  ['unrequestedQuantity','尚可申请范围'],
  ['outstandingApplicationOrApprovedQuantity','待决定及批准未交范围'],
  ['cumulativeHandedQuantity','累计现场签收实交'],
  ['notHandedRegisteredQuantity','原仓管剩余责任范围'],
  ['currentWarehouseVerifiedQuantity','当前仓管核实量'],
  ['historicalCustodyQuantity','原历史实点确认量'],
]
const positive = id => Number.isSafeInteger(id) && id>0
const owned = () => getTabAuthEpoch()===epoch
const open = computed(() => Boolean(pending.value) || route.query[queryPrefix]===String(props.registrationId))
const requestId = computed(() => {
  const value = route.query[queryPrefix+'Request']
  const number = typeof value==='string' && /^\d+$/.test(value) ? Number(value) : null
  return choosesRequest && route.query[queryPrefix]===String(props.registrationId) && positive(number) ? number : null
})
const summary = computed(() => context.value?.returnSummary)
const unit = computed(() => context.value?.inspection.unit)
const sourceLine = computed(() => {
  const row = context.value?.inspection
  return row?.sourcePurchaseRequestNo && row.sourcePurchaseRequestLineNo!=null
    ? row.sourcePurchaseRequestNo+' · 申请第 '+row.sourcePurchaseRequestLineNo+' 行' : '未提供'
})
const chosen = computed(() => summary.value?.requests.find(application => application.requestId===requestId.value))
const returnHistory = computed(() => context.value?.history.filter(item => item.kind in kinds) || [])
const canAct = computed(() => context.value?.actionAuthorization.allowed===true
  && (!choosesRequest || Boolean(chosen.value))
  && (props.kind!=='return_handover' || (positive(chosen.value.decisionFactId) && positive(summary.value.latestCustodyFactId))))
let readCycle = 0

function shown(value) { return value==null || value==='' ? '未提供' : String(value) }
function amount(value, itemUnit=unit.value) { return value==null ? '未提供' : `${value} ${shown(itemUnit)}` }
function applicationLabel(application) {
  const fact = returnHistory.value.find(item => item.kind==='return_request' && item.id===application.requestId)
  return `${amount(application.quantity)} · ${shown(fact?.source?.employeeName)} · ${shown(fact?.occurredAt)}`
}
function toggle() {
  if (pending.value || busy.value) return
  return router.replace({query:{...route.query,[queryPrefix]:open.value ? undefined : String(props.registrationId),
    [queryPrefix+'Request']:undefined}})
}
function selectRequest(event) {
  return router.replace({query:{...route.query,[queryPrefix+'Request']:event.target.value || undefined}})
}
function url(inspectionId) {
  return `/api/procurement/incoming-exceptions/${inspectionId}/returns/${props.kind}/`
}
function read(inspectionId, params) {
  return request({url:url(inspectionId),params,meta:{module,readOnly:true,factLoad:true}}).catch(()=>null)
}
function remember(value) {
  if (!storage) throw Error('Missing tab identity')
  if (value) sessionStorage.setItem(storage, JSON.stringify(value))
  else sessionStorage.removeItem(storage)
  pending.value = value
}
try {
  const value = storage && JSON.parse(sessionStorage.getItem(storage) || 'null')
  if (value?.kind===props.kind && positive(value.inspectionId) && positive(value.registrationId)
    && typeof value.key==='string' && typeof value.intent==='string') pending.value=value
} catch { /* Local data is limited to an action reference. */ }

async function load() {
  const ticket=++readCycle, registrationId=props.registrationId, inspectionId=props.inspectionId
  const selectedRequestId=requestId.value
  context.value=null
  error.value=''
  loading.value=false
  Object.assign(form,defaults())
  if (!open.value || pending.value || !owned() || !positive(inspectionId) || !positive(registrationId)) return
  loading.value=true
  const response=await read(inspectionId,{registrationId,...(selectedRequestId ? {returnRequestId:selectedRequestId} : {})})
  if (!owned() || ticket!==readCycle) return
  loading.value=false
  const data=response?.data
  if (!response?.success || data?.currentStateSource!=='server' || data.contractVersion!=='PCE-NEVER-STOCKED-INCOMING-ONSITE-RETURN-V1'
    || data.inspection?.inspectionId!==inspectionId || data.registration?.id!==registrationId
    || (props.orderId!=null && data.inspection?.purchaseOrderId!==props.orderId)
    || (data.selectedRequestId ?? null)!==selectedRequestId || typeof data.collectionVersion!=='string'
    || !Array.isArray(data.supplierOpinions) || !Array.isArray(data.history) || !Array.isArray(data.returnSummary?.requests)
    || typeof data.actionAuthorization?.allowed!=='boolean' || data.actionAuthorization.permission!==permission) {
    error.value=response?.error?.message || '未取得本笔一致的退供事实和办理资格。'
    return
  }
  context.value=data
}
function details() {
  if (props.kind==='return_request') {
    return {quantity:form.quantity,proposal:{receiverName:form.receiverName,
      receiverAuthorizationReference:form.authorizationReference,returnBasis:form.returnBasis}}
  }
  if (props.kind==='return_decide') {
    return {requestId:chosen.value.requestId,expectedDecisionVersion:chosen.value.decisionVersion,decision:form.decision,
      reviewedSupplierOpinionIds:context.value.supplierOpinions.map(opinion=>opinion.id),supplierConditionsAssessment:form.assessment}
  }
  const app=chosen.value
  return {requestId:app.requestId,decisionId:app.decisionFactId,decisionVersion:app.decisionVersion,quantity:form.quantity,
    custodyFactId:summary.value.latestCustodyFactId,actualVerifiedQuantity:form.verifiedQuantity,
    receiverName:app.proposal.receiverName,receiverAuthorizationReference:app.proposal.receiverAuthorizationReference,
    receiptReference:form.receiptReference,receiverSignatureReference:form.signatureReference,originalReceiptVerified:form.verifiedOriginal}
}
function exactReceipt(value, original) {
  return value?.inspectionId===original.inspectionId && value.registrationId===original.registrationId
    && value.kind===original.kind && value.intentId===original.intent && positive(value.id)
    && value.inventoryEffect==='NONE' && value.historicalFactOnly===true
}
async function submit() {
  if (busy.value || pending.value || !owned() || !canAct.value) return
  const original={kind:props.kind,inspectionId:props.inspectionId,registrationId:props.registrationId,
    intent:crypto.randomUUID(),key:crypto.randomUUID()}
  const body={idempotencyKey:original.key,intentId:original.intent,registrationId:original.registrationId,
    expectedCollectionVersion:context.value.collectionVersion,reason:form.reason,occurredAt:form.occurredAt,details:details()}
  try { remember(original) } catch {
    error.value='无法保存原动作标识，请恢复浏览器会话存储后再提交。'
    return
  }
  busy.value=true
  context.value=null
  error.value=''
  try {
    const reply=await request({method:'POST',url:url(original.inspectionId),data:body,
      meta:{module,actionCode:permission,explicitBusinessAction:true}})
    if (!owned()) return
    if (reply?.success && exactReceipt(reply.data,original)) receipt.value=reply.data
    else if ([400,401,403,404,409].includes(reply?.meta?.status)
      && !['INCOMING_RETURN_RESULT_UNKNOWN','MATERIAL_CONCURRENCY_CONFLICT'].includes(reply?.error?.code)) {
      remember(null)
      await load()
      error.value=reply.error?.message || '本次退供办理被拒绝。'
    } else error.value=reply?.error?.message || '未取得准确回执，请查询同一次退供提交。'
  } catch {
    if (owned()) error.value='未取得准确回执，请查询同一次退供提交。'
  } finally { busy.value=false }
}
async function queryResult() {
  if (!owned() || !pending.value || busy.value) return
  const original=pending.value
  busy.value=true
  error.value=''
  try {
    const response=await read(original.inspectionId,{registrationId:original.registrationId,resultKey:original.key,intentId:original.intent})
    if (!owned()) return
    const data=response?.data
    if (response?.success && data?.resultState==='COMMITTED' && data.historicalReceiptOnly===true
      && data.automaticReplayAllowed===false && data.executionAuthorizedByResult===false && exactReceipt(data.result,original)) {
      receipt.value=data.result
    } else error.value=response?.error?.message || '本次提交的原回执仍待核。'
  } finally { busy.value=false }
}
async function acknowledge() {
  if (!receipt.value) return
  remember(null)
  receipt.value=null
  await load()
  emit('changed')
}
watch([open,requestId,()=>props.inspectionId,()=>props.registrationId],load,{immediate:true})
onBeforeUnmount(()=>{readCycle++})
</script>

<style scoped>
.return-panel{margin-top:12px;padding:12px;border:1px solid #d6e0ee;border-radius:9px;min-width:0;overflow-wrap:anywhere}
.return-grid,.return-form{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}
.return-grid dd{margin:0;font-weight:600}
.return-panel label{display:grid;gap:4px;min-width:0}
.return-panel :is(input,select,textarea,button){min-height:44px;max-width:100%;padding:6px 8px;box-sizing:border-box}
.return-panel :is(input:not([type=checkbox]),select,textarea){width:100%;min-width:0}
.return-form .return-check{display:flex;align-items:center}
.return-list{padding-inline-start:22px}
.reply{white-space:pre-wrap}
.return-form{margin-block:12px;align-items:end}
@media(max-width:600px){.return-form{grid-template-columns:minmax(0,1fr)}.return-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
