<template>
  <section class="material-panel" data-section="production-material-allocation" :data-load-status="state.loadState">
    <h2>生产用料原料分配</h2>
    <p>按准确需求读取合格原料来源，再显式选择本次分配。分配记录和有效占用与实物备料、领料分别核实。</p>
    <details><summary>操作说明</summary><p>从原生产用料需求进入，或填写正式需求ID读取本范围事实。选择来源后显示服务器核定的库存维度、尚可分配量和版本；数量按原单位填写，不自动选批、不计算齐套、不释放原占用。</p></details>
    <div class="material-controls">
      <label>正式生产用料需求ID<input v-model="demandId" aria-label="分配需求ID" inputmode="numeric" :disabled="busy || Boolean(state.pending) || deliveryPending" @input="invalidate" /></label>
      <button type="button" :disabled="busy || Boolean(state.pending) || deliveryPending || !validDemandId" @click="loadDemand">读取需求及原料来源</button>
    </div>
    <p v-if="state.loadState === 'idle' && !state.pending">尚未读取本需求；数量、来源与办理资格未知。</p>
    <p v-if="state.loadState === 'loading'" role="status">正在读取准确需求及原料来源；不沿用旧数量或资格。</p>
    <p v-if="state.error" class="material-error" role="alert">{{ state.error.message }}</p>
    <template v-if="facts">
      <dl class="material-facts">
        <div><dt>正式需求</dt><dd>{{ text(facts.demandNo) }}</dd></div>
        <div><dt>需求数量／单位</dt><dd>{{ text(facts.requiredQty) }} {{ text(facts.uomCode) }}</dd></div>
        <div><dt>已记录占用</dt><dd>{{ text(facts.recordedOccupiedQty) }} {{ text(facts.uomCode) }}</dd></div>
        <div><dt>需求尚未分配量</dt><dd>{{ text(facts.unallocatedDemandQty) }} {{ text(facts.uomCode) }}</dd></div>
        <div><dt>实物备料</dt><dd>请选择原占用记录，在实物备料区读取确认量。</dd></div>
        <div><dt>实际发料及收讫</dt><dd>在原占用记录的实物备料区查看。</dd></div>
      </dl>
      <p v-if="facts.blockingReason" role="alert" class="material-error">{{ facts.blockingReason.message }}。原占用是否仍保留以记录为准，不自动释放。</p>
      <p v-if="facts.sourceStatus === 'NO_PROVEN_SOURCE'">当前没有可证明的原料来源；这不表示库存为0或需求已满足。</p>
      <label v-if="candidates.length">显式选择原料来源<select v-model="sourceId" aria-label="原料来源库存流水" :disabled="busy || Boolean(state.pending) || deliveryPending" @change="readSource">
        <option value="">请选择准确来源</option><option v-for="row in candidates" :key="row.sourceTransactionId" :value="String(row.sourceTransactionId)">{{ sourceLabel(row.sourceTransactionId) }}{{ row.qualification === 'VERIFIED' ? ' · 已核验来源' : ' · 来源待核' }}</option>
      </select></label>
      <template v-if="facts.sourceTransactionId">
        <dl class="material-facts">
          <div><dt>来源库存流水</dt><dd>{{ sourceLabel(facts.sourceTransactionId) }}</dd></div>
          <div><dt>原料编码／名称</dt><dd>{{ text(transaction?.materialCode) }}／{{ text(transaction?.materialName) }}</dd></div>
          <div><dt>仓库／库位／批次</dt><dd>{{ text(transaction?.warehouseCode) }}／{{ text(transaction?.locationCode) }}／{{ text(transaction?.lotNo) }}</dd></div>
          <div><dt>该库存维度实存量</dt><dd>{{ text(facts.physicalStockQty) }} {{ text(facts.uomCode) }}</dd></div>
          <div><dt>该来源合格入库量</dt><dd>{{ text(facts.qualifiedInboundQty) }} {{ text(facts.uomCode) }}</dd></div>
          <div><dt>服务核定合格可用量</dt><dd>{{ text(facts.qualityAvailableQty) }} {{ text(facts.uomCode) }}</dd></div>
          <div><dt>服务核定来源尚可分配量</dt><dd>{{ text(facts.sourceUnoccupiedQty) }} {{ text(facts.uomCode) }}</dd></div>
        </dl>
        <label>本次分配数量<input v-model="quantity" aria-label="本次原料分配数量" inputmode="decimal" :disabled="busy || Boolean(state.pending)" /></label>
        <label>分配原因<textarea v-model="reason" aria-label="原料分配原因" maxlength="300" :disabled="busy || Boolean(state.pending)" /></label>
        <button type="button" :data-action-code="action.actionCode" :disabled="busy || Boolean(state.pending) || preparationPending || deliveryPending || !authorization.enabled || !validQuantity || !reason.trim()" @click="allocate">{{ action.actionName }}</button>
        <p>{{ authorization.reason }}</p>
      </template>
      <section v-if="Array.isArray(facts.allocations)"><h3>本需求原占用记录</h3>
        <p v-if="!facts.allocations.length">本次成功读取的需求尚无占用记录；不表示原料已备齐或已领料。</p>
        <article v-for="row in facts.allocations" :key="row.allocationId" class="material-record">
          <strong>占用记录 {{ row.allocationId }} · {{ text(row.statusLabel) }}</strong>
          <p>{{ text(row.quantity) }} {{ text(facts.uomCode) }}；{{ row.currentSourceStatus === 'CURRENT' ? '当前来源已核验' : '当前来源待重新核验' }}；{{ row.quotaStillHeld === true ? '原占用仍保留' : '占用保留情况未提供' }}</p>
          <p v-if="row.blockingReason" class="material-error">{{ row.blockingReason.message }}</p>
          <button type="button" :disabled="busy || Boolean(state.pending) || preparationPending || deliveryPending" @click="openPreparation(row)">查看本分配实物备料</button>
        </article>
      </section>
      <details><summary>准确来源、数量维度、版本及完整核验</summary><pre>{{ JSON.stringify(facts, null, 2) }}</pre></details>
    </template>
    <ProductionMaterialPreparationPanel
      :allocation="preparationAllocation"
      :source="findTransaction(preparationAllocation?.sourceTransactionId)"
      :selection-version="preparationSelectionVersion"
      :allocation-pending="Boolean(state.pending) || deliveryPending"
      @pending-change="preparationPending = $event"
    />
    <ProductionMaterialDeliveryPanel mode="issue" :allocation="preparationAllocation"
      :source="findTransaction(preparationAllocation?.sourceTransactionId)" :refresh-version="preparationSelectionVersion"
      :allocation-pending="Boolean(state.pending) || preparationPending"
      @pending-change="deliveryPending = $event" @refresh="loadDemand" />
    <div v-if="state.pending" role="status" class="material-pending">
      <p>{{ state.receipt?.resultState === 'COMMITTED' ? '本次分配已有历史回执。' : '本次分配结果未知。' }}不自动重新提交；回执不替代当前来源核验。</p>
      <button type="button" :disabled="state.busy" @click="controller.queryOriginal()">仅查询同一次分配结果</button>
      <button v-if="state.receipt?.resultState === 'COMMITTED'" type="button" :disabled="state.busy" @click="acknowledge">已查看回执，重新读取</button>
      <details><summary>原动作及回执追溯</summary><pre>{{ JSON.stringify({ originalAction: state.pending, receipt: state.receipt }, null, 2) }}</pre></details>
    </div>
  </section>
</template>
<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ProductionMaterialPreparationPanel from './ProductionMaterialPreparationPanel.vue'
import ProductionMaterialDeliveryPanel from './ProductionMaterialDeliveryPanel.vue'
import { createProductionMaterialPage, materialText as text } from '@/meta/runtime/productionMaterialPage.js'
import { PRODUCTION_MATERIAL_ACTIONS, materialActionAuthorization } from '@/meta/process/productionMaterialActions.js'
const props = defineProps({ inventoryFacts: { type: Object, default: () => ({}) }, refreshVersion: { type: Number, default: 0 } })
const route = useRoute(), router = useRouter(), controller = createProductionMaterialPage({ mode: 'allocation' }), state = controller.state
const action = PRODUCTION_MATERIAL_ACTIONS.allocate
const demandId = ref(String(route.query.demandId || '')), sourceId = ref(''), candidates = ref([]), quantity = ref(''), reason = ref('')
const facts = computed(() => state.facts), busy = computed(() => state.busy || state.loadState === 'loading')
const deliveryPending = ref(false)
const savedAllocationId = computed(() => typeof route.query.materialIssueAllocationId === 'string' && /^[1-9]\d{0,14}$/.test(route.query.materialIssueAllocationId) ? Number(route.query.materialIssueAllocationId) : null)
const preparationId = ref(savedAllocationId.value), preparationSelectionVersion = ref(0), preparationPending = ref(false)
const preparationAllocation = computed(() => facts.value?.allocations?.find(row => row.allocationId === preparationId.value))
function openPreparation(row) {
  if (deliveryPending.value) return
  preparationId.value = row.allocationId
  preparationSelectionVersion.value++
  router.replace({ query: { ...route.query, materialIssueAllocationId: String(row.allocationId) } })
}
const validDemandId = computed(() => /^[1-9]\d*$/.test(demandId.value) && Number.isSafeInteger(Number(demandId.value)))
const validQuantity = computed(() => /^\d+(\.\d{1,6})?$/.test(quantity.value))
const authorization = computed(() => materialActionAuthorization(facts.value, 'allocate'))
const findTransaction = id => props.inventoryFacts.transactions?.find(row => String(row.id) === String(id))
const transaction = computed(() => findTransaction(facts.value?.sourceTransactionId))
const sourceLabel = id => findTransaction(id)?.transactionNo || `库存流水ID ${id}（业务编号未提供）`
function invalidate() { controller.invalidate(); candidates.value = []; sourceId.value = '' }
async function loadDemand() {
  if (!validDemandId.value || deliveryPending.value) return
  sourceId.value = ''; candidates.value = []
  await router.replace({ query: { ...route.query, demandId: demandId.value } })
  await controller.read({ demandId: Number(demandId.value) })
  candidates.value = state.facts?.sourceCandidates || []
}
async function readSource() {
  if (!sourceId.value) return loadDemand()
  await controller.read({ demandId: Number(demandId.value), sourceTransactionId: Number(sourceId.value) })
}
async function allocate() {
  const value = facts.value
  if (!value || preparationPending.value || deliveryPending.value) return
  await controller.submit('allocate', { demandId: value.demandId, sourceTransactionId: value.sourceTransactionId, quantity: quantity.value, intentId: crypto.randomUUID(), expectedDemandAllocationVersion: value.demandAllocationVersion, expectedDemandFingerprint: value.demandFingerprint, expectedStockFingerprint: value.stockFingerprint, expectedDimensionFingerprint: value.dimensionFingerprint, reason: reason.value }, value.demandId)
  candidates.value = []
}
async function acknowledge() { controller.acknowledge(); quantity.value = ''; await loadDemand() }
watch(() => route.query.demandId, value => { if (String(value || '') !== demandId.value && !state.pending && !deliveryPending.value) { demandId.value = String(value || ''); invalidate() } })
watch(savedAllocationId, value => { if (!deliveryPending.value) preparationId.value = value })
onMounted(() => { if (savedAllocationId.value && validDemandId.value && !deliveryPending.value) loadDemand() })
// Invalidate at explicit parent refresh start, never when its independent read finishes.
watch(() => props.refreshVersion, () => { if (!state.pending && !deliveryPending.value) { if (savedAllocationId.value && validDemandId.value) loadDemand(); else invalidate() } })
</script>
<style scoped>
.material-panel { display:grid;gap:14px;min-width:0;border:1px solid #dbe3ef;border-radius:10px;padding:20px; } h2,h3,p { margin:0; } p { line-height:1.65; }.material-controls { display:flex;flex-wrap:wrap;gap:12px;align-items:end; }
label { display:grid;gap:6px;min-width:0; } input,select,textarea,button { font:inherit;min-height:44px;max-width:100%;box-sizing:border-box; } input,select,textarea { width:100%;padding:9px;border:1px solid #bdc9db;border-radius:6px; } button { padding:9px 14px;cursor:pointer; } button:disabled { cursor:not-allowed; }
.material-facts { display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin:0; } dt { color:#64748b; } dd { margin:4px 0;overflow-wrap:anywhere; } .material-error { color:#b42318; }.material-pending { padding:12px;background:#fff8e6;display:grid;gap:10px; }.material-record { margin-top:10px;padding:12px;border:1px solid #dbe3ef; }
pre { white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px; } summary { cursor:pointer;min-height:40px;line-height:40px; }
@media(max-width:640px) { .material-facts { grid-template-columns:1fr; }.material-panel { padding:14px; }.material-controls>* { width:100%; } }
</style>
