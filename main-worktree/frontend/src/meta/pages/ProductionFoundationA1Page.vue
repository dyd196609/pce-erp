<template>
  <main class="a1-page" data-page-code="pce-production-a1" data-fact-source="server">
    <header class="a1-header">
      <div>
        <p>Production Foundation Gate</p>
        <h1>A1 / A1.5 / A1.7 生产基础 Gate</h1>
        <span>本页只回读服务端正式事实；不会读取或写入 manufacturing-foundation-state-v1。</span>
      </div>
      <button type="button" @click="load">刷新服务端事实</button>
    </header>

    <section class="gate-card" :data-load-status="loadStatus">
      <article><small>Gate</small><strong>{{ facts.gate || 'PCE-PRODUCTION-A1-V1.0' }}</strong></article>
      <article><small>事实来源</small><strong>{{ facts.factSource || '-' }}</strong></article>
      <article><small>localStorage正式事实</small><strong>{{ facts.legacyLocalStorageFormalFactCount ?? '-' }}</strong></article>
      <article><small>当前阶段</small><strong>A1.7（A2 未进入）</strong></article>
      <article><small>当前验收结果</small><strong>{{ facts.result || '-' }}</strong></article>
    </section>

    <section class="object-card">
      <h2>GATE-INDUSTRY-DATA-01（20项）</h2>
      <table>
        <thead><tr><th>序号</th><th>核验项</th><th>状态</th><th>正式证据</th></tr></thead>
        <tbody>
          <tr v-for="item in facts.industryDataEntryGate || []" :key="item.id">
            <td>{{ item.id }}</td><td>{{ item.subject }}</td><td>{{ item.status }}</td><td>{{ item.evidence }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <section class="object-card">
      <h2>Gate 分层语义</h2>
      <table>
        <thead><tr><th>维度</th><th>状态</th><th>说明</th></tr></thead>
        <tbody>
          <tr v-for="item in gateRows" :key="item.key">
            <td>{{ item.label }}</td><td>{{ item.status }}</td><td>{{ item.reason }}</td>
          </tr>
        </tbody>
      </table>
      <p><strong>A1整体：</strong>{{ facts.a1Status || '-' }}；<strong>A2：</strong>{{ facts.a2Status || 'NOT_ENTERED' }}</p>
    </section>

    <section class="object-card">
      <h2>A1 对象回读</h2>
      <table>
        <thead><tr><th>正式对象</th><th>服务端记录数</th><th>权威来源</th></tr></thead>
        <tbody>
          <tr v-for="item in objectRows" :key="item.key">
            <td>{{ item.label }}</td>
            <td>{{ item.count }}</td>
            <td>Django ORM / Formal Service API</td>
          </tr>
        </tbody>
      </table>
      <p v-if="error" class="error">{{ error }}</p>
      <p v-if="facts.missingTables?.length" class="error">
        待应用 Migration 表：{{ facts.missingTables.join('、') }}
      </p>
      <p v-if="facts.migrationGraphError" class="error">
        Migration 图错误：{{ facts.migrationGraphError }}
      </p>
    </section>

    <section class="object-card calculation-trace" data-fact-source="server">
      <h2>Engineering Calculation Trace / 工程计算追踪</h2>
      <p>只读展示正式计算、输入快照、规则执行顺序、逐步明细、派生事实和错误状态；结果不在前端重算。</p>
      <table>
        <thead><tr><th>计算编号</th><th>Scope</th><th>修订</th><th>规则集</th><th>状态</th><th>明细</th><th>派生事实</th><th>错误</th><th>追踪</th></tr></thead>
        <tbody>
          <tr v-for="row in calculations" :key="row.id">
            <td>{{ row.calculationNo }}</td><td>{{ row.scope }}</td><td>{{ row.revision }}</td>
            <td>{{ row.ruleSetVersion }}</td><td>{{ row.status }}</td>
            <td>{{ row.details?.length || 0 }}</td><td>{{ row.derivedFacts?.length || 0 }}</td>
            <td>{{ row.errorCode || '-' }}</td>
            <td><button type="button" class="secondary" @click="showCalculation(row.id)">逐字段回读</button></td>
          </tr>
          <tr v-if="!calculations.length"><td colspan="9">暂无正式工程计算记录</td></tr>
        </tbody>
      </table>
      <div class="golden-action">
        <button type="button" :disabled="executing || !goldenExecution" @click="executeGolden">
          {{ executing ? '执行中…' : '执行已发布Golden验证' }}
        </button>
        <span>{{ goldenExecution ? `来源 ${goldenExecution.source.source_no} · ${goldenExecution.rules.length} 条规则` : '暂无可执行的已确认Golden来源与已发布规则' }}</span>
      </div>
      <article v-if="selectedCalculation" class="trace-detail" data-fact-source="server">
        <header><h3>{{ selectedCalculation.calculationNo }} 逐字段服务端追踪</h3><button type="button" class="secondary" @click="selectedCalculation = null">关闭</button></header>
        <p><strong>输入快照：</strong><code>{{ JSON.stringify(selectedCalculation.trace?.canonicalInputSnapshot || {}) }}</code></p>
        <table>
          <thead><tr><th>顺序</th><th>规则/版本</th><th>表达式</th><th>输入</th><th>输出</th><th>单位</th><th>状态</th></tr></thead>
          <tbody><tr v-for="row in selectedCalculation.details || []" :key="row.id"><td>{{ row.sequence }}</td><td>{{ row.ruleCode }} / {{ row.ruleVersion }}</td><td>{{ row.expressionSnapshot }}</td><td><code>{{ JSON.stringify(row.inputSnapshot) }}</code></td><td>{{ row.outputValue?.decimal ?? '-' }}</td><td>{{ row.uomCode || '-' }}</td><td>{{ row.status }}</td></tr></tbody>
        </table>
        <h4>Golden Comparison（仅比较，不参与输入）</h4>
        <table>
          <thead><tr><th>字段</th><th>预期</th><th>实际</th><th>差值</th><th>单位</th><th>来源单元格</th><th>结果</th></tr></thead>
          <tbody><tr v-for="row in selectedCalculation.trace?.goldenComparison?.rows || []" :key="row.canonicalField"><td>{{ row.canonicalField }}</td><td>{{ row.expectedValue }}</td><td>{{ row.actualValue }}</td><td>{{ row.difference }}</td><td>{{ row.actualUnit }}</td><td>{{ row.sourceCell }}</td><td>{{ row.result }}</td></tr></tbody>
        </table>
        <p><strong>Golden总结果：</strong>{{ selectedCalculation.trace?.goldenComparison?.result || '-' }}；<strong>预期值作为输入：</strong>{{ selectedCalculation.trace?.goldenComparison?.expectedResultsUsedAsInputs ? '是' : '否' }}</p>
      </article>
      <p v-if="traceError" class="error">{{ traceError }}</p>
      <small>事实来源：server；localStorage正式事实：0</small>
    </section>

    <section class="boundary-card">
      <h2>A1 边界保护</h2>
      <p>未创建行业样例；未运行 MPS、MRP、ProductionPlan、ProductionOrder、WorkOrder；未执行领料、报工或库存动作。</p>
    </section>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { pdeApi } from '@/api/pde.js'

const facts = ref({})
const loadStatus = ref('idle')
const error = ref('')
const calculations = ref([])
const traceError = ref('')
const selectedCalculation = ref(null)
const executing = ref(false)
const labels = Object.freeze({
  units: 'UnitOfMeasure',
  materials: 'Material',
  'product-categories': 'ProductCategory',
  products: 'Product',
  'product-versions': 'ProductVersion',
  'work-centers': 'WorkCenter',
  operations: 'Operation（system.Process）',
  equipment: 'Equipment',
  'standard-capacities': 'StandardCapacity',
  boms: 'BOM',
  'bom-versions': 'BOMVersion',
  'bom-items': 'BOMItem',
  'bom-substitutes': 'BOMItemSubstitute',
  routings: 'Routing',
  'routing-versions': 'RoutingVersion',
  'routing-steps': 'RoutingStep',
  'engineering-document-versions': 'EngineeringDocumentVersion',
  'engineering-documents': 'EngineeringDocument',
  'manufacturing-outputs': 'ProductManufacturingOutput',
  'engineering-readiness': 'ProductEngineeringReadiness',
  'manufacturing-input-references': 'ManufacturingInputReference',
  'engineering-source-records': 'EngineeringSourceRecord',
  'engineering-rule-definitions': 'EngineeringRuleDefinition',
  'order-engineering-instances': 'OrderEngineeringInstance',
  'engineering-calculation-records': 'EngineeringCalculationRecord',
  'engineering-breakdown-items': 'EngineeringBreakdownItem',
  'engineering-derived-facts': 'EngineeringDerivedFact',
  'warehouse-locations': 'WarehouseLocation',
  'inventory-lots': 'InventoryLot / Batch',
})
const objectRows = computed(() => Object.entries(labels).map(([key, label]) => ({
  key,
  label,
  count: facts.value.recordCounts?.[key] ?? 0,
})))
const gateLabels = {
  structure: 'STRUCTURE', data: 'DATA', authorization: 'AUTHORIZATION',
  integration: 'INTEGRATION', industryData: 'INDUSTRY DATA READY',
}
const gateRows = computed(() => Object.entries(gateLabels).map(([key, label]) => ({
  key, label, status: facts.value.gateDimensions?.[key]?.status || '-',
  reason: facts.value.gateDimensions?.[key]?.reason || '',
})))
function requireSuccess(response) {
  if (response?.success === false) throw new Error(response?.error?.message || '正式服务请求失败')
  return response?.data ?? response
}
const goldenExecution = computed(() => {
  const sources = facts.value.facts?.['engineering-source-records'] || []
  const rules = facts.value.facts?.['engineering-rule-definitions'] || []
  const source = sources.find((row) => row.status === 'confirmed' && row.source_payload?.validationClass === 'GOLDEN')
  if (!source) return null
  const packageCode = source.source_payload?.goldenValidation?.rulePackageCode
  const released = rules.filter((row) => row.status === 'released' && (!packageCode || row.specification?.rulePackage?.code === packageCode))
  return released.length ? { source, rules: released } : null
})

async function showCalculation(id) {
  traceError.value = ''
  try {
    const result = requireSuccess(await pdeApi.engineeringCalculation(id))
    selectedCalculation.value = result?.calculation || result
  } catch (exception) {
    traceError.value = exception?.response?.data?.message || '工程计算逐字段追踪读取失败'
  }
}

async function executeGolden() {
  if (!goldenExecution.value) return
  executing.value = true
  traceError.value = ''
  try {
    const result = requireSuccess(await pdeApi.executeEngineeringCalculation({
      scope: 'validation',
      sourceRecordId: goldenExecution.value.source.id,
      ruleIds: goldenExecution.value.rules.map((row) => row.id),
      reason: 'A1.8 DO-4 G1真实Golden Case正式执行',
    })) || {}
    await load()
    if (result.calculation?.id) await showCalculation(result.calculation.id)
  } catch (exception) {
    traceError.value = exception?.response?.data?.message || 'Golden验证正式执行失败'
  } finally {
    executing.value = false
  }
}

async function load() {
  loadStatus.value = 'loading'
  error.value = ''
  try {
    const response = await pdeApi.productionFoundationA1()
    facts.value = requireSuccess(response) || {}
    try {
      const traceResponse = await pdeApi.engineeringCalculations()
      const traceFacts = requireSuccess(traceResponse) || {}
      calculations.value = traceFacts.rows || []
      traceError.value = ''
    } catch (traceException) {
      calculations.value = []
      traceError.value = traceException?.response?.data?.message || '工程计算追踪读取失败'
    }
    loadStatus.value = 'loaded'
  } catch (exception) {
    facts.value = {}
    loadStatus.value = 'failed'
    error.value = exception?.response?.data?.message || 'A1服务端事实读取失败'
  }
}

onMounted(load)
</script>

<style scoped>
.a1-page { display:grid; gap:18px; padding:22px; background:#f4f7fb; color:#182235; }
.a1-header,.gate-card,.object-card,.boundary-card { background:#fff; border:1px solid #dce4ef; border-radius:14px; padding:20px; }
.a1-header { display:flex; justify-content:space-between; gap:20px; align-items:center; }
.a1-header p { color:#3568dc; font-weight:700; margin:0; }
.a1-header h1 { margin:6px 0; }
button { border:1px solid #3568dc; background:#3568dc; color:#fff; border-radius:8px; padding:10px 16px; cursor:pointer; }
button.secondary { background:#fff; color:#3568dc; padding:6px 10px; }
button:disabled { opacity:.55; cursor:not-allowed; }
.golden-action { display:flex; align-items:center; gap:12px; margin-top:14px; }
.trace-detail { border:1px solid #cdd9ea; border-radius:10px; padding:14px; margin-top:14px; background:#f9fbfe; overflow:auto; }
.trace-detail header { display:flex; justify-content:space-between; align-items:center; }
.trace-detail code { white-space:normal; overflow-wrap:anywhere; }
.gate-card { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; }
.gate-card article { background:#f5f8fd; border-radius:10px; padding:14px; }
.gate-card small,.gate-card strong { display:block; }
.gate-card strong { margin-top:8px; }
table { width:100%; border-collapse:collapse; }
th,td { padding:11px 12px; border-bottom:1px solid #e5eaf2; text-align:left; }
.error { color:#b42318; }
@media (max-width:900px) { .gate-card { grid-template-columns:1fr 1fr; } }
</style>
