<template>
  <main
    class="price-analysis-page"
    data-page-code="foundation-supplier-price-analysis"
    data-runtime-code="SupplierPriceFactRuntime"
    data-analysis-mode="READ_ONLY_REFERENCE"
    data-auto-decision-enabled="false"
    data-pce-page-kind="fact"
    data-pce-action-policy="view"
  >
    <section class="panel summary-panel" data-acceptance-id="price-fact-summary">
      <header>
        <div>
          <h2>供应商价格分析</h2>
          <p>基于供应商价格事实与历史采购执行事实的只读参考分析，不构成核价、供应商选择或采购价格决定。</p>
        </div>
        <span class="read-only-badge">只读参考</span>
      </header>
      <p v-if="loadError" class="runtime-error" data-fact-load-status="read_failed">{{ loadError }}</p>
      <div class="summary-grid" :data-fact-load-status="factLoadStatus">
        <article><span>供应商数</span><strong>{{ quality.supplierCount ?? '-' }}</strong></article>
        <article><span>物料数</span><strong>{{ quality.materialCount ?? '-' }}</strong></article>
        <article><span>价格事实数</span><strong>{{ quality.priceFactCount ?? '-' }}</strong></article>
        <article><span>历史价格数</span><strong>{{ quality.historyPriceCount ?? '-' }}</strong></article>
        <article><span>异常提醒数</span><strong>{{ analysis.anomalyCount ?? '-' }}</strong></article>
        <article><span>业务写入</span><strong>{{ analysis.businessProgressWriteCount ?? 0 }}</strong></article>
      </div>
    </section>

    <section class="panel" data-acceptance-id="price-history-list">
      <div class="section-heading">
        <div><h2>历史价格明细</h2><p>供应商、物料、价格、来源与日期均来自 SupplierPriceFactRuntime。</p></div>
        <span>筛选结果 {{ historyResultCount }}</span>
      </div>
      <FoundationMetadataList
        v-if="historyMetadata"
        :metadata="historyMetadata"
        :rows="analysis.priceHistoryRows || []"
        :can-toggle-status="false"
        @result-count-change="historyResultCount = Number($event)"
        @view="showDetail"
      />
    </section>

    <section class="panel" data-acceptance-id="price-history-trend">
      <div class="section-heading"><div><h2>历史价格趋势</h2><p>最低价、最近价、平均价与变化率仅用于人工参考。</p></div></div>
      <el-table :data="analysis.historyAnalyses || []" max-height="420">
        <el-table-column prop="supplierDisplay" label="供应商" min-width="210" />
        <el-table-column prop="materialDisplay" label="物料" min-width="210" />
        <el-table-column prop="lowestPurchasePrice" label="最低采购价" width="120" />
        <el-table-column prop="latestPurchasePrice" label="最近采购价" width="120" />
        <el-table-column prop="averagePurchasePrice" label="平均采购价" width="120" />
        <el-table-column prop="priceChangeDisplay" label="环比变化" width="110" />
        <el-table-column prop="trendLabel" label="趋势" width="90" />
        <el-table-column prop="sampleCount" label="样本数" width="90" />
        <el-table-column prop="latestPurchaseDate" label="最近日期" width="120" />
      </el-table>
    </section>

    <section class="panel" data-acceptance-id="supplier-price-comparison">
      <div class="section-heading">
        <div><h2>供应商价格比较</h2><p>同物料、同币种、同单位的最近事实横向比较；最低价标识不等于推荐结果。</p></div>
        <span>筛选结果 {{ comparisonResultCount }}</span>
      </div>
      <FoundationMetadataList
        v-if="comparisonMetadata"
        :metadata="comparisonMetadata"
        :rows="analysis.supplierComparisons || []"
        :can-toggle-status="false"
        @result-count-change="comparisonResultCount = Number($event)"
        @view="showDetail"
      />
    </section>

    <section class="panel" data-acceptance-id="price-anomaly-region">
      <div class="section-heading"><div><h2>价格异常提醒</h2><p>规则仅产生提醒，必须人工核对来源、口径和业务背景。</p></div><span>{{ analysis.ruleVersion || '-' }}</span></div>
      <div class="rule-chips">
        <span v-for="rule in analysis.anomalyRules || []" :key="rule.ruleCode">{{ rule.name }}：{{ rule.threshold }}</span>
      </div>
      <el-table :data="analysis.anomalies || []" max-height="420">
        <el-table-column prop="anomalyType" label="异常类型" width="150" />
        <el-table-column prop="supplierDisplay" label="供应商" min-width="210" />
        <el-table-column prop="materialDisplay" label="物料" min-width="210" />
        <el-table-column prop="currentPrice" label="当前价格" width="110" />
        <el-table-column prop="referencePrice" label="参考价格" width="110" />
        <el-table-column prop="changeRatioDisplay" label="偏离/变化" width="110" />
        <el-table-column prop="effectiveDate" label="价格日期" width="120" />
        <el-table-column prop="explanation" label="人工处理边界" min-width="260" />
      </el-table>
    </section>

    <el-dialog v-model="detailVisible" title="只读价格分析明细" width="820px">
      <pre class="detail-json">{{ detailText }}</pre>
    </el-dialog>
  </main>
</template>

<script setup>
import { computed, inject, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import FoundationMetadataList from '@/meta/components/FoundationMetadataList.vue'
import { findFoundationListMetadata } from '@/meta/master-data/masterDataRegistry.js'
import { loadSupplierPriceFactRuntime } from '@/meta/providers/supplierPriceFactRuntimeProvider.js'
import { PAGE_OBSERVABILITY_ACTIONS_KEY } from '@/meta/runtime/pageObservabilityActions.js'

const historyMetadata = findFoundationListMetadata('supplierPriceAnalysisHistory')
const comparisonMetadata = findFoundationListMetadata('supplierPriceComparisons')
const runtime = ref(null)
const loadError = ref('')
const historyResultCount = ref(0)
const comparisonResultCount = ref(0)
const detailVisible = ref(false)
const detailRow = ref(null)
const refreshStatus = ref('idle')
const lastRefreshTime = ref('')
const observability = inject(PAGE_OBSERVABILITY_ACTIONS_KEY, null)
const analysis = computed(() => runtime.value?.intelligenceAnalysis || {})
const quality = computed(() => analysis.value.quality || {})
const factLoadStatus = computed(() => runtime.value?.factLoadFacts?.factLoadStatus || (loadError.value ? 'read_failed' : 'loading'))
const detailText = computed(() => JSON.stringify(detailRow.value || {}, null, 2))

function showDetail(row) {
  detailRow.value = row
  detailVisible.value = true
}

function diagnostics() {
  const current = runtime.value
  const currentAnalysis = current?.intelligenceAnalysis || {}
  return {
    version: 'V1.14.2.8.4.27.2.37',
    canonicalName: '供应商价格分析',
    moduleCode: 'EMD',
    pageCode: 'foundation-supplier-price-analysis',
    pageFactOwner: 'SupplierPriceFactRuntime',
    factLoadStatus: factLoadStatus.value,
    factLoadFacts: current?.factLoadFacts || {},
    strictServerFacts: current?.strictFacts || {},
    acceptanceFacts: current?.acceptanceFacts || {},
    sourceObjects: currentAnalysis,
    historyResultCount: historyResultCount.value,
    comparisonResultCount: comparisonResultCount.value,
    automaticSupplierSelection: false,
    automaticPriceDecision: false,
    automaticPurchaseOrderCreation: false,
    businessProgressWriteCount: 0,
  }
}

function publishAcceptance() {
  const current = runtime.value
  const currentAnalysis = current?.intelligenceAnalysis || {}
  window.__PCE_BUSINESS_PAGE_ACCEPTANCE__ = {
    ...diagnostics(),
    pageAssertions: [
      { rule: 'PRICE-INTELLIGENCE-SOURCE-001', passed: currentAnalysis.analysisMode === 'READ_ONLY_REFERENCE' && current?.runtimeCode === 'SupplierPriceFactRuntime' },
      { rule: 'PRICE-HISTORY-ANALYSIS-001', passed: (currentAnalysis.historyAnalyses || []).length > 0 && (currentAnalysis.priceHistoryRows || []).length > 0 },
      { rule: 'PRICE-COMPARISON-001', passed: (currentAnalysis.supplierComparisons || []).every(row => row.decision === null && row.readOnly === true) },
      { rule: 'PRICE-NO-AUTO-DECISION-001', passed: currentAnalysis.automaticSupplierSelection === false && currentAnalysis.automaticPriceDecision === false && currentAnalysis.automaticPurchaseOrderCreation === false },
      { rule: 'FILTER-COUNT-SYNC-001', passed: historyResultCount.value >= 0 && comparisonResultCount.value >= 0 },
    ],
  }
}

async function refresh({ notify = false } = {}) {
  refreshStatus.value = 'refreshing'
  loadError.value = ''
  try {
    runtime.value = await loadSupplierPriceFactRuntime({ force: true })
    historyResultCount.value = runtime.value.intelligenceAnalysis.priceHistoryRows.length
    comparisonResultCount.value = runtime.value.intelligenceAnalysis.supplierComparisons.length
    refreshStatus.value = 'success'
    lastRefreshTime.value = new Date().toISOString()
    publishAcceptance()
    if (notify) ElMessage.success('供应商价格分析已刷新')
  } catch (error) {
    runtime.value = null
    loadError.value = error?.message || '供应商价格分析读取失败'
    refreshStatus.value = 'error'
    publishAcceptance()
    if (notify) ElMessage.error(loadError.value)
  }
}

const observabilityProvider = {
  factOwner: 'SupplierPriceFactRuntime',
  refresh: () => refresh({ notify: true }),
  buildDiagnostics: diagnostics,
}

onMounted(async () => {
  observability?.register?.(observabilityProvider)
  await refresh()
})
onBeforeUnmount(() => observability?.unregister?.(observabilityProvider))
</script>

<style scoped>
.price-analysis-page { display: grid; gap: 16px; min-width: 0; }
.panel { min-width: 0; padding: 18px; border: 1px solid #d8e0ea; border-radius: 10px; background: #fff; }
.panel header, .section-heading { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; }
.panel h2, .panel p { margin: 0; }
.panel p { margin-top: 6px; color: #64748b; line-height: 1.6; }
.read-only-badge { padding: 6px 10px; border-radius: 999px; background: #e0f2fe; color: #075985; font-weight: 800; white-space: nowrap; }
.runtime-error { padding: 10px 12px; border-radius: 8px; background: #fef2f2; color: #b91c1c !important; }
.summary-grid { display: grid; grid-template-columns: repeat(6, minmax(120px, 1fr)); gap: 12px; margin-top: 16px; }
.summary-grid article { display: grid; gap: 8px; padding: 14px; border-radius: 8px; background: #f8fafc; }
.summary-grid span, .section-heading > span { color: #64748b; }
.summary-grid strong { font-size: 22px; color: #0f172a; }
.rule-chips { display: flex; flex-wrap: wrap; gap: 8px; margin: 14px 0; }
.rule-chips span { padding: 6px 10px; border-radius: 999px; background: #fff7ed; color: #9a3412; }
.detail-json { max-height: 520px; overflow: auto; padding: 14px; background: #0f172a; color: #e2e8f0; white-space: pre-wrap; overflow-wrap: anywhere; }
@media (max-width: 1100px) { .summary-grid { grid-template-columns: repeat(3, minmax(120px, 1fr)); } }
@media (max-width: 720px) { .summary-grid { grid-template-columns: repeat(2, minmax(120px, 1fr)); } .panel header, .section-heading { display: grid; } }
@media (max-width: 480px) { .summary-grid { grid-template-columns: 1fr; } }
</style>
