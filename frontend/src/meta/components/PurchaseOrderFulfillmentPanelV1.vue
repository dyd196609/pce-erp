<template>
  <el-card shadow="never" data-acceptance-id="purchase-order-fulfillment-v1">
    <template #header>
      <div class="header">
        <div><h2>供应执行、收货、检验、入库与结案</h2><small>服务端正式事实 · PCE-PURCHASE-FULFILLMENT-V1.0</small></div>
        <el-button :loading="loading" @click="load">刷新执行事实</el-button>
      </div>
    </template>
    <el-alert v-if="error" type="error" show-icon :closable="false" :title="error" />
    <ScmNativeOrderApprovalPanel :key="orderId" :order-id="orderId" @changed="load(); emit('changed')" />
    <el-skeleton v-if="loading && !facts.order" :rows="6" animated />
    <template v-else-if="facts.order">
      <el-descriptions :column="4" border>
        <el-descriptions-item label="订单状态">{{ facts.order.statusLabel }}</el-descriptions-item>
        <el-descriptions-item label="订单数量">{{ facts.order.plannedQuantity }}</el-descriptions-item>
        <el-descriptions-item label="已收 / 合格">{{ facts.order.receivedQuantity }} / {{ facts.order.qualifiedQuantity }}</el-descriptions-item>
        <el-descriptions-item label="已入库 / 不合格">{{ facts.order.inboundQuantity }} / {{ facts.order.rejectedQuantity }}</el-descriptions-item>
      </el-descriptions>
      <el-alert v-if="currentActions[0]" class="identity-proof" type="info" :closable="false" show-icon
        :title="`当前执行身份：${currentActions[0].authorization.account?.username || '未识别'}；角色：${(currentActions[0].authorization.roleCodes || []).join('、') || '无'}；岗位：${currentActions[0].authorization.position?.code || '无'}；职责：${currentActions[0].authorization.responsibility?.code || '无'}`" />

      <div class="actions">
        <el-input-number v-model="quantity" :min="0.0001" :precision="4" />
        <el-select v-model="warehouseCode" placeholder="选择正式仓库">
          <el-option v-for="row in facts.warehouses || []" :key="row.code"
            :label="`${row.code} / ${row.name} / ${row.locationCode}`" :value="row.code" />
        </el-select>
        <el-button v-for="action in currentActions" :key="action.uiCode"
          type="primary" :loading="submitting" :disabled="!action.authorization.allowed"
          :title="action.authorization.disabledReason" @click="execute(action)">
          {{ action.label }}
        </el-button>
      </div>
      <el-alert v-for="action in currentActions.filter(row => !row.authorization.allowed)"
        :key="`${action.uiCode}-denied`" type="warning" :closable="false" show-icon
        :title="`${action.label}：${action.authorization.disabledReason}`" />

      <h3>业务单据链</h3>
      <div class="trace">
        <el-tag v-for="row in facts.trace || []" :key="`${row.type}-${row.id}`">
          {{ row.type }}：{{ row.no || row.id }}
        </el-tag>
      </div>

      <section v-if="String(facts.order.id)===String(orderId)" class="opinion-entry" aria-label="采购订单的供应商意见">
        <h3>来料异常的供应商意见</h3>
        <p>采购订单 {{ facts.order.poNo }} · 供应商 {{ facts.order.supplierName }}</p>
        <label v-if="facts.inspections?.length">相关检验单
          <select :value="opinionInspectionId || ''" @change="selectOpinionInspection($event.target.value)">
            <option value="">请选择本采购订单的检验单</option>
            <option v-for="row in facts.inspections" :key="row.id" :value="row.id">
              {{ row.inspectionNo }} · {{ receiptNumber(row.receiptId) }}
            </option>
          </select>
        </label>
        <p v-else>本采购订单尚无检验单可查。</p>
        <IncomingExceptionPanel kind="opinion" :inspection-id="opinionInspectionId" :order-id="facts.order.id" />
      </section>

      <section v-if="String(facts.order.id)===String(orderId)" class="manager-return-entry" aria-label="采购经理退供决定">
        <h3>采购经理退供决定</h3>
        <label v-if="facts.inspections?.length">
          <span id="manager-return-inspection-label">退供决定的检验单</span>
          <select aria-labelledby="manager-return-inspection-label" :value="managerInspection?.id || ''"
            @change="changeManagerInspection($event.target.value)">
            <option value="">请选择本采购订单的检验单</option>
            <option v-for="row in facts.inspections" :key="row.id" :value="row.id">
              {{ row.inspectionNo }} · {{ receiptNumber(row.receiptId) }}
            </option>
          </select>
        </label>
        <p v-else>本采购订单尚无检验单可查。</p>
        <p v-if="managerLoading" role="status">正在读取本检验单的异常登记。</p>
        <p v-else-if="managerError" role="alert">{{ managerError }}</p>
        <template v-else-if="managerDirectory">
          <p v-if="managerDirectory.count===0" role="status">本检验单没有异常登记候选。</p>
          <template v-else>
            <p role="status">本检验单有 {{ managerDirectory.count }} 笔异常登记。</p>
            <ul class="manager-return-registrations">
              <li v-for="row in managerDirectory.results" :key="row.registrationId">
                <p>{{ row.purchaseOrderNo }} · {{ row.receiptNo }} · {{ row.inspectionNo }}</p>
                <p>{{ visibleValue(row.materialName) }} · {{ visibleValue(row.materialCode) }} · 采购订单行号 {{ visibleValue(row.purchaseOrderLineNo) }}</p>
                <p>登记不合格量 {{ registeredQuantity(row) }} · 登记时间 {{ visibleValue(row.registeredAt) }}</p>
                <p>本登记尚待决定的申请 {{ row.pendingRequestCount==null ? '未提供' : row.pendingRequestCount+' 条' }}</p>
                <p><strong>{{ row.statusLabel }}</strong></p>
                <p v-if="row.sourceStatus==='SOURCE_UNKNOWN'">{{ row.blockingReason?.message || '本异常登记的来源待核。' }}</p>
                <button type="button" :aria-pressed="selectedManagerRegistration===row" @click="selectManagerRegistration(row)">
                  查看本笔退供申请
                </button>
              </li>
            </ul>
          </template>
        </template>
        <button v-if="managerInspection" type="button" :disabled="managerLoading" @click="loadManagerRegistrations">
          刷新异常登记
        </button>
        <IncomingReturnPanel v-if="selectedManagerRegistration" :key="managerDetailKey"
          kind="return_decide" :inspection-id="managerInspection.id" :registration-id="selectedManagerRegistration.registrationId"
          :order-id="facts.order.id" @changed="loadManagerRegistrations" />
      </section>

      <h3>库存变动</h3>
      <el-table :data="facts.inventoryTransactions || []" border empty-text="尚无正式库存流水">
        <el-table-column prop="transactionNo" label="流水号" min-width="170" />
        <el-table-column prop="warehouseCode" label="仓库" min-width="120" />
        <el-table-column prop="materialCode" label="物料" min-width="120" />
        <el-table-column prop="quantity" label="本次数量" min-width="100" />
        <el-table-column prop="beforeQuantity" label="入库前" min-width="100" />
        <el-table-column prop="afterQuantity" label="入库后" min-width="100" />
        <el-table-column prop="operator" label="执行员工" min-width="120" />
      </el-table>
    </template>
  </el-card>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getPurchaseOrderFulfillmentFacts, runScmRuntimeAction } from '../../api/scmStandardPageFacts.js'
import request from '@/api/request.js'
import ScmNativeOrderApprovalPanel from './ScmNativeOrderApprovalPanel.vue'
import IncomingExceptionPanel from './IncomingExceptionPanel.vue'
import IncomingReturnPanel from './IncomingReturnPanel.vue'
import { quoteFailure } from '../runtime/nativeQuoteRegistration.js'
import { getTabAuthEpoch } from '../runtime/tabAuthenticationContext.js'
import { useRoute, useRouter } from 'vue-router'

const props = defineProps({ orderId: { type: [String, Number], required: true } })
const emit = defineEmits(['changed'])
const route = useRoute(), router = useRouter()
const facts = reactive({})
const loading = ref(false)
const submitting = ref(false)
const error = ref('')
const quantity = ref(2)
const warehouseCode = ref('')
let readGeneration = 0
const opinionInspectionId = computed(()=>(facts.inspections || []).find(row=>String(row.id)===route.query.a10OpinionInspection)?.id || null)

function receiptNumber(id){return facts.receipts?.find(row=>row.id===id)?.receiptNo || '收货单号未提供'}
function selectOpinionInspection(id){
  return router.replace({query:{...route.query,a10OpinionInspection:id || undefined,a10Inspection:undefined,a10Registration:undefined}})
}

const managerEpoch = getTabAuthEpoch()
const managerDirectory = ref(null), managerLoading = ref(false), managerError = ref('')
const managerDetailKey = ref(0)
let managerReadCycle = 0
const managerInspection = computed(() => (facts.inspections || []).find(row => String(row.id)===route.query.a10ManagerInspection))
const selectedManagerRegistration = computed(() => managerDirectory.value?.results
  .find(row => String(row.registrationId)===route.query.a10ManagerRegistration))
const decisionUrl = inspectionId => `/api/procurement/incoming-exceptions/${inspectionId}/returns/return_decide/`

function visibleValue(value) {
  return value==null || value==='' ? '未提供' : String(value)
}
function registeredQuantity(row) {
  return row.registeredRejectedQuantity==null ? '未提供' : `${row.registeredRejectedQuantity} ${visibleValue(row.unit)}`
}
function changeManagerInspection(id) {
  return router.replace({query:{...route.query,a10ManagerInspection:id || undefined,
    a10ManagerRegistration:undefined,a10ReturnDecide:undefined,a10ReturnDecideRequest:undefined}})
}
function selectManagerRegistration(row) {
  if (!managerDirectory.value?.results.includes(row)) return
  managerDetailKey.value++
  const root=String(row.registrationId)
  return router.replace({query:{...route.query,a10ManagerRegistration:root,a10ReturnDecide:root,
    a10ReturnDecideRequest:undefined}})
}
function managerReadFailure(reply) {
  const status=reply?.meta?.status
  const label=status===401 ? '请登录后读取异常登记'
    : status===403 ? '无权读取采购经理退供决定的异常登记'
      : status===404 ? '未找到本授权范围内的检验来源'
        : status===409 ? '本检验来源待核' : '异常登记读取失败'
  return reply?.error?.message ? `${label}：${reply.error.message}` : label
}
async function loadManagerRegistrations() {
  const ticket=++managerReadCycle, inspection=managerInspection.value, order=facts.order
  managerDirectory.value=null
  managerError.value=''
  managerLoading.value=false
  if (getTabAuthEpoch()!==managerEpoch || !inspection || !order || String(order.id)!==String(props.orderId)) return
  const url=decisionUrl(inspection.id)
  managerLoading.value=true
  const reply=await request({url,meta:{module:'SCM',readOnly:true,factLoad:true}}).catch(()=>null)
  if (ticket!==managerReadCycle || getTabAuthEpoch()!==managerEpoch) return
  managerLoading.value=false
  const data=reply?.data
  const matches=row => row?.inspectionId===inspection.id && row.purchaseOrderId===order.id
    && row.inspectionNo===inspection.inspectionNo && row.purchaseOrderNo===order.poNo
    && row.receiptId===inspection.receiptId
  if (!reply?.success || data?.contractVersion!=='PCE-NEVER-STOCKED-INCOMING-ONSITE-RETURN-V1'
    || data.projection!=='EXACT_INSPECTION_RETURN_REGISTRATIONS'
    || data.countScope!=='THIS_AUTHORIZED_INSPECTION_REGISTRATIONS_ONLY'
    || data.selectionGrantsExecution!==false || data.requiresSelectedDetailReload!==true
    || !matches(data.inspection) || !Array.isArray(data.results) || data.count!==data.results.length
    || data.results.some(row => !matches(row) || !Number.isSafeInteger(row.registrationId) || row.registrationId<=0
      || row.detailUrl!==`${url}?registrationId=${row.registrationId}`
      || typeof row.statusLabel!=='string' || !row.statusLabel.trim()
      || !['PROVIDED','SOURCE_UNKNOWN'].includes(row.sourceStatus))
    || new Set(data.results.map(row=>row.registrationId)).size!==data.results.length) {
    managerError.value=managerReadFailure(reply)
    return
  }
  managerDirectory.value=data
}
watch([managerInspection,()=>props.orderId],loadManagerRegistrations,{immediate:true})
onBeforeUnmount(()=>{managerReadCycle++})

const auth = code => facts.authorization?.[code] || { allowed: false, disabledReason: '授权事实未读取' }
const currentActions = computed(() => {
  const status = facts.order?.status
  // Four approval actions use the exact server contract in the original approval panel.
  if (['draft', 'submitted', 'approved', 'reviewed'].includes(status)) return []
  if (status === 'final_approved') return [{ uiCode: 'confirm-receipt', label: '确认收货', objectId: props.orderId, authorization: auth('procurement.receipt.receive'), data: () => ({ quantity: quantity.value }) }]
  const receipt = (facts.receipts || []).find(row => !(facts.inspections || []).some(item => item.receiptId === row.id))
  if (receipt) return [{ uiCode: 'create-inspection', label: '生成检验单', objectId: receipt.id, authorization: auth('quality.purchase.inspect') }]
  const pending = (facts.inspections || []).find(row => row.status === 'pending')
  if (pending) return [{ uiCode: 'transition-inspection', label: '开始检验', objectId: pending.id, authorization: auth('quality.purchase.inspect'), data: () => ({ targetStatus: 'inspecting' }) }]
  const inspecting = (facts.inspections || []).find(row => row.status === 'inspecting')
  if (inspecting) return [{ uiCode: 'transition-inspection', label: '判定合格', objectId: inspecting.id, authorization: auth('quality.purchase.inspect'), data: () => ({ targetStatus: 'qualified', qualifiedQuantity: quantity.value }) }]
  const qualified = (facts.inspections || []).find(row => row.status === 'qualified' && !(facts.inbounds || []).some(item => item.inspectionId === row.id))
  if (qualified) return [{ uiCode: 'confirm-inbound', label: '确认入库', objectId: qualified.id, authorization: auth('warehouse.purchase.putaway'), data: () => ({ quantity: quantity.value, warehouseCode: warehouseCode.value }) }]
  if (status === 'stored') return [{ uiCode: 'complete-purchase-order', label: '正常结案', objectId: props.orderId, authorization: auth('procurement.purchase_order.complete') }]
  return []
})

function replaceFacts(value) {
  Object.keys(facts).forEach(key => delete facts[key])
  Object.assign(facts, value || {})
  const remaining = Number(facts.order?.plannedQuantity || 0) - Number(facts.order?.inboundQuantity || 0)
  if (remaining > 0) quantity.value = remaining
  if (!warehouseCode.value && facts.warehouses?.length) warehouseCode.value = facts.warehouses[0].code
}

async function load() {
  if (!props.orderId) return
  const generation = ++readGeneration
  replaceFacts({})
  loading.value = true; error.value = ''
  try {
    const response = await getPurchaseOrderFulfillmentFacts(props.orderId)
    if (generation !== readGeneration) return
    if (response?.success !== true || !response.data?.order) throw quoteFailure(response, 'purchase-order-fulfillment')
    replaceFacts(response?.data || response)
  } catch (exception) {
    if (generation !== readGeneration) return
    replaceFacts({})
    error.value = exception?.response?.data?.error?.message || exception?.message || '执行事实读取失败'
  } finally { if (generation === readGeneration) loading.value = false }
}

async function execute(action) {
  submitting.value = true
  try {
    await runScmRuntimeAction(action.uiCode, action.objectId, action.data?.() || {})
    ElMessage.success(`${action.label}成功`)
    await load(); emit('changed')
  } catch (exception) {
    ElMessage.error(exception?.response?.data?.error?.message || exception?.message || `${action.label}失败`)
  } finally { submitting.value = false }
}

watch(() => props.orderId, load)
onMounted(load)
defineExpose({ load })
</script>

<style scoped>
.header, .actions, .trace { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.header { justify-content: space-between; }
.header h2 { margin: 0 0 4px; }
.actions { margin: 16px 0; }
.identity-proof { margin-top: 14px; }
.actions .el-select { width: 300px; }
.opinion-entry, .manager-return-entry { min-width: 0; overflow-wrap: anywhere; }
:is(.opinion-entry,.manager-return-entry)>label { display: grid; gap: 4px; max-width: 480px; }
:is(.opinion-entry,.manager-return-entry)>label>select { width: 100%; min-height: 44px; min-width: 0; }
.manager-return-registrations { padding: 0; list-style: none; }
.manager-return-registrations li { border-top: 1px solid #d6e0ee; padding: 8px 0; }
.manager-return-registrations p { margin: 4px 0; }
.manager-return-entry button { min-height: 44px; max-width: 100%; }
h3 { margin: 18px 0 10px; }
</style>
