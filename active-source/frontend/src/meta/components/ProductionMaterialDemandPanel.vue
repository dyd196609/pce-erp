<template>
  <section class="material-panel panel block" data-section="production-material-demand" :data-load-status="state.loadState">
    <h2>正式生产用料需求</h2>
    <p>从已批准生产计划与原工程／BOM明细核对用料；需求登记、确认不表示原料已占用、已备齐或已领料。</p>
    <details><summary>操作说明</summary><p>新增时选生产计划，填写本次生产范围，读取并选择正式来源明细。确认已有需求时，从下方选择原记录后重新核对。数量、单位、版本及办理资格以服务结果为准。</p></details>
    <fieldset :disabled="writeLocked || parentLoading">
      <label>已有生产用料需求<select v-model="selectedDemandId" aria-label="已有生产用料需求" @change="selectDemand">
        <option value="">请选择已有需求</option><option v-for="row in materialDemands" :key="row.id" :value="String(row.id)">{{ row.demandNo }} · {{ row.materialCode }} · {{ row.statusLabel }}</option>
      </select></label>
    </fieldset>
    <section v-if="!selectedDemand" class="source-selection" aria-label="新增需求来源选择">
      <h3>新增需求来源选择</h3>
      <fieldset :disabled="writeLocked || parentLoading">
        <label>生产用料计划<select v-model="planId" @change="readApprovedScope">
          <option value="">请选择生产计划</option>
          <option v-for="plan in plans" :key="plan.id" :value="String(plan.id)">{{ plan.label }}</option>
        </select></label>
      </fieldset>
      <p v-if="currentPlan && !approvedScope && catalogue.loadState === 'loading'" role="status">正在读取原批准生产范围。</p>
      <template v-if="approvedScope">
        <p>原批准范围 {{ approvedScope.approvedRangeStart }}–{{ approvedScope.approvedRangeEnd }} {{ approvedScope.productionUomCode }}，生产单位精度 {{ approvedScope.productionDecimalPlaces }} 位。</p>
        <fieldset :disabled="writeLocked || parentLoading">
          <label>本次范围起点<input v-model.trim="rangeStart" inputmode="decimal" @input="invalidateCandidates" /></label>
          <label>本次范围终点<input v-model.trim="rangeEnd" inputmode="decimal" @input="invalidateCandidates" /></label>
        </fieldset>
        <p v-if="(rangeStart || rangeEnd) && !rangeInputReady">请输入完整的十进制范围起点和终点。</p>
        <div class="material-actions">
          <button type="button" :disabled="writeLocked || parentLoading" @click="useApprovedRange">使用全部批准范围</button>
          <button type="button" :disabled="writeLocked || parentLoading || !rangeInputReady || catalogue.loadState === 'loading'" @click="readCandidates">读取正式来源</button>
        </div>
        <p v-if="catalogue.loadState === 'loading'" role="status">正在读取本次范围的正式来源。</p>
      </template>
      <p v-if="catalogueMessage" class="material-error" role="alert">{{ catalogueMessage }}</p>
      <p v-else-if="candidateFacts?.factLoadStatus === 'empty_valid'" role="status">{{ candidateFacts.statusLabel }}</p>
      <fieldset v-if="selectableRows.length" :disabled="writeLocked || parentLoading">
        <label>原料来源明细<select v-model="sourceKey" @change="previewSelectedSource">
          <option value="">请选择正式来源明细</option>
          <option v-for="row in selectableRows" :key="candidateKey(row)" :value="candidateKey(row)">{{ candidateLabel(row) }}</option>
        </select></label>
      </fieldset>
      <ul v-if="pendingRows.length" class="pending-sources" aria-label="来源待核明细">
        <li v-for="row in pendingRows" :key="candidateKey(row)"><strong>{{ candidateLabel(row) }}</strong><p>{{ row.reason || row.statusLabel }}</p></li>
      </ul>
      <template v-if="selectedSource">
        <p class="selected-source">{{ selectedSource.sourceTypeLabel }} · 第 {{ text(selectedSource.sourceLineNo) }} 行 · {{ text(selectedSource.sourceDocumentNo) }}／{{ text(selectedSource.sourceVersion) }}</p>
        <p>{{ selectedSource.statusLabel }}<template v-if="selectedSource.existingDemandNo"> · {{ selectedSource.existingDemandNo }}</template></p>
        <p v-if="selectedSource.coverageMeaningLabel">{{ selectedSource.coverageMeaningLabel }}</p>
        <details v-if="selectedSource.sourceDetails?.length">
          <summary>原工程贡献明细</summary>
          <p>以下数量是原工程总量或 BOM 净贡献，不重复计入本次需求。</p>
          <ul class="pending-sources"><li v-for="detail in selectedSource.sourceDetails" :key="detail.sourceLineId">{{ text(detail.sourceDocumentNo) }} · 第 {{ detail.sourceLineNo }} 行 · BOM 净贡献 {{ text(detail.contributedNetQty) }} {{ text(detail.uomCode) }}<template v-if="selectedSource.coverageKind === 'ENGINEERING_DETAIL' && detail.selectedInThisRow"> · 本次所选工程明细</template></li></ul>
        </details>
        <details v-if="selectedSource.sourceAliases?.length">
          <summary>同源别名</summary>
          <ul class="pending-sources"><li v-for="alias in selectedSource.sourceAliases" :key="`${alias.sourceObjectType}:${alias.sourceLineId}`">{{ text(alias.sourceDocumentNo) }} · 第 {{ text(alias.sourceLineNo) }} 行</li></ul>
        </details>
      </template>
    </section>
    <p v-else-if="!validSelection">本需求缺少准确原来源和范围，当前无法核对。</p>
    <button v-if="selectedDemand" type="button" :disabled="busy || writeLocked || parentLoading || !validSelection" @click="readSource">只读核对用料来源</button>
    <p v-if="parentLoading">原计划目录尚未读取成功，计划及需求数量未知。</p>
    <p v-if="state.loadState === 'loading'" role="status">正在核对来源、生产范围及精确数量；完成前资格未知。</p>
    <p v-if="state.error" class="material-error" role="alert">{{ state.error.message }}</p>
    <p v-if="selectedSource && state.loadState === 'loaded' && !proof" class="material-error" role="alert">{{ previewMismatch }}</p>
    <template v-if="proof">
      <section class="material-relation" aria-labelledby="material-demand-relation-heading">
        <h3 id="material-demand-relation-heading">订单成品与本次用料</h3>
        <ol class="material-relation-steps">
          <li>
            <strong>订单行成品</strong>
            <p v-if="orderLine">{{ text(orderLine.materialName) }} <b>{{ quantityWithUnit(orderLine.requiredQty, orderLine.uomCode) }}</b></p>
            <p v-if="orderLine">成品编码 {{ text(orderLine.materialCode) }}</p>
            <p v-if="orderLine">销售订单 {{ text(orderLine.salesOrderNo) }} · {{ orderLineLabel }}</p>
            <p v-else>{{ orderLinkMissing }}</p>
          </li>
          <li>
            <strong>生产计划与 BOM</strong>
            <p>生产计划 {{ text(proof.productionPlanNo) }}</p>
            <p>BOM 版本 {{ text(proof.bomVersion) }} · {{ bomLineLabel }}</p>
            <p v-if="proof.sourceDocumentNo">{{ proof.sourceObjectType === 'BOMItem' ? 'BOM 编号' : '工程来源' }} {{ proof.sourceDocumentNo }}</p>
          </li>
          <li>
            <strong>本次原料需求</strong>
            <p>{{ text(proof.materialName) }} <b>{{ quantityWithUnit(proof.requiredQty, proof.uomCode) }}</b></p>
            <p>原料编码 {{ text(proof.materialCode) }}</p>
          </li>
        </ol>
      </section>
      <dl class="material-facts">
        <div><dt>本次生产范围</dt><dd>{{ text(proof.rangeStart) }}—{{ text(proof.rangeEnd) }}</dd></div>
        <div><dt>需求日期</dt><dd>{{ text(proof.requiredDate) }}</dd></div>
        <div v-if="selectedDemand"><dt>已有需求／原状态</dt><dd>{{ selectedDemand.demandNo }}／{{ state.facts.statusLabel || selectedDemand.statusLabel }}</dd></div>
      </dl>
      <p>当前未核定物料齐套。实物备料、领料数量未提供。</p>
      <label>办理原因<textarea v-model="reason" aria-label="用料需求办理原因" maxlength="300" :disabled="busy || Boolean(state.pending)" /></label>
      <div class="material-actions">
        <div v-for="key in actionKeys" :key="key"><button type="button" :data-action-code="actions[key].actionCode" :disabled="busy || Boolean(state.pending) || !reason.trim() || !authorization(key).enabled" @click="submit(key)">{{ actions[key].actionName }}</button><p>{{ authorization(key).reason }}</p></div>
      </div>
      <details><summary>来源、版本与完整核验</summary><pre>{{ JSON.stringify(state.facts, null, 2) }}</pre></details>
    </template>
    <p v-if="selectedDemand && !proof">原需求来源为登记时证明，尚未重新核验；不能据此宣称当前允许确认或原料已齐。</p>
    <div v-if="selectedDemand" class="material-actions"><button type="button" @click="openAllocation">{{ actions.allocationPage.actionName }}</button></div>
    <div v-if="state.pending" class="material-pending" role="status">
      <p>本次动作{{ state.receipt?.resultState === 'COMMITTED' ? '已有提交回执' : '结果尚未确认' }}。历史回执不表示当前办理资格，不自动重复提交。</p>
      <p v-if="receiptResult">需求 {{ receiptDemandLabel }} · {{ text(receiptResult.requiredQty) }} {{ text(receiptResult.uomCode) }}</p>
      <button type="button" :disabled="state.busy" @click="controller.queryOriginal()">仅查询同一次动作结果</button>
      <button v-if="state.receipt?.resultState === 'COMMITTED'" type="button" :disabled="state.busy" @click="acknowledge">已查看回执，重新读取</button>
      <details><summary>原动作及回执追溯</summary><pre>{{ JSON.stringify({ originalAction: state.pending, receipt: state.receipt }, null, 2) }}</pre></details>
    </div>
  </section>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { createProductionMaterialPage, materialText as text } from '@/meta/runtime/productionMaterialPage.js'
import { PRODUCTION_MATERIAL_ACTIONS as actions } from '@/meta/process/productionMaterialActions.js'
const props = defineProps({ plans: { type: Array, default: () => [] }, demands: { type: Array, default: () => [] }, parentLoading: Boolean })
const emit = defineEmits(['refresh'])
const router = useRouter(), controller = createProductionMaterialPage({ mode: 'demand' }), state = controller.state
const catalogueController = createProductionMaterialPage({ mode: 'demand', storage: null })
const catalogue = catalogueController.state
const selectedDemandId = ref(''), reason = ref('')
const planId = ref(''), rangeStart = ref(''), rangeEnd = ref(''), sourceKey = ref('')
const approvedScope = ref(null)
const contractName = 'PCE-PRODUCTION-MATERIAL-SOURCE-CATALOGUE-V1'
const decimalText = value => typeof value === 'string' && /^\d+(\.\d+)?$/.test(value)
const canonicalDecimal = value => value.replace(/^0+(?=\d)/, '').replace(/(\.\d*?)0+$/, '$1').replace(/\.$/, '')
const sameDecimal = (left, right) => decimalText(left) && decimalText(right) && canonicalDecimal(left) === canonicalDecimal(right)
const materialDemands = computed(() => props.demands.filter(row => row.sourceType === 'production_material'))
const selectedDemand = computed(() => materialDemands.value.find(row => String(row.id) === selectedDemandId.value))
const currentPlan = computed(() => props.plans.find(plan => String(plan.id) === planId.value))
const rangeInputReady = computed(() => decimalText(rangeStart.value) && decimalText(rangeEnd.value))
const busy = computed(() => state.busy || state.loadState === 'loading')
const writeLocked = computed(() => state.busy || Boolean(state.pending))
const selection = computed(() => selectedDemand.value?.productionMaterialSource)
const validSelection = computed(() => {
  const source = selection.value
  return source && Number.isSafeInteger(source.productionPlanId) && source.productionPlanId > 0
    && Number.isSafeInteger(source.sourceLineId) && source.sourceLineId > 0
    && ['BOMItem', 'EngineeringMaterialRequirement'].includes(source.sourceObjectType)
    && decimalText(source.rangeStart) && decimalText(source.rangeEnd)
})
function matchesPlan(facts, mode) {
  return facts?.contractVersion === contractName && facts.factSource === 'server' && facts.readMode === mode
    && facts.productionPlanId === currentPlan.value?.id && facts.productionPlanNo === currentPlan.value?.label
    && decimalText(facts.approvedRangeStart) && decimalText(facts.approvedRangeEnd)
    && Boolean(facts.productionUomCode) && Number.isInteger(facts.productionDecimalPlaces)
}
const candidateFacts = computed(() => {
  const facts = catalogue.facts, scope = approvedScope.value
  if (!scope || !matchesPlan(facts, 'SOURCE_CANDIDATES')
    || !sameDecimal(facts.approvedRangeStart, scope.approvedRangeStart) || !sameDecimal(facts.approvedRangeEnd, scope.approvedRangeEnd)
    || facts.productionUomId !== scope.productionUomId || facts.productionDecimalPlaces !== scope.productionDecimalPlaces
    || !sameDecimal(facts.rangeStart, rangeStart.value) || !sameDecimal(facts.rangeEnd, rangeEnd.value)
    || !Array.isArray(facts.candidates) || facts.candidateCount !== facts.candidates.length
    || facts.candidates.some(row => !row || !row.sourceObjectType || !Number.isSafeInteger(row.sourceLineId)
      || row.candidateKey !== `${row.sourceObjectType}:${row.sourceLineId}`)
    || new Set(facts.candidates.map(candidateKey)).size !== facts.candidateCount) return null
  if ((facts.factLoadStatus === 'empty_valid' && facts.candidateCount === 0)
    || (facts.factLoadStatus === 'loaded' && facts.candidateCount > 0)) return facts
  return null
})
function selectable(row) {
  const source = row.selection
  return row.selectableForPreview === true && ['BOMItem', 'EngineeringMaterialRequirement'].includes(row.sourceObjectType) && row.quantityStatus === 'PROVEN'
    && ['BOM_AGGREGATE', 'BOM_ROW', 'ENGINEERING_DETAIL'].includes(row.coverageKind)
    && Number.isSafeInteger(row.sourceLineId) && source?.sourceLineId === row.sourceLineId
    && source.sourceObjectType === row.sourceObjectType && source.productionPlanId === currentPlan.value?.id
    && sameDecimal(source.rangeStart, rangeStart.value) && sameDecimal(source.rangeEnd, rangeEnd.value)
    && decimalText(row.requiredQty) && typeof row.expectedSourceFingerprint === 'string' && Boolean(row.expectedSourceFingerprint)
}
const candidateKey = row => row.candidateKey
const selectableRows = computed(() => (candidateFacts.value?.candidates || []).filter(selectable))
const pendingRows = computed(() => (candidateFacts.value?.candidates || []).filter(row => !selectable(row)))
const selectedSource = computed(() => selectableRows.value.find(row => candidateKey(row) === sourceKey.value))
const catalogueMessage = computed(() => {
  if (catalogue.error) {
    const kind = catalogue.error.code === 'MATERIAL_PRODUCTION_RANGE_INVALID' ? '本次生产范围无效。'
      : catalogue.error.status === 409 ? '原来源或批准条件待核。' : ''
    return `${kind}${catalogue.error.message}`
  }
  if (!catalogue.facts || catalogue.facts === approvedScope.value || candidateFacts.value) return ''
  return '返回的范围或来源目录与当前选择不一致，请重新选择计划并读取。'
})
function candidateLabel(row) {
  const sourceLabel = { BOM_AGGREGATE: 'BOM 整组', BOM_ROW: 'BOM 明细', ENGINEERING_DETAIL: '工程明细' }[row.coverageKind] || text(row.sourceTypeLabel)
  return `${sourceLabel} 第 ${text(row.sourceLineNo)} 行 · ${text(row.materialName)}／${text(row.materialCode)} · ${text(row.sourceDocumentNo)}／${text(row.sourceVersion)} · ${text(row.requiredQty)} ${text(row.uomCode)}`
}
const proof = computed(() => {
  const facts = state.facts, current = facts?.sourceProof
  if (selectedDemand.value) return facts?.demandId === selectedDemand.value.id ? current : null
  const row = selectedSource.value
  if (!row || !current || facts.sourceFingerprint !== row.expectedSourceFingerprint
    || current.sourceLineId !== row.sourceLineId || current.sourceObjectType !== row.sourceObjectType
    || current.productionPlanId !== row.selection.productionPlanId
    || !sameDecimal(current.rangeStart, row.selection.rangeStart) || !sameDecimal(current.rangeEnd, row.selection.rangeEnd)
    || current.bomVersionId !== row.bomVersionId || current.bomVersion !== row.sourceVersion || current.bomRevision !== row.sourceRevision
    || current.sourceDocumentNo !== row.sourceDocumentNo || current.materialId !== row.materialId || current.uomId !== row.uomId
    || !sameDecimal(current.requiredQty, row.requiredQty)) return null
  return current
})
const orderLine = computed(() => {
  const source = proof.value
  if (!source?.parentDemandId || !source.salesOrderId || !source.salesOrderItemId) return null
  return props.demands.find(row => row.sourceType === 'sales_order' && row.id === source.parentDemandId
    && row.salesOrderId === source.salesOrderId && row.salesOrderItemId === source.salesOrderItemId) || null
})
const orderLinkMissing = computed(() => {
  const source = proof.value
  if (!source?.parentDemandId) return '正式来源未提供对应的订单计划需求 ID。'
  if (!source.salesOrderId || !source.salesOrderItemId) return '正式来源未提供销售订单或订单行 ID。'
  return '当前可读的订单计划需求未返回这条来源对应的销售订单行，成品信息待核。'
})
const orderLineLabel = computed(() => {
  const row = orderLine.value
  return row.salesOrderLineNo == null
    ? '正式行号未提供（订单行 ID ' + row.salesOrderItemId + '）'
    : '第 ' + row.salesOrderLineNo + ' 行'
})
const bomLineLabel = computed(() => {
  const lineNo = selectedSource.value?.bomLineNo ?? proof.value?.bomLineNo
  return lineNo == null ? 'BOM 行号未提供' : 'BOM 第 ' + lineNo + ' 行'
})
function quantityWithUnit(quantity, unitCode) {
  return text(quantity) + ' ' + (unitCode === 'm2' ? '平方米' : text(unitCode))
}
const actionKeys = computed(() => [selectedDemand.value ? 'confirm' : 'register'])
const previewMismatch = computed(() => {
  const projected = state.facts?.actionAuthorization?.register
  return projected?.allowed === false && projected.reason
    ? projected.reason : '当前范围、来源版本或精确数量与选中明细不一致，请重新读取正式来源。'
})
const receiptResult = computed(() => state.receipt?.resultState === 'COMMITTED' ? state.receipt.result : null)
const receiptDemandLabel = computed(() => {
  const id = receiptResult.value?.demandId
  return materialDemands.value.find(row => row.id === id)?.demandNo || `记录 ID ${text(id)}`
})
function authorization(key) {
  const current = state.facts
  const projected = current?.actionAuthorization?.[key]
  if (!projected || !proof.value) return { enabled: false, reason: '服务尚未提供当前选择的准确办理资格。' }
  const matchesObject = key === 'confirm'
    ? projected.demandId === selectedDemand.value?.id && projected.productionPlanId === selection.value?.productionPlanId
    : projected.productionPlanId === selectedSource.value?.selection.productionPlanId
  const enabled = projected.allowed === true && projected.currentStateSource === 'server'
    && projected.actionCode === actions[key].actionCode && matchesObject
    && typeof current.sourceFingerprint === 'string' && Boolean(current.sourceFingerprint)
    && projected.sourceFingerprint === current.sourceFingerprint
  return { enabled, reason: projected.allowed && !enabled ? '资格与当前对象、原计划或来源版本不一致。' : projected.reason }
}
function clearPreview() { sourceKey.value = ''; reason.value = ''; controller.invalidate() }
function invalidateCandidates() { clearPreview(); catalogueController.invalidate() }
function resetRange() {
  approvedScope.value = null; rangeStart.value = ''; rangeEnd.value = ''; invalidateCandidates()
}
function selectDemand() { planId.value = ''; resetRange() }
async function readApprovedScope() {
  resetRange()
  if (!currentPlan.value) return
  await catalogueController.read({ sourceCandidates: '1', productionPlanId: currentPlan.value.id })
  if (matchesPlan(catalogue.facts, 'APPROVED_RANGE_CONTEXT') && catalogue.facts.candidates === null && catalogue.facts.candidateCount === null) approvedScope.value = catalogue.facts
}
function useApprovedRange() {
  rangeStart.value = approvedScope.value.approvedRangeStart
  rangeEnd.value = approvedScope.value.approvedRangeEnd
  invalidateCandidates()
}
function readCandidates() {
  if (!approvedScope.value || !currentPlan.value || !rangeInputReady.value) return
  clearPreview()
  return catalogueController.read({ sourceCandidates: '1', productionPlanId: currentPlan.value.id, rangeStart: rangeStart.value, rangeEnd: rangeEnd.value })
}
function previewSelectedSource() {
  reason.value = ''
  controller.invalidate()
  const row = selectedSource.value
  if (row) return controller.read({ ...row.selection, expectedSourceFingerprint: row.expectedSourceFingerprint })
}
function readSource() {
  if (!validSelection.value) return
  const { productionPlanId, sourceObjectType, sourceLineId, rangeStart, rangeEnd } = selection.value
  return controller.read({ demandId: selectedDemand.value.id, productionPlanId, sourceObjectType, sourceLineId, rangeStart, rangeEnd })
}
async function submit(action) {
  const source = proof.value
  if (!source || writeLocked.value || props.parentLoading || !reason.value.trim() || !authorization(action).enabled) return
  const payload = action === 'confirm' ? { demandId: selectedDemand.value.id } : { ...selectedSource.value.selection }
  Object.assign(payload, { expectedSourceFingerprint: state.facts.sourceFingerprint, reason: reason.value.trim() })
  await controller.submit(action, payload, source.productionPlanId)
}
function acknowledge() { controller.acknowledge(); resetRange(); emit('refresh') }
function openAllocation() { router.push({ path: actions.allocationPage.nextRoute, query: { demandId: String(selectedDemand.value.id) } }) }
watch(() => props.parentLoading, loading => { if (loading) { planId.value = ''; resetRange() } })
</script>
<style scoped>
.material-panel { min-width:0;display:grid;gap:14px;padding:20px;background:white;border:1px solid #dbe3ef;border-radius:10px; }
h2,p { margin:0; } p { line-height:1.65; } fieldset { border:0;padding:0;margin:0;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;min-width:0; }
label { display:grid;gap:6px;min-width:0; } input,select,textarea,button { font:inherit;min-height:44px;max-width:100%;box-sizing:border-box; } input,select,textarea { width:100%;padding:9px;border:1px solid #bdc9db;border-radius:6px; } button { padding:9px 14px;cursor:pointer; } button:disabled { cursor:not-allowed; }
.material-facts { display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin:0; } dt { color:#64748b; } dd { margin:4px 0;overflow-wrap:anywhere; } .material-actions { display:flex;flex-wrap:wrap;gap:12px; }.material-error { color:#b42318; }.material-pending { padding:12px;background:#fff8e6;display:grid;gap:10px; }
.material-relation { border:1px solid #cbd9ec;background:#f7faff;border-radius:8px;padding:14px; }
.material-relation h3 { margin:0 0 10px; }
.material-relation-steps { display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px;list-style:none;margin:0;padding:0; }
.material-relation-steps li { position:relative;min-width:0;overflow-wrap:anywhere;padding:10px;background:white;border:1px solid #dbe3ef;border-radius:6px; }
.material-relation-steps li + li::before { content:'→';position:absolute;left:-18px;top:8px;color:#526682; }
.material-relation-steps strong { color:#153958; }
.material-relation-steps b { white-space:nowrap; }
.source-selection { display:grid;gap:10px;min-width:0; } .source-selection h3 { margin:0; } .selected-source { overflow-wrap:anywhere; } .pending-sources { margin:0;padding-inline-start:20px;overflow-wrap:anywhere; } .pending-sources li + li { margin-top:8px; }
pre { white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px; } summary { cursor:pointer;min-height:40px;line-height:40px; }
@media(max-width:640px) {
  fieldset,.material-facts,.material-relation-steps { grid-template-columns:1fr; }
  .material-panel { padding:14px; }
  .material-actions>div { width:100%; }
  .material-relation-steps li + li::before { content:'↓';left:12px;top:-20px; }
}
</style>
