<template>
  <main class="creation-request-page" data-acceptance-id="purchase-order-creation-request-page"
    data-business-object="PurchaseOrderCreationRequest"
    data-fact-source="SupplierRecommendationDecisionBatchResult">
    <header class="page-heading">
      <div>
        <span>SCM · 采购订单前置准备</span>
        <h1>采购订单创建申请</h1>
        <p>本页只形成创建申请并保留准入证据，不创建、提交或审批采购订单。</p>
      </div>
      <div class="heading-actions">
        <el-button @click="refresh">刷新</el-button>
        <el-button type="primary" plain data-process-action="NAVIGATE_PURCHASE_ORDER_CREATE_ENTRY"
          @click="goToPurchaseOrderCreate">新增采购订单</el-button>
        <el-button type="primary" data-process-action="GENERATE_PURCHASE_ORDER_CREATION_REQUEST"
          :disabled="!creationAllowed" @click="createRequest">生成创建申请</el-button>
      </div>
    </header>

    <el-alert v-if="entryError" :title="entryError" type="warning" show-icon :closable="false" />
    <el-alert v-else-if="!creationAllowed" title="当前Gate尚未达到可创建申请条件"
      description="只有已确认完整批次且Gate状态为可进入采购订单时，才能生成创建申请。"
      type="warning" show-icon :closable="false" />

    <section class="panel" data-acceptance-id="creation-request-purchase-context">
      <div class="section-heading"><h2>一、采购上下文</h2><span>只读</span></div>
      <el-descriptions :column="3" border>
        <el-descriptions-item label="采购申请编号">{{ purchaseRequestNos }}</el-descriptions-item>
        <el-descriptions-item label="供应商推荐批次">{{ sourceBatchId }}</el-descriptions-item>
        <el-descriptions-item label="Gate编号">{{ currentGate?.gateDecisionId || '-' }}</el-descriptions-item>
      </el-descriptions>
    </section>

    <section v-if="requests.length" class="panel" data-acceptance-id="creation-request-selector">
      <div class="section-heading">
        <div><h2>创建申请</h2><p>按推荐供应商拆分；每个申请保留对应物料和证据。</p></div>
        <el-select v-model="activeRequestId" style="width:360px" placeholder="选择创建申请">
          <el-option v-for="request in requests" :key="request.requestId"
            :label="`${request.requestId} · ${request.supplierName}`" :value="request.requestId" />
        </el-select>
      </div>
    </section>

    <template v-if="activeRequest">
      <section class="panel" data-acceptance-id="creation-request-supplier">
        <div class="section-heading"><h2>二、供应商信息</h2><span>来源：人工推荐结果</span></div>
        <el-descriptions :column="3" border>
          <el-descriptions-item label="供应商编码">{{ activeRequest.supplierCode }}</el-descriptions-item>
          <el-descriptions-item label="供应商名称">{{ activeRequest.supplierName }}</el-descriptions-item>
          <el-descriptions-item label="推荐依据">{{ recommendationBasis }}</el-descriptions-item>
        </el-descriptions>
      </section>

      <section class="panel" data-acceptance-id="creation-request-material-items">
        <div class="section-heading"><h2>三、物料清单</h2><span>{{ activeRequest.materialItems.length }} 项</span></div>
        <el-table :data="activeRequest.materialItems" border stripe>
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="materialCode" label="物料编码" min-width="150" />
          <el-table-column prop="materialName" label="物料名称" min-width="180" />
          <el-table-column label="数量" width="120">
            <template #default="{ row }">{{ row.quantityFactPresent ? row.quantity : '待补充' }}</template>
          </el-table-column>
          <el-table-column label="单价" width="130">
            <template #default="{ row }">{{ money(row.unitPrice) }}</template>
          </el-table-column>
          <el-table-column label="金额" width="140">
            <template #default="{ row }">{{ row.quantityFactPresent ? money(row.amount) : '待补充' }}</template>
          </el-table-column>
        </el-table>
        <div class="total">申请总金额：<strong>{{ money(activeRequest.totalAmount) }}</strong></div>
      </section>

      <section class="panel" data-acceptance-id="creation-request-evidence">
        <div class="section-heading"><h2>四、业务证据</h2><span>只读，不自动判断供应商</span></div>
        <el-table :data="activeRequest.materialItems" border stripe>
          <el-table-column prop="materialCode" label="物料" width="140" />
          <el-table-column label="报价比较依据" min-width="210">
            <template #default="{ row }">{{ evidenceText(row.quoteComparisonEvidence) }}</template>
          </el-table-column>
          <el-table-column prop="recommendationReason" label="推荐理由" min-width="220" />
          <el-table-column label="Gate结果" width="150">
            <template #default>准入检查通过</template>
          </el-table-column>
          <el-table-column label="人工确认" min-width="190">
            <template #default="{ row }">{{ row.manualConfirmedBy }} · {{ formatTime(row.manualConfirmedAt) }}</template>
          </el-table-column>
        </el-table>
      </section>

      <section class="panel" data-acceptance-id="creation-request-status">
        <div class="section-heading"><h2>五、创建申请状态</h2><span>正式采购订单仍未创建</span></div>
        <el-descriptions :column="4" border>
          <el-descriptions-item label="申请编号">{{ activeRequest.requestId }}</el-descriptions-item>
          <el-descriptions-item label="申请状态">{{ statusLabel(activeRequest.requestStatus) }}</el-descriptions-item>
          <el-descriptions-item label="创建人">{{ activeRequest.createdBy || '-' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatTime(activeRequest.createdAt) }}</el-descriptions-item>
        </el-descriptions>
        <div class="status-actions">
          <el-button v-if="activeRequest.requestStatus === 'created'"
            data-process-action="START_CREATION_REQUEST_REVIEW" @click="transition('reviewing')">进入审核准备</el-button>
          <el-button v-if="activeRequest.requestStatus === 'reviewing'" type="primary"
            data-process-action="APPROVE_FOR_PURCHASE_ORDER_CREATION"
            @click="transition('approved_for_creation')">允许后续创建</el-button>
          <el-button v-if="activeRequest.requestStatus !== 'cancelled'" type="danger" plain
            data-process-action="CANCEL_PURCHASE_ORDER_CREATION_REQUEST"
            @click="transition('cancelled')">取消申请</el-button>
        </div>
        <el-alert title="approved_for_creation 仅表示允许进入后续创建环节，不代表采购订单已创建。"
          type="warning" show-icon :closable="false" />
      </section>
    </template>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { stateManager } from '@/meta/runtime/stateManager.js'
import { purchaseOrderCreationRequestProviderV1142821 } from
  '@/meta/providers/purchaseOrderCreationRequestProviderV1142821.js'

const facts = ref({ result: 'FAIL', requests: [], currentGate: null, purchaseContext: {} })
const router = useRouter()
const activeRequestId = ref('')
const requests = computed(() => facts.value.requests || [])
const activeRequest = computed(() => requests.value.find(request =>
  request.requestId === activeRequestId.value) || requests.value[0] || null)
const currentGate = computed(() => facts.value.currentGate)
const sourceBatchId = computed(() => currentGate.value?.sourceBatchId
  || facts.value.sourceTrace?.batchId || '-')
const purchaseRequestNos = computed(() => (facts.value.purchaseContext?.sourceRequestNos || [])
  .join('、') || '-')
const creationAllowed = computed(() => facts.value.result === 'PASS'
  && currentGate.value?.status === 'ready_for_purchase_order'
  && currentGate.value?.batchCompleteness?.pendingItemCount === 0)
const entryError = computed(() => facts.value.result === 'PASS' ? ''
  : `采购订单创建申请数据承接失败：${facts.value.error || '未找到可用Gate上下文'}`)
const recommendationBasis = computed(() => [...new Set((activeRequest.value?.materialItems || [])
  .map(item => item.recommendationReason).filter(Boolean))].join('；') || '-')

function refresh() {
  facts.value = purchaseOrderCreationRequestProviderV1142821.load()
  if (!requests.value.some(request => request.requestId === activeRequestId.value)) {
    activeRequestId.value = requests.value[0]?.requestId || ''
  }
}
function goToPurchaseOrderCreate() {
  router.push('/scm/purchase-order/create')
}
function createRequest() {
  const result = purchaseOrderCreationRequestProviderV1142821.createActive({
    permissionContext: stateManager.snapshot(),
  })
  if (result.result !== 'PASS') return ElMessage.error(result.error || '创建申请生成失败')
  activeRequestId.value = result.requests[0]?.requestId || ''
  ElMessage.success(`已生成 ${result.requestCount} 个采购订单创建申请，未创建采购订单。`)
  refresh()
}
function transition(nextStatus) {
  const result = purchaseOrderCreationRequestProviderV1142821.transition(
    activeRequest.value.requestId, nextStatus, { permissionContext: stateManager.snapshot() })
  if (result.result !== 'PASS') return ElMessage.error(result.error || '申请状态更新失败')
  ElMessage.success(`创建申请状态已更新为：${statusLabel(result.request.requestStatus)}`)
  refresh()
}
const money = value => Number(value || 0).toLocaleString('zh-CN', {
  minimumFractionDigits: 2, maximumFractionDigits: 2,
})
const statusLabel = status => ({ created: '已创建', reviewing: '审核准备中',
  approved_for_creation: '允许后续创建', cancelled: '已取消' })[status] || '待确认'
const formatTime = value => value ? new Date(value).toLocaleString('zh-CN') : '-'
const evidenceText = values => (values || []).map(value => {
  const price = value.currentPrice ?? value.quotePrice
  return `${value.evidenceSource || 'QuoteComparison'}${price == null ? '' : `：${money(price)}`}`
}).join('；') || '-'

onMounted(refresh)
</script>

<style scoped>
.creation-request-page{display:grid;gap:18px;padding:20px}.page-heading,.section-heading{display:flex;align-items:center;justify-content:space-between;gap:16px}.page-heading h1,.section-heading h2{margin:4px 0}.page-heading p,.page-heading span,.section-heading p,.section-heading span{color:#64748b}.heading-actions,.status-actions{display:flex;align-items:center;gap:10px}.panel{display:grid;gap:16px;padding:18px;border:1px solid #dbe4ee;border-radius:12px;background:#fff}.total{text-align:right;font-size:16px}.status-actions{justify-content:flex-end}@media(max-width:800px){.page-heading,.section-heading{align-items:flex-start;flex-direction:column}.heading-actions,.status-actions{flex-wrap:wrap}}
</style>
