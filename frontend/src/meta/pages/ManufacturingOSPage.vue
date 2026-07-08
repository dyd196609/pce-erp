<template>
  <main class="manufacturing-page">
    <header class="page-header">
      <section>
        <p class="eyebrow">掌云智造模块蓝图</p>
        <h1>制造企业数字化集成平台</h1>
        <p>覆盖 ERP、CRM、SCM、WMS、MRP、MPS、APS、MES、QMS、BI、FDM、PFM、KPI 13 大核心模块。</p>
        <p class="app-current-module-badge">当前操作模块：{{ currentManufacturingModuleName }}</p>
      </section>
      <nav class="page-tabs app-module-nav-zone">
        <span class="app-nav-zone-title">制造平台模块导航</span>
        <router-link class="app-nav-button" :class="{ 'app-nav-button-active': isManufacturingNavActive('modules') }" to="/manufacturing/modules">
          13大核心模块
          <span v-if="isManufacturingNavActive('modules')" class="app-current-tag">当前</span>
        </router-link>
        <router-link class="app-nav-button" :class="{ 'app-nav-button-active': isManufacturingNavActive('plan') }" to="/manufacturing/plan">
          六期开发计划
          <span v-if="isManufacturingNavActive('plan')" class="app-current-tag">当前</span>
        </router-link>
        <router-link class="app-nav-button" to="/foundation">第一期基础资料</router-link>
        <router-link class="app-nav-button" to="/foundation/business-partners">业务伙伴档案</router-link>
        <router-link class="app-nav-button" to="/reference">数据引用中心</router-link>
        <router-link class="app-nav-button" to="/reference/check">基础资料检查</router-link>
        <router-link class="app-nav-button" to="/foundation/review-check">基础资料评审检查</router-link>
        <router-link class="app-nav-button" to="/foundation/import-records">基础资料导入记录</router-link>
        <router-link class="app-nav-button" to="/scm">SCM采购管理</router-link>
        <router-link class="app-nav-button" to="/wms">WMS库存管理</router-link>
        <router-link class="app-nav-button" to="/qms">QMS来料检验</router-link>
        <router-link class="app-nav-button" to="/process-center">返回企业操作系统</router-link>
      </nav>
    </header>

    <section v-if="isModuleDetail" class="module-detail">
      <section class="panel primary-panel">
        <header>
          <div>
            <h2>{{ selectedModule?.name || '模块不存在' }}</h2>
            <span>{{ selectedModule?.shortName }} / {{ selectedModule?.englishName }}</span>
          </div>
          <button type="button" @click="router.push('/manufacturing/modules')">返回模块总览</button>
        </header>
        <div v-if="selectedModule" class="detail-grid">
          <article>
            <span>模块定位</span>
            <strong>{{ selectedModule.position }}</strong>
            <p>当前状态：{{ statusLabel(selectedModule.status) }} / 开发阶段：{{ selectedModule.phase }}</p>
          </article>
          <article>
            <span>子模块数量</span>
            <strong>{{ selectedModule.subModules.length }} 个</strong>
            <p>{{ selectedModule.subModules.slice(0, 4).join(' / ') }}</p>
          </article>
          <article>
            <span>核心数据</span>
            <strong>{{ selectedModule.coreData.length }} 类</strong>
            <p>{{ selectedModule.coreData.join(' / ') }}</p>
          </article>
          <article>
            <span>关键预警点</span>
            <strong>{{ selectedModule.warningPoints.length }} 个</strong>
            <p>{{ selectedModule.warningPoints.join(' / ') }}</p>
          </article>
        </div>
      </section>

      <section v-if="selectedModule" class="three-column">
        <section class="panel">
          <h2>子模块清单</h2>
          <ul>
            <li v-for="item in selectedModule.subModules" :key="item">{{ item }}</li>
          </ul>
        </section>
        <section class="panel">
          <h2>核心数据模型预留</h2>
          <ul>
            <li v-for="item in selectedModule.coreData" :key="item">{{ item }}</li>
          </ul>
        </section>
        <section class="panel">
          <h2>集成关系</h2>
          <ul>
            <li v-for="item in selectedModule.integrationWith" :key="item">{{ item }}</li>
          </ul>
        </section>
      </section>
    </section>

    <section v-else-if="isPlanPage" class="operation-shell">
      <section class="panel primary-panel">
        <header>
          <div>
            <h2>六期开发顺序</h2>
            <span>按《掌云智造软件需求文档》固化</span>
          </div>
        </header>
        <div class="phase-grid">
          <article v-for="phase in phases" :key="phase.phase" class="business-card">
            <span>{{ phase.phase }}</span>
            <strong>{{ phase.title }}</strong>
            <p>{{ phase.focus }}</p>
            <ul>
              <li v-for="item in phase.items" :key="item">{{ item }}</li>
            </ul>
          </article>
        </div>
      </section>
      <section class="panel">
        <h2>模块集成主线</h2>
        <ol class="flow-list">
          <li v-for="item in integrationFlow" :key="item">{{ item }}</li>
        </ol>
      </section>
    </section>

    <section v-else class="operation-shell">
      <section class="panel primary-panel">
        <header>
          <div>
            <h2>制造业 13 大核心模块</h2>
            <span>已注册 {{ summary.total }} 个模块，基础层 {{ summary.status.foundation }} 个，规划层 {{ summary.status.planning }} 个</span>
          </div>
          <div class="button-row">
            <button type="button" @click="router.push('/foundation')">进入第一期基础资料</button>
            <button type="button" @click="router.push('/foundation/business-partners')">业务伙伴档案</button>
            <button type="button" @click="router.push('/foundation/sample-data')">样例数据管理</button>
            <button type="button" @click="router.push('/foundation/erp/supplier-material-prices')">供应商物料价格</button>
            <button type="button" @click="router.push('/foundation/erp/material-suppliers')">物料供应商关系</button>
            <button type="button" @click="router.push('/foundation/manufacturing/processes')">工序资料</button>
            <button type="button" @click="router.push('/foundation/manufacturing/routings')">工艺路线</button>
            <button type="button" @click="router.push('/foundation/manufacturing/equipment')">设备资料</button>
            <button type="button" @click="router.push('/reference')">数据引用中心</button>
            <button type="button" @click="router.push('/reference/check')">基础资料检查</button>
            <button type="button" @click="router.push('/foundation/review-check')">基础资料评审检查</button>
            <button type="button" @click="router.push('/foundation/import-records')">基础资料导入记录</button>
            <button type="button" @click="router.push('/scm')">SCM采购管理</button>
            <button type="button" @click="router.push('/scm/purchase-requests')">请购单</button>
            <button type="button" @click="router.push('/scm/purchase-inquiries')">询价单</button>
            <button type="button" @click="router.push('/scm/price-approvals')">核价单</button>
            <button type="button" @click="router.push('/scm/purchase-orders')">采购单</button>
            <button type="button" @click="router.push('/wms')">WMS库存管理</button>
            <button type="button" @click="router.push('/wms/inventory-balances')">库存余额</button>
            <button type="button" @click="router.push('/wms/inventory-transactions')">库存流水</button>
            <button type="button" @click="router.push('/wms/warehouse-tasks')">仓库任务</button>
            <button type="button" @click="router.push('/wms/stock-warnings')">库存预警</button>
            <button type="button" @click="router.push('/wms/purchase-receive-preview')">采购到货预备</button>
            <button type="button" @click="router.push('/wms/purchase-receives')">采购收货预备</button>
            <button type="button" @click="router.push('/qms')">QMS来料检验预备</button>
            <button type="button" @click="router.push('/finance/payable-prepares')">采购应付预备</button>
            <button type="button" @click="router.push('/finance/ap-drafts')">采购应付账款草稿</button>
            <button type="button" @click="router.push('/manufacturing/plan')">查看开发计划</button>
          </div>
        </header>
        <p class="platform-note">
          当前软件定位为制造企业数字化集成平台。V1.10.x 已完成企业操作系统基础能力，V1.11.0 开始进入制造业完整模块蓝图接入阶段。
        </p>
      </section>

      <section class="module-grid">
        <article
          v-for="module in modules"
          :key="module.id"
          class="module-card"
          @click="router.push(`/manufacturing/module/${module.id}`)"
        >
          <header>
            <span>{{ module.shortName }}</span>
            <strong>{{ module.name }}</strong>
          </header>
          <p>{{ module.position }}</p>
          <dl>
            <div>
              <dt>开发阶段</dt>
              <dd>{{ module.phase }}</dd>
            </div>
            <div>
              <dt>当前状态</dt>
              <dd>{{ statusLabel(module.status) }}</dd>
            </div>
            <div>
              <dt>子模块</dt>
              <dd>{{ module.subModules.length }} 个</dd>
            </div>
            <div>
              <dt>预警点</dt>
              <dd>{{ module.warningPoints.length }} 个</dd>
            </div>
          </dl>
          <button type="button" @click.stop="router.push(`/manufacturing/module/${module.id}`)">进入模块详情</button>
        </article>
      </section>
    </section>
  </main>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  getManufacturingModuleById,
  getManufacturingModuleSummary,
  getManufacturingModules,
} from '../manufacturing/manufacturingModuleRegistry.js'
import {
  getManufacturingDevelopmentPhases,
  getManufacturingIntegrationFlow,
} from '../manufacturing/manufacturingDevelopmentPlan.js'

const route = useRoute()
const router = useRouter()
const modules = computed(() => getManufacturingModules())
const summary = computed(() => getManufacturingModuleSummary())
const phases = computed(() => getManufacturingDevelopmentPhases())
const integrationFlow = computed(() => getManufacturingIntegrationFlow())
const selectedModule = computed(() => getManufacturingModuleById(route.params.moduleId))
const isModuleDetail = computed(() => route.path.startsWith('/manufacturing/module/'))
const isPlanPage = computed(() => route.path === '/manufacturing/plan')
const currentManufacturingModuleName = computed(() => {
  if (selectedModule.value) return selectedModule.value.name
  if (isPlanPage.value) return '六期开发计划'
  return '13大核心模块'
})

function isManufacturingNavActive(type) {
  if (type === 'plan') return isPlanPage.value
  return route.path === '/manufacturing/modules' || isModuleDetail.value
}

function statusLabel(status) {
  return {
    planning: '规划中',
    foundation: '基础接入',
    developing: '开发中',
    ready: '可交付',
  }[status] || status
}
</script>

<style scoped>
.manufacturing-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 100%;
  padding: 22px;
  background: #f4f7fb;
  color: #172033;
}

.page-header,
.panel header,
.module-card header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
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

.page-tabs,
.button-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.page-tabs a,
button {
  border: 1px solid #bfdbfe;
  border-radius: 6px;
  padding: 7px 12px;
  background: #eff6ff;
  color: #1d4ed8;
  font-weight: 700;
  text-decoration: none;
  cursor: pointer;
}

button {
  border-color: #0f766e;
  background: #f0fdfa;
  color: #0f766e;
}

.operation-shell,
.module-detail {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.panel,
.module-card {
  border: 1px solid #dce5f2;
  border-radius: 8px;
  background: #fff;
  padding: 16px;
}

.primary-panel {
  border-color: #bfdbfe;
}

.platform-note {
  max-width: 980px;
  color: #475467;
  line-height: 1.6;
}

.module-grid,
.phase-grid,
.detail-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.three-column {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.business-card,
.detail-grid article {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
  padding: 12px;
}

.module-card {
  cursor: pointer;
}

.module-card:hover {
  border-color: #0f766e;
}

.module-card span,
.detail-grid span {
  color: #64748b;
  font-size: 12px;
}

.module-card strong,
.detail-grid strong {
  display: block;
  color: #101828;
  font-size: 18px;
}

dl {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

dt {
  color: #64748b;
  font-size: 12px;
}

dd {
  margin: 0;
  font-weight: 700;
}

li {
  margin-bottom: 6px;
  line-height: 1.5;
}

.flow-list {
  columns: 2;
}

@media (max-width: 1100px) {
  .module-grid,
  .phase-grid,
  .detail-grid,
  .three-column {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .page-header,
  .panel header,
  .module-card header {
    align-items: flex-start;
    flex-direction: column;
  }

  .module-grid,
  .phase-grid,
  .detail-grid,
  .three-column {
    grid-template-columns: 1fr;
  }

  .flow-list {
    columns: 1;
  }
}
</style>
