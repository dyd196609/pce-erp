<template>
  <section v-if="allocation || state.pending" class="preparation" aria-label="实物备料" data-section="production-material-preparation">
    <h3>原库位实物备料</h3>
    <p v-if="state.loadState === 'loading'" role="status">正在读取本分配的备料记录和当前资格。</p>
    <p v-if="state.error" role="alert">{{ state.error.message }}</p>
    <button v-if="allocation && !state.pending" type="button" :disabled="busy || allocationPending" @click="readCurrent">重新读取备料状态</button>

    <template v-if="selected && demand">
      <dl class="facts">
        <div><dt>需求与生产范围</dt><dd>{{ demand.demandNo }} · {{ demand.productionRange?.join(' 至 ') }}</dd></div>
        <div><dt>原占用记录</dt><dd>{{ selected.allocationId }} · {{ amount(selected.allocationQuantity) }}</dd></div>
        <div><dt>原库存流水及批次</dt><dd>{{ text(source?.transactionNo) }} · {{ text(source?.lotNo) }}</dd></div>
        <div><dt>原正式库位</dt><dd>{{ source?.locationCode || `库位编号 ${selected.locationId}` }}</dd></div>
        <div><dt>本分配已登记备料量</dt><dd>{{ amount(selected.recordedPreparedQty) }}</dd></div>
        <div><dt>当前尚可登记确认量</dt><dd>{{ amount(selected.remainingConfirmationQty) }}</dd></div>
        <div><dt>本分配当前状态</dt><dd>{{ selected.statusLabel }}</dd></div>
        <div><dt>本需求当前状态</dt><dd>{{ demand.statusLabel }}<br>{{ demand.scope }}</dd></div>
        <div><dt>本需求原需求量／占用量／已登记备料量</dt><dd>{{ amount(demand.requiredQty) }}／{{ amount(demand.recordedOccupiedQty) }}／{{ amount(demand.recordedPreparedQty) }}</dd></div>
        <div><dt>领料数量</dt><dd>未提供（领料未实施）</dd></div>
      </dl>
      <p v-if="selected.blockingReason" role="alert">{{ selected.blockingReason.message }}</p>
      <p v-if="selected.quotaStillHeld === true">原占用仍保留。</p>
      <p>已登记备料量来自确认记录。实物未备量未采集。</p>

      <form v-if="authorization.enabled" @submit.prevent="confirmPreparation">
        <p>请在原库位实际清点、分拣、标识并摆妥后，登记本人本次备料事实。</p>
        <label>本次备料数量（{{ demand.uomCode }}）<input v-model.trim="form.quantity" inputmode="decimal" required /></label>
        <label>实际发生日期和时间（北京时间）<input v-model="form.occurredAt" type="datetime-local" step="1" required /></label>
        <label>备料标识<input v-model.trim="form.mark" maxlength="160" required /></label>
        <label>清点、分拣及摆妥依据<textarea v-model.trim="form.basis" maxlength="500" required /></label>
        <label>确认原因<textarea v-model.trim="form.reason" maxlength="300" required /></label>
        <button type="submit" :data-action-code="action.actionCode" :disabled="busy || allocationPending || !readyToSubmit">{{ action.actionName }}</button>
      </form>

      <details>
        <summary>备料登记历史及审计</summary>
        <p v-if="!selected.history.length">本分配尚无备料登记记录。</p>
        <article v-for="record in selected.history" :key="record.preparationId">
          <strong>{{ record.statusLabel }} · {{ amount(record.quantity) }} · {{ record.preparationMark }}</strong>
          <p>实际发生 {{ record.occurredAtLabel }} · 系统登记 {{ record.registeredAtLabel }}</p>
          <p>办理人账号编号 {{ record.actorId }} · 审计编号 {{ record.auditId }}</p>
          <p>{{ record.basis }}</p>
        </article>
      </details>
      <details>
        <summary>来源、版本及原凭证</summary>
        <pre>{{ JSON.stringify({ originalAllocation: allocation, selected }, null, 2) }}</pre>
      </details>
    </template>

    <section v-if="state.pending" class="receipt" role="status">
      <p v-if="state.receipt?.resultState === 'COMMITTED'">本次提交已有历史回执。备料记录 {{ state.receipt.result.preparationId }}，原占用 {{ state.pending.objectId }}，登记量 {{ state.receipt.result.quantity }}。</p>
      <p v-else>原占用 {{ state.pending.objectId }} 的备料提交结果待核。请查询原动作。</p>
      <button type="button" :disabled="state.busy" @click="controller.queryOriginal()">查询同一次备料结果</button>
      <button v-if="state.receipt?.resultState === 'COMMITTED'" type="button" :disabled="state.busy" @click="acknowledge">确认已查看回执并重新读取</button>
      <details><summary>本次提交标识与服务端回执</summary><pre>{{ JSON.stringify({ originalAction: state.pending, receipt: state.receipt }, null, 2) }}</pre></details>
    </section>
  </section>
</template>

<script setup>
import { computed, reactive, watch } from 'vue'
import { PRODUCTION_MATERIAL_ACTIONS, materialActionAuthorization } from '@/meta/process/productionMaterialActions.js'
import { createProductionMaterialPage, materialText as text } from '@/meta/runtime/productionMaterialPage.js'

const props = defineProps({ allocation: Object, source: Object, selectionVersion: Number, allocationPending: Boolean })
const emit = defineEmits(['pending-change'])
const controller = createProductionMaterialPage({ mode: 'preparation' })
const { state } = controller
const action = PRODUCTION_MATERIAL_ACTIONS.prepare
const form = reactive({ quantity: '', occurredAt: '', mark: '', basis: '', reason: '' })
const selected = computed(() => {
  const row = state.facts?.selected
  if (!row || row.allocationId !== props.allocation?.allocationId
    || row.demandId !== props.allocation.demandId || row.locationId !== props.allocation.locationId) return null
  return row
})
const demand = computed(() => state.facts?.demand)
const authorization = computed(() => materialActionAuthorization(selected.value ? state.facts : null, 'prepare'))
const busy = computed(() => state.busy || state.loadState === 'loading')
const readyToSubmit = computed(() => {
  const row = selected.value
  return row && [row.preparationCollectionVersion, row.allocationProofHash, row.sourceFingerprint, row.dimensionFingerprint].every(value => typeof value === 'string' && value)
    && /^\d+(\.\d{1,6})?$/.test(form.quantity) && /[1-9]/.test(form.quantity)
    && form.occurredAt && form.mark && form.basis && form.reason
})

function amount(value) {
  return value == null ? '未提供' : `${value} ${text(demand.value?.uomCode)}`
}

function readCurrent() {
  if (!props.allocation || props.allocationPending) return
  return controller.read({ allocationId: props.allocation.allocationId })
}

async function confirmPreparation() {
  if (busy.value || props.allocationPending || !authorization.value.enabled || !readyToSubmit.value) return
  const row = selected.value
  await controller.submit('prepare', {
    allocationId: row.allocationId,
    locationId: row.locationId,
    quantity: form.quantity,
    occurredAt: form.occurredAt,
    preparationMark: form.mark,
    basis: form.basis,
    reason: form.reason,
    evidenceReferences: [],
    intentId: crypto.randomUUID(),
    expectedCollectionVersion: row.preparationCollectionVersion,
    expectedAllocationProofHash: row.allocationProofHash,
    expectedSourceFingerprint: row.sourceFingerprint,
    expectedDimensionFingerprint: row.dimensionFingerprint,
  }, row.allocationId)
}

function resetForm() {
  Object.assign(form, { quantity: '', occurredAt: '', mark: '', basis: '', reason: '' })
}

function acknowledge() {
  controller.acknowledge()
  resetForm()
  return readCurrent()
}

watch(() => Boolean(state.pending), pending => emit('pending-change', pending), { immediate: true, flush: 'sync' })
watch([() => props.allocation?.allocationId, () => props.selectionVersion], () => {
  controller.invalidate()
  resetForm()
  if (!state.pending) readCurrent()
})
</script>

<style scoped>
.preparation { display: grid; gap: 12px; min-width: 0; border-top: 1px solid #dbe3ef; padding-top: 16px; }
h3, p, dl { margin: 0; }
.facts, form { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
form > p { grid-column: 1 / -1; }
dt { color: #526174; }
dd { margin: 4px 0 0; }
dd, p, pre, article { overflow-wrap: anywhere; }
label { display: grid; gap: 6px; min-width: 0; }
input, textarea, button { font: inherit; min-height: 44px; max-width: 100%; box-sizing: border-box; }
input, textarea { width: 100%; padding: 9px; border: 1px solid #bdc9db; border-radius: 6px; }
button { padding: 8px 12px; }
article, .receipt { padding: 12px; border: 1px solid #dbe3ef; }
article + article { margin-top: 8px; }
.receipt { display: grid; gap: 10px; background: #fff8e6; }
summary { cursor: pointer; padding: 10px 0; }
pre { white-space: pre-wrap; font-size: 12px; }
[role="alert"] { color: #b42318; }
@media (max-width: 640px) { .facts, form { grid-template-columns: minmax(0, 1fr); } }
</style>
