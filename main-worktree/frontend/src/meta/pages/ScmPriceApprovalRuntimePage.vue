<template>
  <main class="price-approval-runtime" data-page-code="price-approval"
    data-business-object="PriceApprovalPreparation" :data-mode="runtime.dataMode"
    data-fact-source="QuoteComparisonFact">
    <section class="operation-guide" data-acceptance-id="price-approval-operation-guide">
      <h2>页面操作指引</h2>
      <p>用途：根据报价比较结果进行人工核价。</p>
      <ol>
        <li>查看报价依据。</li><li>比较供应商。</li><li>填写核价意见。</li>
        <li>确认供应商。</li><li>提交审批。</li><li>进入供应商推荐。</li>
      </ol>
      <el-alert title="系统不自动选择最低报价、不自动推荐供应商、不自动审批，也不创建采购订单。"
        type="warning" :closable="false" show-icon />
    </section>

    <section class="runtime-summary">
      <el-descriptions :column="4" border>
        <el-descriptions-item label="运行模式">{{ runtime.dataMode }}</el-descriptions-item>
        <el-descriptions-item label="事实来源">{{ resolveBusinessSourceTypeLabel('QuoteComparisonFact') }}</el-descriptions-item>
        <el-descriptions-item label="记录数">{{ runtime.resultCount }}</el-descriptions-item>
        <el-descriptions-item label="加载状态">{{ runtime.factLoadStatus }}</el-descriptions-item>
      </el-descriptions>
      <el-alert v-if="runtime.factLoadStatus === 'blocked'" :title="runtime.errorMessage"
        type="error" :closable="false" show-icon />
      <el-alert v-else-if="runtime.dataMode === 'canary_acceptance'"
        :title="`Canary链路：${runtime.sourceMapping?.quoteComparisonNo || '-'} → ${runtime.sourceMapping?.priceApprovalPreparationNo || '-'}`"
        type="info" :closable="false" show-icon />
      <el-alert v-if="runtime.sourceConsistency?.status === 'PASS'"
        :title="`供应商正式报价来源已匹配；可追溯报价明细 ${runtime.sourceConsistency.sessionAcceptancePreparationCount} 条，数据库写入 0。`"
        type="success" :closable="false" show-icon data-acceptance-id="PRICE_SOURCE_MATCH_001" />
      <el-alert v-if="runtime.sourceConsistency?.batchArchiveStatus === 'BLOCKED'"
        :title="`批量正式报价归档未就绪：真实来源 ${runtime.sourceConsistency.batchArchiveEligibleCount}/${runtime.sourceConsistency.batchArchiveRequiredCount}；历史验收事实不得补齐。`"
        type="warning" :closable="false" show-icon data-acceptance-id="PRICE_BATCH_SOURCE_MATCH_001" />
    </section>

    <section v-if="runtime.dataMode === 'production'" class="pending-comparisons"
      data-acceptance-id="quote-comparison-fact-handoff">
      <div class="section-heading">
        <div>
          <h2>待生成核价准备任务</h2>
          <p>仅显示 QuoteComparisonFact 已存在、但尚未生成 PriceApprovalPreparation 的数据；生成后进入下方采购核价任务列表。</p>
        </div>
        <el-tag type="info">{{ runtime.availableComparisonCount }} 条</el-tag>
      </div>
      <el-alert v-if="runtime.availableComparisons.some(item => item.factOrigin === 'legacy_verified_fact')"
        title="历史事实不能直接归档；经本次人工核价、选择供应商并确认报价后，可形成新的企业有效价格。"
        type="warning" :closable="false" show-icon />
      <el-table v-if="runtime.availableComparisons.length" :data="runtime.availableComparisons" border>
        <el-table-column prop="quoteComparisonNo" label="报价比较编号" min-width="200" />
        <el-table-column prop="factOriginDisplay" label="事实来源" min-width="230" />
        <el-table-column prop="materialCode" label="物料编码" min-width="140" />
        <el-table-column prop="materialName" label="物料名称" min-width="180" />
        <el-table-column prop="quantity" label="数量" min-width="110" />
        <el-table-column prop="supplierCount" label="供应商数量" min-width="120" />
        <el-table-column prop="lowestPrice" label="最低报价参考" min-width="140" />
        <el-table-column label="人工动作" fixed="right" width="160">
          <template #default="scope">
            <el-button type="primary" link :loading="creatingComparisonNo === scope.row.quoteComparisonNo"
              @click="createPreparation(scope.row)">生成核价准备</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else description="当前暂无待生成核价准备任务。" />
    </section>

    <section class="price-approval-list" data-acceptance-id="price-approval-lifecycle-list">
      <div class="section-heading">
        <div>
          <h2>采购核价任务列表</h2>
          <p>永久显示全部已生成的 PriceApprovalPreparation；状态变化只推进生命周期，完成或拒绝后均不删除、不隐藏。</p>
        </div>
        <div class="lifecycle-summary" aria-label="核价生命周期统计">
          <el-tag>草稿 {{ lifecycleCounts.draft }}</el-tag>
          <el-tag type="warning">核价中 {{ lifecycleCounts.reviewing }}</el-tag>
          <el-tag type="success">已完成 {{ lifecycleCounts.completed }}</el-tag>
          <el-tag type="danger">已拒绝 {{ lifecycleCounts.rejected }}</el-tag>
        </div>
      </div>
      <div class="price-approval-batch-actions" data-acceptance-id="price-approval-batch-actions">
        <span>已选择 {{ selectedRows.length }} 条</span>
        <el-button :disabled="!selectedRows.length" @click="openBatchView">批量查看</el-button>
        <el-button type="primary" :disabled="!selectedEditableCount" @click="openBatchReview">
          批量进入核价
        </el-button>
        <el-button type="success" :disabled="!selectedArchiveCount" @click="openBatchArchive">
          批量确认报价（{{ selectedArchiveCount }}）
        </el-button>
        <span class="batch-hint">可进入核价 {{ selectedEditableCount }} 条；批量入口不会自动核价。</span>
      </div>
      <PceEnterpriseListTable ref="tableRef" :contract="enterpriseListContract"
      page-id="price-approval" table-id="price-approval-runtime-main"
      :rows="rows" :table-rows="filteredRows" :filter-schema="filterSchema" :filters="filters"
      :quick-search="quickSearch" :advanced-visible="advancedVisible" :selected-count="selectedRows.length"
      :active-filter-count="activeFilterCount" :sort-text="sortText" primary-field="approvalPrepareNo"
      primary-label="核价准备编号" :primary-width="220" min-width="1420px"
      scroll-acceptance-id="price-approval-runtime-horizontal-scroll"
      :action-contracts="actionContracts" action-state-field="status"
      :action-label-resolver="resolveReviewActionLabel"
      @row-action="handleRowAction" @update:quick-search="quickSearch=$event" @search="appliedSearch=quickSearch"
      @toggle-advanced="advancedVisible=!advancedVisible" @clear-filters="clearFilters"
      @clear-sort="clearSort" @export-current="exportCurrent" @clear-selection="clearSelection"
      @update-filter="(field,value)=>filters[field]=value" @selection-change="selectedRows=$event"
      @sort-change="handleSort">
      <template #columns>
        <el-table-column prop="sourceComparisonNo" label="来源报价比较" min-width="200" />
        <el-table-column prop="factOriginDisplay" label="事实来源" min-width="230" />
        <el-table-column prop="materialCode" label="物料编码" min-width="140" />
        <el-table-column prop="materialName" label="物料名称" min-width="180" />
        <el-table-column prop="quantity" label="数量" min-width="110" />
        <el-table-column prop="supplierDisplay" label="供应商" min-width="220" />
        <el-table-column prop="supplierCount" label="供应商数量" min-width="120" />
        <el-table-column prop="lowestPriceLabel" label="最低报价参考" min-width="140" />
        <el-table-column prop="selectedSupplierName" label="人工选择供应商" min-width="180" />
        <el-table-column prop="decisionVersion" label="决策版本" min-width="110" />
        <el-table-column prop="displayStatusLabel" label="核价状态" min-width="120" />
        <el-table-column prop="reviewResultLabel" label="核价结论" min-width="150" />
        <el-table-column prop="priceArchiveStatus" label="价格归档状态" min-width="190" />
        <el-table-column prop="archiveBlockReason" label="归档阻断原因" min-width="300" />
        <el-table-column prop="supplierMaterialPriceId" label="有效价格编号" min-width="170" />
        <el-table-column prop="supplierMaterialPriceEffectiveDate" label="有效价格生效日期" min-width="170" />
        <el-table-column prop="supplierQuotationId" label="报价对象ID" min-width="130" />
        <el-table-column prop="supplierQuotationItemId" label="报价明细身份" min-width="150" />
      </template>
      </PceEnterpriseListTable>
    </section>

    <section v-if="recommendationContext" class="handoff-result"
      data-acceptance-id="supplier-recommendation-context-ready">
      <h3>供应商推荐接口</h3>
      <el-alert title="核价已完成，仅形成SupplierRecommendationDecisionContext；采购订单未创建。"
        type="success" :closable="false" show-icon />
      <el-descriptions :column="3" border>
        <el-descriptions-item label="来源核价">{{ recommendationContext.sourcePriceApprovalPreparationNo }}</el-descriptions-item>
        <el-descriptions-item label="来源比较">{{ recommendationContext.sourceComparisonNo }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ recommendationContext.status }}</el-descriptions-item>
      </el-descriptions>
    </section>

    <el-dialog v-model="batchDialogVisible" :title="batchDialogTitle" width="760px">
      <el-alert v-if="batchMode === 'review'" title="批量入口仅建立逐条处理清单，不会自动改变核价状态。"
        type="info" :closable="false" show-icon />
      <el-table :data="batchRows" border>
        <el-table-column type="index" label="序号" width="64" />
        <el-table-column prop="approvalPrepareNo" label="核价准备编号" min-width="220" />
        <el-table-column prop="materialName" label="物料" min-width="150" />
        <el-table-column prop="displayStatusLabel" label="状态" width="120" />
        <el-table-column prop="reviewResultLabel" label="核价结论" width="150" />
        <el-table-column label="操作" fixed="right" width="120">
          <template #default="scope">
            <el-button link type="primary" @click="openBatchRow(scope.row)">
              {{ resolveReviewActionLabel(scope.row) }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <template #footer><el-button @click="batchDialogVisible=false">关闭</el-button></template>
    </el-dialog>

    <el-dialog v-model="dialogVisible" title="人工核价" width="880px" destroy-on-close>
      <template v-if="current">
        <el-alert v-if="current.factOrigin === 'legacy_verified_fact'"
          title="历史事实不能直接归档；经本次人工核价、选择供应商并确认报价后，可形成新的企业有效价格。"
          type="warning" :closable="false" show-icon />
        <h3>一、报价依据</h3>
        <el-table :data="current.sourceQuotationEvidence" border size="small">
          <el-table-column prop="supplierName" label="供应商" min-width="180" />
          <el-table-column prop="quotationNo" label="报价编号" min-width="190" />
          <el-table-column prop="quotationAmount" label="报价金额" min-width="130" />
          <el-table-column prop="quotationStatusLabel" label="报价状态" min-width="130" />
        </el-table>
        <el-descriptions class="material-basis" :column="3" border>
          <el-descriptions-item label="物料">{{ current.materialLines?.[0]?.materialName }}</el-descriptions-item>
          <el-descriptions-item label="数量">{{ current.materialLines?.[0]?.quantity }}</el-descriptions-item>
          <el-descriptions-item label="比较结果">{{ comparisonLabel }}</el-descriptions-item>
        </el-descriptions>

        <h3>二、历史参考</h3>
        <el-empty v-if="!current.historicalPriceReference?.length" description="暂无历史价格参考" />
        <el-table v-else :data="current.historicalPriceReference" border size="small">
          <el-table-column prop="recentPrice" label="最近价格" />
          <el-table-column prop="lowestPrice" label="最低价格" />
          <el-table-column prop="historyCount" label="历史次数" />
        </el-table>

        <h3>三、人工决策区域</h3>
        <el-alert :title="isCurrentEditable ? '请完成人工核价。' : '当前核价已完成，不允许修改。'"
          :type="isCurrentEditable ? 'info' : 'warning'" :closable="false" show-icon />
        <el-form label-width="130px">
          <el-form-item label="核价结论" required>
            <el-radio-group v-model="form.reviewResult" :disabled="!isCurrentEditable">
              <el-radio value="pass">通过</el-radio>
              <el-radio value="reject">不同意</el-radio>
              <el-radio value="adjust">调整后重新核价</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="选择供应商" :required="form.reviewResult === 'pass'">
            <el-select v-model="form.selectedSupplierCode" placeholder="必须由采购人员选择"
              :disabled="!isCurrentEditable" style="width:100%">
              <el-option v-for="candidate in current.supplierCandidates"
                :key="candidate.supplierCode || candidate.supplierId"
                :label="`${candidate.supplierName}（${candidate.quotationAmount ?? '-'}）`"
                :value="candidate.supplierCode || candidate.supplierId" />
            </el-select>
          </el-form-item>
          <el-form-item label="核价意见" required><el-input v-model="form.reviewOpinion" type="textarea"
            :disabled="!isCurrentEditable" /></el-form-item>
          <el-form-item label="异常说明"><el-input v-model="form.exceptionNote" type="textarea"
            :disabled="!isCurrentEditable" /></el-form-item>
          <el-form-item label="审批意见" required><el-input v-model="form.approvalOpinion" type="textarea"
            :disabled="!isCurrentEditable" /></el-form-item>
          <el-form-item label="确认人" required><el-input v-model="form.reviewer"
            :disabled="!isCurrentEditable" /></el-form-item>
          <el-form-item label="确认时间"><span>{{ current.reviewedAt || '确认后由系统记录' }}</span></el-form-item>
        </el-form>
        <el-alert v-if="current.status === 'completed' && !current.supplierRecommendationEligible"
          :title="current.supplierRecommendationBlockedReason || '当前核价结果未通过，不允许进入供应商推荐。'"
          type="error" :closable="false" show-icon />
      </template>
      <template #footer>
        <el-button v-if="current?.status === 'draft'" type="primary" @click="startReview">开始核价</el-button>
        <el-button v-if="current?.status === 'reviewing'" type="success" @click="finishReview">完成核价</el-button>
        <el-button v-if="current?.status === 'completed' && current?.reviewResult === 'adjust'"
          type="primary" @click="startReview">重新核价</el-button>
        <el-button v-if="current?.supplierRecommendationEligible"
          type="primary" @click="enterSupplierRecommendation">进入供应商推荐</el-button>
        <el-button @click="dialogVisible=false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="archiveDialogVisible" title="确认报价并生成有效价格" width="760px" destroy-on-close
      data-acceptance-id="PRICE_CONFIRM_ACTION_001">
      <el-alert title="仅处理已完成且核价结论为通过的任务；每条独立校验，失败不会影响其它记录。"
        type="warning" :closable="false" show-icon />
      <el-table :data="archiveTargets" border size="small" class="archive-targets">
        <el-table-column prop="approvalPrepareNo" label="核价准备编号" min-width="210" />
        <el-table-column prop="selectedSupplierName" label="已选供应商" min-width="180" />
        <el-table-column prop="reviewResultLabel" label="核价结论" width="110" />
      </el-table>
      <el-alert class="archive-direct-note" type="info" :closable="false" show-icon
        title="确认后直接读取供应商正式报价生成当前有效价格；税率和有效期在供应商物料价格页面维护，交货周期在物料供应商关系页面维护。" />
      <template #footer>
        <el-button @click="archiveDialogVisible=false">取消</el-button>
        <el-button type="success" :loading="archiving" @click="confirmArchive">确认报价</el-button>
      </template>
    </el-dialog>
  </main>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { enterpriseMasterDataApi } from '@/api/enterpriseMasterData.js'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import { createPceEnterpriseListContract, usePceEnterpriseListRuntime } from '@/meta/runtime/pceEnterpriseListContract.js'
import { createUnifiedFilterSchema } from '@/meta/runtime/unifiedFilterSchema.js'
import { createRemoteSelectOptionsProvider } from '@/meta/runtime/remoteSelectOptionsProvider.js'
import { priceApprovalRuntimeProvider } from '@/meta/providers/priceApprovalRuntimeProviderV1142824.js'
import { completePriceApprovalReview, createSupplierRecommendationDecisionContext,
  startPriceApprovalReview } from '@/meta/domain/scm/priceApproval/priceApprovalPreparationRuntimeV1142824.js'
import { resolveBusinessSourceTypeLabel } from '@/meta/runtime/businessSourceTypeDisplayMapping.js'
import { SCM_PRICE_APPROVAL_LIST_ACTIONS, SCM_PRICE_ARCHIVE_STATUS_OPTIONS } from '@/meta/process/scm/scmUnifiedListActionContractsV1142813.js'

const route = useRoute()
const runtime = reactive({ records: [], resultCount: 0, dataMode: 'production',
  factSource: 'QuoteComparisonFact', factLoadStatus: 'loading', errorMessage: '', sourceMapping: null,
  availableComparisons: [], availableComparisonCount: 0, sourceConsistency: null })
const records = ref([])
const creatingComparisonNo = ref('')
const dialogVisible = ref(false)
const archiveDialogVisible = ref(false)
const archiveTargets = ref([])
const archiving = ref(false)
const batchDialogVisible = ref(false)
const batchMode = ref('view')
const batchRows = ref([])
const current = ref(null)
const recommendationContext = ref(null)
const form = reactive({ reviewResult: '', selectedSupplierCode: '', reviewOpinion: '', exceptionNote: '', approvalOpinion: '', reviewer: '' })

function resolveFactOriginDisplay(item) {
  return item?.sourceTypeLabel || resolveBusinessSourceTypeLabel(item?.sourceType || item?.factOrigin)
}
function resolveLifecycleStatusCode(item) {
  return item?.storedStatusCode === 'rejected' ? 'rejected' : (item?.statusCode || item?.status || 'draft')
}
function resolveLifecycleStatusLabel(item) {
  return resolveLifecycleStatusCode(item) === 'rejected' ? '已拒绝' : (item?.statusLabel || '草稿')
}
function resolveSupplierDisplay(item) {
  const names = (item?.supplierCandidates || []).map(candidate => candidate.supplierName).filter(Boolean)
  return names.length ? names.join('、') : (item?.selectedSupplier?.supplierName || '待人工选择')
}

const rows = computed(() => records.value.map(item => ({ ...item,
  materialCode: item.materialLines?.[0]?.materialCode || '-',
  materialName: item.materialLines?.[0]?.materialName || '-', quantity: item.materialLines?.[0]?.quantity || '-',
  supplierDisplay: resolveSupplierDisplay(item),
  supplierCount: item.supplierCandidates?.length || 0,
  lowestPriceLabel: item.comparisonBasis?.lowestQuote ?? item.comparisonBasis?.lowestPrice ?? '-',
  factOriginDisplay: resolveFactOriginDisplay(item),
  priceArchiveStatus: item.priceArchiveStatus || (item.factOrigin === 'legacy_verified_fact'
    ? '历史事实，不生成有效价格' : '来源不完整'),
  archiveStatus: item.archiveStatus || (item.supplierMaterialPriceId ? 'ARCHIVED' : 'NOT_ALLOWED'),
  blockReasonCode: item.blockReasonCode || '',
  archiveBlockReason: item.archiveBlockReason || '',
  supplierMaterialPriceId: item.supplierMaterialPriceId || '-',
  supplierMaterialPriceEffectiveDate: item.supplierMaterialPriceEffectiveDate || '-',
  supplierQuotationId: item.supplierQuotationId || '-',
  supplierQuotationItemId: item.supplierQuotationItemId || '-',
  displayStatusLabel: resolveLifecycleStatusLabel(item),
  selectedSupplierName: item.selectedSupplier?.supplierName || '待人工选择' })))
const lifecycleCounts = computed(() => Object.freeze({
  draft: records.value.filter(item => item.status === 'draft').length,
  reviewing: records.value.filter(item => item.status === 'reviewing').length,
  completed: records.value.filter(item => item.status === 'completed' && item.storedStatusCode !== 'rejected').length,
  rejected: records.value.filter(item => item.status === 'rejected' || item.storedStatusCode === 'rejected').length,
}))
const selectedEditableCount = computed(() => selectedRows.value.filter(
  item => ['draft', 'reviewing'].includes(item.status)
    || (item.status === 'completed' && item.reviewResult === 'adjust'),
).length)
const isArchiveEligible = item => item?.canArchive === true
const selectedArchiveCount = computed(() => selectedRows.value.filter(isArchiveEligible).length)
const batchDialogTitle = computed(() => batchMode.value === 'review' ? '批量进入核价' : '批量查看核价准备')
const actionContracts = SCM_PRICE_APPROVAL_LIST_ACTIONS
const optionsProvider = createRemoteSelectOptionsProvider({ providerCode: 'SCM_PRICE_APPROVAL_RUNTIME_FILTER_OPTIONS' })
const filterFields = Object.freeze([
  { field: 'sourceComparisonNo', label: '来源报价比较', type: 'remote-select', optionsProvider },
  { field: 'materialCode', label: '物料编码', type: 'select', optionsSource: 'current_result' },
  { field: 'status', label: '核价状态', type: 'select', options: [
    { label: '草稿', value: 'draft' }, { label: '核价中', value: 'reviewing' },
    { label: '已完成', value: 'completed' }] },
  { field: 'reviewResult', label: '核价结论', type: 'select', options: [
    { label: '通过', value: 'pass' }, { label: '不同意', value: 'reject' },
    { label: '调整后重新核价', value: 'adjust' }] },
  { field: 'archiveStatus', label: '价格归档状态', type: 'select', options: SCM_PRICE_ARCHIVE_STATUS_OPTIONS },
])
const filterSchema = createUnifiedFilterSchema({ filterFields, optionsProvider })
const enterpriseListContract = createPceEnterpriseListContract({ pageCode: 'price-approval',
  pageType: 'list', title: '采购核价', moduleCode: 'SCM_PRICE_APPROVAL' })
const { selectedRows, quickSearch, appliedSearch, advancedVisible, filters, tableRef,
  activeFilterCount, sortText, filteredRows, clearFilters, clearSort, clearSelection,
  handleSort, exportCurrent } = usePceEnterpriseListRuntime({ rows, filterSchema,
  pageCode: 'price-approval', searchFields: ['approvalPrepareNo', 'sourceComparisonNo', 'materialCode', 'materialName', 'factOriginDisplay', 'priceArchiveStatus'],
  exportFileName: 'price-approval-runtime.csv', exportColumns: [
    { field: 'approvalPrepareNo', label: '核价准备编号' }, { field: 'sourceComparisonNo', label: '来源报价比较' },
    { field: 'materialCode', label: '物料编码' }, { field: 'supplierDisplay', label: '供应商' },
    { field: 'displayStatusLabel', label: '核价状态' }] })

const comparisonLabel = computed(() => current.value?.comparisonBasis?.comparisonStatusLabel
  || current.value?.comparisonBasis?.summary || JSON.stringify(current.value?.comparisonBasis || {}))
const isCurrentEditable = computed(() => ['draft', 'reviewing'].includes(current.value?.status))

function resolveReviewActionLabel(row, contract) {
  if (contract?.actionCode === 'CONFIRM_QUOTATION') return '确认报价'
  if (contract?.actionCode === 'VIEW_EFFECTIVE_PRICE') return '查看有效价格'
  if (contract?.actionCode === 'VIEW_ARCHIVE_BLOCK_REASON') return '查看阻断原因'
  if (row?.status === 'draft') return '人工核价'
  if (row?.status === 'reviewing' || row?.reviewResult === 'adjust') return '继续核价'
  if (row?.supplierRecommendationEligible) return '查看供应商推荐'
  return '查看'
}

function handleRowAction(action, row) {
  if (action?.actionCode === 'CONFIRM_QUOTATION') return openArchive([row])
  if (action?.actionCode === 'VIEW_EFFECTIVE_PRICE') {
    return window.open('#/foundation/erp/supplier-material-prices', '_blank', 'noopener,noreferrer')
  }
  if (action?.actionCode === 'VIEW_ARCHIVE_BLOCK_REASON') {
    return ElMessage.warning(row.archiveBlockReason || '该核价任务当前不允许归档。')
  }
  return openReview(action, row)
}

function openArchive(targets) {
  archiveTargets.value = targets.filter(isArchiveEligible)
  if (!archiveTargets.value.length) return ElMessage.warning('只有已完成且核价结论为通过的任务可以确认报价。')
  archiveDialogVisible.value = true
}

function openBatchArchive() {
  openArchive(selectedRows.value)
}

async function confirmArchive() {
  try {
    archiving.value = true
    const items = archiveTargets.value.map(item => ({ preparationId: item.id }))
    const response = await enterpriseMasterDataApi.archivePriceApprovalPreparations(items)
    const result = response?.preparationArchiveResult || response?.data?.preparationArchiveResult
    if (!result) throw new Error(response?.errorMessage || '确认报价失败')
    archiveDialogVisible.value = false
    if (result.failureCount) {
      const reasons = (result.items || []).filter(item => item.status === 'FAILED')
        .map(item => `${item.preparationId}：${item.errorMessage || item.errorCode}`).join('；')
      ElMessage.warning(`确认完成：成功 ${result.successCount} 条，失败 ${result.failureCount} 条。${reasons}`)
    } else ElMessage.success(`已确认报价并生成 ${result.successCount} 条有效价格。`)
    await load()
  } catch (error) {
    ElMessage.error(error?.response?.data?.errorMessage || error?.message || '确认报价失败')
  } finally {
    archiving.value = false
  }
}

function openBatchView() {
  batchMode.value = 'view'
  batchRows.value = [...selectedRows.value]
  batchDialogVisible.value = true
}

function openBatchReview() {
  batchMode.value = 'review'
  batchRows.value = selectedRows.value.filter(item => ['draft', 'reviewing'].includes(item.status)
    || (item.status === 'completed' && item.reviewResult === 'adjust'))
  if (!batchRows.value.length) return ElMessage.warning('所选核价准备均已完成，只能查看。')
  if (batchRows.value.length < selectedRows.value.length) ElMessage.info('已完成记录保持只读，本次仅列出可继续处理的核价准备。')
  batchDialogVisible.value = true
}

function openBatchRow(row) {
  batchDialogVisible.value = false
  openReview(null, row)
}

async function load() {
  runtime.factLoadStatus = 'loading'
  const result = await priceApprovalRuntimeProvider.loadRuntime(route.query)
  Object.assign(runtime, result)
  let sourceConsistency = null
  if (result.dataMode === 'production') {
    try {
      const response = await enterpriseMasterDataApi.priceSourceConsistency()
      sourceConsistency = response?.data || null
    } catch (_error) {
      sourceConsistency = null
    }
  }
  runtime.sourceConsistency = sourceConsistency
  runtime.availableComparisons = result.availableComparisons.map(item => ({ ...item,
    factOriginDisplay: resolveFactOriginDisplay(item) }))
  const reconciliationById = new Map((sourceConsistency?.priceArchiveReconciliation || [])
    .map(item => [String(item.preparationId), item]))
  records.value = [...(sourceConsistency?.sessionAcceptancePreparations || []), ...result.records.map(item => ({
    ...item, ...(reconciliationById.get(String(item.id)) || {}),
  }))]
  runtime.resultCount = records.value.length
}

async function createPreparation(comparison) {
  try {
    creatingComparisonNo.value = comparison.quoteComparisonNo
    const response = await priceApprovalRuntimeProvider.createFromComparison(comparison)
    if (!response?.success) throw new Error(response?.error?.message || '生成核价准备失败')
    ElMessage.success(`已生成 ${response.data.preparation.approvalPrepareNo}，请进入人工核价`)
    await load()
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    creatingComparisonNo.value = ''
  }
}

function resetForm(item) {
  form.reviewResult = item.reviewResult || ''
  form.selectedSupplierCode = item.selectedSupplier?.supplierCode || ''
  form.reviewOpinion = item.reviewOpinion || ''
  form.exceptionNote = item.exceptionNote || ''
  form.approvalOpinion = item.approvalOpinion || ''
  form.reviewer = item.reviewer || ''
}

function openReview(_action, row) {
  current.value = records.value.find(item => item.approvalPrepareNo === row.approvalPrepareNo) || row
  resetForm(current.value)
  dialogVisible.value = true
}

function replaceRecord(updated) {
  records.value = records.value.map(item => item.approvalPrepareNo === updated.approvalPrepareNo ? updated : item)
  current.value = updated
}

async function startReview() {
  try {
    if (runtime.dataMode === 'canary_acceptance') replaceRecord(startPriceApprovalReview(current.value))
    else {
      const response = await priceApprovalRuntimeProvider.transition(current.value.id, { targetStatus: 'reviewing' })
      if (!response.success) throw new Error(response.error?.message || '开始核价失败')
      replaceRecord(response.data.preparation)
    }
    ElMessage.success('已进入人工核价')
  } catch (error) { ElMessage.error(error.message) }
}

async function finishReview() {
  try {
    const input = { ...form, targetStatus: 'completed' }
    let updated
    if (runtime.dataMode === 'canary_acceptance') updated = completePriceApprovalReview(current.value, input, 'completed')
    else {
      const response = await priceApprovalRuntimeProvider.transition(current.value.id, input)
      if (!response.success) throw new Error(response.error?.message || '核价动作失败')
      updated = response.data.preparation
      recommendationContext.value = response.data.supplierRecommendationContext || null
    }
    replaceRecord(updated)
    if (updated.supplierRecommendationEligible) {
      recommendationContext.value ||= createSupplierRecommendationDecisionContext(updated)
      ElMessage.success('人工核价完成，供应商推荐上下文已准备；采购订单未创建')
    } else ElMessage.warning(updated.supplierRecommendationBlockedReason
      || '当前核价结果未通过，不允许进入供应商推荐。')
  } catch (error) { ElMessage.error(error.message) }
}

function enterSupplierRecommendation() {
  try {
    recommendationContext.value = createSupplierRecommendationDecisionContext(current.value)
    ElMessage.success('供应商推荐准入检查通过；仅生成上下文，采购订单未创建。')
  } catch (error) {
    ElMessage.warning(current.value?.supplierRecommendationBlockedReason
      || error.message || '当前核价结果未通过，不允许进入供应商推荐。')
  }
}

onMounted(load)
watch(() => route.fullPath, load)
</script>

<style scoped>
.price-approval-runtime{display:grid;gap:16px;min-width:0;max-width:100%;overflow-x:hidden}.operation-guide,.runtime-summary,.pending-comparisons,.price-approval-list,.handoff-result{padding:16px;border:1px solid #dbe4ee;border-radius:10px;background:#fff;min-width:0;max-width:100%}
.operation-guide h2,.handoff-result h3{margin:0 0 8px}.operation-guide p{margin:0 0 8px}.operation-guide ol{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px 24px;margin:12px 0;padding-left:22px}
.archive-targets{margin-top:14px}.archive-direct-note{margin-top:16px}
.runtime-summary{display:grid;gap:12px}.material-basis{margin-top:12px}.el-dialog h3{margin:18px 0 10px}
.section-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:12px}.section-heading h2{margin:0 0 6px}.section-heading p{margin:0;color:#667085}
.lifecycle-summary,.price-approval-batch-actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.price-approval-batch-actions{margin-bottom:12px;padding:10px 12px;background:#f7f9fc;border-radius:8px}.batch-hint{color:#667085;font-size:13px}
@media(max-width:900px){.operation-guide ol{grid-template-columns:1fr}}
</style>
