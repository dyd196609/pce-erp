<template>
  <main class="decision-workbench" data-page-code="supplier-recommendation"
    data-page-name="供应商推荐" data-module-code="SCM"
    data-business-object="SupplierRecommendationDecisionBatch">
    <header class="page-heading">
      <div><p class="eyebrow">SCM · 采购决策</p><h1>供应商推荐</h1>
        <p>按采购推荐批次逐项完成多物料供应商选择；系统只提供报价与历史价格证据。</p></div>
      <el-button @click="refresh">刷新</el-button>
    </header>

    <el-alert v-if="entryError" type="error" :closable="false" :title="entryError" />

    <section class="panel" data-acceptance-region="purchase-context">
      <div class="section-heading"><div><h2>一、采购上下文</h2><p>所有入口恢复同一个供应商推荐任务及采购决策批次。</p></div>
        <el-tag v-if="batch" effect="plain">{{ batch.items.length }} 个物料</el-tag></div>
      <el-descriptions v-if="batch" :column="2" border>
        <el-descriptions-item label="决策批次">{{ batch.batchId }}</el-descriptions-item>
        <el-descriptions-item label="当前状态">{{ batchStatusLabel }}</el-descriptions-item>
        <el-descriptions-item label="采购申请编号">{{ handoffFacts.purchaseContext?.sourceRequestNos.join('、') || '-' }}</el-descriptions-item>
        <el-descriptions-item label="核价编号">{{ handoffFacts.purchaseContext?.priceApprovalNos.join('、') || '-' }}</el-descriptions-item>
        <el-descriptions-item label="核价批次">{{ batch.sourcePriceApprovalBatch.join('、') }}</el-descriptions-item>
        <el-descriptions-item label="报价比较批次">{{ batch.sourceQuoteComparisonBatch.join('、') }}</el-descriptions-item>
      </el-descriptions>
    </section>

    <section class="panel" data-acceptance-region="material-recommendation-list">
      <div class="section-heading"><div><h2>二、物料推荐清单</h2><p>一个决策批次包含多个物料，每个物料保留独立候选与人工结论。</p></div></div>
      <el-table :data="batch?.items || []" border empty-text="暂无待决策物料">
        <el-table-column prop="materialCode" label="物料编码" width="150" />
        <el-table-column prop="materialName" label="物料名称" min-width="170" />
        <el-table-column label="核价编号" min-width="190"><template #default="{ row }">{{ row.priceApprovalNos?.join('、') || row.priceApprovalNo }}</template></el-table-column>
        <el-table-column label="报价比较编号" min-width="210"><template #default="{ row }">{{ row.quoteComparisonIds?.join('、') || row.quoteComparisonId }}</template></el-table-column>
        <el-table-column label="候选供应商" width="130"><template #default="{ row }">{{ row.supplierCandidates.length }} 家</template></el-table-column>
        <el-table-column label="决策供应商" min-width="180"><template #default="{ row }">{{ row.selectedSupplierName || row.decisionSupplier?.supplierName || '待选择' }}</template></el-table-column>
        <el-table-column label="物料推荐决策状态" width="130"><template #default="{ row }">{{ itemStatusLabel(row.reviewStatus, row.status) }}</template></el-table-column>
      </el-table>
    </section>

    <section class="panel" data-acceptance-region="supplier-comparison">
      <div class="section-heading"><div><h2>三、供应商报价比较</h2><p>每行是一项物料的一家供应商报价，不将供应商误作多个商品。</p></div></div>
      <el-table :data="comparisonRows" border empty-text="暂无供应商报价">
        <el-table-column prop="materialCode" label="物料编码" width="150" fixed="left" />
        <el-table-column prop="materialName" label="物料名称" min-width="160" />
        <el-table-column prop="supplierCode" label="供应商编码" width="150" />
        <el-table-column prop="supplierName" label="供应商" min-width="180" />
        <el-table-column prop="quotePriceLabel" label="供应商报价" width="140" />
        <el-table-column prop="priceRankLabel" label="价格排名" width="120" />
      </el-table>
    </section>

    <section class="panel" data-acceptance-region="historical-price-reference" data-read-only="true">
      <div class="section-heading"><div><h2>四、历史价格参考</h2><p>历史价格仅作为证据，不自动判断合理性或推荐供应商。</p></div></div>
      <el-table :data="historyRows" border empty-text="暂无历史价格参考">
        <el-table-column prop="materialCode" label="物料编码" width="150" />
        <el-table-column prop="supplierCode" label="供应商编码" width="150" />
        <el-table-column prop="historyPriceLabel" label="历史价格" width="140" />
        <el-table-column prop="currentPriceLabel" label="当前报价" width="140" />
        <el-table-column prop="changeRateLabel" label="变化比例" width="130" />
        <el-table-column prop="evidenceSource" label="证据来源" min-width="180" />
      </el-table>
    </section>

    <section class="panel" data-acceptance-region="manual-recommendation-decision">
      <div class="section-heading"><div><h2>五、人工推荐决策</h2><p>采购人员必须为每个物料选择一家供应商并填写独立理由。</p></div></div>
      <div class="decision-grid">
        <article v-for="item in batch?.items || []" :key="item.materialCode" class="decision-card">
          <strong>{{ item.materialCode }} · {{ item.materialName }}</strong>
          <div class="candidate-evidence-list" data-acceptance-region="candidate-evidence-list">
            <article v-for="supplier in item.supplierCandidates" :key="supplier.supplierCode"
              class="candidate-evidence-card" data-supplier-candidate>
              <strong>{{ supplier.supplierName }}</strong>
              <span>报价金额：{{ formatMoney(supplier.quotePrice) }}</span>
              <span>报价比较：{{ candidateComparisonLabel(supplier) }}</span>
              <span>历史价格：{{ candidateHistoryLabel(item, supplier) }}</span>
              <span>资格状态：{{ candidateQualificationLabel(supplier) }}</span>
            </article>
          </div>
          <el-select v-model="drafts[item.materialCode].supplierCode" placeholder="选择供应商"
            :disabled="item.status === 'confirmed' || !canExecute">
            <el-option v-for="supplier in item.supplierCandidates" :key="supplier.supplierCode"
              :label="`${supplier.supplierName} · ${formatMoney(supplier.quotePrice)}`"
              :value="supplier.supplierCode" />
          </el-select>
          <el-input v-model="drafts[item.materialCode].reason" type="textarea" :rows="2"
            placeholder="填写该物料的推荐理由" :disabled="item.status === 'confirmed' || !canExecute" />
          <el-button type="primary" data-process-action="SELECT_DECISION_BATCH_SUPPLIER"
            :disabled="!itemDecisionExecutable(item)" @click="saveItemDecision(item)">保存本项决策</el-button>
          <span class="status-note">{{ itemStatusLabel(item.reviewStatus, item.status) }}</span>
        </article>
      </div>
    </section>

    <section class="panel" data-acceptance-region="batch-confirmation">
      <div class="section-heading"><div><h2>六、确认提交</h2><p>全部物料完成后，由采购人员一次性确认决策批次并交接采购订单准入。</p></div></div>
      <div class="confirm-row">
        <el-input v-model="confirmedBy" placeholder="确认人" :disabled="Boolean(batchResult)" />
        <el-button type="success" data-process-action="CONFIRM_RECOMMENDATION_DECISION_BATCH"
          :disabled="!batchConfirmExecutable" @click="confirmBatch">批量确认推荐</el-button>
        <el-button data-process-action="OPEN_PURCHASE_ORDER_GATE" :disabled="!batchHandoff"
          @click="router.push({ path: '/scm/purchase-order-gate', query: { batchId: batch.batchId } })">进入采购订单准入</el-button>
      </div>
      <el-descriptions v-if="batchResult" :column="3" border>
        <el-descriptions-item label="批次结果">SupplierRecommendationDecisionBatchResult</el-descriptions-item>
        <el-descriptions-item label="确认人">{{ batchResult.confirmedBy }}</el-descriptions-item>
        <el-descriptions-item label="确认时间">{{ batchResult.confirmedAt }}</el-descriptions-item>
      </el-descriptions>
    </section>
  </main>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { canPerformAction } from '@/meta/runtime/permissionEngine.js'
import { stateManager } from '@/meta/runtime/stateManager.js'
import { executeConfirmSupplierRecommendationDecisionBatchV11428169,
  executeSelectDecisionBatchSupplierV11428169,
  supplierRecommendationDecisionBatchStoreV11428169 } from '@/meta/process/scm/supplierRecommendation/supplierRecommendationDecisionBatchV11428169.js'
import { supplierRecommendationRouteContextResolverV11428171 } from '@/meta/process/scm/supplierRecommendation/supplierRecommendationRouteContextResolverV11428171.js'
import { supplierRecommendationDataHandoffProviderV1142818 } from '@/meta/providers/supplierRecommendationDataHandoffProviderV1142818.js'

const router = useRouter()
const batch = ref(null)
const handoffFacts = ref({ result: 'FAIL', purchaseContext: null, items: [] })
const batchResult = ref(null)
const batchRuntimeResult = ref(null)
const batchHandoff = ref(null)
const entryError = ref('')
const confirmedBy = ref('')
const drafts = reactive({})
const canExecute = computed(() => canPerformAction(stateManager.snapshot().role, 'EXECUTE'))
const batchStatusLabel = computed(() => {
  if (batchResult.value) return '批次已确认'
  if (batchRuntimeResult.value?.status === 'reopen_review') return '已退回人工复核'
  return '待人工决策'
})
const comparisonRows = computed(() => (batch.value?.items || []).flatMap(item =>
  item.supplierCandidates.map(supplier => ({ ...supplier, materialCode: item.materialCode,
    materialName: item.materialName, quotePriceLabel: formatMoney(supplier.quotePrice),
    priceRankLabel: supplier.priceRank ? `第 ${supplier.priceRank} 名` : '-' }))))
const historyRows = computed(() => (batch.value?.items || []).flatMap(item => {
  const references = item.priceReferenceContexts?.length ? item.priceReferenceContexts : item.priceEvidence
  return references.filter(evidence => evidence.historyPrice != null || evidence.historicalPurchasePrice != null
    || evidence.priceReferenceContext || evidence.priceChangeEvidence)
    .map(evidence => {
      const change = evidence.priceChangeEvidence || {}
      const reference = evidence.priceReferenceContext || evidence
      return { materialCode: item.materialCode, supplierCode: evidence.supplierCode,
        historyPriceLabel: formatMoney(evidence.historyPrice ?? evidence.historicalPurchasePrice
          ?? change.historyPrice ?? reference.latestPurchasePrice),
        currentPriceLabel: formatMoney(evidence.currentPrice ?? evidence.currentQuote ?? change.currentPrice),
        changeRateLabel: (change.changeRate ?? evidence.priceChangeRatio) == null ? '暂无参考'
          : `${(Number(change.changeRate ?? evidence.priceChangeRatio) * 100).toFixed(2)}%`,
        evidenceSource: evidence.evidenceSource || change.evidenceSource || 'PurchaseOrderHistory' }
    })
}))
const batchConfirmExecutable = computed(() => canExecute.value && !batchResult.value && Boolean(confirmedBy.value.trim())
  && Boolean(batch.value?.items.length)
  && batch.value.items.every(item => ['selected', 'confirmed'].includes(item.status))
  && batch.value.items.some(item => item.status === 'selected'))

function formatMoney(value) { return value == null || value === '' ? '暂无参考' : Number(value).toFixed(2) }
function itemStatusLabel(reviewStatus, status) {
  if (reviewStatus === 'confirmed' || status === 'confirmed') return '已确认'
  if (status === 'selected') return '人工复核完成'
  if (reviewStatus === 'manual_review') return '人工复核中'
  return '待人工决策'
}
function candidateComparisonLabel(supplier) {
  return supplier.priceRank ? `第 ${supplier.priceRank} 名` : '报价比较证据已提供'
}
function candidateQualificationLabel(supplier) {
  return supplier.qualificationStatus || supplier.supplierStatus || supplier.statusLabel || '资格状态待复核'
}
function candidateHistoryLabel(item, supplier) {
  const evidence = (item.priceReferenceContexts || item.priceEvidence || []).find(value =>
    value.supplierCode === supplier.supplierCode && (value.historyPrice != null
      || value.historicalPurchasePrice != null || value.priceReferenceContext || value.priceChangeEvidence))
  if (!evidence) return '暂无历史价格参考'
  const reference = evidence.priceReferenceContext || evidence
  const change = evidence.priceChangeEvidence || {}
  return formatMoney(evidence.historyPrice ?? evidence.historicalPurchasePrice
    ?? change.historyPrice ?? reference.latestPurchasePrice)
}
function initializeDrafts() {
  for (const item of batch.value?.items || []) drafts[item.materialCode] = {
    supplierCode: item.selectedSupplierCode || item.decisionSupplier?.supplierCode || '',
    reason: item.selectionReason || item.decisionReason || '' }
}
function refresh() {
  entryError.value = ''
  const context = supplierRecommendationRouteContextResolverV11428171.resolve()
  if (context.result !== 'PASS') { batch.value = null
    entryError.value = `供应商推荐内部上下文恢复失败：${context.error}`; return }
  handoffFacts.value = supplierRecommendationDataHandoffProviderV1142818.load({ taskId: context.providerTaskId })
  batch.value = handoffFacts.value.batch
  if (handoffFacts.value.result !== 'PASS' || !batch.value) {
    entryError.value = `供应商推荐真实数据承接失败：${handoffFacts.value.error || '业务实例不存在'}`; return
  }
  supplierRecommendationDecisionBatchStoreV11428169.markActive(batch.value.batchId)
  batchRuntimeResult.value = supplierRecommendationDecisionBatchStoreV11428169.findResult(batch.value.batchId)
  batchResult.value = batchRuntimeResult.value?.status === 'confirmed' ? batchRuntimeResult.value : null
  const runtimeHandoff = supplierRecommendationDecisionBatchStoreV11428169.findHandoff(batch.value.batchId)
  batchHandoff.value = runtimeHandoff?.status === 'handoff_ready' ? runtimeHandoff : null
  confirmedBy.value = batchResult.value?.confirmedBy || confirmedBy.value
  initializeDrafts()
}
function itemDecisionExecutable(item) {
  const draft = drafts[item.materialCode] || {}
  return canExecute.value && !batchResult.value && item.status !== 'confirmed'
    && Boolean(draft.supplierCode && draft.reason?.trim())
    && item.supplierCandidates.some(candidate => candidate.supplierCode === draft.supplierCode)
    && item.priceEvidence.length > 0
}
function saveItemDecision(item) {
  const draft = drafts[item.materialCode]
  const result = executeSelectDecisionBatchSupplierV11428169(batch.value.batchId, item.materialCode,
    draft.supplierCode, draft.reason, { permissionContext: stateManager.snapshot() })
  if (result.result !== 'PASS') return ElMessage.error(result.error || '本项决策未保存')
  ElMessage.success(`${item.materialName}的推荐决策已保存`); refresh()
}
function confirmBatch() {
  if (!batchConfirmExecutable.value) return ElMessage.error('请完成全部物料决策并填写确认人')
  const result = executeConfirmSupplierRecommendationDecisionBatchV11428169(batch.value.batchId,
    { confirmedBy: confirmedBy.value }, { permissionContext: stateManager.snapshot() })
  if (result.result !== 'PASS') return ElMessage.error(result.error || '批次确认失败')
  ElMessage.success('供应商推荐决策批次已确认并交接采购订单准入'); refresh()
}
onMounted(refresh)
</script>

<style scoped>
.decision-workbench{display:grid;gap:18px;padding:20px}.page-heading,.section-heading,.confirm-row{display:flex;align-items:center;justify-content:space-between;gap:16px}.page-heading h1{margin:4px 0}.eyebrow,.page-heading p,.section-heading p,.status-note{color:#64748b}.panel{display:grid;gap:16px;padding:18px;border:1px solid #dbe4ee;border-radius:12px;background:#fff}.decision-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.decision-card{display:grid;gap:10px;padding:14px;border:1px solid #e2e8f0;border-radius:10px}.candidate-evidence-list{display:grid;gap:8px}.candidate-evidence-card{display:grid;grid-template-columns:minmax(150px,1.2fr) repeat(4,minmax(120px,1fr));gap:8px;padding:10px;border:1px solid #dbe4ee;border-radius:8px;background:#f8fafc}.candidate-evidence-card span{color:#475569}.confirm-row .el-input{max-width:280px}@media(max-width:900px){.page-heading,.section-heading,.confirm-row{align-items:flex-start;flex-direction:column}.decision-grid{grid-template-columns:1fr}.candidate-evidence-card{grid-template-columns:1fr}.confirm-row .el-input{max-width:none}}
</style>
