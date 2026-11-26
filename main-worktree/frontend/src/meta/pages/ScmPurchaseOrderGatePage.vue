<template>
  <main class="node-page" data-page-code="purchase-order-gate" data-page-name="采购订单准入"
    data-module-code="SCM" data-business-object="PurchaseOrderCreationGateDecision">
    <header class="page-heading">
      <div><p>SCM · 采购订单</p><h1>采购订单准入</h1>
        <span>复核供应商推荐批次的完整性与业务证据，仅保存准入决定，不创建采购订单。</span></div>
      <el-button @click="refresh">刷新</el-button>
    </header>

    <el-alert v-if="entryError" :title="entryError" type="error" :closable="false" show-icon />

    <section class="panel" data-acceptance-region="supplier-recommendation-gate-status">
      <div class="section-heading"><div><h2>Gate状态区域</h2>
        <p>供应商推荐结果已形成独立准入Gate；人工确认Gate不会创建采购订单。</p></div>
        <PceBusinessStatus :status-code="supplierGate?.status || 'WAITING_SOURCE'"
          :status-label="supplierGate?.statusLabel || '等待供应商推荐承接'" source="runtime" />
      </div>
      <div class="facts">
        <article><span>Gate编号</span><strong>{{ supplierGate?.gateId || '待承接' }}</strong></article>
        <article><span>推荐决策编号</span><strong>{{ supplierGate?.recommendationDecisionId || '待承接' }}</strong></article>
        <article><span>推荐供应商</span><strong>{{ supplierGate?.supplierName || '待承接' }}</strong></article>
        <article><span>Gate确认人</span><strong>{{ supplierGate?.confirmedBy || '待人工确认' }}</strong></article>
        <article><span>Gate确认时间</span><strong>{{ supplierGate?.confirmedAt || '待人工确认' }}</strong></article>
        <article><span>采购订单</span><strong>未创建</strong></article>
      </div>
    </section>

    <section class="panel" data-acceptance-region="purchase-order-admission-source-chain">
      <h2>来源链区域</h2>
      <div class="facts">
        <article><span>采购申请</span><strong>{{ supplierGate?.purchaseRequestId || '缺失' }}</strong></article>
        <article><span>采购询价</span><strong>{{ supplierGate?.inquiryId || '缺失' }}</strong></article>
        <article><span>报价比较</span><strong>{{ supplierGate?.quoteComparisonId || '缺失' }}</strong></article>
        <article><span>采购核价</span><strong>{{ supplierGate?.priceApprovalId || '缺失' }}</strong></article>
      </div>
    </section>

    <section class="panel" data-acceptance-region="purchase-order-admission-evidence">
      <h2>推荐证据区域</h2>
      <div class="facts">
        <article><span>推荐理由</span><strong>{{ supplierGate?.recommendationReason || '缺失' }}</strong></article>
        <article><span>报价证据</span><strong>{{ supplierGate?.quoteEvidence?.length || 0 }}项</strong></article>
        <article><span>核价证据</span><strong>{{ supplierGate?.priceEvidence?.length || 0 }}项</strong></article>
        <article><span>资格证据</span><strong>{{ supplierGate?.qualificationEvidence?.length || 0 }}项</strong></article>
      </div>
    </section>

    <section class="panel" data-acceptance-region="purchase-order-admission-check">
      <div class="section-heading"><div><h2>采购订单准入检查区域</h2>
        <p>先人工确认Gate，再检查推荐确认、报价、核价和完整来源链。</p></div>
        <div class="actions" aria-label="操作区域" data-acceptance-region="purchase-order-admission-actions">
          <el-button type="primary" data-process-action="CONFIRM_PURCHASE_ORDER_GATE"
            :disabled="!supplierGateConfirmExecutable" @click="confirmSupplierGate">人工确认Gate</el-button>
          <el-button type="success" data-process-action="EVALUATE_PURCHASE_ORDER_ADMISSION"
            :disabled="!admissionCheckExecutable" @click="evaluateAdmission">执行采购订单准入检查</el-button>
        </div>
      </div>
      <el-table v-if="admissionResult?.checks?.length" :data="admissionResult.checks" border>
        <el-table-column prop="checkName" label="检查项目" min-width="220" />
        <el-table-column prop="currentValue" label="当前值" min-width="300" />
        <el-table-column prop="result" label="结果" width="110" />
        <el-table-column prop="reason" label="原因" min-width="300" />
      </el-table>
      <el-empty v-else description="等待人工确认Gate并执行准入检查" />
      <el-alert v-if="admissionResult?.status === 'BLOCKED'"
        :title="admissionResult.blockedReasons.join('；')" type="error" :closable="false" show-icon />
      <el-alert v-else-if="admissionResult?.status === 'READY_FOR_PURCHASE_ORDER'"
        title="准入检查通过，仅开放采购订单创建入口；采购订单尚未创建。"
        type="success" :closable="false" show-icon />
    </section>

    <section class="panel" data-acceptance-region="gate-purchase-context">
      <h2>一、采购上下文</h2>
      <div class="facts">
        <article><span>采购申请编号</span><strong>{{ purchaseRequestNos }}</strong></article>
        <article><span>推荐批次编号</span><strong>{{ current?.sourceBatchId || '待承接' }}</strong></article>
        <article><span>Decision Revision</span><strong>{{ current?.sourceDecisionRevision || '缺失' }}</strong></article>
        <article><span>Gate决定编号</span><strong>{{ current?.gateDecisionId || '待建立' }}</strong></article>
        <article><span>采购订单</span><strong>未创建</strong></article>
      </div>
    </section>

    <section class="panel" data-acceptance-region="decision-batch-gate-handoff">
      <h2>二、物料清单</h2>
      <el-empty v-if="!current?.items?.length" description="暂无已确认的供应商推荐批次" />
      <el-table v-else :data="current.items" border>
        <el-table-column prop="materialCode" label="物料编码" min-width="140" />
        <el-table-column prop="materialName" label="物料名称" min-width="170" />
        <el-table-column prop="selectedSupplierName" label="推荐供应商" min-width="180" />
        <el-table-column label="确认状态" width="120">
          <template #default="{ row }">{{ row.reviewStatus === 'confirmed' ? '已确认' : '未确认' }}</template>
        </el-table-column>
        <el-table-column prop="selectionReason" label="推荐理由" min-width="260" />
        <el-table-column label="阻断原因" min-width="220">
          <template #default="{ row }">{{ (row.blockedReasons || []).join('；') || '无' }}</template>
        </el-table-column>
        <el-table-column label="物料操作" fixed="right" width="300">
          <template #default="{ row }">
            <el-button link type="primary" @click="viewRecommendationBasis(row)">查看推荐依据</el-button>
            <el-button link type="primary" @click="viewSupplierSelection(row)">查看供应商选择</el-button>
            <el-button link type="warning" @click="returnForModification(row)">返回供应商推荐修改</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div v-if="current" class="completeness" data-acceptance-region="batch-completeness">
        <span>Total Item Count：{{ current.batchCompleteness.totalItemCount }}</span>
        <span>Completed Item Count：{{ current.batchCompleteness.completedItemCount }}</span>
        <span>Pending Item Count：{{ current.batchCompleteness.pendingItemCount }}</span>
      </div>
    </section>

    <section class="panel" data-acceptance-region="gate-check-results">
      <div class="section-heading"><div><h2>三、Gate检查结果</h2>
        <p>检查批量完整性、Decision状态、供应商、人工记录与业务证据。</p></div>
        <el-button type="primary" data-process-action="EVALUATE_PURCHASE_ORDER_CREATION_GATE"
          :disabled="!gateActionExecutable" @click="evaluateGate">
          {{ current?.status === 'pending_review' ? '执行准入检查' : '重新执行准入检查' }}
        </el-button></div>
      <el-table v-if="current?.checks?.length" :data="current.checks" border>
        <el-table-column prop="checkName" label="检查项目" min-width="190" />
        <el-table-column prop="result" label="结果" width="110" />
        <el-table-column prop="blockedReason" label="阻断原因" min-width="280" />
      </el-table>
      <el-empty v-else description="等待采购人员执行准入检查" />
      <el-alert v-if="current?.status === 'blocked'" :title="current.blockedReasons.join('；')"
        type="error" :closable="false" show-icon />
      <el-alert v-else-if="current?.status === 'ready_for_purchase_order'"
        title="采购订单创建准入检查通过；采购订单尚未创建。" type="success" :closable="false" show-icon />
    </section>

    <section class="panel" data-acceptance-region="gate-inspection-records">
      <h2>四、准入检查记录</h2>
      <el-table v-if="inspectionRows.length" :data="inspectionRows" border>
        <el-table-column prop="inspectionId" label="检查记录编号" min-width="250" />
        <el-table-column prop="checkedAt" label="检查时间" min-width="190" />
        <el-table-column prop="checker" label="检查人" width="150" />
        <el-table-column prop="decisionRevision" label="Decision Revision" width="150" />
        <el-table-column prop="supplierSnapshotLabel" label="供应商快照" min-width="200" />
        <el-table-column prop="checkName" label="检查项目" min-width="220" />
        <el-table-column prop="result" label="PASS/FAIL" width="110" />
        <el-table-column prop="blockedReason" label="阻断原因" min-width="260" />
      </el-table>
      <el-empty v-else description="尚无准入检查记录" />
    </section>

    <section class="panel" data-acceptance-region="gate-human-audit">
      <h2>五、人工审计</h2>
      <div class="facts">
        <article><span>确认动作</span><strong>供应商推荐批次确认</strong></article>
        <article><span>确认人</span><strong>{{ reviewers }}</strong></article>
        <article><span>确认时间</span><strong>{{ reviewedTimes }}</strong></article>
        <article><span>检查动作</span><strong>执行采购订单准入检查</strong></article>
        <article><span>检查结果</span><strong>{{ latestInspection?.checkResult || '尚未检查' }}</strong></article>
        <article><span>检查人</span><strong>{{ latestInspection?.checker || current?.checkedBy || '尚未检查' }}</strong></article>
        <article><span>检查时间</span><strong>{{ latestInspection?.checkedAt || current?.lastCheckedAt || '尚未检查' }}</strong></article>
        <article><span>当前状态</span><strong>{{ gateStatusLabel }}</strong></article>
      </div>
    </section>

    <section class="panel" data-acceptance-region="purchase-order-gate-list">
      <PceEnterpriseListTable ref="tableRef" :contract="enterpriseListContract"
        page-id="purchase-order-gate" table-id="purchase-order-gate-main" :rows="rows"
        :table-rows="filteredRows" :filter-schema="filterSchema" :filters="filters"
        :quick-search="quickSearch" :advanced-visible="advancedVisible"
        :selected-count="selectedRows.length" :active-filter-count="activeFilterCount"
        :sort-text="sortText" primary-field="gateNo" primary-label="准入编号"
        :primary-width="250" min-width="1450px"
        scroll-acceptance-id="purchase-order-gate-horizontal-scroll" :action-width="110"
        @update:quick-search="quickSearch=$event" @search="appliedSearch=quickSearch"
        @toggle-advanced="advancedVisible=!advancedVisible" @clear-filters="clearFilters"
        @clear-sort="clearSort" @export-current="exportCurrent" @clear-selection="clearSelection"
        @update-filter="(field,value)=>filters[field]=value" @selection-change="selectedRows=$event"
        @sort-change="handleSort">
        <template #columns>
          <el-table-column prop="recommendedSupplierName" label="推荐供应商" width="220" />
          <el-table-column prop="purchaseDetailCount" label="物料数量" width="110" />
          <el-table-column prop="sourceInquiryNo" label="来源询价" width="200" />
          <el-table-column label="准入状态" width="170"><template #default="{row}">
            <PceBusinessStatus :status-code="row.statusCode" :status-label="row.statusLabel" source="runtime" />
          </template></el-table-column>
          <el-table-column prop="blockedReasonLabel" label="阻断原因" min-width="280" />
        </template>
        <template #actions><span class="readonly">准入检查</span></template>
      </PceEnterpriseListTable>
    </section>

    <section class="panel next" data-acceptance-region="next-action">
      <div><span>当前节点</span><strong>采购订单准入</strong></div>
      <div><span>下一动作</span><strong>准入通过后进入采购订单</strong></div>
      <el-button type="primary" :disabled="!purchaseOrderCreationEntry"
        @click="enterPurchaseOrderCreation">人工进入采购订单创建</el-button>
    </section>

    <el-dialog v-model="creationDialogVisible" title="人工确认创建采购订单" width="620px"
      data-acceptance-id="purchase-order-gate-creation-confirmation">
      <el-alert :title="`将按${activeCreationRequest?.supplierCount || 0}家供应商创建等量正式采购订单草稿；不会提交、审批、下达或发送供应商。`"
        type="warning" :closable="false" show-icon />
      <el-descriptions v-if="activeCreationRequest" :column="1" border class="creation-request">
        <el-descriptions-item label="采购模式">STANDARD（标准采购）</el-descriptions-item>
        <el-descriptions-item label="显式推荐批次">{{ routeBatchId }}</el-descriptions-item>
        <el-descriptions-item label="创建请求编号">{{ activeCreationRequest.requestId }}</el-descriptions-item>
        <el-descriptions-item label="Gate编号">{{ activeCreationRequest.gateId }}</el-descriptions-item>
        <el-descriptions-item label="供应商拆单数">{{ activeCreationRequest.supplierCount }} 家</el-descriptions-item>
        <el-descriptions-item label="物料明细">{{ activeCreationRequest.materialLines.length }} 项</el-descriptions-item>
        <el-descriptions-item label="正式供应商主数据">
          <div class="supplier-split-selections">
            <div v-for="group in activeCreationRequest.supplierGroups" :key="group.supplierCode"
              class="supplier-split-row">
              <span>{{ group.supplierCode }} · {{ group.supplierName }}（{{ group.materialLines.length }}项）</span>
              <el-select v-model="supplierSelections[group.supplierCode]" filterable
                placeholder="必须人工核对正式供应商" style="width:100%"
                @change="invalidateServerContext"
                :data-acceptance-id="`purchase-order-server-supplier-selector-${group.supplierCode}`">
                <el-option v-for="supplier in serverSuppliers" :key="supplier.id"
                  :label="`${supplier.code} · ${supplier.name}`" :value="supplier.id" />
              </el-select>
            </div>
          </div>
        </el-descriptions-item>
        <el-descriptions-item label="逐行PAR / SMP唯一引用">
          <div class="standard-context-selections">
            <div v-for="group in activeCreationRequest.supplierGroups" :key="`price-${group.supplierCode}`">
              <div v-for="line in group.materialLines" :key="selectionKey(group, line)"
                class="standard-context-row">
                <span>{{ line.sourceRequestNo }} · {{ line.materialCode }} · 数量 {{ line.quantity }}</span>
                <el-select v-model="priceSelections[selectionKey(group, line)]" filterable
                  placeholder="必须明确选择本次PAR对应的SMP" style="width:100%"
                  @change="invalidateServerContext"
                  :data-acceptance-id="`standard-price-selector-${line.materialCode}`">
                  <el-option v-for="price in effectivePriceOptions(group, line)" :key="price.priceNo"
                    :label="`${price.priceNo} · ${price.priceApprovalResultId} · ${price.unitPrice} ${price.currency} · 税率${price.taxRate}% · ${price.effectiveDate}`"
                    :value="price.priceNo" />
                </el-select>
              </div>
            </div>
          </div>
        </el-descriptions-item>
      </el-descriptions>
      <el-alert v-if="supplierMasterWarning" :title="supplierMasterWarning"
        type="warning" :closable="false" show-icon />
      <el-alert v-if="contextError" :title="contextError" type="error" :closable="false" show-icon />
      <el-table v-if="serverCreationContexts.length" :data="serverCreationContexts" border stripe
        data-acceptance-id="standard-purchase-server-context">
        <el-table-column prop="purchaseMode" label="模式" width="110" />
        <el-table-column prop="purchaseRequestNo" label="采购申请" min-width="150" />
        <el-table-column prop="purchaseRequestItemId" label="PR明细ID" width="110" />
        <el-table-column prop="priceApprovalResultNo" label="PAR" min-width="210" />
        <el-table-column prop="supplierMaterialPriceNo" label="SMP" min-width="250" />
        <el-table-column prop="supplierCode" label="供应商" width="120" />
        <el-table-column prop="materialCode" label="物料" width="120" />
        <el-table-column prop="quantity" label="数量" width="90" />
        <el-table-column prop="unitPrice" label="价格" width="100" />
        <el-table-column prop="taxRate" label="税率" width="90" />
        <el-table-column prop="currency" label="币种" width="90" />
        <el-table-column prop="effectiveDate" label="生效日" width="130" />
      </el-table>
      <template #footer>
        <el-button @click="creationDialogVisible=false">取消</el-button>
        <el-button :loading="contextInspecting" :disabled="!allRequiredSelections"
          data-process-action="INSPECT_STANDARD_PURCHASE_CONTEXT" @click="inspectCreationContext">
          验证标准采购创建上下文
        </el-button>
        <el-button type="primary" :loading="purchaseOrderCreating" :disabled="!serverContextReady"
          data-process-action="CONFIRM_CREATE_PURCHASE_ORDER" @click="confirmCreatePurchaseOrder">
          确认创建采购订单
        </el-button>
      </template>
    </el-dialog>

    <section class="panel" data-acceptance-region="purchase-order-admission-diagnostics">
      <h2>诊断区域</h2>
      <div class="facts">
        <article><span>dataMode</span><strong>production</strong></article>
        <article><span>factSource</span><strong>{{ supplierGateFacts.factSource || 'read_failed' }}</strong></article>
        <article><span>factLoadStatus</span><strong>{{ supplierGateFacts.factLoadStatus || 'read_failed' }}</strong></article>
        <article><span>resultCount</span><strong>{{ supplierGateFacts.resultCount || 0 }}</strong></article>
        <article><span>Business Write Count</span><strong>{{ actionBusinessWriteCount }}</strong></article>
        <article><span>Gate Action Count</span><strong>{{ gateActionCount }}</strong></article>
        <article><span>CreationRequest Count</span><strong>{{ creationRequestCount }}</strong></article>
        <article><span>PurchaseOrder Create Count</span><strong>{{ purchaseOrderCreateCount }}</strong></article>
        <article><span>List Visible Count</span><strong>{{ listVisibleCount }}</strong></article>
        <article><span>自动创建采购订单</span><strong>NO</strong></article>
      </div>
    </section>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import PceBusinessStatus from '@/meta/components/PceBusinessStatus.vue'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import { createPceEnterpriseListContract,
  usePceEnterpriseListRuntime } from '@/meta/runtime/pceEnterpriseListContract.js'
import { canPerformAction } from '@/meta/runtime/permissionEngine.js'
import { stateManager } from '@/meta/runtime/stateManager.js'
import { purchaseOrderGateHandoffProviderV11428161 } from '@/meta/providers/purchaseOrderGateHandoffProviderV11428161.js'
import { purchaseOrderGateRuntimeProviderV1142820 } from '@/meta/providers/purchaseOrderGateRuntimeProviderV1142820.js'
import { supplierRecommendationGateProviderV11428425 } from '@/meta/providers/supplierRecommendationGateProviderV11428425.js'
import { purchaseOrderAdmissionProviderV11428425 } from '@/meta/providers/purchaseOrderAdmissionProviderV11428425.js'
import { executeConfirmPurchaseOrderGateV11428425,
  executeEvaluatePurchaseOrderAdmissionV11428425 } from '@/meta/process/scm/purchaseOrderCreationGate/supplierRecommendationGateRuntimeV11428425.js'
import { buildPurchaseOrderCreationEntryHandoffV11428425 } from '@/meta/process/scm/purchaseOrderCreationGate/purchaseOrderCreationEntryHandoffV11428425.js'
import { createPurchaseOrderGateCreationRequestV11428427219,
  purchaseOrderGateCreationRequestStoreV11428427219 } from
  '@/meta/process/scm/purchaseOrderCreationRequest/purchaseOrderGateCreationRequestV11428427219.js'
import { createPurchaseOrderFromGateRequest, getActivePurchaseOrderSuppliers,
  inspectPurchaseOrderGateCreation, preparePurchaseOrderGateCreation,
  getScmStandardPageFacts } from '@/api/scmStandardPageFacts.js'
import { loadSupplierMaterialPriceRuntime } from '@/meta/providers/supplierMaterialPriceRuntimeProvider.js'

const route = useRoute()
const router = useRouter()
const routeBatchId = computed(() => String(route.query.batchId || '').trim())
const providerFacts = ref({ result: 'FAIL', records: [], current: null, inspectionRecords: [] })
const legacyProviderFacts = ref({ records: [] })
const entryError = ref('')
const supplierGateFacts = ref({ result: 'FAIL', gate: null, resultCount: 0 })
const admissionFacts = ref({ result: 'FAIL', gate: null, admissionResult: null })
const actionBusinessWriteCount = ref(0)
const gateActionCount = ref(0)
const creationRequestCount = ref(0)
const purchaseOrderCreateCount = ref(0)
const listVisibleCount = ref(0)
const creationDialogVisible = ref(false)
const purchaseOrderCreating = ref(false)
const activeCreationRequest = ref(null)
const serverSuppliers = ref([])
const supplierSelections = ref({})
const supplierMasterWarning = ref('')
const gateCreationCsrfToken = ref('')
const formalPriceRows = ref([])
const priceSelections = ref({})
const serverCreationContexts = ref([])
const contextError = ref('')
const contextInspecting = ref(false)
function normalizedSupplierIdentity(value) {
  const matched = String(value || '').toUpperCase().match(/^([A-Z]+)[-_ ]*0*(\d+)$/)
  return matched ? `${matched[1]}:${Number(matched[2])}` : String(value || '').toUpperCase()
}
const current = computed(() => providerFacts.value.current)
const supplierGate = computed(() => admissionFacts.value.gate || supplierGateFacts.value.gate)
const admissionResult = computed(() => admissionFacts.value.admissionResult || null)
const purchaseOrderCreationEntry = computed(() => {
  if (admissionResult.value?.status !== 'READY_FOR_PURCHASE_ORDER') return null
  try { return buildPurchaseOrderCreationEntryHandoffV11428425(admissionResult.value) }
  catch { return null }
})
const allSuppliersMapped = computed(() => Boolean(activeCreationRequest.value?.supplierGroups?.length)
  && activeCreationRequest.value.supplierGroups.every(group =>
    Number(supplierSelections.value[group.supplierCode]) > 0))
const allRequiredSelections = computed(() => allSuppliersMapped.value
  && activeCreationRequest.value.supplierGroups.every(group => group.materialLines.every(line =>
    Boolean(priceSelections.value[selectionKey(group, line)]))))
const serverContextReady = computed(() => allRequiredSelections.value
  && serverCreationContexts.value.length === activeCreationRequest.value?.materialLines?.length
  && serverCreationContexts.value.every(row => row.priceValueConsistent === true))
const latestInspection = computed(() => providerFacts.value.latestInspectionRecord
  || providerFacts.value.inspectionRecords?.at(-1) || null)
const inspectionRows = computed(() => (providerFacts.value.inspectionRecords || []).flatMap(record =>
  record.checkItems.map(item => ({ inspectionId: record.inspectionId,
    checkedAt: record.checkedAt, checker: record.checker, checkResult: record.checkResult,
    decisionRevision: record.decisionRevision || '-',
    supplierSnapshotLabel: (record.supplierSnapshot || []).map(value =>
      `${value.materialCode}：${value.supplierName || '未确认'}`).join('；') || '-',
    checkName: item.checkName, result: item.result,
    blockedReason: item.blockedReason || record.blockReasons.join('；') || '无' }))))
const rows = computed(() => providerFacts.value.records?.length
  ? providerFacts.value.records : legacyProviderFacts.value.records || [])
const canExecute = computed(() => canPerformAction(stateManager.snapshot().role, 'EXECUTE'))
const gateActionExecutable = computed(() => canExecute.value
  && Boolean(current.value?.sourceBatchId))
const supplierGateConfirmExecutable = computed(() => canExecute.value
  && supplierGate.value?.status === 'WAITING_CONFIRMATION')
const admissionCheckExecutable = computed(() => canExecute.value
  && supplierGate.value?.status === 'CONFIRMED')
const purchaseRequestNos = computed(() =>
  current.value?.purchaseContext?.sourceRequestNos?.join('、') || '待补充')
const reviewers = computed(() => [...new Set((current.value?.items || [])
  .map(item => item.reviewer).filter(Boolean))].join('、') || '待补充')
const reviewedTimes = computed(() => [...new Set((current.value?.items || [])
  .map(item => item.reviewedAt).filter(Boolean))].join('、') || '待补充')
const gateStatusLabel = computed(() => ({ pending_review: '待准入检查', blocked: '准入阻断',
  ready_for_purchase_order: '可进入采购订单' })[current.value?.status] || '待承接')
const filterSchema = Object.freeze([
  { field: 'recommendedSupplierName', label: '推荐供应商', filterType: 'text' },
  { field: 'statusCode', label: '准入状态', filterType: 'select', options: [
    { label: '待准入检查', value: 'pending_review' },
    { label: '可进入采购订单', value: 'ready_for_purchase_order' },
    { label: '准入阻断', value: 'blocked' },
  ] },
])
const enterpriseListContract = createPceEnterpriseListContract({ pageCode: 'purchase-order-gate',
  pageType: 'list', title: '采购订单准入', moduleCode: 'SCM_PURCHASE_ORDER_GATE' })
const { selectedRows, quickSearch, appliedSearch, advancedVisible, filters, tableRef,
  activeFilterCount, sortText, filteredRows, clearFilters, clearSort, clearSelection,
  handleSort, exportCurrent } = usePceEnterpriseListRuntime({ rows, filterSchema,
  pageCode: 'purchase-order-gate', searchFields: ['gateNo', 'recommendedSupplierName',
    'sourceInquiryNo'], exportFileName: 'purchase-order-gates.csv', exportColumns: [
    { field: 'gateNo', label: '准入编号' },
    { field: 'recommendedSupplierName', label: '推荐供应商' },
    { field: 'statusLabel', label: '准入状态' },
  ] })

function refresh() {
  const runtimeFacts = routeBatchId.value ? purchaseOrderGateRuntimeProviderV1142820.load() : null
  providerFacts.value = runtimeFacts?.current?.sourceBatchId === routeBatchId.value
    ? runtimeFacts : { result: 'FAIL', records: [], current: null, inspectionRecords: [] }
  legacyProviderFacts.value = { records: [] }
  supplierGateFacts.value = supplierRecommendationGateProviderV11428425.load({ batchId: routeBatchId.value })
  admissionFacts.value = purchaseOrderAdmissionProviderV11428425.load({ batchId: routeBatchId.value })
  entryError.value = !routeBatchId.value
    ? '采购订单准入真实数据承接失败：EXPLICIT_DECISION_BATCH_REQUIRED'
    : supplierGateFacts.value.result === 'PASS' ? ''
      : `采购订单准入真实数据承接失败：${supplierGateFacts.value.error || '明确批次不存在或尚未确认'}`
}

function selectionKey(group, line) {
  return `${group.supplierCode}::${line.sourceRequestNo}::${line.materialCode}`
}

function effectivePriceOptions(group, line) {
  const supplierId = Number(supplierSelections.value[group.supplierCode])
  const today = new Date().toISOString().slice(0, 10)
  return formalPriceRows.value.filter(price => Number(price.supplierId) === supplierId
    && price.materialCode === line.materialCode && price.status === 'ACTIVE'
    && price.effectiveDate <= today && (!price.expiryDate || price.expiryDate >= today))
}

function invalidateServerContext() {
  serverCreationContexts.value = []
  contextError.value = ''
}

function creationPayload() {
  return {
    ...activeCreationRequest.value,
    supplierGroups: activeCreationRequest.value.supplierGroups.map(group => ({ ...group,
      supplierId: supplierSelections.value[group.supplierCode],
      materialLines: group.materialLines.map(line => {
        const selectedNo = priceSelections.value[selectionKey(group, line)]
        const price = formalPriceRows.value.find(row => row.priceNo === selectedNo)
        return { ...line, priceApprovalResultId: price?.priceApprovalResultId || '',
          priceApprovalResultNo: price?.priceApprovalResultId || '',
          supplierMaterialPriceNo: price?.priceNo || '', unitPrice: price?.unitPrice || '',
          taxRate: price?.taxRate || '', currency: price?.currency || '',
          effectiveDate: price?.effectiveDate || '' }
      }),
    })),
  }
}

async function inspectCreationContext() {
  if (!allRequiredSelections.value) return
  contextInspecting.value = true
  invalidateServerContext()
  try {
    const response = await inspectPurchaseOrderGateCreation(creationPayload(), gateCreationCsrfToken.value)
    if (!response?.success || response.data?.result !== 'PASS') {
      throw new Error(response?.error?.message || '标准采购创建上下文验证失败')
    }
    serverCreationContexts.value = response.data.contexts || []
    if (!serverContextReady.value) throw new Error('服务端未返回完整且值一致的标准采购创建上下文')
    ElMessage.success('服务端已确认PR、PAR、SMP及价格值级一致；现在可以创建。')
  } catch (error) { contextError.value = error.message || String(error) }
  finally { contextInspecting.value = false }
}
function confirmSupplierGate() {
  if (!supplierGateConfirmExecutable.value) return ElMessage.error('当前Gate不允许确认')
  const result = executeConfirmPurchaseOrderGateV11428425(supplierGate.value, {}, {
    permissionContext: stateManager.snapshot(),
  })
  if (result.result !== 'PASS') return ElMessage.error(result.error || 'Gate确认失败')
  actionBusinessWriteCount.value += result.businessWriteCount
  ElMessage.success('Gate已人工确认；采购订单尚未创建。')
  refresh()
}
function evaluateAdmission() {
  if (!admissionCheckExecutable.value) return ElMessage.error('请先人工确认Gate')
  const result = executeEvaluatePurchaseOrderAdmissionV11428425(supplierGate.value, {}, {
    permissionContext: stateManager.snapshot(),
    decisionBatchResult: supplierGateFacts.value.source?.decisionBatchResult || {},
  })
  if (result.result !== 'PASS') return ElMessage.error(result.error || '采购订单准入检查失败')
  actionBusinessWriteCount.value += result.businessWriteCount
  ElMessage.success(result.admissionResult.status === 'READY_FOR_PURCHASE_ORDER'
    ? '准入检查通过，仅开放采购订单创建入口。' : '准入检查已阻断。')
  refresh()
}
function evaluateGate() {
  if (!gateActionExecutable.value) return ElMessage.error('当前推荐批次不满足准入检查执行条件')
  const result = purchaseOrderGateRuntimeProviderV1142820.evaluateActive({
    permissionContext: stateManager.snapshot(),
  })
  if (result.result !== 'PASS') return ElMessage.error(result.error || '准入检查失败')
  ElMessage.success(result.decision.status === 'ready_for_purchase_order'
    ? '准入检查通过，采购订单尚未创建' : '准入检查已阻断')
  refresh()
}
function viewRecommendationBasis(row) {
  ElMessageBox.alert(row.selectionReason || '暂无推荐依据', `${row.materialCode} 推荐依据`,
    { confirmButtonText: '关闭' })
}
function viewSupplierSelection(row) {
  ElMessageBox.alert(`${row.selectedSupplierName || '未选择'}（${row.selectedSupplierCode || '-'}）`,
    `${row.materialCode} 供应商选择`, { confirmButtonText: '关闭' })
}
function returnForModification(row) {
  const result = purchaseOrderGateRuntimeProviderV1142820.reopenMaterial(row.materialCode, {
    permissionContext: stateManager.snapshot(),
  })
  if (result.result !== 'PASS') return ElMessage.error(result.error || '供应商推荐决策退回失败')
  ElMessage.success(`${row.materialCode} 已解除确认锁定并返回人工复核。`)
  router.push('/scm/supplier-recommendation')
}
async function enterPurchaseOrderCreation() {
  if (!purchaseOrderCreationEntry.value) return ElMessage.error('采购订单准入尚未通过')
  try {
    gateActionCount.value += 1
    const actor = stateManager.snapshot()
    const requestFacts = await getScmStandardPageFacts('purchase-request')
    if (!requestFacts?.success) throw new Error(requestFacts?.error?.message || '采购申请来源事实读取失败')
    const requestObjects = requestFacts.data?.objects || requestFacts.data?.rows || []
    const sourceIds = new Set(supplierGate.value.purchaseRequestIds || [])
    const sourceMaterialLines = requestObjects
      .filter(item => sourceIds.has(item.objectNo) || sourceIds.has(item.requestNo))
      .flatMap(item => (item.items || []).map(line => ({ ...line,
        sourceRequestNo: item.requestNo || item.objectNo })))
    const request = createPurchaseOrderGateCreationRequestV11428427219({
      gate: supplierGate.value, admissionResult: admissionResult.value,
      creationEntry: purchaseOrderCreationEntry.value, actor, sourceMaterialLines,
    })
    activeCreationRequest.value = purchaseOrderGateCreationRequestStoreV11428427219.save(request)
    creationRequestCount.value = 1
    const response = await getActivePurchaseOrderSuppliers()
    if (!response?.success) throw new Error(response?.error?.message || '供应商主数据读取失败')
    const payload = response.data || {}
    serverSuppliers.value = (payload.results || payload || []).filter(item => item.is_active !== false)
    formalPriceRows.value = (await loadSupplierMaterialPriceRuntime({ force: true })).rows
    const csrfPreparation = await preparePurchaseOrderGateCreation()
    if (!csrfPreparation?.success) throw new Error(csrfPreparation?.error?.message
      || '采购订单创建安全预检失败')
    gateCreationCsrfToken.value = csrfPreparation.data?.csrfToken || ''
    if (!gateCreationCsrfToken.value) throw new Error('采购订单创建安全预检未返回CSRF Token')
    const warnings = []
    supplierSelections.value = Object.fromEntries(request.supplierGroups.map(group => {
      const exact = serverSuppliers.value.find(item => String(item.code) === group.supplierCode
        && String(item.name) === group.supplierName)
      const equivalent = exact || serverSuppliers.value.find(item =>
        normalizedSupplierIdentity(item.code) === normalizedSupplierIdentity(group.supplierCode))
      if (!exact) warnings.push(equivalent
        ? `Gate供应商 ${group.supplierCode}/${group.supplierName} 与服务端 ${equivalent.code}/${equivalent.name} 不完全一致，请人工核对。`
        : `Gate供应商 ${group.supplierCode}/${group.supplierName} 未匹配正式主数据。`)
      return [group.supplierCode, null]
    }))
    priceSelections.value = Object.fromEntries(request.supplierGroups.flatMap(group =>
      group.materialLines.map(line => [selectionKey(group, line), null])))
    invalidateServerContext()
    supplierMasterWarning.value = warnings.join('；')
    creationDialogVisible.value = true
  } catch (error) { ElMessage.error(error.message || String(error)) }
}

async function confirmCreatePurchaseOrder() {
  if (!activeCreationRequest.value || !serverContextReady.value) return
  purchaseOrderCreating.value = true
  try {
    const actor = stateManager.snapshot()
    const response = await createPurchaseOrderFromGateRequest({
      ...creationPayload(),
      confirmedBy: actor.userName || actor.user?.name || actor.userId || actor.role,
    }, gateCreationCsrfToken.value)
    if (!response?.success) throw new Error(response?.error?.message || '采购订单创建失败')
    purchaseOrderGateCreationRequestStoreV11428427219.markCreated(
      activeCreationRequest.value.requestId, response.data, actor)
    purchaseOrderCreateCount.value = Number(response.data.createdCount || 0)
    actionBusinessWriteCount.value += Number(response.meta?.businessWriteCount || 0)
    const listFacts = await getScmStandardPageFacts('purchase-order')
    const objects = listFacts?.data?.objects || listFacts?.data?.rows || []
    const createdIds = new Set((response.data.purchaseOrders || []).map(item => item.objectId))
    listVisibleCount.value = objects.filter(item => createdIds.has(item.objectId)).length
    if (listVisibleCount.value !== Number(response.data.purchaseOrderCount || 0)) {
      throw new Error('采购订单已创建，但正式列表事实源数量不一致')
    }
    creationDialogVisible.value = false
    ElMessage.success(`${response.data.purchaseOrderCount} 个采购订单已按供应商拆分并进入正式列表。`)
    await router.push('/scm/purchase-order')
  } catch (error) { ElMessage.error(error.message || String(error)) }
  finally { purchaseOrderCreating.value = false }
}
onMounted(refresh)
</script>

<style scoped>
.node-page{display:grid;gap:18px;padding:20px}.page-heading,.section-heading,.next{display:flex;align-items:center;justify-content:space-between;gap:16px}.page-heading h1{margin:4px 0}.page-heading p,.page-heading span,.section-heading p,.facts span,.next span,.readonly{color:#64748b}.panel{display:grid;gap:16px;padding:18px;border:1px solid #dbe4ee;border-radius:12px;background:#fff}.facts{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.facts article,.next div{display:grid;gap:5px}.actions{display:flex;flex-wrap:wrap;gap:10px}.completeness{display:flex;flex-wrap:wrap;gap:20px;padding:12px;border-radius:8px;background:#f8fafc}.supplier-split-selections,.standard-context-selections{display:grid;gap:12px;width:100%}.supplier-split-row,.standard-context-row{display:grid;grid-template-columns:minmax(180px,1fr) minmax(260px,1.5fr);align-items:center;gap:12px}.standard-context-row{padding:10px;border:1px solid #dbe4ee;border-radius:8px}@media(max-width:800px){.page-heading,.section-heading,.next{align-items:flex-start;flex-direction:column}.facts{grid-template-columns:1fr}.supplier-split-row,.standard-context-row{grid-template-columns:1fr}}
</style>
