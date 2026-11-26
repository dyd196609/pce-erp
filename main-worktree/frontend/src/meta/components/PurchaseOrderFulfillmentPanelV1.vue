<template>
  <el-card shadow="never" data-acceptance-id="purchase-order-fulfillment-v1">
    <template #header>
      <div class="header">
        <div><h2>供应执行、收货、检验、入库与结案</h2><small>服务端正式事实 · PCE-PURCHASE-FULFILLMENT-V1.0</small></div>
        <el-button :loading="loading" @click="load">刷新执行事实</el-button>
      </div>
    </template>
    <el-alert v-if="error" type="error" show-icon :closable="false" :title="error" />
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
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getPurchaseOrderFulfillmentFacts, runScmRuntimeAction } from '../../api/scmStandardPageFacts.js'

const props = defineProps({ orderId: { type: [String, Number], required: true } })
const emit = defineEmits(['changed'])
const facts = reactive({})
const loading = ref(false)
const submitting = ref(false)
const error = ref('')
const quantity = ref(2)
const warehouseCode = ref('')

const auth = code => facts.authorization?.[code] || { allowed: false, disabledReason: '授权事实未读取' }
const currentActions = computed(() => {
  const status = facts.order?.status
  if (status === 'draft') return [{ uiCode: 'submit-purchase-order', label: '提交订单', objectId: props.orderId, authorization: auth('procurement.purchase_order.submit') }]
  if (status === 'submitted') return [{ uiCode: 'approve-purchase-order', label: '审核订单', objectId: props.orderId, authorization: auth('procurement.purchase_order.approve') }]
  if (status === 'approved') return [{ uiCode: 'review-purchase-order', label: '复核订单', objectId: props.orderId, authorization: auth('procurement.purchase_order.review') }]
  if (status === 'reviewed') return [{ uiCode: 'release-purchase-order', label: '下达订单', objectId: props.orderId, authorization: auth('procurement.purchase_order.release') }]
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
  loading.value = true; error.value = ''
  try {
    const response = await getPurchaseOrderFulfillmentFacts(props.orderId)
    replaceFacts(response?.data || response)
  } catch (exception) {
    error.value = exception?.response?.data?.error?.message || exception?.message || '执行事实读取失败'
  } finally { loading.value = false }
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
h3 { margin: 18px 0 10px; }
</style>
