<template>
  <main
    class="price-review-assistant"
    data-page-code="price-review-assistant"
    data-runtime-code="SupplierPriceFactRuntime"
    data-effective-price-runtime-code="SupplierMaterialPriceRuntime"
    data-rule-runtime-code="PriceReviewRuleRuntime"
    data-decision-mode="manual_test_session_only"
    data-auto-price-decision="false"
    data-business-write-count="0"
  >
    <section class="panel hero" data-acceptance-id="price-review-assistant-summary">
      <div>
        <h2>供应商核价智能辅助</h2>
        <p>系统汇集报价、历史价格、供应商比较与规则提示；最终核价意见必须由人工确认。本页不修改报价、价格事实或采购订单。</p>
      </div>
      <div class="badges"><span>辅助决策</span><span>TEST_CASE</span><span>业务写入 0</span></div>
    </section>

    <section class="panel" data-acceptance-id="price-intelligence-input-chain">
      <div class="section-heading">
        <div>
          <h2>智能核价输入链</h2>
          <p>四类输入由既有Runtime汇集，只提供参考；缺失正式事实时明确标记，不由页面或Gate补造。</p>
        </div>
        <span>只读参考</span>
      </div>
      <div class="input-chain-grid">
        <article v-for="item in priceInputChain" :key="item.objectCode" :data-price-input-object="item.objectCode" :data-input-status="item.statusCode">
          <strong>{{ item.name }}</strong>
          <span>{{ item.source }}</span>
          <p>{{ item.statusLabel }}</p>
        </article>
      </div>
    </section>

    <section class="panel" data-acceptance-id="current-effective-price-reference">
      <div class="section-heading">
        <div>
          <h2>当前企业有效价格</h2>
          <p>来源：SupplierMaterialPriceRuntime；仅显示人工确认后正式归档的当前服务端会话价格，不使用页面默认值。</p>
        </div>
        <span data-acceptance-id="effective-price-count">已生成有效价格 {{ effectivePriceRuntime?.sessionConfirmedPriceCount || 0 }} 条</span>
      </div>
      <el-descriptions v-if="currentEffectivePrice" :column="3" border>
        <el-descriptions-item label="价格编号">{{ currentEffectivePrice.priceId }}</el-descriptions-item>
        <el-descriptions-item label="供应商">{{ currentEffectivePrice.supplierDisplay }}</el-descriptions-item>
        <el-descriptions-item label="物料">{{ currentEffectivePrice.materialDisplay }}</el-descriptions-item>
        <el-descriptions-item label="含税单价">{{ currentEffectivePrice.unitPrice }} {{ currentEffectivePrice.currency }}</el-descriptions-item>
        <el-descriptions-item label="来源类型">{{ currentEffectivePrice.sourceType }}</el-descriptions-item>
        <el-descriptions-item label="来源编号">{{ currentEffectivePrice.sourceReference }}</el-descriptions-item>
        <el-descriptions-item label="确认人">{{ currentEffectivePrice.confirmedBy }}</el-descriptions-item>
        <el-descriptions-item label="确认时间">{{ currentEffectivePrice.confirmedAt }}</el-descriptions-item>
        <el-descriptions-item label="持久化">否（服务端会话）</el-descriptions-item>
      </el-descriptions>
      <el-empty v-else description="暂无有效价格" />
    </section>

    <section class="panel" data-acceptance-id="batch-price-confirmation">
      <div class="section-heading">
        <div>
          <h2>已完成人工确认的核价结果</h2>
          <p>仅 ACCEPT 且待归档的结果可选择；每条独立校验，单条失败不影响其他成功记录。</p>
        </div>
        <span>可归档 {{ effectivePriceRuntime?.archiveEligibleResultCount || 0 }} 条</span>
      </div>
      <el-table ref="approvalResultTable" :data="effectivePriceRuntime?.priceApprovalResults || []" row-key="resultId"
        class="approval-result-table" @selection-change="handleArchiveSelection">
        <el-table-column type="selection" width="50" :selectable="isArchiveSelectable" />
        <el-table-column prop="resultId" label="核价结果编号" min-width="150" />
        <el-table-column prop="supplierDisplay" label="供应商" min-width="190" />
        <el-table-column prop="materialDisplay" label="物料" min-width="190" />
        <el-table-column label="报价" min-width="120"><template #default="scope">{{ scope.row.unitPrice }} {{ scope.row.currency }}</template></el-table-column>
        <el-table-column prop="confirmationResultLabel" label="人工结果" min-width="110" />
        <el-table-column prop="confirmedBy" label="确认人" min-width="100" />
        <el-table-column prop="archiveStatusLabel" label="归档状态" min-width="140" />
      </el-table>
      <div class="batch-actions">
        <el-button type="primary" :disabled="!selectedArchiveResultIds.length || batchArchiving" @click="archiveSelectedResults">
          批量生成有效价格（{{ selectedArchiveResultIds.length }}）
        </el-button>
        <span v-if="effectivePriceRuntime?.lastBatchArchiveResult?.requestedCount">
          最近批次：成功 {{ effectivePriceRuntime.lastBatchArchiveResult.successCount }}，失败 {{ effectivePriceRuntime.lastBatchArchiveResult.failureCount }}
        </span>
      </div>
    </section>

    <p v-if="loadError" class="runtime-error" data-fact-load-status="read_failed">{{ loadError }}</p>
    <section v-if="contexts.length > 1" class="panel context-selector">
      <label>核价案例</label>
      <el-select v-model="selectedContextId" aria-label="核价案例">
        <el-option v-for="item in contexts" :key="item.reviewContextId"
          :label="`${item.currentQuotationFact.supplierDisplay} / ${item.currentQuotationFact.materialDisplay}`"
          :value="item.reviewContextId" />
      </el-select>
    </section>

    <template v-if="currentContext">
      <section class="panel" data-acceptance-id="current-quotation-information">
        <div class="section-heading"><div><h2>当前报价信息</h2><p>来源：SupplierPriceFactRuntime / SupplierQuotationItem</p></div><span>{{ quote.statusLabel }}</span></div>
        <el-descriptions :column="3" border>
          <el-descriptions-item label="供应商">{{ quote.supplierDisplay }}</el-descriptions-item>
          <el-descriptions-item label="物料">{{ quote.materialDisplay }}</el-descriptions-item>
          <el-descriptions-item label="报价价格">{{ quote.priceDisplay }}</el-descriptions-item>
          <el-descriptions-item label="币种">{{ quote.currency || '-' }}</el-descriptions-item>
          <el-descriptions-item label="报价来源">{{ quote.sourceReference }}</el-descriptions-item>
          <el-descriptions-item label="报价日期">{{ quote.effectiveDate }}</el-descriptions-item>
        </el-descriptions>
      </section>

      <section class="panel" data-acceptance-id="historical-price-reference">
        <div class="section-heading"><div><h2>历史价格参考</h2><p>{{ history.source }}</p></div><span>{{ history.analysisStatus }}</span></div>
        <div class="metric-grid">
          <article><span>最低采购价</span><strong>{{ history.lowestPurchasePrice || '-' }}</strong></article>
          <article><span>最近采购价</span><strong>{{ history.latestPurchasePrice || '-' }}</strong></article>
          <article><span>平均采购价</span><strong>{{ history.averagePurchasePrice || '-' }}</strong></article>
          <article><span>历史次数</span><strong>{{ history.historicalPurchaseCount }}</strong></article>
          <article><span>最近采购日期</span><strong>{{ history.latestPurchaseDate || '-' }}</strong></article>
          <article><span>价格趋势</span><strong>{{ history.trendLabel }}</strong></article>
        </div>
      </section>

      <section class="panel" data-acceptance-id="price-review-supplier-comparison">
        <div class="section-heading"><div><h2>供应商比较</h2><p>同物料、同币种、同单位的最近价格比较；最低价格不等于推荐结果。</p></div><span>{{ comparison.candidateCount }} 家</span></div>
        <FoundationMetadataList v-if="comparisonMetadata" :metadata="comparisonMetadata"
          :rows="comparison.candidates || []" :can-toggle-status="false"
          @result-count-change="comparisonResultCount = Number($event)" @view="showComparison" />
        <div class="performance-grid">
          <span>关系编号：{{ performance.relationCode || '-' }}</span>
          <span>交期记录：{{ performance.deliveryPeriodLabel }}</span>
          <span>质量记录：{{ performance.qualityLevel }}</span>
          <span>准时率：{{ performance.onTimeRateLabel }}</span>
        </div>
      </section>

      <section class="panel" data-acceptance-id="price-review-rule-prompts">
        <div class="section-heading"><div><h2>异常提醒</h2><p>PriceReviewRuleRuntime 只生成提示，不生成决定。</p></div><span>{{ rules.ruleVersion }}</span></div>
        <el-empty v-if="!rules.prompts?.length" description="当前规则未产生异常提示，仍须人工核价" />
        <div v-else class="prompt-list">
          <article v-for="prompt in rules.prompts" :key="prompt.promptId">
            <strong>{{ prompt.message }}</strong>
            <span>{{ prompt.ruleCode }} · {{ prompt.threshold }} · {{ prompt.ruleVersion }}</span>
          </article>
        </div>
      </section>

      <section class="panel" data-acceptance-id="manual-price-decision">
        <div class="section-heading"><div><h2>报价确认结果</h2><p>这是核价结果确认，不是报价审批。人工结果先进入待归档队列；仅 ACCEPT 可由人工选择批量生成有效价格。</p></div><span>{{ decisionRecord.decisionStatusLabel || decisionRecord.confirmationResultLabel }}</span></div>
        <el-form label-position="top" class="decision-form">
          <el-form-item label="核价意见"><el-input v-model="form.reviewOpinion" type="textarea" :rows="3" placeholder="请输入人工核价意见" :disabled="confirmed" /></el-form-item>
          <el-form-item label="确认人"><el-input v-model="form.confirmedBy" placeholder="请输入确认人" :disabled="confirmed" /></el-form-item>
          <el-alert title="确认只记录人工核价结论；税率与有效期在供应商物料价格维护，交货周期在物料供应商关系维护。" type="info" :closable="false" />
          <div class="confirmation-actions">
            <el-button type="primary" :disabled="confirmed" @click="confirmDecision('ACCEPT_QUOTATION')">确认采用报价</el-button>
            <el-button :disabled="confirmed" @click="confirmDecision('REJECT_QUOTATION')">拒绝报价</el-button>
            <el-button :disabled="confirmed" @click="confirmDecision('REQUEST_RENEGOTIATION')">要求重新议价</el-button>
          </div>
        </el-form>
        <el-descriptions v-if="confirmed" :column="2" border class="audit-result" data-acceptance-id="manual-decision-audit-record">
          <el-descriptions-item label="确认状态">{{ decisionRecord.decisionStatusLabel }}</el-descriptions-item>
          <el-descriptions-item label="确认结果">{{ decisionRecord.confirmationResultLabel || decisionRecord.confirmationResult }}</el-descriptions-item>
          <el-descriptions-item label="确认人">{{ decisionRecord.confirmedBy }}</el-descriptions-item>
          <el-descriptions-item label="确认时间">{{ decisionRecord.confirmedAt }}</el-descriptions-item>
          <el-descriptions-item label="核价意见">{{ decisionRecord.reviewOpinion }}</el-descriptions-item>
          <el-descriptions-item label="审计模式">{{ decisionRecord.auditMode }} / persisted=false</el-descriptions-item>
        </el-descriptions>
      </section>
    </template>

    <section v-else-if="!loadError" class="panel"><el-empty description="当前没有可供人工核价辅助的报价事实" /></section>

    <el-dialog v-model="detailVisible" title="供应商比较明细" width="760px">
      <pre class="detail-json">{{ detailText }}</pre>
    </el-dialog>
  </main>
</template>

<script setup>
import { computed, inject, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import FoundationMetadataList from '@/meta/components/FoundationMetadataList.vue'
import { findFoundationListMetadata } from '@/meta/master-data/masterDataRegistry.js'
import { loadSupplierPriceFactRuntime } from '@/meta/providers/supplierPriceFactRuntimeProvider.js'
import { batchArchiveSupplierMaterialPrices, loadSupplierMaterialPriceRuntime, recordPriceApprovalResult } from '@/meta/providers/supplierMaterialPriceRuntimeProvider.js'
import { PAGE_OBSERVABILITY_ACTIONS_KEY } from '@/meta/runtime/pageObservabilityActions.js'
import { createPurchasePriceDecisionContext, confirmPurchasePriceDecisionContext } from '@/meta/process/scm/priceApproval/priceReferenceContext.js'

const comparisonMetadata = findFoundationListMetadata('supplierPriceComparisons')
const runtime = ref(null)
const effectivePriceRuntime = ref(null)
const selectedContextId = ref('')
const decisionRecord = ref({ decisionStatusLabel: '待人工确认' })
const comparisonResultCount = ref(0)
const loadError = ref('')
const detailVisible = ref(false)
const detailRow = ref(null)
const refreshStatus = ref('idle')
const lastRefreshTime = ref('')
const approvalResultTable = ref(null)
const selectedArchiveResultIds = ref([])
const batchArchiving = ref(false)
const observability = inject(PAGE_OBSERVABILITY_ACTIONS_KEY, null)
const form = reactive({ reviewOpinion: '', confirmedBy: '' })
const contexts = computed(() => runtime.value?.purchasePriceReviewContexts || [])
const currentContext = computed(() => contexts.value.find(item => item.reviewContextId === selectedContextId.value) || contexts.value[0] || null)
const quote = computed(() => currentContext.value?.currentQuotationFact || {})
const history = computed(() => currentContext.value?.historicalPriceReference || {})
const comparison = computed(() => currentContext.value?.supplierComparison || {})
const performance = computed(() => currentContext.value?.supplierPerformance || {})
const rules = computed(() => currentContext.value?.ruleAssist || {})
const currentEffectivePrice = computed(() => (effectivePriceRuntime.value?.rows || []).find(item => (
  item.supplierCode === quote.value?.supplierCode
  && item.materialCode === quote.value?.materialCode
  && item.status === 'ACTIVE'
)) || null)
const priceInputChain = computed(() => {
  const sourceCounts = runtime.value?.sourceCounts || {}
  const effectivePriceCount = Number(effectivePriceRuntime.value?.formalPriceCount || 0)
  return [
    {
      objectCode: 'MaterialSupplierRelation', name: '供应关系', source: 'MaterialSupplierRelationRuntime',
      statusCode: performance.value?.source === 'MaterialSupplierRelationRuntime' ? 'AVAILABLE' : 'UNAVAILABLE',
      statusLabel: performance.value?.relationCode ? `已引用 ${performance.value.relationCode}` : '当前案例无正式关系事实',
    },
    {
      objectCode: 'SupplierMaterialPrice', name: '企业认可有效价格', source: 'SupplierMaterialPriceRuntime',
      statusCode: effectivePriceCount > 0 ? 'AVAILABLE' : 'NO_ELIGIBLE_APPROVED_PRICE',
      statusLabel: effectivePriceCount > 0
        ? `已引用 ${effectivePriceCount} 条企业认可有效价格`
        : `正式价格 0 条；${effectivePriceRuntime.value?.rejectedCandidateCount || 0} 条不完整候选保持隔离`,
    },
    {
      objectCode: 'SupplierPriceFact', name: '历史价格事实', source: 'SupplierPriceFactRuntime.intelligenceAnalysis',
      statusCode: runtime.value?.priceFactCount > 0 ? 'AVAILABLE' : 'UNAVAILABLE',
      statusLabel: `统一价格事实 ${runtime.value?.priceFactCount || 0} 条`,
    },
    {
      objectCode: 'SupplierQuotation', name: '当前供应商报价', source: 'SupplierPriceFactRuntime / SupplierQuotationItem',
      statusCode: Number(sourceCounts.SupplierQuotation || 0) > 0 ? 'AVAILABLE' : 'UNAVAILABLE',
      statusLabel: `报价事实 ${sourceCounts.SupplierQuotation || 0} 条`,
    },
  ]
})
const confirmed = computed(() => decisionRecord.value?.manualDecisionRecorded === true || Boolean(decisionRecord.value?.resultId))
const detailText = computed(() => JSON.stringify(detailRow.value || {}, null, 2))

function resetDecision() {
  Object.assign(form, { reviewOpinion: '', confirmedBy: '' })
  const recorded = (effectivePriceRuntime.value?.priceApprovalResults || []).find(item => item.sourceFactReference === quote.value?.sourceReference)
  decisionRecord.value = recorded || (currentContext.value
    ? createPurchasePriceDecisionContext(currentContext.value)
    : { decisionStatusLabel: '待人工确认' })
}
watch(() => currentContext.value?.reviewContextId, resetDecision)

function showComparison(row) { detailRow.value = row; detailVisible.value = true }

async function confirmDecision(result) {
  try {
    const resultMap = { ACCEPT_QUOTATION: 'PASS', REJECT_QUOTATION: 'REJECT', REQUEST_RENEGOTIATION: 'ADJUST' }
    const input = { ...form, confirmationResult: resultMap[result] }
    effectivePriceRuntime.value = await recordPriceApprovalResult({
      confirmationResult: result,
      reviewOpinion: form.reviewOpinion,
      confirmedBy: form.confirmedBy,
      sourceFactReference: quote.value?.sourceReference,
    })
    const recorded = (effectivePriceRuntime.value?.priceApprovalResults || []).find(item => item.sourceFactReference === quote.value?.sourceReference)
    decisionRecord.value = Object.freeze({
      ...confirmPurchasePriceDecisionContext(decisionRecord.value, input),
      ...recorded,
      quoteConfirmationResult: result,
      generatedSupplierMaterialPriceId: '',
      effectivePriceGenerated: false,
    })
    ElMessage.success(result === 'ACCEPT_QUOTATION'
      ? '报价已人工确认并进入待归档队列；尚未生成有效价格'
      : '核价结果已记录；不可归档为有效价格')
    publishAcceptance()
  } catch (error) {
    ElMessage.warning(error.message === 'MANUAL_PRICE_DECISION_FIELDS_REQUIRED'
      ? '请完整填写核价意见和确认人'
      : (error.message || '核价结果记录失败'))
  }
}

function isArchiveSelectable(row) {
  return row.confirmationResult === 'ACCEPT' && row.archiveStatus === 'PENDING_ARCHIVE'
}

function handleArchiveSelection(rows) {
  selectedArchiveResultIds.value = rows.map(item => item.resultId)
}

async function archiveSelectedResults() {
  batchArchiving.value = true
  try {
    effectivePriceRuntime.value = await batchArchiveSupplierMaterialPrices(selectedArchiveResultIds.value)
    const summary = effectivePriceRuntime.value.lastBatchArchiveResult
    selectedArchiveResultIds.value = []
    approvalResultTable.value?.clearSelection?.()
    ElMessage.success(`批量归档完成：成功 ${summary.successCount} 条，失败 ${summary.failureCount} 条；数据库写入0`)
    resetDecision()
    publishAcceptance()
  } catch (error) {
    ElMessage.error(error?.message || '批量归档失败')
  } finally {
    batchArchiving.value = false
  }
}

function diagnostics() {
  return {
    version: 'V1.14.2.8.4.27.2.45', canonicalName: '供应商核价智能辅助', moduleCode: 'SCM',
    pageCode: 'price-review-assistant', pageFactOwner: 'SupplierPriceFactRuntime',
    factLoadStatus: runtime.value?.factLoadFacts?.factLoadStatus || (loadError.value ? 'read_failed' : 'loading'),
    factLoadFacts: runtime.value?.factLoadFacts || {}, strictServerFacts: runtime.value?.strictFacts || {},
    acceptanceFacts: runtime.value?.acceptanceFacts || {}, reviewContext: currentContext.value,
    effectivePriceFacts: effectivePriceRuntime.value?.strictFacts || {},
    manualDecisionAudit: decisionRecord.value, comparisonResultCount: comparisonResultCount.value,
    priceApprovalResultCount: effectivePriceRuntime.value?.priceApprovalResultCount || 0,
    archiveEligibleResultCount: effectivePriceRuntime.value?.archiveEligibleResultCount || 0,
    sessionConfirmedPriceCount: effectivePriceRuntime.value?.sessionConfirmedPriceCount || 0,
    lastBatchArchiveResult: effectivePriceRuntime.value?.lastBatchArchiveResult || {},
    automaticPriceDecision: false, automaticSupplierSelection: false, automaticPriceModification: false,
    automaticPurchaseOrderCreation: false, businessProgressWriteCount: 0,
  }
}

function publishAcceptance() {
  const context = currentContext.value
  window.__PCE_BUSINESS_PAGE_ACCEPTANCE__ = { ...diagnostics(), pageAssertions: [
    { rule: 'PRICE-REVIEW-CONTEXT-001', passed: context?.objectType === 'PurchasePriceReviewContext' },
    { rule: 'PRICE-HISTORY-REFERENCE-001', passed: context?.historicalPriceReference?.source === 'SupplierPriceFactRuntime.intelligenceAnalysis' },
    { rule: 'PRICE-RULE-ASSIST-001', passed: context?.ruleAssist?.runtimeCode === 'PriceReviewRuleRuntime' && context?.ruleAssist?.resultType === 'ASSISTIVE_PROMPT_ONLY' },
    { rule: 'PRICE-NO-AUTO-DECISION-001', passed: context?.automaticPriceDecision === false && context?.automaticSupplierSelection === false && context?.automaticPurchaseOrderCreation === false },
    { rule: 'NO-AUTO-PRICE-DECISION-001', passed: context?.automaticPriceDecision === false && context?.automaticPriceModification === false },
    { rule: 'PRICE-INTELLIGENCE-CHAIN-001', passed: priceInputChain.value.length === 4 && priceInputChain.value.every(item => item.source) && context?.automaticPurchaseOrderCreation === false },
    { rule: 'PRICE_REVIEW_REFERENCE_001', passed: effectivePriceRuntime.value?.runtimeCode === 'SupplierMaterialPriceRuntime' && effectivePriceRuntime.value?.autoGenerationEnabled === false },
    { rule: 'PRICE_CONFIRMATION_CHAIN_001', passed: effectivePriceRuntime.value?.confirmationResults?.length === 3 && effectivePriceRuntime.value?.sessionPersistence === 'SERVER_MEMORY_ONLY' },
    { rule: 'PRICE_APPROVAL_RESULT_SCAN_001', passed: Array.isArray(effectivePriceRuntime.value?.priceApprovalResults) },
    { rule: 'EFFECTIVE_PRICE_ARCHIVE_001', passed: effectivePriceRuntime.value?.rows?.every(item => item.sourceType !== 'SupplierQuotationConfirmed' || (item.status === 'ACTIVE' && item.persisted === false)) },
    { rule: 'BATCH_PRICE_CONFIRMATION_001', passed: Number(effectivePriceRuntime.value?.lastBatchArchiveResult?.failureCount || 0) + Number(effectivePriceRuntime.value?.lastBatchArchiveResult?.successCount || 0) === Number(effectivePriceRuntime.value?.lastBatchArchiveResult?.requestedCount || 0) },
    { rule: 'DECISION-AUDIT-001', passed: decisionRecord.value?.auditMode === 'memory_session_only' && decisionRecord.value?.persisted === false },
  ] }
}

async function refresh({ notify = false } = {}) {
  refreshStatus.value = 'refreshing'; loadError.value = ''
  try {
    ;[runtime.value, effectivePriceRuntime.value] = await Promise.all([
      loadSupplierPriceFactRuntime({ force: true }),
      loadSupplierMaterialPriceRuntime({ force: true }),
    ])
    selectedContextId.value = runtime.value.purchasePriceReviewContexts[0]?.reviewContextId || ''
    comparisonResultCount.value = currentContext.value?.supplierComparison?.candidateCount || 0
    resetDecision(); refreshStatus.value = 'success'; lastRefreshTime.value = new Date().toISOString(); publishAcceptance()
    if (notify) ElMessage.success('核价辅助事实已刷新')
  } catch (error) {
    runtime.value = null; effectivePriceRuntime.value = null; loadError.value = error?.message || '核价辅助事实读取失败'; refreshStatus.value = 'error'; publishAcceptance()
    if (notify) ElMessage.error(loadError.value)
  }
}

const observabilityProvider = { factOwner: 'SupplierPriceFactRuntime', refresh: () => refresh({ notify: true }), buildDiagnostics: diagnostics }
onMounted(async () => { observability?.register?.(observabilityProvider); await refresh() })
onBeforeUnmount(() => observability?.unregister?.(observabilityProvider))
</script>

<style scoped>
.price-review-assistant{display:grid;gap:16px;min-width:0}.panel{min-width:0;padding:18px;border:1px solid #d8e0ea;border-radius:10px;background:#fff}.hero,.section-heading{display:flex;justify-content:space-between;gap:16px;align-items:flex-start}.panel h2,.panel p{margin:0}.panel p{margin-top:6px;color:#64748b;line-height:1.6}.badges,.performance-grid{display:flex;flex-wrap:wrap;gap:8px}.badges span,.section-heading>span,.performance-grid span{padding:6px 10px;border-radius:999px;background:#e0f2fe;color:#075985;white-space:nowrap}.input-chain-grid{display:grid;grid-template-columns:repeat(4,minmax(170px,1fr));gap:12px;margin-top:14px}.input-chain-grid article{display:grid;gap:6px;padding:14px;border-radius:8px;background:#f8fafc}.input-chain-grid article span{font-size:12px;color:#475569;overflow-wrap:anywhere}.runtime-error{padding:12px;border-radius:8px;background:#fef2f2;color:#b91c1c}.context-selector{display:flex;align-items:center;gap:12px}.context-selector .el-select{min-width:460px}.metric-grid{display:grid;grid-template-columns:repeat(6,minmax(120px,1fr));gap:12px;margin-top:14px}.metric-grid article{display:grid;gap:8px;padding:14px;border-radius:8px;background:#f8fafc}.metric-grid article span{color:#64748b}.metric-grid article strong{font-size:20px}.performance-grid{margin-top:14px}.prompt-list{display:grid;gap:10px;margin-top:14px}.prompt-list article{display:grid;gap:6px;padding:14px;border-left:4px solid #f59e0b;background:#fffbeb}.prompt-list span{color:#92400e}.decision-form{display:grid;grid-template-columns:repeat(3,minmax(180px,1fr));gap:12px;align-items:end;margin-top:14px}.confirmation-actions{display:flex;flex-wrap:wrap;gap:8px;grid-column:1/-1}.audit-result{margin-top:16px}.detail-json{max-height:500px;overflow:auto;padding:14px;background:#0f172a;color:#e2e8f0;white-space:pre-wrap}@media(max-width:1100px){.input-chain-grid,.metric-grid{grid-template-columns:repeat(2,minmax(120px,1fr))}.decision-form{grid-template-columns:1fr 1fr}}@media(max-width:720px){.hero,.section-heading{display:grid}.input-chain-grid,.metric-grid,.decision-form{grid-template-columns:1fr}.context-selector{display:grid}.context-selector .el-select{min-width:0;width:100%}}
.approval-result-table{margin-top:14px}.batch-actions{display:flex;align-items:center;gap:14px;margin-top:14px;color:#475569}
</style>
