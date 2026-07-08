<template>
  <main class="profit-dashboard">
    <header class="topbar">
      <section>
        <p class="eyebrow">ProfitOS Production Validation</p>
        <h1>ProfitOS Dashboard</h1>
      </section>

      <section class="switcher" aria-label="System switch">
        <el-radio-group v-model="activeView" size="large">
          <el-radio-button label="ERP">ERP View</el-radio-button>
          <el-radio-button label="ProfitOS">ProfitOS View</el-radio-button>
        </el-radio-group>
      </section>
    </header>

    <nav class="navline">
      <router-link to="/purchase/order/412">Purchase Order 412</router-link>
      <router-link to="/purchase/order">Purchase Orders</router-link>
      <router-link to="/control-tower">Control Tower</router-link>
    </nav>

    <section class="kpi-grid">
      <article class="metric-panel">
        <p>Profit KPI</p>
        <strong>{{ formatCurrency(profitDecision.profit.profit) }}</strong>
        <span>{{ formatPercent(profitDecision.profit.margin) }} margin</span>
      </article>

      <article class="metric-panel">
        <p>Order Profit Summary</p>
        <strong>{{ profitDecision.decision }}</strong>
        <span>Order {{ profitDecision.orderId || 'A001' }}</span>
      </article>

      <article class="metric-panel">
        <p>System Health</p>
        <strong>{{ health.errorCount === 0 ? 'HEALTHY' : 'ATTENTION' }}</strong>
        <span>{{ health.totalEvents }} runtime events</span>
      </article>

      <article class="metric-panel">
        <p>Agent Execution</p>
        <strong>{{ agentStatus }}</strong>
        <span>{{ agentTasks }} planned tasks</span>
      </article>
    </section>

    <section class="content-grid">
      <article class="panel order-panel">
        <header>
          <h2>Order Profit Summary</h2>
          <el-tag :type="profitDecision.decision === 'EXPAND' ? 'success' : 'warning'">
            {{ profitDecision.decision }}
          </el-tag>
        </header>

        <div class="summary-row">
          <span>Revenue</span>
          <b>{{ formatCurrency(order.revenue) }}</b>
        </div>
        <div class="summary-row">
          <span>Material Cost</span>
          <b>{{ formatCurrency(order.materialCost) }}</b>
        </div>
        <div class="summary-row">
          <span>Labor Cost</span>
          <b>{{ formatCurrency(order.laborCost) }}</b>
        </div>
        <div class="summary-row">
          <span>Overhead</span>
          <b>{{ formatCurrency(order.overhead) }}</b>
        </div>
      </article>

      <article class="panel">
        <header>
          <h2>Customer Profit Ranking</h2>
        </header>

        <div v-for="customer in customerRanking" :key="customer.name" class="ranking-row">
          <span>{{ customer.name }}</span>
          <div class="bar-track">
            <div class="bar-fill" :style="{ width: customer.width }" />
          </div>
          <b>{{ formatCurrency(customer.profit) }}</b>
        </div>
      </article>

      <article class="panel">
        <header>
          <h2>{{ activeView }} Status</h2>
        </header>

        <div v-if="activeView === 'ERP'" class="status-stack">
          <div class="status-item">
            <span>Current Module</span>
            <b>Purchase Order Detail</b>
          </div>
          <div class="status-item">
            <span>Module Link</span>
            <router-link to="/purchase/order/412">Open /purchase/order/412</router-link>
          </div>
          <div class="status-item">
            <span>Execution Layer</span>
            <b>PalmCloud ERP</b>
          </div>
        </div>

        <div v-else class="status-stack">
          <div class="status-item">
            <span>Decision Layer</span>
            <b>{{ profitOSResult.mode }}</b>
          </div>
          <div class="status-item">
            <span>Tenant</span>
            <b>{{ profitOSResult.tenant }}</b>
          </div>
          <div class="status-item">
            <span>Architecture</span>
            <b>ProfitOS Production v1.0</b>
          </div>
        </div>
      </article>

      <article class="panel trace-panel">
        <header>
          <h2>Trace Panel</h2>
          <el-button size="small" type="primary" @click="runTrace">Run Trace</el-button>
        </header>

        <div class="trace-line">
          <code>window.__TRACE__.profitOS.run()</code>
          <span>{{ traceStatus.profitOS }}</span>
        </div>
        <div class="trace-line">
          <code>window.__TRACE__.system.health()</code>
          <span>{{ traceStatus.health }}</span>
        </div>

        <pre>{{ traceOutput }}</pre>
      </article>
    </section>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { runProfitOS } from '../profitOS.js'
import { getSystemHealth } from '../core/monitoringLayer.js'
import { getDemoCustomers, getDemoOrder, getProfitSession } from '../demo/demoMode.js'

const activeView = ref('ProfitOS')

const session = getProfitSession()
const order = getDemoOrder()

const profitOSResult = ref(runProfitOS(
  { goal: 'optimize procurement system' },
  {
    tenantId: session.tenantId,
    data: order,
  }
))

const health = ref(getSystemHealth())
const traceOutput = ref('')
const traceStatus = ref({
  profitOS: 'READY',
  health: 'READY',
})

const profitDecision = computed(() => profitOSResult.value.business.decision)
const agentTasks = computed(() => profitOSResult.value.agent.plan.tasks.length)
const agentStatus = computed(() => (
  profitOSResult.value.agent.execution.results.some((item) => item.status === 'BLOCKED')
    ? 'REVIEW'
    : 'READY'
))

const customerRanking = computed(() => getDemoCustomers())

function formatCurrency(value) {
  return `$${Number(value || 0).toLocaleString()}`
}

function formatPercent(value) {
  return `${Math.round(Number(value || 0) * 100)}%`
}

function runTrace() {
  const traceApi = window.__TRACE__
  const result = traceApi?.profitOS?.run
    ? traceApi.profitOS.run({ goal: 'optimize procurement system' }, { tenantId: session.tenantId, data: order })
    : runProfitOS({ goal: 'optimize procurement system' }, { tenantId: session.tenantId, data: order })

  const systemHealth = traceApi?.system?.health
    ? traceApi.system.health()
    : getSystemHealth()

  profitOSResult.value = result
  health.value = systemHealth
  traceStatus.value = {
    profitOS: result?.mode || 'UNAVAILABLE',
    health: systemHealth?.errorCount === 0 ? 'HEALTHY' : 'ATTENTION',
  }
  traceOutput.value = JSON.stringify({
    mode: result.mode,
    tenant: result.tenant,
    health: systemHealth,
  }, null, 2)
}

onMounted(runTrace)
</script>

<style scoped>
.profit-dashboard {
  min-height: 100vh;
  padding: 24px;
  background: #f4f7fb;
  color: #1f2937;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.eyebrow {
  margin: 0 0 4px;
  color: #64748b;
  font-size: 13px;
}

h1,
h2 {
  margin: 0;
}

h1 {
  font-size: 28px;
  line-height: 1.2;
}

h2 {
  font-size: 16px;
}

.navline {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 18px;
}

.navline a {
  color: #1559b7;
  text-decoration: none;
  font-weight: 600;
}

.kpi-grid,
.content-grid {
  display: grid;
  gap: 14px;
}

.kpi-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin-bottom: 14px;
}

.content-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.metric-panel,
.panel {
  background: #fff;
  border: 1px solid #dce5f2;
  border-radius: 8px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.metric-panel {
  min-height: 104px;
  padding: 16px;
}

.metric-panel p,
.metric-panel span {
  margin: 0;
  color: #64748b;
}

.metric-panel strong {
  display: block;
  margin: 8px 0 4px;
  font-size: 26px;
}

.panel {
  min-height: 260px;
  padding: 18px;
}

.panel header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.summary-row,
.status-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid #edf2f7;
}

.ranking-row {
  display: grid;
  grid-template-columns: 110px 1fr 80px;
  align-items: center;
  gap: 12px;
  padding: 11px 0;
}

.bar-track {
  height: 10px;
  background: #e5edf6;
  border-radius: 999px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  background: #2563eb;
}

.status-stack {
  display: grid;
  gap: 6px;
}

.trace-panel pre {
  max-height: 118px;
  overflow: auto;
  margin: 12px 0 0;
  padding: 12px;
  background: #0f172a;
  color: #e5edf6;
  border-radius: 6px;
  font-size: 12px;
}

.trace-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid #edf2f7;
}

code {
  color: #0f766e;
  white-space: nowrap;
}

@media (max-width: 900px) {
  .topbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .kpi-grid,
  .content-grid {
    grid-template-columns: 1fr;
  }

  .ranking-row {
    grid-template-columns: 96px 1fr 74px;
  }
}
</style>
