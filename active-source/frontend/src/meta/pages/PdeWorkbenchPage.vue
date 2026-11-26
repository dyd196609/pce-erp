<template>
  <main
    class="pde-workbench"
    data-acceptance-id="pde-product-engineering-workbench"
    data-page-module="PDE"
    data-page-version="V1.14.2.8.4.10.4"
    data-page-template="PceListPageShell"
    data-entry-level="primary"
    data-crm-source="true"
    data-purchase-order-generation="false"
    data-production-user-data-written="false"
  >
    <section class="workbench-card workbench-intro">
      <div>
        <span class="workbench-eyebrow">订单驱动研发</span>
        <h2>PDE产品工程工作台</h2>
        <p>订单驱动的产品研发与制造准备入口。客户订单归属CRM，PDE只承接工程需求。</p>
      </div>
      <router-link class="process-center-link" to="/process-center?module=PDE">返回PDE业务流程中心</router-link>
    </section>

    <section class="workbench-card" data-acceptance-id="pde-order-driven-chain">
      <header>
        <div>
          <h2>订单驱动研发链</h2>
          <p>CRM客户订单是唯一订单来源，PDE不建设销售订单能力。</p>
        </div>
        <span class="source-badge">来源：CRM</span>
      </header>
      <div class="relationship-chain">
        <template v-for="(step, index) in pdeWorkbenchRelationship.chain" :key="step">
          <strong>{{ step }}</strong>
          <span v-if="index < pdeWorkbenchRelationship.chain.length - 1" aria-hidden="true">→</span>
        </template>
      </div>
    </section>

    <section class="workbench-card" data-acceptance-id="pde-workbench-entry-grid">
      <header>
        <div>
          <h2>产品工程导航</h2>
          <p>原PDE页面全部保留，并由本工作台统一进入。</p>
        </div>
        <span class="source-badge">{{ pdeWorkbenchEntries.length }} 个工程入口</span>
      </header>
      <nav class="workbench-grid" aria-label="PDE产品工程导航">
        <router-link
          v-for="(entry, index) in pdeWorkbenchEntries"
          :key="entry.code"
          :to="entry.route"
          class="workbench-entry"
          :data-workbench-entry="entry.code"
        >
          <span>{{ String(index + 1).padStart(2, '0') }}</span>
          <strong>{{ entry.label }}</strong>
          <small>{{ entry.sourceModule === 'CRM' ? 'CRM订单来源' : 'PDE工程页面' }}</small>
        </router-link>
      </nav>
    </section>

    <section class="workbench-card" data-acceptance-id="pde-workbench-boundary-protection">
      <header>
        <div>
          <h2>业务边界保护</h2>
          <p>PDE只提供工程资料和制造输入，不执行采购、库存、付款或财务业务。</p>
        </div>
      </header>
      <div class="boundary-grid">
        <article><span>CAD / 三维设计</span><strong>禁止</strong></article>
        <article><span>PLM / PDM</span><strong>禁止</strong></article>
        <article><span>采购订单生成</span><strong>否</strong></article>
        <article><span>SCM采购依据</span><strong>只读</strong></article>
        <article><span>BOM物料所有权</span><strong>EMD</strong></article>
        <article><span>工艺工作中心所有权</span><strong>EMD</strong></article>
      </div>
    </section>
  </main>
</template>

<script setup>
import {
  pdeWorkbenchEntries as registeredPdeWorkbenchEntries,
  pdeWorkbenchRelationship,
} from '@/meta/process/pdeWorkbenchRegistry.js'

const pdeWorkbenchEntries = registeredPdeWorkbenchEntries.map(entry => (
  entry.code === 'engineering-readiness'
    ? Object.freeze({ ...entry, route: '/pde/engineering-calculations' })
    : entry
))
</script>

<style scoped>
.pde-workbench {
  display: grid;
  gap: 18px;
}

.workbench-card {
  padding: 22px;
  border: 1px solid #dce6f2;
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 8px 24px rgb(24 64 104 / 7%);
}

.workbench-card > header,
.workbench-intro {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}

.workbench-card h2 {
  margin: 0 0 8px;
  color: #173b63;
}

.workbench-card p {
  margin: 0;
  color: #60758a;
}

.workbench-eyebrow,
.source-badge {
  display: inline-flex;
  margin-bottom: 8px;
  color: #1769aa;
  font-size: 13px;
  font-weight: 700;
}

.process-center-link {
  padding: 10px 15px;
  border-radius: 9px;
  color: #fff;
  background: #1769aa;
  text-decoration: none;
  white-space: nowrap;
}

.relationship-chain {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-top: 18px;
}

.relationship-chain strong {
  padding: 9px 12px;
  border-radius: 8px;
  color: #174f7d;
  background: #eef6fd;
}

.workbench-grid,
.boundary-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
  margin-top: 18px;
}

.workbench-entry,
.boundary-grid article {
  display: grid;
  gap: 6px;
  min-height: 92px;
  padding: 15px;
  border: 1px solid #d9e6f2;
  border-radius: 10px;
  color: #173b63;
  background: #f8fbfe;
  text-decoration: none;
}

.workbench-entry:hover {
  border-color: #3b83bd;
  transform: translateY(-1px);
}

.workbench-entry span,
.workbench-entry small,
.boundary-grid span {
  color: #6f8295;
}

.boundary-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.boundary-grid article {
  min-height: auto;
}

@media (max-width: 1100px) {
  .workbench-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .boundary-grid { grid-template-columns: 1fr; }
}
</style>
