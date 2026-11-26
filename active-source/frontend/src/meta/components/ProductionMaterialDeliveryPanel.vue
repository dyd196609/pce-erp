<template>
  <section v-if="!sending || allocation || state.pending" class="material-delivery" :aria-label="heading">
    <h4>{{ heading }}</h4>
    <template v-if="!state.pending">
      <button v-if="sending || issueId" type="button" :disabled="busy" @click="readCurrent">刷新当前交付事实</button>
      <button v-if="!sending && issueId" type="button" :disabled="busy" @click="returnToReceipts">返回本人交付记录</button>
      <button v-if="!sending && !issueId" type="button" :disabled="busy" @click="readCurrent">刷新本人交付记录</button>
    </template>
    <p v-if="state.loadState === 'loading'" role="status">正在读取当前交付事实和办理资格。</p>
    <p v-if="state.error" role="alert">{{ state.error.message }}</p>

    <template v-if="facts && !state.pending">
      <template v-if="sending">
        <dl class="delivery-fields">
          <div><dt>原需求</dt><dd>{{ text(facts.demandNo) }}</dd></div>
          <div><dt>原分配</dt><dd>{{ text(facts.allocationId) }}</dd></div>
          <div><dt>物料</dt><dd>{{ text(stockSource?.materialName) }}</dd></div>
          <div><dt>当前来源流水批次</dt><dd>{{ text(stockSource?.lotNo) }}</dd></div>
          <div><dt>当前来源流水库位</dt><dd>{{ text(stockSource?.locationCode) }}</dd></div>
          <div><dt>本次仍可发</dt><dd>{{ quantityText(facts.currentIssueableQty, facts.uomCode) }}</dd></div>
          <div><dt>剩余在库占用</dt><dd>{{ quantityText(facts.remainingOccupiedQty, facts.uomCode) }}</dd></div>
          <div><dt>已发料</dt><dd>{{ quantityText(facts.issuedQty, facts.uomCode) }}</dd></div>
          <div><dt>正式收讫</dt><dd>{{ quantityText(facts.receivedQty, facts.uomCode) }}</dd></div>
          <div><dt>待核交付责任量</dt><dd>{{ quantityText(facts.pendingReceiptQty, facts.uomCode) }}</dd></div>
        </dl>
        <details v-if="facts.destinationBlockingReasons?.length">
          <summary>其他目的地待核原因</summary>
          <ul><li v-for="(reason, index) in facts.destinationBlockingReasons" :key="index">{{ reason.message }}</li></ul>
        </details>
      </template>
      <p v-if="!sending && !issueId && facts.count === 0">服务端确认当前没有指定给本人的原料交付记录。</p>
      <p v-if="!sending && !issueId && facts.scope">{{ facts.scope }}</p>
      <article v-for="row in rows" :key="row.issueId" class="delivery-record" :data-issue-id="row.issueId">
        <h5>发料 {{ row.issueId }} · {{ text(row.statusLabel) }}</h5>
        <dl class="delivery-fields">
          <div><dt>工单 / 车间</dt><dd>{{ text(row.workOrderNo) }} / {{ text(row.workshopLabel) }}</dd></div>
          <div><dt>物料 / 冻结批次</dt><dd>{{ text(row.materialName) }} / {{ text(row.lotNo) }}</dd></div>
          <div><dt>发料人</dt><dd>{{ text(row.senderLabel) }}</dd></div>
          <div><dt>指定收方</dt><dd>{{ text(row.receiverLabel) }}</dd></div>
          <div><dt>发出数量</dt><dd>{{ quantityText(row.quantity, row.uomCode) }}</dd></div>
          <div><dt>现场申报数量</dt><dd>{{ quantityText(row.reportedQuantity, row.uomCode) }}</dd></div>
          <div><dt>正式收讫数量</dt><dd>{{ quantityText(row.receivedQty, row.uomCode) }}</dd></div>
          <div><dt>待核交付责任量</dt><dd>{{ quantityText(row.pendingReceiptQty, row.uomCode) }}</dd></div>
          <div><dt>当前责任人</dt><dd>{{ responsiblePerson(row) }} · {{ text(row.custodyLabel) }}</dd></div>
          <div><dt>出库流水</dt><dd>{{ text(row.outboundTransactionId) }}</dd></div>
          <div><dt>发料实际发生时间</dt><dd>{{ text(row.occurredAtLabel || row.occurredAt) }}</dd></div>
        </dl>
        <p v-if="row.statusCode === 'discrepancy_pending'">整笔交付责任待核，现场申报量保留。</p>
        <button v-if="!sending && !issueId" type="button" :disabled="busy" @click="selectReceipt(row)">查看本笔并核对</button>
      </article>
      <template v-if="sending || issueId">
        <p v-if="!authorization.enabled" role="status">{{ authorization.reason }}</p>
        <form v-else class="delivery-form" @submit.prevent="submit">
          <label v-if="sending">本次目的地<select v-model="destinationId" aria-label="本次目的地" required>
            <option value="">请选择工单、车间和指定收方</option>
            <option v-for="choice in (facts.destinations || [])" :key="choice.expectedDestinationFingerprint" :value="choice.expectedDestinationFingerprint">
              {{ choice.workOrderNo }} · {{ choice.workshopName }} · {{ choice.receiverLabel }}
            </option>
          </select></label>
          <label>{{ sending ? '本次实际发料量' : '本次现场申报数量' }}（{{ text(facts.uomCode) }}）<input v-model.trim="quantity" :aria-label="sending ? '本次实际发料量' : '本次现场申报数量'" inputmode="decimal" required /></label>
          <label>实际发生时间（北京时间）<input v-model="occurredAt" aria-label="实际发生时间（北京时间）" type="datetime-local" step="1" required /></label>
          <label>{{ sending ? '实物发出依据' : '现场核对依据' }}<textarea v-model.trim="basis" :aria-label="sending ? '实物发出依据' : '现场核对依据'" maxlength="500" required /></label>
          <label>办理原因<textarea v-model.trim="reason" aria-label="办理原因" maxlength="300" required /></label>
          <p v-if="!sending">按现场核对填写；数量不同由原服务登记差异。</p>
          <button type="submit" :disabled="!canSubmit">{{ action.actionName }}</button>
        </form>
      </template>
    </template>

    <section v-if="state.pending" role="status" class="delivery-record">
      <p v-if="state.receipt?.resultState === 'COMMITTED'">已取得本次原回执。发料 {{ state.receipt.result.issueId }} · {{ text(state.receipt.result.statusLabel) }}。<template v-if="sending">出库流水 {{ text(state.receipt.result.outboundTransactionId) }}。</template></p>
      <p v-else>原动作结果待核。原对象 {{ state.pending.objectId }} · 原动作标识 {{ state.pending.idempotencyKey }}。</p>
      <button type="button" :disabled="state.busy" @click="controller.queryOriginal()">仅查询同一次提交</button>
      <button v-if="state.receipt?.resultState === 'COMMITTED'" type="button" :disabled="state.busy" @click="confirmReadback">读取当前交付结果</button>
    </section>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { PRODUCTION_MATERIAL_ACTIONS, materialActionAuthorization } from '@/meta/process/productionMaterialActions.js'
import { createProductionMaterialPage, materialText as text } from '@/meta/runtime/productionMaterialPage.js'

const props = defineProps({ mode: { type: String, required: true }, allocation: { type: Object, default: null }, source: { type: Object, default: null }, refreshVersion: { type: Number, default: 0 }, allocationPending: { type: Boolean, default: false } })
const emit = defineEmits(['pending-change', 'refresh'])
const route = useRoute(), router = useRouter()
const sending = props.mode === 'issue'
const heading = sending ? '实际发料' : '本人原料收讫'
const action = PRODUCTION_MATERIAL_ACTIONS[props.mode]
const controller = createProductionMaterialPage({ mode: props.mode })
const state = controller.state
const facts = computed(() => state.facts)
const queryIssue = computed(() => typeof route.query.materialIssueId === 'string' && /^[1-9]\d{0,14}$/.test(route.query.materialIssueId) ? Number(route.query.materialIssueId) : null)
const issueId = computed(() => sending ? null : queryIssue.value)
const stockSource = computed(() => props.source?.id === props.allocation?.sourceTransactionId ? props.source : null)
const rows = computed(() => !facts.value ? [] : sending ? facts.value.history : issueId.value ? [facts.value] : facts.value.rows)
const authorization = computed(() => materialActionAuthorization(facts.value, props.mode))
const busy = computed(() => state.busy || state.loadState === 'loading' || props.allocationPending)
const destinationId = ref(''), quantity = ref(''), occurredAt = ref(''), basis = ref(''), reason = ref('')
const destination = computed(() => facts.value?.destinations?.find(row => row.expectedDestinationFingerprint === destinationId.value))
const exactTime = computed(() => /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?$/.test(occurredAt.value) ? `${occurredAt.value}+08:00` : '')
const quantitySyntax = computed(() => /^\d+(\.\d{1,6})?$/.test(quantity.value))
const canSubmit = computed(() => !busy.value && !state.pending && authorization.value.enabled && quantitySyntax.value && exactTime.value && basis.value && reason.value &&
  (sending ? Boolean(destination.value) && facts.value.allocationId === props.allocation?.allocationId : facts.value.issueId === issueId.value))

function quantityText(value, unit) {
  return value == null || value === '' ? '未提供' : `${value} ${text(unit)}`
}
function responsiblePerson(row) {
  if (row.custodianId === row.senderId) return text(row.senderLabel)
  if (row.custodianId === row.receiverId) return text(row.receiverLabel)
  return '未提供'
}
function readCurrent() {
  if (state.pending || props.allocationPending) return
  if (sending && !Number.isSafeInteger(props.allocation?.allocationId)) return controller.invalidate()
  destinationId.value = ''
  return controller.read(sending ? { allocationId: props.allocation.allocationId } : issueId.value ? { issueId: issueId.value } : {})
}
function selectReceipt(row) {
  if (!facts.value?.rows?.some(entry => entry.issueId === row.issueId)) return
  return router.push({ query: { ...route.query, materialIssueId: String(row.issueId) } })
}
function returnToReceipts() {
  return router.replace({ query: { ...route.query, materialIssueId: undefined } })
}
async function submit() {
  if (!canSubmit.value) return
  const current = facts.value
  const fields = { quantity: quantity.value, occurredAt: exactTime.value, basis: basis.value, reason: reason.value, intentId: crypto.randomUUID() }
  if (sending) {
    const selected = destination.value
    await controller.submit('issue', { ...fields, allocationId: current.allocationId, workOrderId: selected.workOrderId,
      workshopId: selected.workshopId, receiverId: selected.receiverId, expectedCollectionVersion: current.collectionVersion,
      expectedAllocationProofHash: current.allocationProofHash, expectedSourceFingerprint: current.sourceFingerprint,
      expectedDimensionFingerprint: current.dimensionFingerprint, expectedDestinationFingerprint: selected.expectedDestinationFingerprint }, current.allocationId)
  } else {
    await controller.submit('receive', { ...fields, issueId: current.issueId, expectedVersion: current.version,
      expectedSourceFingerprint: current.sourceFingerprint }, current.issueId)
  }
}
function clearForm() {
  destinationId.value = quantity.value = occurredAt.value = basis.value = reason.value = ''
}
async function confirmReadback() {
  controller.acknowledge()
  clearForm()
  await readCurrent()
  if (sending) emit('refresh')
}
watch(() => Boolean(state.pending), pending => emit('pending-change', pending), { immediate: true, flush: 'sync' })
watch([() => props.allocation?.allocationId, issueId], () => { clearForm(); readCurrent() }, { immediate: true })
watch(() => props.refreshVersion, () => { if (!state.pending) readCurrent() })
</script>

<style scoped>
.material-delivery{min-width:0;padding:12px;border:1px solid #d6e0ee;border-radius:8px;overflow-wrap:anywhere}
.material-delivery h4,.material-delivery h5{margin:0 0 8px}
.delivery-record{padding:10px;margin-block:10px;border:1px solid #d6e0ee;border-radius:8px}
.delivery-fields{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-block:10px}
.delivery-fields dd{margin:0;font-weight:600;font-variant-numeric:tabular-nums}
.delivery-form{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-block:8px}
.delivery-form label{display:grid;gap:4px;min-width:0}
.delivery-form input,.delivery-form select,.delivery-form textarea,.material-delivery button{min-height:44px;max-width:100%;padding:5px 8px}
@media(max-width:600px){.delivery-fields{grid-template-columns:repeat(2,minmax(0,1fr))}.delivery-form{grid-template-columns:1fr}}
</style>
