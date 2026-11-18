<template>
  <main class="p2p-trace-page">
    <header class="page-header">
      <section>
        <p class="eyebrow">V1.13.26.11 P2P风险追踪数据源统一设计</p>
        <h1>P2P业务链追踪</h1>
        <p>本页只读展示风险事件所在的业务链节点，用于人工定位断点；不修改 SCM、WMS、QMS、Finance，不写 localStorage，不自动修复风险。</p>
        <p class="finance-current-module-badge">当前操作模块：P2P业务链追踪</p>
      </section>
      <nav class="page-tabs finance-flow-nav" aria-label="P2P追踪导航">
        <router-link class="finance-nav-button" to="/finance/p2p-validation-center">返回P2P验证中心</router-link>
        <router-link class="finance-nav-button" to="/finance/formal-payment-vouchers">正式付款凭证</router-link>
      </nav>
    </header>

    <section class="operation-shell">
      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>风险事件定位</h2>
              <span>{{ traceSummary }}</span>
            </div>
            <el-tag :type="riskLevelType">{{ trace.riskLevel || '待确认' }}</el-tag>
          </div>
        </template>
        <div class="overview-grid">
          <article>
            <span>风险事件</span>
            <strong>{{ trace.id }}</strong>
          </article>
          <article>
            <span>来源单据</span>
            <strong>{{ trace.sourceDocument || '未提供' }}</strong>
          </article>
          <article>
            <span>风险类型</span>
            <strong>{{ trace.riskType || '待确认' }}</strong>
          </article>
          <article>
            <span>断点位置</span>
            <strong>{{ trace.breakPoint || '未指定' }}</strong>
          </article>
        </div>
        <p class="boundary-note">定位原则：验证中心只发现问题并标记断点，人工确认后再判断是操作问题、测试数据问题、流程设计问题还是系统逻辑问题。</p>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>P2P业务链追踪模型</h2>
              <span>采购订单 -> 收货 -> 检验 -> 入库 -> 库存流水 -> 应付 -> 付款</span>
            </div>
            <el-tag type="info">只读定位</el-tag>
          </div>
        </template>
        <section class="trace-chain">
          <article
            v-for="node in traceNodes"
            :key="node.key"
            class="trace-node"
            :class="{ 'trace-node-break': node.isBreakPoint }"
          >
            <div class="node-title">
              <strong>{{ node.title }}</strong>
              <el-tag :type="node.tagType">{{ node.status }}</el-tag>
            </div>
            <p>{{ node.documentNo || '未提供来源号' }}</p>
            <small>{{ node.description }}</small>
          </article>
        </section>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>风险断点说明</h2>
              <span>用于人工核对 PO2026070314534951、PO2026070605510641 等重点订单的链路位置。</span>
            </div>
            <el-tag :type="trace.breakPoint ? 'warning' : 'info'">{{ trace.breakPoint ? '已标记断点' : '待确认断点' }}</el-tag>
          </div>
        </template>
        <div class="detail-grid">
          <article>
            <span>断点节点</span>
            <strong>{{ breakNodeTitle }}</strong>
          </article>
          <article>
            <span>入库完成判断</span>
            <strong>{{ inventoryDecisionText }}</strong>
          </article>
          <article>
            <span>命中规则</span>
            <strong>{{ trace.inventoryRuleMatch || '待确认' }}</strong>
          </article>
          <article>
            <span>追踪来源</span>
            <strong>{{ traceResolverText }}</strong>
          </article>
          <article>
            <span>风险描述</span>
            <strong>{{ trace.riskDescription || '风险描述待从验证中心确认' }}</strong>
          </article>
          <article>
            <span>保护边界</span>
            <strong>只读定位，不创建数据，不自动修复，不写总账</strong>
          </article>
        </div>
      </el-card>
    </section>
  </main>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { resolveP2PTraceNodeStatuses } from './p2pTraceResolver.js'

const route = useRoute()

function queryText(key) {
  const value = route.query[key]
  if (Array.isArray(value)) return value[0] || ''
  return value || ''
}

function parseQueryJson(key) {
  const text = queryText(key)
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    return null
  }
}

const trace = computed(() => ({
  id: route.params.id || 'unknown',
  sourceDocument: queryText('sourceDocument') || queryText('purchaseOrder'),
  riskType: queryText('riskType'),
  riskLevel: queryText('riskLevel'),
  sourceModule: queryText('sourceModule'),
  breakPoint: queryText('breakPoint'),
  riskDescription: queryText('riskDescription'),
  riskEvidence: parseQueryJson('riskEvidence'),
  inventoryRuleMatch: queryText('inventoryRuleMatch'),
  inventoryChainDecision: parseQueryJson('inventoryChainDecision'),
  traceResolverEvidence: parseQueryJson('traceResolverEvidence'),
  p2pNodeStatuses: parseQueryJson('p2pNodeStatuses') || [],
  purchaseOrder: queryText('purchaseOrder') || queryText('sourceDocument'),
  receipt: queryText('receipt'),
  inspection: queryText('inspection'),
  warehouseEntry: queryText('warehouseEntry'),
  inventoryTransaction: queryText('inventoryTransaction'),
}))

const inventoryDecisionPassed = computed(() => trace.value.inventoryChainDecision?.status === 'passed')

const inventoryDecisionText = computed(() => {
  const decision = trace.value.inventoryChainDecision
  if (!decision) return '未提供库存链判断依据'
  return decision.reason || decision.status || '待确认'
})

const traceResolverText = computed(() => {
  const evidence = trace.value.traceResolverEvidence
  if (!evidence) return '未提供统一追踪解析依据'
  const nos = (evidence.matchedInventoryTransaction || []).join('、') || '未命中库存流水'
  return `${evidence.source || 'missing'} / ${evidence.sourceNo || '无来源号'} / ${nos}`
})

const traceSummary = computed(() => {
  const source = trace.value.sourceDocument || '未提供来源单据'
  const breakPoint = trace.value.breakPoint || '待确认断点'
  return `${source} 当前定位到：${breakPoint}`
})

const riskLevelType = computed(() => {
  const text = `${trace.value.riskLevel || ''} ${trace.value.riskType || ''}`
  if (text.includes('严重') || text.includes('critical') || text.includes('断裂')) return 'danger'
  if (text.includes('提醒') || text.includes('warning') || text.includes('异常')) return 'warning'
  return 'info'
})

function resolveBreakNodeKey() {
  const text = `${trace.value.riskType || ''} ${trace.value.breakPoint || ''} ${trace.value.riskDescription || ''}`
  if (inventoryDecisionPassed.value && (text.includes('入库') || text.includes('库存'))) return ''
  if (text.includes('采购')) return 'purchaseOrder'
  if (text.includes('收货')) return 'receipt'
  if (text.includes('检验')) return 'inspection'
  if (text.includes('入库')) return 'warehouseEntry'
  if (text.includes('库存流水')) return 'inventoryTransaction'
  if (text.includes('库存')) return 'inventoryTransaction'
  if (text.includes('应付')) return 'payable'
  if (text.includes('付款') || text.includes('供应商')) return 'payment'
  return ''
}

const traceNodes = computed(() => {
  const breakKey = resolveBreakNodeKey()
  const statuses = Array.isArray(trace.value.p2pNodeStatuses) && trace.value.p2pNodeStatuses.length
    ? trace.value.p2pNodeStatuses
    : resolveP2PTraceNodeStatuses({
        purchaseOrderNo: trace.value.purchaseOrder,
        receiveNo: trace.value.receipt,
        inspectionNo: trace.value.inspection,
        warehouseEntryNo: trace.value.warehouseEntry,
        inventoryTransaction: trace.value.inventoryTransaction,
        payable: '',
        paymentVoucher: '',
      })
  return statuses.map((node) => {
    const isBreakPoint = node.node === breakKey && node.status !== 'normal'
    return {
      key: node.node,
      title: node.title,
      documentNo: node.sourceNo,
      isBreakPoint,
      status: node.statusText || node.status,
      tagType: node.tagType,
      description: node.evidence,
    }
  })
})

const breakNodeTitle = computed(() => {
  const breakKey = resolveBreakNodeKey()
  return traceNodes.value.find((node) => node.key === breakKey)?.title || trace.value.breakPoint || '待确认'
})
</script>

<style scoped>
.p2p-trace-page {
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

.page-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.finance-nav-button {
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  color: #374151;
  text-decoration: none;
  background: #fff;
}

.finance-current-module-badge,
.boundary-note {
  padding: 10px 12px;
  border-radius: 6px;
  background: #eff6ff;
  color: #1e40af;
}

.operation-shell {
  display: grid;
  gap: 16px;
  margin-top: 16px;
}

.overview-grid,
.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}

.overview-grid article,
.detail-grid article {
  padding: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: #fff;
}

.overview-grid span,
.detail-grid span {
  display: block;
  color: #6b7280;
  font-size: 13px;
}

.overview-grid strong,
.detail-grid strong {
  display: block;
  margin-top: 6px;
  overflow-wrap: anywhere;
}

.trace-chain {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 12px;
}

.trace-node {
  padding: 14px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
}

.trace-node-break {
  border-color: #f97316;
  background: #fff7ed;
}

.node-title {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: center;
}

.trace-node p {
  margin: 10px 0 6px;
  font-weight: 700;
  overflow-wrap: anywhere;
}

.trace-node small {
  color: #6b7280;
}
</style>
