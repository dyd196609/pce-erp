<template>
  <main class="reference-page">
    <header class="page-header">
      <section>
        <p class="eyebrow">V1.11.2 基础资料引用源标准化</p>
        <h1>{{ pageTitle }}</h1>
        <p>这些数据来自 V1.11.1 基础资料底座，不是独立数据；本页面只读展示引用源，不提供新增、编辑、删除。</p>
      </section>
      <nav class="page-tabs">
        <router-link to="/reference">数据引用中心</router-link>
        <router-link to="/reference/master-data">主数据引用</router-link>
        <router-link to="/reference/organization">组织人员引用</router-link>
        <router-link to="/reference/warehouse">仓库库位引用</router-link>
        <router-link to="/reference/production">生产资源引用</router-link>
        <router-link to="/reference/warning">预警引用</router-link>
        <router-link to="/reference/check">完整性检查</router-link>
        <router-link to="/foundation">返回基础资料</router-link>
      </nav>
    </header>

    <section v-if="route.path === '/reference'" class="operation-shell">
      <section class="panel primary-panel">
        <header>
          <div>
            <h2>后续模块引用关系</h2>
            <span>SCM / CRM / WMS / MRP / MPS / APS / MES / QMS / BI / KPI / FDM</span>
          </div>
          <button type="button" @click="router.push('/reference/check')">基础资料检查</button>
        </header>
        <div class="module-grid">
          <article v-for="module in integrationCards" :key="module.moduleId" class="module-card">
            <span>{{ module.moduleId.toUpperCase() }}</span>
            <strong>{{ module.moduleName }}</strong>
            <p>{{ module.description }}</p>
            <ul>
              <li v-for="item in module.references" :key="item">{{ referenceUsageLabels[item] || item }}</li>
            </ul>
          </article>
        </div>
      </section>
    </section>

    <section v-else-if="route.path === '/reference/check'" class="operation-shell">
      <section class="panel primary-panel">
        <header>
          <div>
            <h2>基础资料完整性检查</h2>
            <span>通过 / 警告 / 缺失</span>
          </div>
          <button type="button" @click="router.push('/foundation')">返回基础资料</button>
        </header>
        <div class="check-summary">
          <article><span>通过</span><strong>{{ checkSummary.passed }}</strong></article>
          <article><span>警告</span><strong>{{ checkSummary.warning }}</strong></article>
          <article><span>缺失</span><strong>{{ checkSummary.missing }}</strong></article>
        </div>
        <div class="table-card">
          <table>
            <thead>
              <tr>
                <th>检查项目</th>
                <th>检查结果</th>
                <th>问题说明</th>
                <th>建议处理页面</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in checkResults" :key="item.id">
                <td>{{ item.category }} / {{ item.name }}</td>
                <td><span :class="['status-pill', item.status]">{{ statusText(item.status) }}</span></td>
                <td>{{ item.message }}<br><small>{{ item.suggestion }}</small></td>
                <td>{{ item.route }}</td>
                <td><button type="button" @click="router.push(item.route)">跳转处理</button></td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </section>

    <section v-else class="operation-shell">
      <section class="panel primary-panel">
        <header>
          <div>
            <h2>{{ pageTitle }}</h2>
            <span>{{ pageDescription }}</span>
          </div>
          <button type="button" @click="router.push('/reference')">返回引用中心</button>
        </header>
        <EmptyState v-if="!currentRows.length" :target-route="emptyTargetRoute" />
        <div v-else class="table-card">
          <table>
            <thead>
              <tr>
                <th>编码</th>
                <th>名称</th>
                <th>类型</th>
                <th>状态</th>
                <th>来源模块</th>
                <th>可被哪些后续模块引用</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in currentRows" :key="row.id">
                <td>{{ row.code }}</td>
                <td>
                  <strong>{{ row.name }}</strong>
                  <small v-if="row.note">{{ row.note }}</small>
                </td>
                <td>{{ row.type }}</td>
                <td>{{ row.status }}</td>
                <td>{{ row.sourceModule }}</td>
                <td>{{ row.users }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </section>
  </main>
</template>

<script setup>
import { computed, defineComponent, h } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { runFoundationCheck } from '../manufacturing/manufacturingFoundationChecker.js'
import {
  getCodingRuleOptions,
  getCustomerOptions,
  getDataDictionaryOptions,
  getDepartmentOptions,
  getEmployeeOptions,
  getLocationOptions,
  getMaterialOptions,
  getPermissionPointOptions,
  getReferenceState,
  getRoleOptions,
  getShiftOptions,
  getSupplierOptions,
  getSystemParameterValue,
  getWarehouseOptions,
  getWarningRuleOptions,
  getWarningSubscriberOptions,
  getWorkCenterOptions,
} from '../manufacturing/manufacturingReferenceService.js'
import {
  formatReferenceUsers,
  getManufacturingIntegrationMap,
  referenceUsageLabels,
} from '../manufacturing/manufacturingIntegrationMap.js'

const route = useRoute()
const router = useRouter()
const foundation = computed(() => getReferenceState())
const checkResults = computed(() => runFoundationCheck())
const integrationCards = computed(() => Object.entries(getManufacturingIntegrationMap()).map(([moduleId, config]) => ({
  moduleId,
  ...config,
})))

const pageTitle = computed(() => ({
  '/reference': '数据引用中心',
  '/reference/master-data': '主数据引用源',
  '/reference/organization': '组织人员引用源',
  '/reference/warehouse': '仓库库位引用源',
  '/reference/production': '生产资源引用源',
  '/reference/warning': '预警引用源',
  '/reference/check': '基础资料完整性检查',
})[route.path] || '数据引用中心')

const pageDescription = computed(() => ({
  '/reference/master-data': '显示物料、客户、供应商、数据字典、编码规则、系统参数引用源。',
  '/reference/organization': '显示员工、部门、岗位/角色、技能、班次引用源。',
  '/reference/warehouse': '显示仓库、库位、仓库属性、是否纳入MRP、是否允许负库存。',
  '/reference/production': '显示工作中心、班次、人员技能、物料、生产参数引用源。',
  '/reference/warning': '显示预警规则、预警订阅人、预警等级、所属模块、启用状态。',
})[route.path] || '统一展示 V1.11.1 基础资料如何被后续制造业模块引用。')

const checkSummary = computed(() => checkResults.value.reduce((result, item) => ({
  ...result,
  [item.status]: result[item.status] + 1,
}), { passed: 0, warning: 0, missing: 0 }))

const currentRows = computed(() => {
  if (route.path === '/reference/master-data') return masterDataRows()
  if (route.path === '/reference/organization') return organizationRows()
  if (route.path === '/reference/warehouse') return warehouseRows()
  if (route.path === '/reference/production') return productionRows()
  if (route.path === '/reference/warning') return warningRows()
  return []
})

const emptyTargetRoute = computed(() => ({
  '/reference/master-data': '/foundation/erp/materials',
  '/reference/organization': '/foundation/pfm/employees',
  '/reference/warehouse': '/foundation/erp/warehouses',
  '/reference/production': '/foundation/erp/work-centers',
  '/reference/warning': '/foundation/warnings/rules',
})[route.path] || '/foundation')

const EmptyState = defineComponent({
  props: {
    targetRoute: { type: String, required: true },
  },
  setup(props) {
    return () => h('section', { class: 'empty-state' }, [
      h('h2', '暂无可引用数据'),
      h('p', '请先回到 V1.11.1 基础资料底座维护对应资料，再返回引用中心查看。'),
      h('a', { href: `#${props.targetRoute}` }, '前往基础资料维护'),
    ])
  },
})

function row(item, referenceKey, type, sourceModule, note = '') {
  return {
    id: `${referenceKey}-${item.id}`,
    code: item.code || item.employeeNo || item.key || item.id,
    name: item.name || item.userName || item.role || item.key || item.id,
    type,
    status: item.status || '启用',
    sourceModule,
    users: formatReferenceUsers(referenceKey),
    note,
  }
}

function masterDataRows() {
  return [
    ...getMaterialOptions().map((item) => row(item.raw, 'materials', '物料', 'ERP主数据', `安全库存：${item.raw.safetyStock ?? '-'}`)),
    ...getCustomerOptions().map((item) => row(item.raw, 'customers', '客户', 'ERP主数据', `信用：${item.raw.creditLimit || item.raw.creditLevel || '未配置'}`)),
    ...getSupplierOptions().map((item) => row(item.raw, 'suppliers', '供应商', 'ERP主数据', `交货周期：${item.raw.leadTime || item.raw.deliveryCycle || '未配置'}`)),
    ...getDataDictionaryOptions().map((item) => row(item.raw, 'dataDictionaries', '数据字典', 'ERP主数据', `字典值：${(item.values || []).join('、')}`)),
    ...getCodingRuleOptions().map((item) => row(item.raw, 'codingRules', '编码规则', 'ERP主数据', `前缀：${item.raw.prefix || '-'}`)),
    ...foundation.value.systemParameters.map((item) => row(item, 'systemParameters', '系统参数', 'ERP主数据', `参数值：${getSystemParameterValue(item.key) ?? '-'}`)),
  ]
}

function organizationRows() {
  return [
    ...getEmployeeOptions().map((item) => row(item.raw, 'employees', '员工', 'PFM人员档案', `岗位：${item.raw.role || '-'}`)),
    ...getDepartmentOptions().map((item) => row(item.raw, 'departments', '部门', 'PFM组织资料', `负责人：${item.raw.owner || '-'}`)),
    ...getRoleOptions().map((item) => row(item.raw, 'employees', '岗位/角色', 'PFM组织资料', `所属部门：${item.raw.department || '-'}`)),
    ...foundation.value.skills.map((item) => row(item, 'employees', '技能', 'PFM人员档案', `责任岗位：${item.ownerRole || '-'}`)),
    ...getShiftOptions().map((item) => row(item.raw, 'shifts', '班次', 'PFM人员档案', `${item.raw.startTime || '-'} - ${item.raw.endTime || '-'}`)),
  ]
}

function warehouseRows() {
  const warehouseRows = getWarehouseOptions().map((item) => row(
    item.raw,
    'warehouses',
    '仓库',
    'ERP主数据',
    `仓库属性：${item.raw.warehouseType || '普通仓'}；纳入MRP：${item.raw.includeInMrp ?? '是'}；允许负库存：${item.raw.allowNegativeStock ?? '否'}`
  ))
  const locationRows = getLocationOptions().map((item) => row(
    item.raw,
    'locations',
    '库位',
    'ERP主数据',
    `所属仓库：${item.warehouseName}`
  ))
  return [...warehouseRows, ...locationRows]
}

function productionRows() {
  return [
    ...getWorkCenterOptions().map((item) => row(item.raw, 'workCenters', '工作中心', 'ERP主数据', `产能：${item.raw.capacity || '-'}`)),
    ...getShiftOptions().map((item) => row(item.raw, 'shifts', '班次', 'PFM人员档案', `${item.raw.startTime || '-'} - ${item.raw.endTime || '-'}`)),
    ...foundation.value.skills.map((item) => row(item, 'employees', '人员技能', 'PFM人员档案', `等级：${item.level || '-'}`)),
    ...getMaterialOptions().map((item) => row(item.raw, 'materials', '物料', 'ERP主数据', `单位：${item.raw.unit || '-'}`)),
    ...foundation.value.systemParameters.map((item) => row(item, 'systemParameters', '生产参数', 'ERP主数据', `参数值：${item.value || '-'}`)),
  ]
}

function warningRows() {
  return [
    ...getWarningRuleOptions().map((item) => row(item.raw, 'warningRules', '预警规则', '预警引擎基础', `等级：${item.raw.level || '-'}；对象：${item.raw.target || '-'}`)),
    ...getWarningSubscriberOptions().map((item) => row(item.raw, 'warningRules', '预警订阅人', '预警引擎基础', `渠道：${item.raw.channel || '-'}；范围：${item.raw.scope || '-'}`)),
    ...getPermissionPointOptions().map((item) => row(item.raw, 'warningRules', '权限关联', '权限与日志', `动作：${item.raw.action || '-'}`)),
  ]
}

function statusText(status) {
  return {
    passed: '通过',
    warning: '警告',
    missing: '缺失',
  }[status] || status
}
</script>

<style scoped>
.reference-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 100%;
  padding: 22px;
  background: #f4f7fb;
  color: #172033;
}

.page-header,
.panel header {
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
.empty-state a,
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

.operation-shell {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.panel,
.module-card,
.check-summary article,
.empty-state {
  border: 1px solid #dce5f2;
  border-radius: 8px;
  background: #fff;
  padding: 16px;
}

.primary-panel {
  border-color: #bfdbfe;
}

.module-grid,
.check-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.module-card {
  background: #f8fafc;
}

.module-card span,
.panel header span,
.check-summary span {
  color: #64748b;
  font-size: 12px;
}

.module-card strong,
.check-summary strong {
  display: block;
  color: #101828;
  font-size: 18px;
}

.table-card {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  min-width: 900px;
}

th,
td {
  border-bottom: 1px solid #e2e8f0;
  padding: 10px;
  text-align: left;
  vertical-align: top;
}

th {
  background: #f8fafc;
  color: #334155;
}

td strong {
  display: block;
  color: #101828;
}

td small {
  display: block;
  margin-top: 4px;
  color: #64748b;
}

.status-pill {
  display: inline-flex;
  border-radius: 999px;
  padding: 4px 9px;
  font-weight: 700;
}

.status-pill.passed {
  background: #dcfce7;
  color: #166534;
}

.status-pill.warning {
  background: #fef3c7;
  color: #92400e;
}

.status-pill.missing {
  background: #fee2e2;
  color: #991b1b;
}

p,
li {
  color: #475467;
  line-height: 1.55;
}

@media (max-width: 1100px) {
  .module-grid,
  .check-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .page-header,
  .panel header {
    align-items: flex-start;
    flex-direction: column;
  }

  .module-grid,
  .check-summary {
    grid-template-columns: 1fr;
  }
}
</style>
