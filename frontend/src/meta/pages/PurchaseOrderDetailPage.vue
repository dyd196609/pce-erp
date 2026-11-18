<template>
  <main class="purchase-order-detail-page"
    data-page-runtime="PAGE-RUNTIME-001"
    data-page-migration="PAGE-MIGRATION-002"
    data-route-component="PurchaseOrderDetailPage">
    <el-alert v-if="loadError" type="error" show-icon :closable="false"
      data-acceptance-id="purchase-order-detail-load-error" :title="loadError" />
    <el-skeleton v-if="loading && !purchaseOrder.id" :rows="10" animated />
    <PurchaseOrderDetailRuntimeViewV1142842727
      v-else-if="purchaseOrder.id"
      :purchase-order="purchaseOrder"
      :order-lines="orderLines"
      :lifecycle-detail-model="lifecycleDetailModel"
      :refresh-loading="loading"
      :data-updated-at="lastReloadAt"
      :provider-reload-count="providerReloadCount"
      :refresh-result="refreshResult"
      :current-purchase-order-item-count="currentPurchaseOrderItemCount"
      :filtered-item-count="filteredItemCount"
      :refresh-action-trace="refreshActionTrace"
      :refresh-status="refreshStatus"
      :last-refresh-time="lastRefreshTime"
      :server-item-codes="serverItemCodes"
      @reload-page-data="reloadPageData({ userAction: true })"
      @print-audit="handlePrintAudit"
    />
    <p v-if="purchaseOrder.id && !loadError">
      <router-link :to="{ path:'/wms/purchase-receive-preview', query:{a07Order:String(purchaseOrder.id)} }">本采购订单的仓管正式收货入口</router-link>
    </p>
    <PurchaseOrderFulfillmentPanelV1 v-if="purchaseOrder.id"
      :order-id="purchaseOrder.id" @changed="reloadPageData({ userAction: true })" />
    <el-empty v-else-if="!loading" description="未找到当前采购订单" />
    <output class="runtime-refresh-evidence" aria-live="polite"
      data-acceptance-id="purchase-order-refresh-runtime-evidence">
      {{ refreshResult || '订单事实尚未完成读取' }}
    </output>
  </main>
</template>

<script setup>
import { nextTick, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import PurchaseOrderDetailRuntimeViewV1142842727 from
  '../components/PurchaseOrderDetailRuntimeViewV1142842727.vue'
import PurchaseOrderFulfillmentPanelV1 from '../components/PurchaseOrderFulfillmentPanelV1.vue'
import { readPurchaseOrderDetailFactSnapshotV1142842728 } from
  '../providers/purchaseOrderDetailDataProviderV1142842728.js'
import { getScmStandardPageFacts } from '../../api/scmStandardPageFacts.js'
import { reloadPurchaseOrderDetailDataV1142842728 } from
  '../runtime/purchaseOrderDetailDataRuntimeV1142842728.js'

const route = useRoute()
const purchaseOrder = reactive({})
const orderLines = ref([])
const lifecycleDetailModel = ref(null)
const loading = ref(false)
const loadError = ref('')
const providerReloadCount = ref(0)
const lastReloadAt = ref('')
const currentBusinessKey = ref('')
const refreshResult = ref('')
const currentPurchaseOrderItemCount = ref(0)
const filteredItemCount = ref(0)
const refreshClickCount = ref(0)
const refreshActionTrace = ref('首次加载：等待Provider调用与DOM提交')
const refreshStatus = ref('idle')
const lastRefreshTime = ref('')
const serverItemCodes = ref([])

function replaceReactive(target, source = {}) {
  Object.keys(target).forEach(key => delete target[key])
  Object.assign(target, source)
}

async function reloadPageData({ userAction = false } = {}) {
  if (loading.value) return
  const routeBefore = route.fullPath
  const clickEvent = userAction ? `CLICK-${refreshClickCount.value + 1}` : 'INITIAL-LOAD'
  if (userAction) refreshClickCount.value += 1
  if (userAction) refreshStatus.value = 'refreshing'
  refreshActionTrace.value = `${clickEvent} → Provider调用中 → DOM等待提交`
  loading.value = true
  loadError.value = ''
  if (userAction) await nextTick()
  try {
    const result = await reloadPurchaseOrderDetailDataV1142842728({
      purchaseOrderId: route.params.id,
      loadSnapshot: () => readPurchaseOrderDetailFactSnapshotV1142842728({
        loadServerFacts: getScmStandardPageFacts,
      }),
      previousBusinessKey: currentBusinessKey.value,
      executionSequence: providerReloadCount.value,
    })
    replaceReactive(purchaseOrder, result.purchaseOrder)
    orderLines.value = result.orderLines
    lifecycleDetailModel.value = result.lifecycleDetailModel
    currentBusinessKey.value = result.businessKey
    providerReloadCount.value += 1
    lastReloadAt.value = result.providerExecutedAt
    currentPurchaseOrderItemCount.value = result.currentPurchaseOrderItemCount
    filteredItemCount.value = result.filteredItemCount
    serverItemCodes.value = result.serverItemCodes
    refreshResult.value = `${result.providerExecutionId} 已重新读取当前订单；源明细 ${result.sourcePurchaseOrderItemCount} 条，当前订单 ${result.currentPurchaseOrderItemCount} 条，严格过滤后 ${result.filteredItemCount} 条。`
    await nextTick()
    if (route.fullPath !== routeBefore) throw new Error('刷新不应改变当前页面URL。')
    refreshActionTrace.value = `${clickEvent} → ${result.providerExecutionId} → DOM-COMMIT-${providerReloadCount.value}；当前订单 ${result.businessKey}；渲染 ${result.filteredItemCount} 条物料。`
    if (userAction) {
      lastRefreshTime.value = result.providerExecutedAt
      refreshStatus.value = 'success'
      ElMessage.success(`刷新成功：采购订单及 ${result.filteredItemCount} 条物料已重新读取。`)
    }
  } catch (error) {
    loadError.value = error?.message || '采购订单详情加载失败。'
    if (userAction) { refreshStatus.value = 'error'; ElMessage.error(loadError.value) }
  } finally {
    loading.value = false
  }
}

function handlePrintAudit() {}

watch(() => route.params.id, () => reloadPageData(), { immediate: true })

defineExpose({ reloadPageData, providerReloadCount, currentBusinessKey,
  currentPurchaseOrderItemCount, filteredItemCount, refreshResult, refreshActionTrace })
</script>

<style scoped>
.purchase-order-detail-page { display: grid; gap: 14px; width: 100%; min-width: 0; }
.runtime-refresh-evidence { padding: 10px 14px; border: 1px solid var(--el-border-color);
  border-radius: 8px; color: var(--el-text-color-secondary); background: var(--el-fill-color-lighter);
  font-size: 13px; }
</style>
