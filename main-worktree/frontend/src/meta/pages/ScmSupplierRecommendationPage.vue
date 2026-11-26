<template>
  <main class="supplier-recommendation-page" data-page-code="supplier-recommendation"
    :data-page-name="businessName.pageTitle" data-module-code="SCM"
    data-business-object="SupplierRecommendationDecision">
    <header class="page-heading">
      <div><p class="eyebrow">SCM · 采购决策</p><h1>{{ businessName.pageTitle }}</h1>
        <p>承接报价比较事实，由采购人员逐物料确认推荐供应商；系统不自动推荐、不创建采购订单。</p></div>
      <el-button @click="refreshFacts">刷新</el-button>
    </header>

    <section v-if="currentBatchContext" class="panel batch-context"
      data-acceptance-region="supplier-recommendation-batch-context">
      <div class="section-heading"><div><h2>批量推荐任务</h2>
        <p>批次 {{ currentBatchContext.batchId }} 仅管理任务；下方每项分别绑定一个独立推荐实例。</p></div>
        <el-tag effect="plain">{{ currentBatchContext.taskCount }} 个推荐任务</el-tag></div>
      <div class="batch-context__items">
        <el-button v-for="task in currentBatchTasks" :key="task.taskId"
          :type="task.taskId === activeTaskId ? 'primary' : 'default'"
          :data-task-id="task.taskId" :data-runtime-context-id="task.runtimeContextId"
          @click="openBatchTask(task.taskId)">
          {{ task.materialCode }} · {{ task.materialName }} · {{ taskStatusLabel(task) }}
        </el-button>
      </div>
    </section>

    <section class="panel" data-acceptance-region="business-context">
      <div class="section-heading"><div><h2>一、业务上下文</h2><p>生产运行优先承接采购核价真实交接；演示模式仅可加载隔离的只读验收事实。</p></div>
        <el-select v-model="selectedPreparationNo" placeholder="由采购核价入口锁定业务实例" disabled>
          <el-option v-for="record in providerFacts.records" :key="record.recommendationPreparationNo"
            :label="`${record.sourceInquiryNo} · ${record.statusLabel}`"
            :value="record.recommendationPreparationNo" />
        </el-select></div>
      <el-empty v-if="!providerFacts.recordCount" :description="providerFacts.emptyMessage" />
      <el-alert v-else-if="entryResolution.result === 'FAIL'" type="error" :closable="false"
        title="缺少有效供应商推荐任务，请从采购核价或流程中心任务入口进入。" />
      <div v-else-if="currentRecord" class="facts">
        <article><span>采购核价编号</span><strong>{{ currentRecord.priceApprovalNo || currentRecord.priceApprovalId || '-' }}</strong></article>
        <article><span>当前报价比较</span><strong>{{ currentRecord.runtimeContext?.quoteComparisonId || currentRecord.sourceQuoteComparisonId }}</strong></article>
        <article><span>当前核价物料</span><strong>{{ currentRecord.runtimeContext?.materialName || '-' }}（{{ currentRecord.runtimeContext?.materialCode || '-' }}）</strong></article>
        <article><span>来源询价</span><strong>{{ currentRecord.sourceInquiryNo }}</strong></article>
        <article><span>来源采购申请</span><strong>{{ currentRecord.sourceRequestNo }}</strong></article>
        <article><span>物料数量</span><strong>{{ currentRecord.materialCount }}</strong></article>
        <article><span>候选供应商</span><strong>{{ currentRecord.supplierCount }}</strong></article>
        <article><span>事实来源</span><strong>{{ currentRecord.preparation.factScope }}</strong></article>
        <article><span>推荐任务</span><strong>{{ currentTask?.taskId || '-' }}</strong></article>
        <article><span>当前办理人</span><strong>{{ currentTask?.currentAssignee || '-' }}</strong></article>
        <article><span>当前状态</span><PceBusinessStatus :status-code="currentRecord.recommendationStatus"
          :status-label="currentRecord.statusLabel" source="provider" /></article>
      </div>
      <el-alert v-if="currentRecord && !singleInstanceValid" type="error" :closable="false"
        title="当前推荐任务包含多个物料，已阻断人工决策；请返回批量任务列表逐项处理。" />
      <el-button v-if="currentRecord && !currentRecord.context" type="primary"
        data-process-action="CREATE_RECOMMENDATION_DECISION_CONTEXT"
        :disabled="!actionExecutable('CREATE_RECOMMENDATION_DECISION_CONTEXT')" @click="createContext">
        建立推荐决策上下文</el-button>
    </section>

    <section class="panel" data-acceptance-region="comparison-evidence">
      <div class="section-heading"><div><h2>二、单物料供应商报价比较</h2>
        <p>当前任务只显示一个物料；下表每行代表一家供应商的报价，不代表多个商品。</p></div></div>
      <el-descriptions v-if="currentRecord" :column="2" border data-acceptance-id="single-material-summary">
        <el-descriptions-item label="物料编码">{{ currentRecord.runtimeContext?.materialCode }}</el-descriptions-item>
        <el-descriptions-item label="物料名称">{{ currentRecord.runtimeContext?.materialName }}</el-descriptions-item>
      </el-descriptions>
      <el-table :data="evidenceRows" border empty-text="尚未建立推荐决策上下文">
        <el-table-column type="index" label="序号" width="72" fixed="left" />
        <el-table-column prop="supplierName" label="供应商" min-width="160" />
        <el-table-column prop="unitPrice" label="供应商报价" width="140" />
        <el-table-column prop="priceRankLabel" label="价格排名" width="120" />
        <el-table-column prop="deliveryDate" label="交付日期" width="130" />
        <el-table-column prop="deliveryRankLabel" label="交期排名" width="120" />
        <el-table-column prop="validityStatusLabel" label="有效期状态" width="140" />
      </el-table>
    </section>

    <section class="panel" data-acceptance-region="historical-price-reference" data-read-only="true">
      <div class="section-heading"><div><h2>三、历史价格参考</h2>
        <p>PriceReferenceContext 仅提供历史价格证据，不自动选择最低价供应商。</p></div></div>
      <el-table :data="priceReferenceRows" border empty-text="暂无历史价格参考">
        <el-table-column prop="materialName" label="物料" min-width="160" />
        <el-table-column prop="supplierName" label="供应商" min-width="170" />
        <el-table-column prop="materialTypeLabel" label="物料核价类型" width="140" />
        <el-table-column prop="historicalLowestPriceLabel" label="历史最低采购价" width="150" />
        <el-table-column prop="latestPriceLabel" label="最近采购价格" width="140" />
        <el-table-column prop="lastPurchaseDateLabel" label="最近采购日期" width="140" />
        <el-table-column prop="currentQuoteLabel" label="当前报价" width="120" />
        <el-table-column prop="changeRateLabel" label="价格变化比例" width="140" />
      </el-table>
    </section>

    <section class="panel" data-acceptance-region="recommendation-candidates">
      <div class="section-heading"><div><h2>四、供应商推荐候选</h2>
        <p>候选来自报价比较与供应商主数据资格事实。</p></div></div>
      <PceEnterpriseListTable ref="tableRef" :contract="enterpriseListContract"
        page-id="supplier-recommendation" table-id="supplier-recommendation-candidates"
        :rows="candidateRows" :table-rows="filteredRows" :filter-schema="filterSchema" :filters="filters"
        :quick-search="quickSearch" :advanced-visible="advancedVisible" :selected-count="selectedRows.length"
        :active-filter-count="activeFilterCount" :sort-text="sortText" primary-field="supplierCode"
        primary-label="供应商编码" :primary-width="170" min-width="1460px"
        scroll-acceptance-id="supplier-recommendation-horizontal-scroll" :action-width="110"
        @update:quick-search="quickSearch = $event" @search="appliedSearch = quickSearch"
        @toggle-advanced="advancedVisible = !advancedVisible" @clear-filters="clearFilters"
        @clear-sort="clearSort" @export-current="exportCurrent" @clear-selection="clearSelection"
        @update-filter="(field, value) => filters[field] = value" @selection-change="selectedRows = $event"
        @sort-change="handleSort">
        <template #columns>
          <el-table-column prop="supplierName" label="供应商名称" width="180" />
          <el-table-column prop="supplierStatusLabel" label="供应商状态" width="130" />
          <el-table-column prop="supplierCategoryLabel" label="供应商分类" width="140" />
          <el-table-column prop="qualificationStatusLabel" label="资格状态" width="140" />
          <el-table-column prop="quotePriceLabel" label="当前报价" width="130" />
          <el-table-column prop="priceRankLabel" label="价格依据" width="130" />
          <el-table-column prop="deliveryRankLabel" label="交期依据" width="130" />
        </template>
        <template #actions="{ row }">
          <el-button link type="primary" data-process-action="SELECT_RECOMMENDATION_SUPPLIER"
            :disabled="!actionExecutable('SELECT_RECOMMENDATION_SUPPLIER', { candidate: row })"
            @click="selectCandidate(row)">选择供应商</el-button>
        </template>
      </PceEnterpriseListTable>
    </section>

    <section class="panel" data-acceptance-region="recommendation-evidence">
      <div class="section-heading"><div><h2>五、推荐证据</h2>
        <p>人工确认将引用所选物料与供应商对应的比较证据。</p></div>
        <div class="actions">
          <el-button data-process-action="START_RECOMMENDATION_EVALUATION"
            :disabled="!actionExecutable('START_RECOMMENDATION_EVALUATION')" @click="startEvaluation">整理推荐依据</el-button>
          <el-button type="primary" data-process-action="PREPARE_RECOMMENDATION_DECISION"
            :disabled="!actionExecutable('PREPARE_RECOMMENDATION_DECISION')" @click="prepareDecision">准备人工决策</el-button>
        </div></div>
      <el-alert title="价格、交期、有效期与资格信息仅作为人工判断依据，不产生系统推荐结果。"
        type="info" :closable="false" show-icon />
    </section>

    <section class="panel" data-acceptance-region="manual-confirmation">
      <div class="section-heading"><div><h2>六、人工确认区域</h2>
        <p>每个物料必须由采购人员从当前报价候选中选择供应商并填写推荐理由；资格状态仅作为证据展示。</p></div>
        <el-button data-process-action="START_MANUAL_REVIEW" :disabled="!actionExecutable('START_MANUAL_REVIEW')"
          @click="startManualReview">开始人工确认</el-button></div>
      <el-descriptions :column="3" border data-acceptance-id="current-recommendation-selection">
        <el-descriptions-item label="推荐供应商">{{ currentRecommendation?.supplierName || '尚未人工选择' }}</el-descriptions-item>
        <el-descriptions-item label="供应商报价">{{ currentRecommendation ? currentRecommendation.supplierQuote.toFixed(2) : '-' }}</el-descriptions-item>
        <el-descriptions-item label="选择方式">{{ currentRecommendation ? '人工选择' : '-' }}</el-descriptions-item>
      </el-descriptions>
      <div class="manual-grid">
        <article v-for="material in materialOptions" :key="material.materialCode" class="manual-card">
          <strong>{{ material.materialCode }} · {{ material.materialName }}</strong>
          <div class="candidate-action-list">
            <el-button v-for="candidate in material.candidates" :key="candidate.supplierCode"
              :type="manualSelections[material.materialCode] === candidate.supplierCode ? 'primary' : 'default'"
              data-process-action="SELECT_RECOMMENDATION_CANDIDATE"
              :disabled="!actionExecutable('SELECT_RECOMMENDATION_SUPPLIER', { candidate })"
              @click="selectCandidate(candidate)">
              选择 {{ candidate.supplierName }} · {{ candidate.quotePriceLabel }}
            </el-button>
          </div>
          <el-select v-model="manualSelections[material.materialCode]" placeholder="选择推荐供应商"
            :disabled="!canEditManualDecision" @change="selectCandidateByCode(material, $event)">
            <el-option v-for="candidate in material.candidates" :key="candidate.supplierCode"
              :label="`${candidate.supplierCode} · ${candidate.supplierName} · ${candidate.qualificationStatusLabel}`"
              :value="candidate.supplierCode" />
          </el-select>
        </article>
      </div>
      <el-input v-model="recommendationReason" type="textarea" :rows="3" placeholder="填写人工推荐理由"
        :disabled="!canEditManualDecision" />
      <div class="confirm-row"><el-input v-model="confirmedBy" placeholder="确认人" :disabled="!canEditManualDecision" />
        <el-button type="success" data-process-action="CONFIRM_RECOMMENDATION_DECISION"
          :disabled="!canConfirm" @click="confirmDecision">确认推荐结果</el-button></div>
      <div v-if="currentDecision" class="confirmation-facts" data-read-only="true">
        <span>确认人：{{ currentDecision.manualReviewer }}</span>
        <span>确认时间：{{ currentDecision.manualReviewedAt || currentDecision.manualConfirmedAt }}</span>
        <span>确认状态：人工确认完成（不代表采购订单已生成）</span>
      </div>
      <el-table :data="currentDecision?.selectedRecommendations || []" border empty-text="尚未确认推荐结果">
        <el-table-column prop="materialName" label="物料" min-width="150" />
        <el-table-column prop="supplierName" label="人工确认供应商" min-width="180" />
        <el-table-column prop="recommendationReason" label="推荐理由" min-width="260" />
      </el-table>
    </section>

    <section class="panel next-panel" data-acceptance-region="next-action">
      <div><span>当前节点</span><strong>{{ businessName.pageTitle }}</strong></div>
      <div><span>当前状态</span><strong>{{ currentRecord?.statusLabel || '未选择决策准备' }}</strong></div>
      <div><span>下一节点</span><strong>采购订单准入</strong></div>
      <div><span>下一动作</span><strong>{{ nextActionLabel }}</strong></div>
      <el-button type="primary" data-process-action="PREPARE_PURCHASE_ORDER_GATE_HANDOFF"
        :disabled="!actionExecutable('PREPARE_PURCHASE_ORDER_GATE_HANDOFF')" @click="prepareGateHandoff">准备准入交接</el-button>
      <el-button :disabled="currentStatus !== 'handoff_ready' || !currentBatchContext?.batchId"
        @click="router.push({ path: '/scm/purchase-order-gate', query: { batchId: currentBatchContext.batchId } })">进入采购订单准入</el-button>
    </section>
  </main>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { resolveBusinessName } from '@/meta/governance/businessNameRegistry.js'
import PceBusinessStatus from '@/meta/components/PceBusinessStatus.vue'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import { createPceEnterpriseListContract, usePceEnterpriseListRuntime } from '@/meta/runtime/pceEnterpriseListContract.js'
import { supplierRecommendationDecisionProviderV1142816 } from '@/meta/providers/supplierRecommendationDecisionProviderV1142816.js'
import { supplierRecommendationRuntimeStoreV1142811 } from '@/meta/runtime/supplierRecommendationRuntimeStoreV1142811.js'
import { executeConfirmRecommendationDecision, executeCreateRecommendationDecisionContext,
  executePreparePurchaseOrderGateHandoff, executePrepareRecommendationDecision,
  executeStartManualReview, executeStartRecommendationEvaluation } from '@/meta/runtime/supplierRecommendationActionRuntimeV1142811.js'
import { resolveSupplierRecommendationEntryV11428163,
  resolveSupplierRecommendationRuntimeContextIdV11428164 } from '@/meta/process/scm/supplierRecommendation/supplierRecommendationRuntimeContextV11428163.js'
import { supplierRecommendationBatchStoreV11428165 } from '@/meta/process/scm/supplierRecommendation/supplierRecommendationBatchContextV11428165.js'
import { createSupplierRecommendationCurrentSelectionV11428166 } from '@/meta/process/scm/supplierRecommendation/supplierRecommendationCurrentSelectionV11428166.js'
import { supplierRecommendationTaskStoreV11428167 } from '@/meta/process/scm/supplierRecommendation/supplierRecommendationTaskRuntimeV11428167.js'
import { supplierRecommendationTaskProcessCenterProviderV11428167 } from '@/meta/process/scm/supplierRecommendation/supplierRecommendationTaskProcessCenterContextV11428167.js'
import { evaluateSupplierRecommendationActionExecutabilityV11428168 } from '@/meta/process/scm/supplierRecommendation/supplierRecommendationActionExecutabilityV11428168.js'
import { stateManager } from '@/meta/runtime/stateManager.js'

const businessName = resolveBusinessName('supplier-recommendation')
const route = useRoute()
const router = useRouter()
const providerFacts = ref({ records: [], contexts: [], approvalContexts: [], decisions: [], recordCount: 0 })
const selectedPreparationNo = ref('')
const recommendationReason = ref('')
const confirmedBy = ref('')
const currentRecommendation = ref(null)
const manualSelections = reactive({})
const taskRevision = ref(0)
const entryResolution = ref({ result: 'FAIL', entryKey: '', runtimeContextId: '', record: null })
const activeTaskId = computed(() => String(route.query.taskId || ''))
const currentTask = computed(() => {
  void taskRevision.value
  return supplierRecommendationTaskStoreV11428167.findById(activeTaskId.value)
})
const activeRuntimeContextId = computed(() => String(currentTask.value?.runtimeContextId || ''))
const currentBatchContext = computed(() => route.query.batchId
  ? supplierRecommendationBatchStoreV11428165.findContextById(route.query.batchId) : null)
const currentBatchTasks = computed(() => currentBatchContext.value
  ? supplierRecommendationBatchStoreV11428165.listTasks(currentBatchContext.value.batchId)
    .map(taskIndex => ({ ...taskIndex,
      ...supplierRecommendationTaskStoreV11428167.findByRuntimeContextId(taskIndex.runtimeContextId) }))
    .filter(task => task.taskId) : [])
const currentRecord = computed(() => providerFacts.value.records.find(item =>
  item.recommendationPreparationNo === selectedPreparationNo.value
    && (entryResolution.value.runtimeContextId
      ? item.runtimeContext?.runtimeContextNo === entryResolution.value.runtimeContextId
      : item.entryKey === entryResolution.value.entryKey)) || entryResolution.value.record || null)
const currentContext = computed(() => currentRecord.value?.recommendationContext || currentRecord.value?.context || null)
const currentDecision = computed(() => currentRecord.value?.decision || null)
const currentStatus = computed(() => currentRecord.value?.recommendationStatus || '')
const approvalContext = computed(() => providerFacts.value.approvalContexts.find(item =>
  item.decisionContextNo === currentContext.value?.decisionContextNo) || null)
const rawEvidence = computed(() => currentContext.value?.evidence || (currentRecord.value?.preparation?.comparisons || []).map(item => ({
  ...item, quoteBasis: { unitPrice: item.unitPrice, totalPrice: item.totalPrice }, priceRank: item.comparisonResult.priceRank,
  deliveryBasis: { deliveryDate: item.deliveryDate, rank: item.comparisonResult.deliveryRank },
  validityStatus: item.comparisonResult.validityStatus })))
const evidenceRows = computed(() => rawEvidence.value.map(item => ({ ...item,
  unitPrice: item.quoteBasis.unitPrice, deliveryDate: item.deliveryBasis.deliveryDate,
  priceRankLabel: `第 ${item.priceRank} 名`, deliveryRankLabel: `第 ${item.deliveryBasis.rank} 名`,
  validityStatusLabel: item.validityStatus === 'valid' ? '有效' : '已失效' })))
const priceReferenceRows = computed(() => (currentRecord.value?.priceReferenceContexts || []).map(item => ({
  ...item,
  materialTypeLabel: item.materialPriceContextType === 'existing_material' ? '老物料' : '新物料',
  historicalLowestPriceLabel: item.historicalLowestPurchasePrice == null ? '暂无参考'
    : Number(item.historicalLowestPurchasePrice).toFixed(2),
  latestPriceLabel: item.historicalPurchasePrice == null ? '暂无参考'
    : Number(item.historicalPurchasePrice).toFixed(2),
  lastPurchaseDateLabel: item.lastPurchaseDate || '暂无参考',
  currentQuoteLabel: item.currentQuote == null ? '-' : Number(item.currentQuote).toFixed(2),
  changeRateLabel: item.priceChangeRatio == null ? '暂无参考'
    : `${(Number(item.priceChangeRatio) * 100).toFixed(2)}%`,
})))
const sourceCandidates = computed(() => currentContext.value?.supplierCandidates ||
  (currentRecord.value?.preparation?.comparisons || []).map(item => {
    const qualification = currentRecord.value.preparation.supplierQualificationFacts?.find(fact =>
      fact.supplierCode === item.supplierCode) || {}
    return { materialCode: item.materialCode, materialName: item.materialName,
      supplierCode: item.supplierCode, supplierName: item.supplierName,
      supplierStatus: qualification.supplierStatus || 'unverified',
      supplierCategory: qualification.supplierCategory || 'unclassified',
      qualificationStatus: qualification.qualificationStatus || 'unverified' }
  }))
const candidateRows = computed(() => sourceCandidates.value.map(candidate => {
  const evidence = rawEvidence.value.find(item => item.materialCode === candidate.materialCode
    && item.supplierCode === candidate.supplierCode)
  return { ...candidate,
    quotePrice: Number(candidate.quotePrice ?? evidence?.quoteBasis?.unitPrice ?? 0),
    supplierStatusLabel: ['active', 'enabled'].includes(candidate.supplierStatus) ? '有效' : '待核验',
    supplierCategoryLabel: candidate.supplierCategory === 'unclassified' ? '未分类' : candidate.supplierCategory,
    qualificationStatusLabel: candidate.qualificationStatus === 'qualified' ? '资格有效'
      : candidate.qualificationStatus === 'restricted' ? '资格受限' : '资格待核验',
    quotePriceLabel: evidence?.quoteBasis?.unitPrice == null ? '-' : Number(evidence.quoteBasis.unitPrice).toFixed(2),
    priceRankLabel: `第 ${evidence?.priceRank || '-'} 名`,
    deliveryRankLabel: `第 ${evidence?.deliveryBasis?.rank || '-'} 名` }
}))
const rows = computed(() => candidateRows.value)
const materialOptions = computed(() => [...new Map(candidateRows.value.map(item => [item.materialCode,
  { materialCode: item.materialCode, materialName: item.materialName,
    candidates: candidateRows.value.filter(candidate => candidate.materialCode === item.materialCode) }])).values()])
const singleInstanceValid = computed(() => materialOptions.value.length === 1
  && materialOptions.value[0]?.materialCode === currentRecord.value?.runtimeContext?.materialCode)
function actionEvaluation(actionCode, extraFacts = {}) {
  const selections = materialOptions.value.map(item => ({ materialCode: item.materialCode,
    supplierCode: manualSelections[item.materialCode] }))
  return evaluateSupplierRecommendationActionExecutabilityV11428168({ actionCode,
    state: currentStatus.value || 'comparison_ready', permissionContext: stateManager.snapshot(),
    visible: Boolean(currentRecord.value) && singleInstanceValid.value,
    facts: { task: currentTask.value, runtimeContext: currentRecord.value?.runtimeContext,
      preparation: currentRecord.value?.preparation, context: currentContext.value,
      approvalContext: approvalContext.value, decision: currentDecision.value,
      input: { selections, reason: recommendationReason.value, confirmedBy: confirmedBy.value },
      ...extraFacts } })
}
const actionExecutable = (actionCode, extraFacts = {}) => actionEvaluation(actionCode, extraFacts).executable
const canEditManualDecision = computed(() => actionExecutable('SELECT_RECOMMENDATION_SUPPLIER',
  { candidate: candidateRows.value[0] }))
const canConfirm = computed(() => currentRecommendation.value?.runtimeContextId === activeRuntimeContextId.value
  && actionExecutable('CONFIRM_RECOMMENDATION_DECISION'))
const nextActionLabel = computed(() => ({ created: '整理推荐依据', evaluating: '准备人工推荐决策',
  decision_prepared: '开始人工确认', manual_review: '确认推荐结果', confirmed: '准备采购订单准入交接',
  handoff_ready: '进入采购订单准入' })[currentStatus.value] || '建立推荐决策上下文')
const filterSchema = Object.freeze([
  Object.freeze({ field: 'materialCode', label: '物料编码', filterType: 'text' }),
  Object.freeze({ field: 'supplierCode', label: '供应商编码', filterType: 'text' }),
  Object.freeze({ field: 'qualificationStatus', label: '资格状态', filterType: 'select', options: Object.freeze([
    Object.freeze({ label: '资格有效', value: 'qualified' }), Object.freeze({ label: '资格受限', value: 'restricted' }),
    Object.freeze({ label: '资格待核验', value: 'unverified' })]) }),
])
const enterpriseListContract = createPceEnterpriseListContract({ pageCode: 'supplier-recommendation',
  pageType: 'list', title: businessName.pageTitle, moduleCode: 'SCM_SUPPLIER_RECOMMENDATION' })
const { selectedRows, quickSearch, appliedSearch, advancedVisible, filters, tableRef, activeFilterCount,
  sortText, filteredRows, clearFilters, clearSort, clearSelection, handleSort, exportCurrent } =
  usePceEnterpriseListRuntime({ rows, filterSchema, pageCode: 'supplier-recommendation',
    searchFields: ['supplierCode', 'supplierName', 'materialCode', 'materialName'],
    exportFileName: 'supplier-recommendation-candidates.csv', exportColumns: [
      { field: 'materialCode', label: '物料编码' }, { field: 'supplierCode', label: '供应商编码' },
      { field: 'qualificationStatusLabel', label: '资格状态' }] })

function resolvePageEntry() {
  // V16.3 composite resolver remains imported for model regression only; it is not a page entry.
  void resolveSupplierRecommendationEntryV11428163
  if (!activeTaskId.value || !currentTask.value || !activeRuntimeContextId.value) {
    return { result: 'FAIL', error: 'SUPPLIER_RECOMMENDATION_TASK_ENTRY_REQUIRED',
      entryKey: '', runtimeContextId: '', record: null }
  }
  return resolveSupplierRecommendationRuntimeContextIdV11428164(
    providerFacts.value.records, activeRuntimeContextId.value)
}
function refreshFacts() {
  providerFacts.value = supplierRecommendationDecisionProviderV1142816.load()
  entryResolution.value = resolvePageEntry()
  selectedPreparationNo.value = entryResolution.value.record?.recommendationPreparationNo || ''
  if (entryResolution.value.result === 'PASS' && currentTask.value) {
    const status = entryResolution.value.record?.recommendationStatus || currentTask.value.status
    const currentAssignee = entryResolution.value.record?.decision?.confirmedBy
      || entryResolution.value.record?.decision?.manualReviewer || currentTask.value.currentAssignee
    if (status !== currentTask.value.status || currentAssignee !== currentTask.value.currentAssignee) {
      supplierRecommendationTaskStoreV11428167.update(currentTask.value.taskId,
        { status, currentAssignee })
      taskRevision.value += 1
    }
    supplierRecommendationTaskProcessCenterProviderV11428167.markActive(currentTask.value.taskId)
  }
}
function taskStatusLabel(task) {
  const record = providerFacts.value.records.find(item => item.runtimeContext?.runtimeContextNo === task.runtimeContextId)
  return record?.statusLabel || '待人工处理'
}
async function openBatchTask(taskId) {
  recommendationReason.value = ''
  confirmedBy.value = ''
  currentRecommendation.value = null
  Object.keys(manualSelections).forEach(key => delete manualSelections[key])
  await router.replace({ path: route.path, query: { ...route.query, taskId } })
  refreshFacts()
}
function selectCandidate(candidate) {
  const evaluation = actionEvaluation('SELECT_RECOMMENDATION_SUPPLIER', { candidate })
  if (!evaluation.executable) return ElMessage.error(evaluation.reason || '当前动作不可执行')
  try {
    const selection = createSupplierRecommendationCurrentSelectionV11428166({
      runtimeContext: currentRecord.value?.runtimeContext, candidate,
    })
    manualSelections[selection.materialCode] = selection.supplierCode
    currentRecommendation.value = selection
    supplierRecommendationTaskStoreV11428167.update(activeTaskId.value,
      { status: 'manual_review' })
    taskRevision.value += 1
    ElMessage.success(`已人工选择 ${selection.supplierName}`)
  } catch (error) { ElMessage.error(error.message || '候选供应商选择失败') }
}
function selectCandidateByCode(material, supplierCode) {
  const candidate = material.candidates.find(item => item.supplierCode === supplierCode)
  if (candidate) selectCandidate(candidate)
}
function notify(result, message) { if (result.result === 'PASS') ElMessage.success(message); else ElMessage.error(result.error || result.reason || '操作未完成'); refreshFacts() }
function executeAllowed(actionCode, executor, message) {
  const evaluation = actionEvaluation(actionCode)
  if (!evaluation.executable) return ElMessage.error(evaluation.reason || '当前动作不可执行')
  return notify(executor(), message)
}
function createContext() { return executeAllowed('CREATE_RECOMMENDATION_DECISION_CONTEXT',
  () => executeCreateRecommendationDecisionContext(currentRecord.value.preparation), '推荐决策上下文已建立') }
function startEvaluation() { return executeAllowed('START_RECOMMENDATION_EVALUATION',
  () => executeStartRecommendationEvaluation(currentContext.value), '推荐依据整理已开始') }
function prepareDecision() { return executeAllowed('PREPARE_RECOMMENDATION_DECISION',
  () => executePrepareRecommendationDecision(currentContext.value), '人工推荐决策已准备') }
function startManualReview() { return executeAllowed('START_MANUAL_REVIEW',
  () => executeStartManualReview(currentContext.value), '已进入人工确认') }
function confirmDecision() {
  const selections = materialOptions.value.map(item => ({ materialCode: item.materialCode,
    supplierCode: manualSelections[item.materialCode] }))
  const evaluation = actionEvaluation('CONFIRM_RECOMMENDATION_DECISION')
  if (!evaluation.executable) return ElMessage.error(evaluation.reason || '推荐确认条件不完整')
  const result = executeConfirmRecommendationDecision(currentContext.value, approvalContext.value,
    { selections, reason: recommendationReason.value, confirmedBy: confirmedBy.value })
  if (result.result === 'PASS') supplierRecommendationTaskStoreV11428167.update(activeTaskId.value,
    { status: 'confirmed', currentAssignee: confirmedBy.value })
  if (result.result === 'PASS') taskRevision.value += 1
  notify(result, '推荐结果已由人工确认')
}
function prepareGateHandoff() {
  const evaluation = actionEvaluation('PREPARE_PURCHASE_ORDER_GATE_HANDOFF')
  if (!evaluation.executable) return ElMessage.error(evaluation.reason || '准入交接条件不完整')
  const result = executePreparePurchaseOrderGateHandoff(currentDecision.value,
    supplierRecommendationRuntimeStoreV1142811)
  if (result.result === 'PASS') supplierRecommendationTaskStoreV11428167.update(activeTaskId.value,
    { status: 'handoff_ready' })
  if (result.result === 'PASS') taskRevision.value += 1
  notify(result, '采购订单准入交接已准备；未创建采购订单')
}
onMounted(refreshFacts)
watch(() => route.query.taskId, (value, previous) => {
  if (value !== previous) refreshFacts()
})
</script>

<style scoped>
.supplier-recommendation-page{display:grid;gap:18px;padding:20px}.page-heading,.section-heading,.next-panel,.confirm-row{display:flex;align-items:center;justify-content:space-between;gap:16px}.page-heading h1{margin:4px 0}.eyebrow,.page-heading p,.section-heading p,.facts span,.next-panel span,.readonly-mark{color:#64748b}.panel{display:grid;gap:16px;padding:18px;border:1px solid #dbe4ee;border-radius:12px;background:#fff}.batch-context__items,.candidate-action-list{display:flex;flex-wrap:wrap;gap:10px}.facts{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px}.facts article,.next-panel div{display:grid;gap:5px}.manual-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.manual-card{display:grid;gap:10px;padding:14px;border:1px solid #e2e8f0;border-radius:10px}.actions{display:flex;gap:10px}.confirm-row .el-input{max-width:280px}.confirmation-facts{display:flex;flex-wrap:wrap;gap:18px;color:#475467}@media(max-width:900px){.page-heading,.section-heading,.next-panel,.confirm-row{align-items:flex-start;flex-direction:column}.facts,.manual-grid{grid-template-columns:1fr}.confirm-row .el-input{max-width:none}}
</style>
