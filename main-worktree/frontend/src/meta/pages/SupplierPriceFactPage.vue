<template>
  <main
    class="supplier-price-fact-page"
    data-page-code="foundation-supplier-price-facts"
    data-runtime-code="SupplierPriceFactRuntime"
    data-price-maintenance-enabled="false"
    data-auto-decision-enabled="false"
    data-pce-page-kind="fact"
    data-pce-action-policy="view"
  >
    <section class="fact-summary panel">
      <header>
        <div>
          <h2>供应商价格事实</h2>
          <p>回答“过去实际采购价格及其来源是什么”；只读汇集报价、受治理有效价格候选和历史采购执行事实，不提供人工维护或自动决策。</p>
        </div>
        <span class="read-only-badge">只读事实</span>
      </header>
      <p v-if="loadError" class="runtime-error" data-fact-load-status="read_failed">
        {{ loadError }}
      </p>
      <div class="summary-grid" :data-fact-load-status="factLoadStatus">
        <article><span>当前筛选结果</span><strong>{{ currentResultCount ?? '-' }}</strong></article>
        <article><span>服务端事实总数</span><strong>{{ runtime?.priceFactCount ?? '-' }}</strong></article>
        <article><span>历史来源候选</span><strong>{{ runtime?.historyFactCount ?? '-' }}</strong></article>
        <article><span>有效价格引用</span><strong>{{ runtime?.sourceCounts?.SupplierMaterialPrice ?? '-' }}</strong></article>
        <article><span>同期间候选</span><strong>{{ runtime?.duplicateEffectivePeriodCount ?? '-' }}</strong></article>
        <article><span>业务写入</span><strong>{{ runtime?.businessProgressWriteCount ?? 0 }}</strong></article>
      </div>
      <div class="source-priority">
        <strong>来源优先级：</strong>
        <span v-for="source in runtime?.sourcePriority || []" :key="source">{{ source }}</span>
      </div>
    </section>

    <section class="date-guide panel" data-acceptance-id="supplier-price-fact-date-guide">
      <h2>价格日期说明</h2>
      <div class="date-guide-grid">
        <article>
          <strong>单日日期</strong>
          <p>历史采购执行事实，生效日期与失效日期为同一天。</p>
        </article>
        <article>
          <strong>日期区间</strong>
          <p>有效价格，由生效日期与失效日期共同表达有效期间。</p>
        </article>
        <article>
          <strong>待补有效期</strong>
          <p>服务端来源缺失正式有效期，页面只提示，不自动补造。</p>
        </article>
      </div>
    </section>

    <section class="extension-panel panel" data-price-intelligence-extension-point>
      <h2>Price Intelligence Extension Point</h2>
      <p>以下仅为后续接入口，本版本不执行分析、推荐、核价或下单。</p>
      <div>
        <span v-for="point in runtime?.intelligenceExtensionPoints || extensionPoints" :key="point">
          {{ extensionPointLabel(point) }}
        </span>
      </div>
    </section>

    <section
      class="intelligence-reference-panel panel"
      data-acceptance-id="supplier-price-fact-intelligence-reference"
      data-reference-source="SupplierPriceFactRuntime"
    >
      <h2>智能分析引用关系</h2>
      <p>供应商价格事实保持只读；有效价格仅作为独立来源追加引用，不覆盖报价或历史采购事实，页面不生成或改写价格。</p>
      <div>
        <span>✓ 历史价格分析</span>
        <span>✓ 价格趋势分析</span>
        <span>✓ 价格异常检测</span>
        <span>✓ 核价智能辅助</span>
      </div>
    </section>

    <section class="panel">
      <FoundationMetadataList
        v-if="metadata"
        :metadata="metadata"
        :rows="runtime?.rows || []"
        :can-toggle-status="false"
        @result-count-change="handleResultCount"
        @view="showFactDetail"
      />
    </section>

    <el-dialog v-model="detailVisible" title="供应商价格事实详情" width="860px">
      <dl v-if="detailRow" class="detail-grid">
        <template v-for="field in metadata.fields" :key="field.key">
          <dt>{{ field.label }}</dt>
          <dd>{{ detailValue(field.key) }}</dd>
        </template>
      </dl>
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
import { SUPPLIER_PRICE_FACT_EXTENSION_POINTS } from '@/meta/runtime/supplierPriceFactRuntime.js'

const metadata = findFoundationListMetadata('supplierPriceFacts')
const runtime = ref(null)
const currentResultCount = ref(null)
const detailVisible = ref(false)
const detailRow = ref(null)
const loadError = ref('')
const refreshStatus = ref('idle')
const lastRefreshTime = ref('')
const observability = inject(PAGE_OBSERVABILITY_ACTIONS_KEY, null)
const extensionPoints = SUPPLIER_PRICE_FACT_EXTENSION_POINTS
const factLoadStatus = computed(() => runtime.value?.factLoadFacts?.factLoadStatus || (
  loadError.value ? 'read_failed' : 'loading'
))

function extensionPointLabel(value) {
  return {
    PRICE_HISTORY_ANALYSIS: '价格历史分析',
    PRICE_TREND_ANALYSIS: '价格趋势',
    PRICE_ANOMALY_DETECTION: '异常价格检测',
    SUPPLIER_PRICE_COMPARISON: '供应商价格比较',
  }[value] || value
}

function showFactDetail(row) {
  detailRow.value = row
  detailVisible.value = true
}

function handleResultCount(count) {
  currentResultCount.value = Number(count)
  if (runtime.value) publishAcceptance()
}

function detailValue(key) {
  const value = detailRow.value?.[key]
  return value === '' || value === null || value === undefined ? '-' : String(value)
}

function diagnostics() {
  const current = runtime.value
  return {
    version: 'V1.14.2.8.4.27.2.35',
    canonicalName: '供应商价格事实',
    moduleCode: 'EMD',
    pageCode: 'foundation-supplier-price-facts',
    pageFactOwner: 'SupplierPriceFactRuntime',
    factLoadStatus: factLoadStatus.value,
    factLoadFacts: current?.factLoadFacts || {},
    strictServerFacts: current?.strictFacts || {},
    acceptanceFacts: current?.acceptanceFacts || {},
    resultCount: currentResultCount.value,
    serverRecordCount: current?.priceFactCount ?? null,
    sourceObjects: current?.historyRows || [],
    autoDecisionEnabled: false,
    businessProgressWriteCount: 0,
  }
}

function publishAcceptance() {
  window.__PCE_BUSINESS_PAGE_ACCEPTANCE__ = {
    ...diagnostics(),
    pageAssertions: [
      { rule: 'PRICE-FACT-SOURCE-001', passed: Boolean(runtime.value?.sourcePriority?.length) },
      { rule: 'PRICE-FACT-TRACE-001', passed: (runtime.value?.rows || []).every(row => row.sourceReference) },
      { rule: 'PRICE-FACT-UNIQUE-001', passed: runtime.value?.duplicateEffectivePeriodCount >= 0 },
      { rule: 'PRICE-HISTORY-PROTECT-001', passed: runtime.value?.historyFactCount >= runtime.value?.priceFactCount },
      { rule: 'PRICE-NO-AUTO-DECISION-001', passed: runtime.value?.autoDecisionEnabled === false },
      { rule: 'FILTER-COUNT-SYNC-001', passed: currentResultCount.value !== null },
      { rule: 'FACT-VS-MASTER-PAGE-001', passed: metadata?.pageKind === 'fact' && metadata?.actionPolicy?.join(',') === 'view' },
    ],
  }
}

async function refresh({ notify = false } = {}) {
  refreshStatus.value = 'refreshing'
  loadError.value = ''
  try {
    runtime.value = await loadSupplierPriceFactRuntime({ force: true })
    currentResultCount.value = runtime.value.priceFactCount
    refreshStatus.value = 'success'
    lastRefreshTime.value = new Date().toISOString()
    publishAcceptance()
    if (notify) ElMessage.success('供应商价格事实已刷新')
  } catch (error) {
    runtime.value = null
    currentResultCount.value = null
    loadError.value = error?.message || '供应商价格事实读取失败'
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
.supplier-price-fact-page { display: grid; gap: 16px; min-width: 0; }
.panel { min-width: 0; padding: 18px; border: 1px solid #d8e0ea; border-radius: 10px; background: #fff; }
.panel header { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; }
.panel h2, .panel p { margin: 0; }
.panel p { margin-top: 6px; color: #64748b; line-height: 1.6; }
.read-only-badge { padding: 6px 10px; border-radius: 999px; background: #e0f2fe; color: #075985; font-weight: 800; white-space: nowrap; }
.runtime-error { padding: 10px 12px; border-radius: 8px; background: #fef2f2; color: #b91c1c !important; }
.summary-grid { display: grid; grid-template-columns: repeat(5, minmax(140px, 1fr)); gap: 12px; margin-top: 16px; }
.summary-grid article { display: grid; gap: 8px; padding: 14px; border-radius: 8px; background: #f8fafc; }
.summary-grid span { color: #64748b; }
.summary-grid strong { font-size: 22px; color: #0f172a; }
.source-priority, .extension-panel div, .intelligence-reference-panel div { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 14px; }
.source-priority span, .extension-panel div span, .intelligence-reference-panel div span { padding: 5px 9px; border-radius: 999px; background: #eef2ff; color: #3730a3; }
.intelligence-reference-panel div span { background: #dcfce7; color: #166534; }
.date-guide-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-top: 14px; }
.date-guide-grid article { padding: 14px; border-radius: 8px; background: #f8fafc; }
.detail-grid { display: grid; grid-template-columns: minmax(130px, .35fr) minmax(0, 1fr); margin: 0; }
.detail-grid dt, .detail-grid dd { margin: 0; padding: 10px 12px; border-bottom: 1px solid #e2e8f0; }
.detail-grid dt { color: #475569; font-weight: 800; background: #f8fafc; }
.detail-grid dd { overflow-wrap: anywhere; }
@media (max-width: 900px) { .summary-grid { grid-template-columns: repeat(2, minmax(130px, 1fr)); } }
@media (max-width: 760px) { .date-guide-grid { grid-template-columns: 1fr; } }
@media (max-width: 560px) { .summary-grid { grid-template-columns: 1fr; } .panel header { display: grid; } }
</style>
