<template>
  <main class="formal-execution-page">
    <header>
      <div>
        <h1 data-acceptance-id="page-business-title">{{ isQuality ? '来料检验' : '库存余额' }}</h1>
        <p>唯一来源：{{ facts.authoritySource || '正在读取正式服务端事实' }}</p>
      </div>
      <el-button :loading="loading" @click="loadFacts">刷新</el-button>
    </header>

    <el-alert
      v-if="error"
      type="error"
      :closable="false"
      :title="error"
      show-icon
    />
    <el-alert
      v-else
      type="success"
      :closable="false"
      :title="isInventoryBalance || selectedQuality ? '库存及检验依据来自正式服务，办理以当前单据的服务端资格为准。' : '当前正式路由只读取 Django Service/API；Demo fixture 与浏览器本地状态不参与正式事实。'"
      show-icon
    />

    <section class="summary-grid">
      <article v-for="(value, key) in facts.summary || {}" :key="key">
        <span>{{ labels[key] || key }}</span><strong>{{ value }}</strong>
      </article>
    </section>

    <template v-if="isQuality">
      <RawIncomingLinePanel v-if="selectedQuality" mode="quality" :quality-rows="[selectedQuality]"
        :initial-source-id="selectedQuality.id" @changed="loadFacts" />
      <h2>来料检验</h2>
      <el-table :data="facts.inspections || []" stripe>
        <el-table-column prop="inspectionNo" label="检验单号" min-width="160" />
        <el-table-column prop="purchaseOrderNo" label="采购订单" min-width="160" />
        <el-table-column prop="status" label="检验单状态" width="120" />
        <el-table-column prop="qualifiedQuantity" label="合格数量" width="120">
          <template #default="{ row }">{{ row.lineReleaseFacts?.qualifiedQuantity ?? '未提供' }}</template>
        </el-table-column>
        <el-table-column prop="rejectedQuantity" label="不合格数量" width="120">
          <template #default="{ row }">{{ row.lineReleaseFacts?.rejectedQuantity ?? '未提供' }}</template>
        </el-table-column>
      </el-table>
      <h2>正式入库回读</h2>
      <el-table :data="facts.inbounds || []" stripe>
        <el-table-column prop="inboundNo" label="入库单号" min-width="160" />
        <el-table-column prop="inspectionNo" label="来源检验" min-width="160" />
        <el-table-column prop="warehouseCode" label="仓库" width="130" />
        <el-table-column prop="locationCode" label="库位" width="130" />
        <el-table-column prop="quantity" label="数量" width="120" />
      </el-table>
    </template>

    <template v-else>
      <RawIncomingLinePanel v-if="isInventoryBalance" mode="inbound" :inventory-facts="facts" @changed="loadFacts" />
      <ProductionMaterialAllocationPanel :inventory-facts="facts" :refresh-version="readVersion" />
      <section v-if="isInventoryBalance" class="m09-stock-panel" aria-label="订单行成品库存分配">
        <h2>订单行成品库存分配</h2>
        <form class="m09-stock-search" @submit.prevent="locateStockLine">
          <label>原订单行 ID<input v-model.trim="stockLineInput" inputmode="numeric" required /></label>
          <label>原订单记录 ID（可选）<input v-model.trim="stockOrderInput" inputmode="numeric" /></label>
          <button type="submit">查看分配与释放</button>
          <button v-if="stockLineId" type="button" @click="closeStockLine">返回库存余额</button>
        </form>
        <p>当前只支持按准确的原订单行标识查看，已授权的订单行和合格入库候选待服务端提供。</p>
        <p v-if="stockInputError" role="alert">{{ stockInputError }}</p>
        <p v-if="stockLoading" role="status">正在读取本订单行的分配和释放历史。</p>
        <p v-if="stockError" role="alert">{{ stockError }}</p>
        <template v-if="stockRead">
          <h3>订单 {{ stockOrder?.orderNo || '未提供' }} · {{ stockOrderItem?.lineNo ? `第 ${stockOrderItem.lineNo} 行` : `订单行 ID ${stockRead.salesOrderItemId}` }}</h3>
          <dl class="m09-stock-facts">
            <div><dt>订单行成品</dt><dd>{{ stockOrderItem?.materialName || '未提供' }}</dd></div>
            <div><dt>实际制造完成量</dt><dd>{{ stockQuantity(stockCoverage?.manufacturingCompletedQuantity, stockCoverage?.uomLabel) }}</dd></div>
            <div><dt>当前订单行库存覆盖</dt><dd>{{ stockQuantity(stockCoverage?.confirmedStockCoverageQuantity, stockCoverage?.uomLabel) }}</dd></div>
          </dl>
          <p v-if="stockOrderError" role="status">{{ stockOrderError }}</p>
          <p v-if="stockRead.factLoadFacts.factLoadStatus === 'empty_valid'">服务端确认本订单行当前无库存分配记录。</p>
          <article v-for="row in stockRead.allocations" :key="row.allocationId" class="m09-stock-record" :data-allocation-id="row.allocationId">
            <h4>分配 {{ row.allocationId }} · {{ row.statusLabel || '状态未提供' }}</h4>
            <dl class="m09-stock-facts">
              <div><dt>库存成品</dt><dd>{{ sourceTransaction(row)?.materialName || '未提供' }}</dd></div>
              <div><dt>批次</dt><dd>{{ row.lotNo || '未提供' }}</dd></div>
              <div><dt>原入库</dt><dd>{{ sourceTransaction(row)?.sourceInboundNo || '未提供' }}</dd></div>
              <div><dt>原入库流水</dt><dd>{{ sourceTransaction(row)?.transactionNo || (row.sourceTransactionId ? `流水 ID ${row.sourceTransactionId}` : '未提供') }}</dd></div>
              <div><dt>原分配量</dt><dd>{{ stockQuantity(row.recordedQuantity ?? row.quantity, row.uomLabel) }}</dd></div>
              <div><dt>本笔当前覆盖</dt><dd>{{ row.status === 'released' && row.active === false ? '已释放，退出覆盖' : stockQuantity(row.targetQuantity, row.targetUomLabel) }}</dd></div>
              <div><dt>原分配审计</dt><dd>{{ row.auditId ?? '未提供' }}</dd></div>
            </dl>
            <div v-if="releaseEvidence(row).length">
              <strong>释放依据</strong>
              <ul><li v-for="event in releaseEvidence(row)" :key="event.transitionId">{{ event.auditReference || '审计引用未提供' }}</li></ul>
            </div>
          </article>
          <details>
            <summary>查询同一次动作结果</summary>
            <form class="m09-stock-search" @submit.prevent="queryStockAction">
              <label>原动作<select v-model="stockActionKind" aria-label="原动作" @change="clearActionRead"><option value="allocate">确认分配</option><option value="release">释放分配</option></select></label>
              <label v-if="stockActionKind === 'release'">原分配<select v-model="stockActionAllocation" aria-label="原分配" required @change="clearActionRead"><option value="">请选择</option><option v-for="row in stockRead.allocations" :key="row.allocationId" :value="String(row.allocationId)">分配 {{ row.allocationId }}</option></select></label>
              <label>原动作标识<input v-model.trim="stockActionKey" maxlength="160" required @input="clearActionRead" /></label>
              <button type="submit" :disabled="stockActionLoading">查询原结果</button>
            </form>
            <p v-if="stockActionMessage" role="status">{{ stockActionMessage }}</p>
          </details>
          <p>当前办理资格未提供。确认还需合格入库候选，释放还需本分配的当前版本和服务端释放资格。</p>
        </template>
      </section>
      <h2>库存余额</h2>
      <el-table :data="facts.balances || []" stripe>
        <el-table-column prop="warehouseCode" label="仓库" width="130" />
        <el-table-column prop="locationCode" label="库位" width="130" />
        <el-table-column prop="materialCode" label="物料编码" min-width="150" />
        <el-table-column prop="materialName" label="物料名称" min-width="180" />
        <el-table-column prop="lotNo" label="批号" width="150" />
        <el-table-column prop="quantity" label="数量" width="120" />
      </el-table>
      <h2>库存流水</h2>
      <el-table :data="facts.transactions || []" stripe>
        <el-table-column prop="transactionNo" label="流水号" min-width="160" />
        <el-table-column prop="sourceInboundNo" label="来源入库" min-width="160" />
        <el-table-column prop="materialCode" label="物料" width="150" />
        <el-table-column prop="locationCode" label="库位" width="120" />
        <el-table-column prop="lotNo" label="批号" width="140" />
        <el-table-column prop="quantity" label="数量" width="100" />
        <el-table-column prop="afterQuantity" label="变动后" width="100" />
      </el-table>
      <section class="formal-trace-empty" data-acceptance-id="inventory-formal-trace-empty">
        <strong>业务追踪</strong>
        <span>本汇总区暂无正式业务追踪关系明细可显示（接口未提供独立追踪列表）；本需求的占用及来源核验见上方原料分配区。</span>
      </section>
    </template>
  </main>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ProductionMaterialAllocationPanel from '@/meta/components/ProductionMaterialAllocationPanel.vue'
import RawIncomingLinePanel from '@/meta/components/RawIncomingLinePanel.vue'
import { formalExecutionApi } from '@/api/formalExecution'
import request from '@/api/request.js'
import { getTabAuthEpoch } from '@/meta/runtime/tabAuthenticationContext.js'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const readVersion = ref(0)
const facts = ref({})
const error = ref('')
const isQuality = computed(() => route.path.startsWith('/qms'))
const isInventoryBalance = computed(() => route.path === '/wms/inventory-balances')
const selectedQuality = computed(() => isQuality.value && (facts.value.inspections || []).find(row => String(row.id) === route.params.id))
const validStockId = value => typeof value === 'string' && /^[1-9]\d{0,14}$/.test(value)
const stockLineId = computed(() => isInventoryBalance.value && validStockId(route.query.m09StockLine) ? route.query.m09StockLine : '')
const stockOrderId = computed(() => isInventoryBalance.value && validStockId(route.query.m09StockOrder) ? route.query.m09StockOrder : '')
const stockLineInput = ref(''), stockOrderInput = ref(''), stockInputError = ref('')
const stockRead = ref(null), stockOrder = ref(null), stockOrderItem = ref(null), stockCoverage = ref(null)
const stockLoading = ref(false), stockError = ref(''), stockOrderError = ref('')
const stockActionKind = ref('allocate'), stockActionAllocation = ref(''), stockActionKey = ref('')
const stockActionMessage = ref(''), stockActionLoading = ref(false)
let stockCycle = 0, stockActionCycle = 0
const stockQuantity = (qty, unit) => qty == null || qty === '' ? '未提供' : `${qty} ${unit || '（单位未提供）'}`
const sourceTransaction = row => facts.value.transactions?.find(tx => tx.id === row.sourceTransactionId && tx.direction === 'IN')
const releaseEvidence = row => row.stateHistory?.filter(event => event.targetState === 'released') || []
const stockHistoryUrl = id => `/api/procurement/order-lines/${encodeURIComponent(id)}/stock-allocations/`
const stockReleaseUrl = id => `/api/procurement/order-stock-allocations/${encodeURIComponent(id)}/release/`
async function stockGet(url, params, module = 'WMS') {
  const response = await request({ url, params, meta: { module, readOnly: true, factLoad: true } }).catch(() => null)
  // Coverage responses carry their native envelope without the generic meta field.
  if (module === 'WMS' && response?.success && typeof response.data?.success === 'boolean') return response.data
  return response
}
const stockFailure = (response, fallback) => response?.error?.message || response?.factLoadFacts?.errorMessage || fallback

function locateStockLine() {
  stockInputError.value = ''
  if (!validStockId(stockLineInput.value) || (stockOrderInput.value && !validStockId(stockOrderInput.value))) {
    stockInputError.value = '请从原记录核对订单行和订单记录的准确 ID。'
    return
  }
  if (stockLineInput.value === stockLineId.value && stockOrderInput.value === stockOrderId.value) return readStockLine()
  return router.push({ query: { ...route.query, m09StockLine: stockLineInput.value, m09StockOrder: stockOrderInput.value || undefined } })
}
function closeStockLine() {
  return router.replace({ query: { ...route.query, m09StockLine: undefined, m09StockOrder: undefined } })
}
function clearActionRead() {
  stockActionCycle++
  stockActionMessage.value = ''
  stockActionLoading.value = false
}
async function readStockLine() {
  const cycle = ++stockCycle
  const epoch = getTabAuthEpoch(), lineId = stockLineId.value, orderId = stockOrderId.value
  stockRead.value = stockOrder.value = stockOrderItem.value = stockCoverage.value = null
  stockError.value = stockOrderError.value = ''
  stockLoading.value = Boolean(lineId)
  clearActionRead()
  if (!lineId) return
  const [history, sales] = await Promise.all([
    stockGet(stockHistoryUrl(lineId)),
    orderId ? stockGet(`/api/sales/orders/${encodeURIComponent(orderId)}/`, { includeCompletionFacts: '1' }, 'SALES') : null,
  ])
  if (cycle !== stockCycle) return
  stockLoading.value = false
  if (epoch !== getTabAuthEpoch()) return
  const data = history?.data
  if (!history?.success || String(data?.salesOrderItemId) !== lineId || !Array.isArray(data?.allocations) ||
    !['loaded', 'empty_valid'].includes(data.factLoadFacts?.factLoadStatus)) {
    stockError.value = stockFailure(history, '原服务未返回该订单行的分配历史。')
    return
  }
  stockRead.value = data
  if (!orderId) {
    stockOrderError.value = '分配历史仅提供订单行 ID。订单编号和整行覆盖需从原订单依据读取。'
    return
  }
  const order = sales?.data?.order
  const completion = order?.mesCompletionFacts
  const item = order?.items?.find(row => String(row.id) === lineId)
  const line = completion?.lines?.find(row => String(row.salesOrderItemId) === lineId)
  if (!sales?.success || String(order?.id) !== orderId || !item || !line || completion.salesOrderId !== order.id || completion.contractVersion !== 'PCE-ORDER-MES-COMPLETION-V1' || completion.factLoadStatus !== 'loaded') {
    stockOrderError.value = stockFailure(sales, '原服务未返回当前订单行的完成依据。')
    return
  }
  stockOrder.value = order
  stockOrderItem.value = item
  if (line.supplyCoverage?.contractVersion === 'PCE-ORDER-SUPPLY-COVERAGE-V1' && line.supplyCoverage.uomId === line.uomId) {
    stockCoverage.value = line.supplyCoverage
  } else {
    stockOrderError.value = line.blockingReasons?.[0]?.message || '原服务未提供当前订单行的库存覆盖。'
  }
}
async function queryStockAction() {
  const lineId = stockLineId.value, key = stockActionKey.value
  if (!stockRead.value || !lineId || !key) return
  const allocation = stockRead.value.allocations.find(row => String(row.allocationId) === stockActionAllocation.value)
  if (stockActionKind.value === 'release' && !allocation) return
  const url = stockActionKind.value === 'release' ? stockReleaseUrl(allocation.allocationId) : stockHistoryUrl(lineId)
  const cycle = ++stockActionCycle, epoch = getTabAuthEpoch()
  stockActionLoading.value = true
  stockActionMessage.value = ''
  const response = await stockGet(url, { idempotencyKey: key })
  if (cycle !== stockActionCycle) return
  stockActionLoading.value = false
  if (epoch !== getTabAuthEpoch()) return
  const facts = response?.data
  if (!response?.success || facts?.sameActionKey !== key) {
    stockActionMessage.value = stockFailure(response, '本次动作结果未取得，待核。')
  } else {
    stockActionMessage.value = facts.resultState === 'COMMITTED' ? `原动作已登记，分配 ${facts.result?.allocationId ?? '未提供'}。` : '原动作结果仍待核，保留当前动作标识。'
  }
}
watch([stockLineId, stockOrderId], ([lineId, orderId]) => {
  stockLineInput.value = lineId
  stockOrderInput.value = orderId
  stockInputError.value = ''
  stockActionKey.value = stockActionAllocation.value = ''
  readStockLine()
}, { immediate: true, flush: 'sync' })
watch(readVersion, readStockLine)
onBeforeUnmount(() => { stockCycle++; stockActionCycle++ })
const labels = {
  warehouseCount: '仓库数', locationCount: '库位数', lotCount: '批号数',
  balanceCount: '余额行数', transactionCount: '流水数', totalQuantity: '库存总量',
  inspectionCount: '检验单数', inboundCount: '入库单数',
}

async function loadFacts() {
  readVersion.value++
  loading.value = true
  error.value = ''
  const response = isQuality.value
    ? await formalExecutionApi.qualityFacts()
    : await formalExecutionApi.inventoryFacts()
  if (!response.success) {
    error.value = response.error?.message || '正式服务端事实读取失败'
    facts.value = {}
  } else {
    facts.value = response.data || {}
  }
  loading.value = false
}

onMounted(loadFacts)
watch(() => route.path, loadFacts)
</script>

<style scoped>
.formal-execution-page { padding: 24px; display: grid; grid-template-columns: minmax(0, 1fr); gap: 18px; }
header { display: flex; flex-wrap: wrap; gap: 12px; justify-content: space-between; align-items: center; }
header > div { min-width: 0; overflow-wrap: anywhere; }
h1, h2, p { margin: 0; }
p { margin-top: 6px; color: #64748b; }
.summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }
.summary-grid article { padding: 16px; border: 1px solid #dbeafe; border-radius: 10px; background: #f8fbff; }
.summary-grid span, .summary-grid strong { display: block; }
.summary-grid strong { margin-top: 8px; font-size: 24px; }
.formal-trace-empty { display: flex; gap: 12px; align-items: center; padding: 14px 16px; border: 1px dashed #94a3b8; border-radius: 8px; color: #475569; }
.m09-stock-panel,.m09-stock-record{min-width:0;padding:12px;border:1px solid #d6e0ee;border-radius:8px;overflow-wrap:anywhere}
.m09-stock-panel h2,.m09-stock-panel h3,.m09-stock-record h4{margin:0 0 8px}
.m09-stock-panel form,.m09-stock-panel article,.m09-stock-panel details{margin:10px 0}
.m09-stock-search{display:flex;flex-wrap:wrap;gap:8px;align-items:end}
.m09-stock-search label{display:grid;gap:4px;flex:1 1 160px;min-width:0}
.m09-stock-search input,.m09-stock-search select,.m09-stock-search button,.m09-stock-panel summary{min-height:44px;max-width:100%;padding:4px 8px}
.m09-stock-facts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:8px 0}
.m09-stock-facts dd{margin:0;font-weight:600;font-variant-numeric:tabular-nums}
@media(max-width:600px){.m09-stock-facts{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
