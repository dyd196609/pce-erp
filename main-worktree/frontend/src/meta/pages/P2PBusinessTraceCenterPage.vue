<template>
  <main class="p2p-business-trace-center-page">
    <header class="page-header">
      <section>
        <p class="eyebrow">V1.13.27 Business Trace Center</p>
        <h1>P2P业务追踪中心</h1>
        <p>从业务源头只读追踪请购、采购订单、收货、检验、入库、库存流水、应付、付款链路。本页只查询，不修改业务流程和财务状态。</p>
        <p class="finance-current-module-badge">当前模块：P2P业务追踪中心</p>
      </section>
      <nav class="page-tabs finance-flow-nav" aria-label="P2P业务追踪导航">
        <router-link class="finance-nav-button" to="/finance/p2p-validation-center">P2P验证中心</router-link>
        <router-link class="finance-nav-button" to="/finance/formal-payment-vouchers">正式付款凭证</router-link>
      </nav>
    </header>

    <section class="operation-shell">
      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>业务追踪查询</h2>
              <span>第一阶段优先支持采购订单号查询，其他入口保留为只读设计占位。</span>
            </div>
            <el-tag type="info">只读查询</el-tag>
          </div>
        </template>
        <section class="query-row">
          <el-select v-model="queryType" class="query-type" placeholder="入口类型">
            <el-option label="采购订单号" value="purchaseOrder" />
            <el-option label="请购单号" value="purchaseRequest" disabled />
            <el-option label="供应商" value="supplier" disabled />
            <el-option label="收货单号" value="receipt" disabled />
            <el-option label="检验单号" value="inspection" disabled />
            <el-option label="库存流水号" value="inventoryTransaction" disabled />
            <el-option label="应付单号" value="payable" disabled />
            <el-option label="付款凭证号" value="paymentVoucher" disabled />
          </el-select>
          <el-input v-model="queryNo" clearable placeholder="例如：PO2026070605510641" @keyup.enter="runTrace" />
          <el-button type="primary" @click="runTrace">查询业务链</el-button>
        </section>
        <p class="boundary-note">业务追踪中心负责查找业务链；P2P一致性验证中心负责发现异常；风险闭环中心负责处理问题。本页不写 localStorage、不生成业务数据、不写总账。</p>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>业务链总览</h2>
              <span>{{ businessTraceSummary.traceStatusText }}</span>
            </div>
            <el-tag :type="businessTraceSummary.traceStatus === 'complete' ? 'success' : 'warning'">{{ businessTraceSummary.traceStatusText }}</el-tag>
          </div>
        </template>
        <div class="overview-grid">
          <article>
            <span>入口类型</span>
            <strong>{{ businessTraceSummary.sourceTypeText }}</strong>
          </article>
          <article>
            <span>入口单号</span>
            <strong>{{ businessTraceSummary.sourceNo || '-' }}</strong>
          </article>
          <article>
            <span>供应商</span>
            <strong>{{ businessTraceSummary.supplier || '-' }}</strong>
          </article>
          <article>
            <span>链路节点</span>
            <strong>{{ businessTraceSummary.traceNodes.length }}</strong>
          </article>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>P2P业务链</h2>
              <span>请购 -> 采购订单 -> 收货 -> 检验 -> 入库 -> 库存流水 -> 应付 -> 付款</span>
            </div>
            <el-tag type="info">业务源头追踪</el-tag>
          </div>
        </template>
        <section class="trace-chain">
          <article v-for="node in traceNodes" :key="node.key" class="trace-node" :class="{ 'trace-node-missing': node.status !== 'normal' }">
            <div class="node-title">
              <strong>{{ node.title }}</strong>
              <el-tag :type="node.status === 'normal' ? 'success' : 'warning'">{{ node.statusText }}</el-tag>
            </div>
            <p>{{ node.documentNo || '-' }}</p>
            <small>{{ node.description }}</small>
            <dl>
              <template v-for="item in node.details" :key="item.label">
                <dt>{{ item.label }}</dt>
                <dd>{{ item.value || '-' }}</dd>
              </template>
            </dl>
          </article>
        </section>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>库存流水明细</h2>
              <span>同一订单 TXN 编号去重展示，不重复放大链路数量。</span>
            </div>
            <el-tag type="info">数量：{{ inventoryTransactionDetails.length }}</el-tag>
          </div>
        </template>
        <el-table :data="inventoryTransactionDetails" border stripe height="260">
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="transactionNo" label="库存流水号" min-width="180" />
          <el-table-column prop="transactionType" label="流水类型" min-width="180" />
          <el-table-column prop="sourceInspectionNo" label="来源检验单" min-width="170" />
          <el-table-column prop="sourceReceiptNo" label="来源收货单" min-width="170" />
          <el-table-column prop="sourcePurchaseOrderNo" label="来源采购订单" min-width="180" />
        </el-table>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>businessTraceSummary 诊断</h2></template>
        <pre class="diagnostic-json">{{ formattedBusinessTraceSummary }}</pre>
      </el-card>
    </section>
  </main>
</template>

<script setup>
import { computed, ref } from 'vue'
import { listFormalPaymentVouchers } from '../finance/formalPaymentVoucherStore.js'
import { getScmState } from '../scm/scmStore.js'
import { getPurchaseReceiveState } from '../wms/purchaseReceiveStore.js'
import { getQmsState } from '../qms/qmsStore.js'
import { getWmsState } from '../wms/wmsStore.js'
import { resolveP2PBusinessTrace } from '../trace/businessTraceEngine.js'

const queryType = ref('purchaseOrder')
const queryNo = ref('PO2026070605510641')
const activeQuery = ref('PO2026070605510641')

const scmSnapshot = ref(getScmState())
const receiveSnapshot = ref(getPurchaseReceiveState())
const qmsSnapshot = ref(getQmsState())
const wmsSnapshot = ref(getWmsState())
const vouchers = ref(listFormalPaymentVouchers())

function runTrace() {
  scmSnapshot.value = getScmState()
  receiveSnapshot.value = getPurchaseReceiveState()
  qmsSnapshot.value = getQmsState()
  wmsSnapshot.value = getWmsState()
  vouchers.value = listFormalPaymentVouchers()
  activeQuery.value = String(queryNo.value || '').trim()
}

function hasText(value) {
  return String(value || '').trim().length > 0
}

function amount(value) {
  const number = Number(value || 0)
  if (!Number.isFinite(number)) return 0
  return Math.round(number * 100) / 100
}

function recordNo(record = {}, keys = []) {
  return keys.map((key) => record?.[key]).find((value) => hasText(value)) || ''
}

function matches(value, targets = []) {
  const text = String(value || '')
  return targets.some((target) => hasText(target) && text === String(target))
}

function uniqueList(items = []) {
  return Array.from(new Set(items.map((item) => String(item || '').trim()).filter(Boolean)))
}

function orderNo(order = {}) {
  return recordNo(order, ['poNo', 'purchaseOrderNo', 'orderNo'])
}

function lineAmount(line = {}) {
  return amount(line.amount || line.totalAmount || (Number(line.quantity || 0) * Number(line.price || line.unitPrice || 0)))
}

function voucherAmount(voucher = {}) {
  return amount(voucher.totalVoucherAmount || voucher.amount || voucher.debitAmount || voucher.creditAmount)
}

function inventoryTransactionType(record = {}) {
  return record.transactionTypeText || record.transactionType || record.typeText || record.type || '采购入库类库存流水'
}

const traceData = computed(() => {
  const sourceNo = activeQuery.value
  return resolveP2PBusinessTrace(sourceNo, {
    scm: scmSnapshot.value,
    receive: receiveSnapshot.value,
    qms: qmsSnapshot.value,
    wms: wmsSnapshot.value,
    formalVouchers: vouchers.value,
  })
})

function buildNode(key, title, documentNo, description, details = []) {
  const normal = hasText(documentNo)
  return {
    key,
    title,
    status: normal ? 'normal' : 'missing',
    statusText: normal ? '正常' : '缺失',
    documentNo,
    description: normal ? description : '当前未找到对应来源，仅用于只读定位。',
    details,
  }
}

const inventoryTransactionDetails = computed(() => {
  const seen = new Set()
  return (traceData.value.transactions || [])
    .map((item) => ({
      transactionNo: item.transactionNo || item.id || item.no || '',
      transactionType: inventoryTransactionType(item),
      sourceInspectionNo: item.sourceInspectionNo || traceData.value.inspectionNos.join('、'),
      sourceReceiptNo: item.sourceReceiptNo || traceData.value.receiptNos.join('、'),
      sourcePurchaseOrderNo: item.sourcePurchaseOrderNo || item.sourceOrderNo || traceData.value.poNo,
    }))
    .filter((item) => {
      if (!hasText(item.transactionNo) || seen.has(item.transactionNo)) return false
      seen.add(item.transactionNo)
      return true
    })
})

const traceNodes = computed(() => {
  const data = traceData.value
  const supplier = data.supplierList.join('、')
  return [
    buildNode('purchaseRequest', '请购', data.purchaseOrder?.rootRequestNo || data.purchaseOrder?.sourceRequestNo || '', '未来支持请购单入口追踪。', [
      { label: '入口状态', value: '第一阶段占位' },
    ]),
    buildNode('purchaseOrder', '采购订单', data.poNo, '采购订单作为当前业务追踪入口。', [
      { label: '供应商', value: supplier },
      { label: '金额', value: data.purchaseAmount },
    ]),
    buildNode('receipt', '收货', data.receiptNos.join('、'), '找到采购订单对应收货记录。', [
      { label: '收货数量', value: data.receipts.length },
    ]),
    buildNode('inspection', '检验', data.inspectionNos.join('、'), '找到收货或采购订单对应检验记录。', [
      { label: '检验数量', value: data.inspections.length },
    ]),
    buildNode('warehouseEntry', '入库', data.transactionNos.length ? '库存流水代表入库完成' : '', '库存流水可作为入库完成依据。', [
      { label: '入库来源', value: data.transactionNos.length ? '库存流水' : '' },
    ]),
    buildNode('inventoryTransaction', '库存流水', data.transactionNos.join('、'), '库存流水编号已按同一订单去重。', [
      { label: '流水数量', value: inventoryTransactionDetails.value.length },
    ]),
    buildNode('payable', '应付', data.payableNos.join('、'), '从正式付款凭证来源链识别应付来源。', [
      { label: '应付来源数量', value: data.payableNos.length },
    ]),
    buildNode('payment', '付款', data.paymentVoucherNos.join('、'), '从正式付款凭证识别付款凭证或付款记录。', [
      { label: '付款凭证数量', value: data.paymentVoucherNos.length },
      { label: '付款金额', value: amount(data.formalVouchers.reduce((total, item) => total + voucherAmount(item), 0)) },
    ]),
  ]
})

const businessTraceSummary = computed(() => {
  const nodes = traceNodes.value
  const missingRequired = nodes.filter((node) => !['purchaseRequest'].includes(node.key) && node.status !== 'normal')
  return {
    sourceType: queryType.value,
    sourceTypeText: '采购订单号',
    sourceNo: traceData.value.poNo || activeQuery.value,
    supplier: traceData.value.supplierList.join('、'),
    traceNodes: nodes.map((node) => ({
      key: node.key,
      title: node.title,
      status: node.status,
      documentNo: node.documentNo,
    })),
    traceStatus: missingRequired.length ? 'partial' : 'complete',
    traceStatusText: missingRequired.length ? '链路部分缺失' : '链路完整',
  }
})

const formattedBusinessTraceSummary = computed(() => JSON.stringify(businessTraceSummary.value, null, 2))
</script>

<style scoped>
.p2p-business-trace-center-page {
  padding: 24px;
  color: #1f2937;
}

.page-header,
.card-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.eyebrow {
  margin: 0 0 8px;
  color: #2563eb;
  font-weight: 700;
}

.page-header h1,
.card-header h2 {
  margin: 0;
}

.page-tabs,
.query-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.operation-shell {
  display: grid;
  gap: 16px;
}

.query-type {
  width: 180px;
}

.boundary-note {
  margin: 12px 0 0;
  padding: 10px 12px;
  border: 1px solid #dbeafe;
  background: #eff6ff;
  color: #1d4ed8;
  border-radius: 6px;
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
}

.overview-grid article,
.trace-node {
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 12px;
  background: #fff;
}

.overview-grid span,
.trace-node small {
  color: #6b7280;
  font-size: 12px;
}

.overview-grid strong {
  display: block;
  margin-top: 6px;
}

.trace-chain {
  display: grid;
  gap: 12px;
}

.node-title {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.trace-node-missing {
  background: #fffbeb;
  border-color: #fcd34d;
}

.trace-node p {
  margin: 8px 0;
  font-weight: 700;
}

.trace-node dl {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: 6px 10px;
  margin: 10px 0 0;
}

.trace-node dt {
  color: #6b7280;
}

.trace-node dd {
  margin: 0;
}

.diagnostic-json {
  margin: 0;
  padding: 12px;
  background: #111827;
  color: #e5e7eb;
  border-radius: 6px;
  overflow: auto;
  max-height: 360px;
}
</style>
