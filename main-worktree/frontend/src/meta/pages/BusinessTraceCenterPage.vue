<template>
  <main class="business-trace-center-page">
    <header class="page-header">
      <section>
        <p class="eyebrow">V1.13.28 Enterprise Business Trace Center</p>
        <h1>企业业务追踪中心</h1>
        <p>
          从业务源头只读追踪完整业务链。本轮以 P2P 采购链作为第一实例，预留 O2C 销售、MFG 生产、
          QMS 质量、APS 计划追踪框架；不修改业务流程，不写总账，不核销，不生成银行流水。
        </p>
        <p class="module-badge">当前实例：P2P Business Trace</p>
      </section>
      <nav class="trace-nav" aria-label="企业业务追踪导航">
        <router-link class="trace-nav-button" to="/analytics">返回分析中心</router-link>
        <router-link class="trace-nav-button" to="/finance/p2p-validation-center">P2P验证中心</router-link>
        <span class="module-badge">业务追踪中心 当前</span>
      </nav>
    </header>

    <section class="trace-shell">
      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>高级查询</h2>
              <span>当前优先支持采购订单号查询，其他入口保留为企业级追踪框架设计。</span>
            </div>
            <el-tag type="info">只读查询</el-tag>
          </div>
        </template>

        <section class="query-grid">
          <label>
            <span>单据类型</span>
            <el-select v-model="query.documentType" placeholder="选择单据类型">
              <el-option label="请购单" value="purchaseRequest" />
              <el-option label="采购订单" value="purchaseOrder" />
              <el-option label="收货单" value="receipt" />
              <el-option label="检验单" value="inspection" />
              <el-option label="库存流水" value="inventoryTransaction" />
              <el-option label="应付单" value="payable" />
              <el-option label="付款凭证" value="paymentVoucher" />
            </el-select>
          </label>
          <label>
            <span>单号</span>
            <el-input v-model="query.documentNo" clearable placeholder="例如：PO2026070605510641 或 PO202607" @keyup.enter="selectFirstResult" />
          </label>
          <label>
            <span>供应商</span>
            <el-input v-model="query.supplier" clearable placeholder="支持供应商名称模糊查询" />
          </label>
          <label>
            <span>日期范围</span>
            <el-date-picker
              v-model="query.dateRange"
              type="daterange"
              unlink-panels
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              value-format="YYYY-MM-DD"
            />
          </label>
          <label>
            <span>业务状态</span>
            <el-select v-model="query.businessStatus" placeholder="业务状态">
              <el-option label="全部" value="all" />
              <el-option label="采购中" value="purchasing" />
              <el-option label="待收货" value="pendingReceipt" />
              <el-option label="检验中" value="inspection" />
              <el-option label="待入库" value="pendingInventory" />
              <el-option label="已入库" value="inInventory" />
              <el-option label="待付款" value="pendingPayment" />
              <el-option label="已付款" value="paid" />
              <el-option label="异常" value="abnormal" />
            </el-select>
          </label>
          <label>
            <span>风险状态</span>
            <el-select v-model="query.riskStatus" placeholder="风险状态">
              <el-option label="全部" value="all" />
              <el-option label="正常" value="normal" />
              <el-option label="有风险" value="risk" />
            </el-select>
          </label>
        </section>

        <div class="query-actions">
          <el-button type="primary" @click="selectFirstResult">查询业务链</el-button>
          <el-button @click="resetQuery">重置条件</el-button>
        </div>
        <p class="boundary-note">
          边界：业务追踪中心负责查业务链；P2P验证中心负责发现数据问题；风险闭环中心负责处理问题。三个模块只读衔接，不反向修改业务。
        </p>
      </el-card>

      <section class="architecture-grid">
        <article v-for="item in traceDomains" :key="item.key" :class="['domain-card', { active: item.active }]">
          <strong>{{ item.title }}</strong>
          <span>{{ item.description }}</span>
          <el-tag :type="item.active ? 'success' : 'info'">{{ item.statusText }}</el-tag>
        </article>
      </section>

      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>业务追踪结果</h2>
              <span>显示符合条件的 P2P 采购链，点击一行查看完整时间轴。</span>
            </div>
            <el-tag>{{ filteredTraces.length }} 条</el-tag>
          </div>
        </template>

        <el-table :data="displayTraces" border stripe height="320" @row-click="selectTrace">
          <el-table-column prop="traceType" label="跟踪类型" min-width="130" fixed="left" />
          <el-table-column prop="traceNo" label="跟踪单号" min-width="180" />
          <el-table-column prop="relatedPurchaseOrderNo" label="关联采购订单" min-width="180" />
          <el-table-column prop="supplierText" label="供应商" min-width="220" />
          <el-table-column prop="amountText" label="金额" min-width="120" />
          <el-table-column prop="businessStatusText" label="业务状态" min-width="130" />
          <el-table-column prop="riskStatusText" label="风险状态" min-width="120">
            <template #default="{ row }">
              <el-tag :type="row.riskStatus === 'normal' ? 'success' : 'warning'">{{ row.riskStatusText }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="chainSummary" label="链路摘要" min-width="460" />
          <template v-if="false">
          <el-table-column prop="purchaseOrderNo" label="采购订单" min-width="180" fixed="left" />
          <el-table-column prop="supplierText" label="供应商" min-width="220" />
          <el-table-column prop="amountText" label="金额" min-width="120" />
          <el-table-column prop="businessStatusText" label="业务状态" min-width="130" />
          <el-table-column prop="riskStatusText" label="风险状态" min-width="120">
            <template #default="{ row }">
              <el-tag :type="row.riskStatus === 'normal' ? 'success' : 'warning'">{{ row.riskStatusText }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="nodeSummary" label="链路摘要" min-width="300" />
          </template>
        </el-table>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>P2P业务链时间轴</h2>
              <span>{{ selectedTrace ? selectedTrace.purchaseOrderNo : '请选择一条采购链' }}</span>
            </div>
            <el-tag :type="selectedTrace?.riskStatus === 'normal' ? 'success' : 'warning'">
              {{ selectedTrace?.riskStatusText || '待查询' }}
            </el-tag>
          </div>
        </template>

        <section v-if="selectedTrace" class="selected-trace-summary">
          <article>
            <span>跟踪类型</span>
            <strong>{{ selectedTraceSummary.traceType }}</strong>
          </article>
          <article>
            <span>跟踪单号</span>
            <strong>{{ selectedTraceSummary.traceNo }}</strong>
          </article>
          <article>
            <span>关联采购订单</span>
            <strong>{{ selectedTraceSummary.relatedPurchaseOrderNo }}</strong>
          </article>
          <article>
            <span>供应商</span>
            <strong>{{ selectedTraceSummary.supplier }}</strong>
          </article>
          <article>
            <span>业务状态</span>
            <strong>{{ selectedTraceSummary.businessStatus }}</strong>
          </article>
          <article>
            <span>风险状态</span>
            <strong>{{ selectedTraceSummary.riskStatus }}</strong>
          </article>
        </section>

        <section v-if="selectedTrace" class="amount-reconciliation-card">
          <header>
            <div>
              <h3>金额对照</h3>
              <span>链路完整不代表金额一致，金额只按最终业务对象核对。</span>
            </div>
            <el-tag :type="selectedAmountReconciliation.amountStatus === 'matched' ? 'success' : selectedAmountReconciliation.amountStatus === 'pending' ? 'info' : 'warning'">
              {{ selectedAmountReconciliation.amountStatusText }}
            </el-tag>
          </header>
          <div class="amount-grid">
            <article>
              <span>采购金额</span>
              <strong>{{ selectedAmountReconciliation.purchaseAmountText }}</strong>
              <small>{{ selectedAmountReconciliation.purchaseAmountSource }}</small>
            </article>
            <article>
              <span>应付金额</span>
              <strong>{{ selectedAmountReconciliation.payableAmountText }}</strong>
              <small>{{ selectedAmountReconciliation.payableAmountSourceDocumentsText }}</small>
            </article>
            <article>
              <span>付款金额</span>
              <strong>{{ selectedAmountReconciliation.paymentAmountText }}</strong>
              <small>{{ selectedAmountReconciliation.paymentAmountSourceDocumentsText }}</small>
            </article>
          </div>
          <p>{{ selectedAmountReconciliation.amountConclusion }}</p>
        </section>

        <section v-if="selectedTrace" class="trace-timeline">
          <article v-for="node in selectedDisplayNodes" :key="node.key" :class="['trace-node', node.status]">
            <header>
              <strong>{{ node.title }}</strong>
              <el-tag :type="node.status === 'normal' ? 'success' : node.status === 'placeholder' ? 'info' : 'warning'">{{ node.statusText }}</el-tag>
            </header>
            <p class="node-documents">
              <span v-for="doc in node.primaryDocuments" :key="doc">{{ doc }}</span>
              <span v-if="!node.primaryDocuments.length">-</span>
            </p>
            <p v-if="node.moreCount > 0" class="node-more">另有 {{ node.moreCount }} 条，点击展开查看。</p>
            <dl class="node-summary-dl">
              <template v-for="detail in node.summaryDetails" :key="detail.label">
                <dt>{{ detail.label }}</dt>
                <dd>{{ detail.value || '-' }}</dd>
              </template>
            </dl>
            <el-collapse v-if="node.detailGroups.length" v-model="expandedNodeKeys" class="node-detail-collapse">
              <el-collapse-item :name="node.key" title="展开明细">
                <section v-for="group in node.detailGroups" :key="group.key" class="node-detail-group">
                  <header>
                    <strong>{{ group.title }}</strong>
                    <span>{{ group.documents.length }} 张</span>
                  </header>
                  <p>
                    <span v-for="doc in group.documents" :key="doc">{{ doc }}</span>
                    <span v-if="!group.documents.length">-</span>
                  </p>
                </section>
              </el-collapse-item>
            </el-collapse>
          </article>
        </section>
        <el-empty v-else description="请输入或选择一条业务链进行追踪" />
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>只读诊断</h2>
              <span>businessTraceSummary 仅用于页面核对，不写入任何业务状态。</span>
            </div>
            <div class="diagnostic-actions">
              <button type="button" class="diagnostic-copy-button" @click="copyDiagnosticData">复制诊断数据</button>
              <el-tag type="info">{{ copyStatus || '诊断数据' }}</el-tag>
            </div>
          </div>
        </template>
        <section v-if="selectedTrace" class="trace-analysis-panel">
          <header>
            <div>
              <h3>业务追踪数据分析</h3>
              <span>只读分析业务链健康度，不作为正式 KPI，不反向修改业务数据。</span>
            </div>
            <el-tag :type="businessTraceAnalysis.traceScore >= 85 ? 'success' : businessTraceAnalysis.traceScore >= 70 ? 'warning' : 'danger'">
              综合评分 {{ businessTraceAnalysis.traceScore }}
            </el-tag>
          </header>

          <div class="analysis-card-grid">
            <article class="score-card">
              <span>综合追踪评分</span>
              <strong>{{ businessTraceAnalysis.traceScore }} / 100</strong>
              <small>仅作为业务链健康度分析参考，不作为正式 KPI。</small>
            </article>
            <article>
              <span>业务链完整度</span>
              <strong>{{ businessTraceAnalysis.chainCompleteness.percentText }}</strong>
              <small>{{ businessTraceAnalysis.chainCompleteness.summary }}</small>
            </article>
            <article>
              <span>金额一致性</span>
              <strong>{{ businessTraceAnalysis.amountConsistency.amountStatusText }}</strong>
              <small>{{ businessTraceAnalysis.amountConsistency.amountConclusion }}</small>
            </article>
            <article>
              <span>证据完整度</span>
              <strong>{{ businessTraceAnalysis.evidenceCompleteness.percentText }}</strong>
              <small>{{ businessTraceAnalysis.evidenceCompleteness.summary }}</small>
            </article>
            <article>
              <span>分析结论</span>
              <strong>{{ businessTraceAnalysis.analysisConclusion }}</strong>
            </article>
          </div>

          <div class="node-health-list">
            <article v-for="node in businessTraceAnalysis.nodeHealth" :key="node.key" :class="['node-health-item', node.status]">
              <strong>{{ node.nodeName }}</strong>
              <span>{{ node.statusText }}</span>
              <small>{{ node.description }}</small>
            </article>
          </div>

          <section class="enterprise-health-panel">
            <header>
              <div>
                <h3>企业数据健康评分</h3>
                <span>评分仅用于数据健康观察，不作为正式 KPI；评分结果受当前会话数据完整性影响。</span>
              </div>
              <el-tag :type="enterpriseDataHealthScore.overallScore >= 90 ? 'success' : enterpriseDataHealthScore.overallScore >= 70 ? 'warning' : 'danger'">
                {{ enterpriseDataHealthScore.scoreLevel }}
              </el-tag>
            </header>
            <div class="health-score-layout">
              <article class="health-score-main">
                <span>综合健康评分</span>
                <strong>{{ enterpriseDataHealthScore.overallScore }} / 100</strong>
                <small>{{ enterpriseDataHealthScore.scoreConclusion }}</small>
              </article>
              <article v-for="dimension in enterpriseDataHealthScore.dimensionScores" :key="dimension.key" class="health-score-dimension">
                <span>{{ dimension.name }}</span>
                <strong>{{ dimension.score }} / {{ dimension.weight }}</strong>
                <small>{{ dimension.summary }}</small>
              </article>
            </div>
            <div class="health-deduction-list">
              <strong>扣分原因</strong>
              <span v-for="reason in enterpriseDataHealthScore.deductionReasons" :key="reason">{{ reason }}</span>
            </div>
          </section>
        </section>
        <pre class="diagnostic-json">{{ formattedBusinessTraceSummary }}</pre>
      </el-card>
    </section>
  </main>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import {
  buildBusinessTraceDiagnostic,
  businessTraceSearchText,
  createBusinessTraceSnapshot,
  listP2PBusinessTraces,
} from '../trace/businessTraceEngine.js'
import { buildEnterpriseDataHealthScore } from '../analysis/dataHealthScoreModel.js'

const query = reactive({
  documentType: 'purchaseOrder',
  documentNo: 'PO2026070605510641',
  supplier: '',
  dateRange: [],
  businessStatus: 'all',
  riskStatus: 'all',
})

const selectedTraceId = ref('')
const copyStatus = ref('')
const expandedNodeKeys = ref([])
const selectedTraceSource = ref({
  selectedTraceNo: '',
  selectedRelatedPurchaseOrderNo: '',
  selectedBy: 'auto',
  selectedAt: '',
})

const traceDomains = [
  { key: 'p2pTrace', title: 'P2P采购追踪', description: '请购、询价、核价、采购订单、收货、检验、入库、库存流水、应付、付款。', statusText: '已启用', active: true },
  { key: 'salesTrace', title: 'O2C销售追踪', description: '销售机会、订单、发货、开票、收款，后续版本扩展。', statusText: '预留', active: false },
  { key: 'productionTrace', title: 'MFG生产追踪', description: '计划、工单、领料、报工、完工入库，后续版本扩展。', statusText: '预留', active: false },
  { key: 'qualityTrace', title: 'QMS质量追踪', description: '来料、过程、成品质量追踪，后续版本扩展。', statusText: '预留', active: false },
  { key: 'scheduleTrace', title: 'APS计划追踪', description: '计划、排程、产能与交付追踪，后续版本扩展。', statusText: '预留', active: false },
]

const traceSnapshot = computed(() => createBusinessTraceSnapshot())

const displayResultColumns = [
  '跟踪类型',
  '跟踪单号',
  '关联采购订单',
  '供应商',
  '金额',
  '业务状态',
  '风险状态',
  '链路摘要',
]

const allTraces = computed(() => listP2PBusinessTraces({
  documentNo: query.documentNo,
  documentType: query.documentType,
}, traceSnapshot.value))

const filteredTraces = computed(() => {
  const keyword = normalizeText(query.documentNo)
  return allTraces.value.filter((trace) => {
    const documentMatched = !keyword || traceSearchText(trace).includes(keyword)
    const supplierMatched = !normalizeText(query.supplier) || normalizeText(trace.supplierText).includes(normalizeText(query.supplier))
    const statusMatched = query.businessStatus === 'all' || trace.businessStatus === query.businessStatus
    const riskMatched = query.riskStatus === 'all' || trace.riskStatus === query.riskStatus
    const dateMatched = matchDateRange(trace)
    const typeMatched = matchDocumentType(trace)
    return documentMatched && supplierMatched && statusMatched && riskMatched && dateMatched && typeMatched
  })
})

const selectedTrace = computed(() => (
  filteredTraces.value.find((trace) => trace.id === selectedTraceId.value)
  || filteredTraces.value[0]
  || null
))

const displayTraces = computed(() => filteredTraces.value.map((trace) => ({
  ...trace,
  ...buildDisplayTrace(trace),
})))

const selectedTraceSummary = computed(() => buildSelectedTraceSummary(selectedTrace.value))

const selectedAmountReconciliation = computed(() => buildSelectedAmountReconciliation(selectedTrace.value))

const selectedDisplayNodes = computed(() => buildDisplayNodes(selectedTrace.value))

const displayLayoutSummary = computed(() => buildDisplayLayoutSummary(selectedDisplayNodes.value))

const businessTraceAnalysis = computed(() => buildBusinessTraceAnalysis(selectedTrace.value))

const enterpriseDataHealthScore = computed(() => buildEnterpriseDataHealthScore({
  trace: selectedTrace.value,
  businessTraceAnalysis: businessTraceAnalysis.value,
  amountReconciliation: selectedTrace.value?.amountReconciliation || selectedAmountReconciliation.value,
  operationCapability: {
    sorting: true,
    exportCurrentResult: true,
    advancedFilter: true,
    diagnosticCopy: true,
  },
}))

const selectedTraceSourceDiagnostic = computed(() => ({
  selectedTraceNo: selectedTraceSummary.value.traceNo,
  selectedRelatedPurchaseOrderNo: selectedTraceSummary.value.relatedPurchaseOrderNo,
  selectedBy: selectedTraceSource.value.selectedBy,
  selectedAt: selectedTraceSource.value.selectedAt,
}))

const businessTraceSummary = computed(() => ({
  version: 'V1.13.28',
  traceCenter: 'Enterprise Business Trace Center',
  activeScenario: 'p2pTrace',
  sourceType: query.documentType,
  sourceTypeText: documentTypeText(query.documentType),
  sourceNo: query.documentNo || selectedTrace.value?.purchaseOrderNo || '',
  supplier: query.supplier || selectedTrace.value?.supplierText || '',
  traceStatus: selectedTrace.value?.riskStatus === 'normal' ? 'normal' : 'attention',
  traceStatusText: selectedTrace.value?.riskStatusText || '待查询',
  traceNodes: selectedTrace.value?.nodes || [],
  reservedTraceDomains: ['salesTrace', 'productionTrace', 'qualityTrace', 'scheduleTrace'],
  boundary: '只读查询；不修改业务流程；不写总账；不核销；不生成银行流水。',
}))

const businessTraceDiagnostic = computed(() => ({
  ...buildBusinessTraceDiagnostic({
  page: 'BusinessTraceCenter',
  version: 'V1.13.28.3',
  queryType: query.documentType,
  queryValue: query.documentNo,
  traces: filteredTraces.value,
  selectedTrace: selectedTrace.value,
  warnings: filteredTraces.value.length ? [] : ['当前查询未匹配业务链，请检查单据类型或单号。'],
  }),
  displayResultColumns,
  selectedTraceSummary: selectedTraceSummary.value,
  selectedTraceSource: selectedTraceSourceDiagnostic.value,
  displayLayoutSummary: displayLayoutSummary.value,
  businessTraceAnalysis: businessTraceAnalysis.value,
  enterpriseDataHealthScore: enterpriseDataHealthScore.value,
}))

const formattedBusinessTraceSummary = computed(() => JSON.stringify({
  businessTraceSummary: businessTraceSummary.value,
  businessTraceDiagnostic: businessTraceDiagnostic.value,
  enterpriseDataHealthScore: enterpriseDataHealthScore.value,
}, null, 2))

watch(filteredTraces, (traces) => {
  if (!traces.some((trace) => trace.id === selectedTraceId.value)) {
    selectedTraceId.value = traces[0]?.id || ''
    updateSelectedTraceSource(traces[0], 'auto')
  }
}, { immediate: true })

function selectTrace(row) {
  selectedTraceId.value = row?.id || ''
  updateSelectedTraceSource(row, 'rowClick')
}

function selectFirstResult() {
  selectedTraceId.value = filteredTraces.value[0]?.id || ''
  updateSelectedTraceSource(filteredTraces.value[0], 'queryButton')
}

function resetQuery() {
  query.documentType = 'purchaseOrder'
  query.documentNo = ''
  query.supplier = ''
  query.dateRange = []
  query.businessStatus = 'all'
  query.riskStatus = 'all'
  selectFirstResult()
}

function updateSelectedTraceSource(trace, selectedBy = 'auto') {
  const summary = buildSelectedTraceSummary(trace)
  selectedTraceSource.value = {
    selectedTraceNo: summary.traceNo,
    selectedRelatedPurchaseOrderNo: summary.relatedPurchaseOrderNo,
    selectedBy,
    selectedAt: new Date().toISOString(),
  }
}

async function copyDiagnosticData() {
  const text = JSON.stringify({
    businessTraceDiagnostic: businessTraceDiagnostic.value,
    businessTraceSummary: businessTraceSummary.value,
    enterpriseDataHealthScore: enterpriseDataHealthScore.value,
  }, null, 2)
  try {
    if (navigator?.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
    } else {
      fallbackCopy(text)
    }
    copyStatus.value = '已复制诊断数据'
  } catch (error) {
    try {
      fallbackCopy(text)
      copyStatus.value = '已复制诊断数据'
    } catch (fallbackError) {
      copyStatus.value = '复制失败，请重试'
    }
  }
}

function fallbackCopy(text) {
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', 'readonly')
  textarea.style.position = 'fixed'
  textarea.style.left = '-9999px'
  document.body.appendChild(textarea)
  textarea.select()
  document.execCommand('copy')
  document.body.removeChild(textarea)
}

function buildDisplayTrace(trace = {}) {
  const traceNo = resolveTraceNo(trace)
  return {
    traceType: documentTypeText(query.documentType),
    traceNo,
    relatedPurchaseOrderNo: trace.purchaseOrderNo || trace.poNo || '-',
    supplierText: trace.supplierText || '-',
    amountText: trace.amountText || '-',
    businessStatusText: trace.businessStatusText || '-',
    riskStatus: trace.riskStatus || 'risk',
    riskStatusText: trace.riskStatusText || '-',
    chainSummary: buildChainSummary(trace),
  }
}

function buildSelectedTraceSummary(trace = null) {
  if (!trace) {
    return {
      traceType: documentTypeText(query.documentType),
      traceNo: query.documentNo || '-',
      relatedPurchaseOrderNo: '-',
      supplier: '-',
      amount: '-',
      businessStatus: '-',
      riskStatus: '-',
      chainSummary: '-',
    }
  }
  const display = buildDisplayTrace(trace)
  return {
    traceType: display.traceType,
    traceNo: display.traceNo,
    relatedPurchaseOrderNo: display.relatedPurchaseOrderNo,
    supplier: display.supplierText,
    amount: display.amountText,
    businessStatus: display.businessStatusText,
    riskStatus: display.riskStatusText,
    chainSummary: display.chainSummary,
  }
}

function buildSelectedAmountReconciliation(trace = null) {
  const reconciliation = trace?.amountReconciliation || {}
  const summary = trace?.amountSummary || {}
  const amountStatus = reconciliation.amountStatus || 'pending'
  return {
    amountStatus,
    amountStatusText: amountStatus === 'matched' ? '基本一致' : amountStatus === 'difference' ? '金额待核对' : '金额待确认',
    purchaseAmountText: formatCurrency(reconciliation.purchaseAmount ?? summary.purchaseAmount ?? 0),
    payableAmountText: reconciliation.payableAmount === null || reconciliation.payableAmount === undefined
      ? '应付金额待确认'
      : formatCurrency(reconciliation.payableAmount),
    paymentAmountText: reconciliation.paymentAmount === null || reconciliation.paymentAmount === undefined
      ? '付款金额待确认'
      : formatCurrency(reconciliation.paymentAmount),
    purchaseAmountSource: reconciliation.purchaseAmountSource || '采购订单金额',
    payableAmountSourceDocumentsText: reconciliation.payableAmountSourceDocuments?.join('、') || '应付金额待确认',
    paymentAmountSourceDocumentsText: reconciliation.paymentAmountSourceDocuments?.join('、') || '付款金额待确认',
    amountConclusion: reconciliation.amountConclusion || '金额仍待最终业务对象确认。',
  }
}

function buildDisplayNodes(trace = null) {
  if (!trace?.nodes?.length) return []
  return trace.nodes.map((node) => {
    if (node.key === 'warehouseEntry') return buildWarehouseEntryDisplayNode(node, trace)
    if (node.key === 'inventoryTransaction') return buildInventoryDisplayNode(node, trace)
    if (node.key === 'payable') return buildPayableDisplayNode(node, trace)
    if (node.key === 'payment') return buildPaymentDisplayNode(node, trace)
    return buildDefaultDisplayNode(node)
  })
}

function buildDefaultDisplayNode(node = {}) {
  const documents = asArray(node.documentNo)
  return {
    ...node,
    primaryDocuments: documents.slice(0, 3),
    moreCount: Math.max(documents.length - 3, 0),
    summaryDetails: node.details || [],
    detailGroups: documents.length > 3 ? [{ key: `${node.key}-all`, title: '完整单据', documents }] : [],
  }
}

function buildWarehouseEntryDisplayNode(node = {}, trace = {}) {
  const txns = trace.inventoryDisplay?.displayedTxnNos || asArray(node.documentNo)
  return {
    ...node,
    documentNo: txns.join('、'),
    primaryDocuments: txns.slice(0, 3),
    moreCount: Math.max(txns.length - 3, 0),
    summaryDetails: [
      { label: '入库依据', value: txns.length ? '库存流水代表入库完成' : '待确认' },
      { label: '业务流水数量', value: trace.inventoryDisplay?.businessTxnCount ?? txns.length },
    ],
    detailGroups: txns.length > 3 ? [{ key: 'warehouseEntry-txn', title: '完整业务 TXN', documents: txns }] : [],
  }
}

function buildInventoryDisplayNode(node = {}, trace = {}) {
  const txns = trace.inventoryDisplay?.displayedTxnNos || asArray(node.documentNo)
  return {
    ...node,
    documentNo: txns.join('、'),
    primaryDocuments: txns.slice(0, 3),
    moreCount: Math.max(txns.length - 3, 0),
    summaryDetails: [
      { label: '业务流水数量', value: trace.inventoryDisplay?.businessTxnCount ?? txns.length },
    ],
    detailGroups: txns.length > 3 ? [{ key: 'inventoryTransaction-txn', title: '完整业务 TXN', documents: txns }] : [],
  }
}

function buildPayableDisplayNode(node = {}, trace = {}) {
  const groups = trace.documentGroups || {}
  const apdDocs = uniqueList(groups.accountPayable || [])
  return {
    ...node,
    documentNo: apdDocs.join('、'),
    primaryDocuments: apdDocs.slice(0, 3),
    moreCount: Math.max(apdDocs.length - 3, 0),
    summaryDetails: [
      { label: '最终应付对象', value: `${apdDocs.length} 张` },
      { label: '应付金额', value: trace.amountSummary?.payableAmountText || '应付金额待确认' },
      { label: '金额依据', value: apdDocs.length ? 'APD' : '待确认' },
    ],
    detailGroups: [
      { key: 'payablePrepare', title: '应付预备 PP', documents: uniqueList(groups.payablePrepare || []) },
      { key: 'payableCheck', title: '应付核对 PC', documents: uniqueList(groups.payableCheck || []) },
      { key: 'invoicePrepare', title: '发票预备 IP', documents: uniqueList(groups.invoicePrepare || []) },
      { key: 'accountPayable', title: '应付对象 APD', documents: apdDocs },
    ],
  }
}

function buildPaymentDisplayNode(node = {}, trace = {}) {
  const groups = trace.documentGroups || {}
  const fpvDocs = uniqueList(groups.formalPaymentVoucher || [])
  const fallbackVoucherDocs = uniqueList(groups.paymentVoucher || [])
  const mainDocs = fpvDocs.length ? fpvDocs : fallbackVoucherDocs
  const amountStatusText = selectedAmountReconciliation.value.amountStatusText
  return {
    ...node,
    documentNo: mainDocs.join('、'),
    primaryDocuments: mainDocs.slice(0, 4),
    moreCount: Math.max(mainDocs.length - 4, 0),
    summaryDetails: [
      { label: '最终付款凭证', value: `${mainDocs.length} 张` },
      { label: '付款金额', value: trace.amountSummary?.paymentAmountText || '付款金额待确认' },
      { label: '金额状态', value: amountStatusText },
      { label: '金额依据', value: fpvDocs.length ? '正式付款凭证 FPV' : fallbackVoucherDocs.length ? '付款凭证' : '待确认' },
    ],
    detailGroups: [
      { key: 'paymentDraft', title: '付款草稿 SPD', documents: uniqueList(groups.paymentDraft || []) },
      { key: 'paymentOrder', title: '付款指令 POP / POD', documents: uniqueList(groups.paymentOrder || []) },
      { key: 'paymentExecution', title: '付款执行 PEX', documents: uniqueList(groups.paymentExecution || []) },
      { key: 'paymentRecord', title: '付款记录 PRR', documents: uniqueList(groups.paymentRecord || []) },
      { key: 'paymentVoucher', title: '付款凭证 PVD / PVR', documents: fallbackVoucherDocs },
      { key: 'formalPaymentVoucher', title: '正式付款凭证 FPV', documents: fpvDocs },
    ],
  }
}

function buildDisplayLayoutSummary(nodes = []) {
  const mainDisplayedDocuments = {}
  const hiddenDetailDocuments = {}
  nodes.forEach((node) => {
    mainDisplayedDocuments[node.key] = node.primaryDocuments || []
    hiddenDetailDocuments[node.key] = (node.detailGroups || []).flatMap((group) => group.documents || [])
  })
  return {
    collapsedNodeCount: nodes.filter((node) => node.detailGroups?.length).length,
    expandedNodeKeys: [...expandedNodeKeys.value],
    mainDisplayedDocuments,
    hiddenDetailDocuments,
  }
}

function buildBusinessTraceAnalysis(trace = null) {
  const nodes = trace?.nodes || []
  const scorableNodes = nodes.filter((node) => node.status !== 'placeholder')
  const normalNodes = scorableNodes.filter((node) => node.status === 'normal')
  const missingNodes = scorableNodes.filter((node) => node.status === 'missing')
  const chainPercent = scorableNodes.length ? Math.round((normalNodes.length / scorableNodes.length) * 100) : 0
  const nodeHealth = nodes.map((node) => buildNodeHealth(node))
  const amountConsistency = buildAmountConsistencyAnalysis(trace)
  const evidenceCompleteness = buildEvidenceCompletenessAnalysis(trace)
  const criticalMissingCount = nodeHealth.filter((node) => node.isCritical && node.status === 'missing').length
  const evidenceMissingCount = evidenceCompleteness.items.filter((item) => !item.completed).length
  const amountPenalty = amountConsistency.amountStatus === 'difference' ? 10 : amountConsistency.amountStatus === 'pending' ? 6 : 0
  const traceScore = Math.max(0, 100 - criticalMissingCount * 12 - evidenceMissingCount * 5 - amountPenalty)
  return {
    chainCompleteness: {
      totalNodeCount: scorableNodes.length,
      completedNodeCount: normalNodes.length,
      missingNodeCount: missingNodes.length,
      percent: chainPercent,
      percentText: `${chainPercent}%`,
      summary: missingNodes.length
        ? `业务链存在 ${missingNodes.length} 个缺失节点：${missingNodes.map((node) => node.title).join('、')}`
        : '业务链关键节点已追踪完整。',
    },
    nodeHealth,
    amountConsistency,
    evidenceCompleteness,
    traceScore,
    analysisConclusion: buildAnalysisConclusion({ missingNodes, amountConsistency, evidenceCompleteness }),
  }
}

function buildNodeHealth(node = {}) {
  const criticalNodes = ['purchaseOrder', 'receipt', 'inspection', 'warehouseEntry', 'inventoryTransaction', 'payable', 'payment']
  const isCritical = criticalNodes.includes(node.key)
  return {
    key: node.key,
    nodeName: node.title,
    status: node.status,
    statusText: node.status === 'normal' ? '完成' : node.status === 'placeholder' ? '预留' : '缺失',
    isCritical,
    affectsClosure: isCritical && node.status === 'missing',
    description: node.status === 'placeholder'
      ? '当前为预留节点，不纳入扣分。'
      : node.status === 'normal'
        ? '已找到对应业务证据。'
        : '未找到对应业务证据，需要核对来源链。',
  }
}

function buildAmountConsistencyAnalysis(trace = null) {
  const reconciliation = trace?.amountReconciliation || {}
  const amountStatus = reconciliation.amountStatus || 'pending'
  return {
    purchaseAmount: reconciliation.purchaseAmount ?? null,
    payableAmount: reconciliation.payableAmount ?? null,
    paymentAmount: reconciliation.paymentAmount ?? null,
    purchaseAmountText: formatOptionalCurrency(reconciliation.purchaseAmount),
    payableAmountText: formatOptionalCurrency(reconciliation.payableAmount),
    paymentAmountText: formatOptionalCurrency(reconciliation.paymentAmount),
    amountStatus,
    amountStatusText: amountStatus === 'matched' ? '基本一致' : amountStatus === 'difference' ? '金额待核对' : '金额待确认',
    amountConclusion: reconciliation.amountConclusion || '金额仍待最终业务对象确认。',
  }
}

function buildEvidenceCompletenessAnalysis(trace = null) {
  const nodes = trace?.nodes || []
  const evidenceRules = [
    { key: 'purchaseOrder', label: '采购订单' },
    { key: 'receipt', label: '收货单' },
    { key: 'inspection', label: '检验单' },
    { key: 'inventoryTransaction', label: '库存流水' },
    { key: 'payable', label: '应付对象' },
    { key: 'payment', label: '付款凭证' },
  ]
  const items = evidenceRules.map((rule) => {
    const node = nodes.find((item) => item.key === rule.key)
    return {
      key: rule.key,
      label: rule.label,
      completed: node?.status === 'normal',
      statusText: node?.status === 'normal' ? '已具备' : '缺失',
    }
  })
  const completedCount = items.filter((item) => item.completed).length
  const percent = items.length ? Math.round((completedCount / items.length) * 100) : 0
  const missingLabels = items.filter((item) => !item.completed).map((item) => item.label)
  return {
    totalEvidenceCount: items.length,
    completedEvidenceCount: completedCount,
    missingEvidenceCount: missingLabels.length,
    percent,
    percentText: `${percent}%`,
    items,
    summary: missingLabels.length ? `缺少：${missingLabels.join('、')}` : '关键证据已具备。',
  }
}

function buildAnalysisConclusion({ missingNodes = [], amountConsistency = {}, evidenceCompleteness = {} } = {}) {
  if (missingNodes.length) {
    return `业务链存在断点，需要核对 ${missingNodes.map((node) => node.title).join('、')} 节点。`
  }
  if (amountConsistency.amountStatus === 'difference') {
    return '业务链完整，但金额需要核对。'
  }
  if (amountConsistency.amountStatus === 'pending') {
    return '业务链基本完整，金额仍待最终业务对象确认。'
  }
  if (evidenceCompleteness.missingEvidenceCount > 0) {
    return '业务链可追踪，但部分证据仍需补充核对。'
  }
  return '业务链完整，金额基本一致。'
}

function resolveTraceNo(trace = {}) {
  const mappedKey = {
    purchaseRequest: 'purchaseRequest',
    purchaseOrder: 'purchaseOrder',
    receipt: 'receipt',
    inspection: 'inspection',
    inventoryTransaction: 'inventoryTransaction',
    payable: 'payable',
    paymentVoucher: 'payment',
  }[query.documentType]
  const nodeNo = (trace.nodes || []).find((node) => node.key === mappedKey)?.documentNo
  const keyword = normalizeText(query.documentNo)
  if (query.documentNo && (!nodeNo || normalizeText(nodeNo).includes(keyword))) return query.documentNo
  return nodeNo || query.documentNo || trace.purchaseOrderNo || trace.poNo || '-'
}

function buildChainSummary(trace = {}) {
  if (trace.nodes?.length) {
    return trace.nodes.map((node) => `${node.title}:${node.statusText}`).join(' / ')
  }
  return trace.nodeSummary || '-'
}

function matchDocumentType(trace) {
  const keyword = normalizeText(query.documentNo)
  if (!keyword) return true
  const nodeMap = Object.fromEntries(trace.nodes.map((node) => [node.key, normalizeText(node.documentNo)]))
  const mappedKey = {
    purchaseRequest: 'purchaseRequest',
    purchaseOrder: 'purchaseOrder',
    receipt: 'receipt',
    inspection: 'inspection',
    inventoryTransaction: 'inventoryTransaction',
    payable: 'payable',
    paymentVoucher: 'payment',
  }[query.documentType]
  return !mappedKey || nodeMap[mappedKey]?.includes(keyword) || traceSearchText(trace).includes(keyword)
}

function matchDateRange(trace) {
  if (!Array.isArray(query.dateRange) || query.dateRange.length !== 2) return true
  if (!trace.sourceDate) return true
  const [start, end] = query.dateRange
  return String(trace.sourceDate).slice(0, 10) >= start && String(trace.sourceDate).slice(0, 10) <= end
}

function traceSearchText(trace) {
  return businessTraceSearchText(trace)
}

function collectDocumentNos(nodes = []) {
  return uniqueList(nodes.flatMap((node) => asArray(node.documentNo)))
}

function resolveBusinessStatus({ receipts, inspections, transactions, payableNos, paymentNos, riskStatus }) {
  if (riskStatus === 'risk' && !receipts.length) return 'pendingReceipt'
  if (!inspections.length) return 'inspection'
  if (!transactions.length) return 'pendingInventory'
  if (!payableNos.length) return 'pendingPayment'
  if (!paymentNos.length) return 'pendingPayment'
  return 'paid'
}

function businessStatusText(status) {
  const map = {
    purchasing: '采购中',
    pendingReceipt: '待收货',
    inspection: '检验中',
    pendingInventory: '待入库',
    inInventory: '已入库',
    pendingPayment: '待付款',
    paid: '已付款',
    abnormal: '异常',
  }
  return map[status] || '待确认'
}

function documentTypeText(type) {
  const map = {
    purchaseRequest: '请购单',
    purchaseOrder: '采购订单',
    receipt: '收货单',
    inspection: '检验单',
    inventoryTransaction: '库存流水',
    payable: '应付单',
    paymentVoucher: '付款凭证',
  }
  return map[type] || '采购订单'
}

function orderNo(order = {}) {
  return recordNo(order, ['poNo', 'purchaseOrderNo', 'orderNo', 'no'])
}

function recordNo(record = {}, keys = []) {
  return keys.map((key) => record?.[key]).find((value) => hasText(value)) || ''
}

function firstText(...values) {
  return values.find((value) => hasText(value)) || ''
}

function hasText(value) {
  return String(value || '').trim().length > 0
}

function normalizeText(value) {
  return String(value || '').trim().toLowerCase()
}

function asArray(value) {
  if (Array.isArray(value)) return value.filter(Boolean)
  return String(value || '').split(/[、,，;；\s]+/).map((item) => item.trim()).filter(Boolean)
}

function uniqueList(items = []) {
  return Array.from(new Set(items.map((item) => String(item || '').trim()).filter(Boolean)))
}

function matchesAny(values = [], targets = []) {
  const normalizedTargets = targets.map((item) => String(item || '')).filter(Boolean)
  return values.some((value) => normalizedTargets.includes(String(value || '')))
}

function intersects(left = [], right = []) {
  const rightSet = new Set(right.map((item) => String(item || '')))
  return left.some((item) => rightSet.has(String(item || '')))
}

function amount(value) {
  const number = Number(value || 0)
  if (!Number.isFinite(number)) return 0
  return Math.round(number * 100) / 100
}

function lineAmount(line = {}) {
  return amount(line.amount || line.totalAmount || (Number(line.quantity || 0) * Number(line.price || line.unitPrice || 0)))
}

function formatCurrency(value) {
  return amount(value).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function formatOptionalCurrency(value) {
  return value === null || value === undefined ? '待确认' : formatCurrency(value)
}
</script>

<style scoped>
.business-trace-center-page {
  min-height: 100vh;
  padding: 24px;
  background: #f6f7fb;
  color: #1f2937;
}

.page-header {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: flex-start;
  margin-bottom: 18px;
}

.page-header h1 {
  margin: 6px 0 10px;
  font-size: 28px;
  font-weight: 700;
}

.page-header p {
  max-width: 860px;
  margin: 0 0 8px;
  line-height: 1.7;
  color: #5b6472;
}

.eyebrow {
  margin: 0;
  font-size: 12px;
  font-weight: 700;
  color: #2f6fbd;
  text-transform: uppercase;
}

.module-badge {
  display: inline-flex;
  padding: 4px 10px;
  border: 1px solid #b7d4ff;
  border-radius: 6px;
  background: #eaf3ff;
  color: #1d4f91;
}

.trace-nav {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.trace-nav-button {
  display: inline-flex;
  align-items: center;
  min-height: 34px;
  padding: 0 12px;
  border: 1px solid #d6dbe6;
  border-radius: 6px;
  background: #fff;
  color: #2f3a4a;
  text-decoration: none;
}

.trace-shell {
  display: grid;
  gap: 16px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
}

.card-header h2 {
  margin: 0 0 4px;
  font-size: 18px;
}

.card-header span {
  color: #6b7280;
}

.query-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(220px, 1fr));
  gap: 14px;
}

.query-grid label {
  display: grid;
  gap: 6px;
  font-size: 13px;
  color: #4b5563;
}

.query-actions {
  display: flex;
  gap: 10px;
  margin-top: 14px;
}

.diagnostic-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.boundary-note {
  margin: 14px 0 0;
  padding: 10px 12px;
  border: 1px solid #cfe0ff;
  border-radius: 6px;
  background: #f0f6ff;
  color: #31527a;
  line-height: 1.7;
}

.architecture-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(160px, 1fr));
  gap: 12px;
}

.domain-card {
  display: grid;
  gap: 8px;
  align-content: start;
  min-height: 110px;
  padding: 14px;
  border: 1px solid #dce2ec;
  border-radius: 8px;
  background: #fff;
}

.domain-card.active {
  border-color: #8ab9ff;
  background: #f2f7ff;
}

.domain-card span {
  color: #6b7280;
  line-height: 1.5;
}

.selected-trace-summary {
  display: grid;
  grid-template-columns: repeat(6, minmax(140px, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}

.selected-trace-summary article {
  display: grid;
  gap: 4px;
  padding: 12px;
  border: 1px solid #dbe2eb;
  border-radius: 8px;
  background: #fff;
}

.selected-trace-summary span {
  color: #6b7280;
  font-size: 12px;
}

.selected-trace-summary strong {
  color: #1f2937;
  word-break: break-word;
}

.amount-reconciliation-card {
  display: grid;
  gap: 12px;
  margin-bottom: 14px;
  padding: 14px;
  border: 1px solid #f0d48a;
  border-radius: 8px;
  background: #fffaf0;
}

.amount-reconciliation-card header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.amount-reconciliation-card h3 {
  margin: 0 0 4px;
  font-size: 16px;
}

.amount-reconciliation-card span,
.amount-reconciliation-card small,
.amount-reconciliation-card p {
  color: #6b7280;
}

.amount-reconciliation-card p {
  margin: 0;
  line-height: 1.7;
}

.amount-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(180px, 1fr));
  gap: 12px;
}

.amount-grid article {
  display: grid;
  gap: 4px;
  padding: 12px;
  border: 1px solid #ead6a1;
  border-radius: 8px;
  background: #fff;
}

.amount-grid strong {
  color: #1f2937;
  font-size: 18px;
}

.trace-timeline {
  display: grid;
  grid-template-columns: repeat(5, minmax(180px, 1fr));
  gap: 12px;
}

.trace-node {
  display: grid;
  gap: 8px;
  min-height: 160px;
  padding: 14px;
  border: 1px solid #dbe2eb;
  border-radius: 8px;
  background: #fff;
}

.trace-node.normal {
  border-color: #9bd1a6;
}

.trace-node.missing {
  border-color: #ffc4c4;
}

.trace-node.placeholder {
  border-color: #c9d8f0;
}

.trace-node header {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: center;
}

.trace-node p {
  margin: 0;
  color: #1f2937;
}

.node-documents,
.node-detail-group p {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.node-documents span,
.node-detail-group p span {
  display: inline-flex;
  max-width: 100%;
  padding: 3px 7px;
  border: 1px solid #d7deea;
  border-radius: 6px;
  background: #f8fafc;
  color: #243142;
  font-size: 12px;
  word-break: break-word;
}

.node-more {
  color: #64748b;
  font-size: 12px;
}

.trace-node dl {
  display: grid;
  grid-template-columns: 72px 1fr;
  gap: 6px 8px;
  margin: 0;
  font-size: 12px;
}

.trace-node dt {
  color: #7a8493;
}

.trace-node dd {
  margin: 0;
  color: #364152;
  word-break: break-word;
}

.node-detail-collapse {
  margin-top: 2px;
  border-top: 1px solid #eef2f7;
  border-bottom: 0;
}

.node-detail-group {
  display: grid;
  gap: 6px;
  padding: 8px 0;
  border-top: 1px dashed #e2e8f0;
}

.node-detail-group:first-child {
  border-top: 0;
}

.node-detail-group header {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  color: #475569;
  font-size: 12px;
}

.trace-analysis-panel {
  border-color: #d8e4f5;
}

.analysis-card-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(180px, 1fr));
  gap: 12px;
}

.analysis-card-grid article {
  display: grid;
  gap: 6px;
  min-height: 116px;
  padding: 14px;
  border: 1px solid #dbe4f0;
  border-radius: 8px;
  background: #fbfdff;
}

.analysis-card-grid span,
.analysis-card-grid small {
  color: #64748b;
  line-height: 1.5;
}

.analysis-card-grid strong {
  color: #1f2937;
  line-height: 1.45;
}

.analysis-card-grid .score-card {
  border-color: #bfdbfe;
  background: linear-gradient(180deg, #eff6ff 0%, #ffffff 100%);
}

.analysis-card-grid .score-card strong {
  font-size: 30px;
  color: #1d4ed8;
}

.node-health-list {
  display: grid;
  grid-template-columns: repeat(5, minmax(160px, 1fr));
  gap: 10px;
  margin-top: 14px;
}

.node-health-item {
  display: grid;
  gap: 4px;
  padding: 10px;
  border: 1px solid #dbe4f0;
  border-radius: 8px;
  background: #fff;
}

.node-health-item.normal {
  border-color: #9bd1a6;
}

.node-health-item.missing {
  border-color: #ffc4c4;
}

.node-health-item.placeholder {
  border-color: #c9d8f0;
}

.enterprise-health-panel {
  display: grid;
  gap: 14px;
  margin-top: 18px;
  padding: 16px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #ffffff;
}

.enterprise-health-panel header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.enterprise-health-panel h3 {
  margin: 0 0 6px;
}

.enterprise-health-panel header span {
  color: #64748b;
}

.health-score-layout {
  display: grid;
  grid-template-columns: minmax(220px, 1.2fr) repeat(5, minmax(150px, 1fr));
  gap: 12px;
}

.health-score-layout article {
  display: grid;
  gap: 6px;
  min-height: 118px;
  padding: 14px;
  border: 1px solid #dbe4f0;
  border-radius: 8px;
  background: #fbfdff;
}

.health-score-layout span,
.health-score-layout small {
  color: #64748b;
  line-height: 1.5;
}

.health-score-layout strong {
  color: #1f2937;
  line-height: 1.45;
}

.health-score-main {
  border-color: #bbf7d0;
  background: linear-gradient(180deg, #f0fdf4 0%, #ffffff 100%);
}

.health-score-main strong {
  font-size: 32px;
  color: #15803d;
}

.health-deduction-list {
  display: grid;
  gap: 8px;
  padding: 12px;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  background: #f8fafc;
}

.health-deduction-list strong {
  color: #334155;
}

.health-deduction-list span {
  color: #475569;
  line-height: 1.5;
}

.diagnostic-copy-button {
  height: 30px;
  padding: 0 12px;
  border: 1px solid #2563eb;
  border-radius: 6px;
  background: #2563eb;
  color: #fff;
  font-size: 12px;
  cursor: pointer;
}

.diagnostic-copy-button:hover {
  background: #1d4ed8;
}

.node-health-item span,
.node-health-item small {
  color: #64748b;
  line-height: 1.45;
}

.diagnostic-json {
  max-height: 360px;
  overflow: auto;
  margin: 0;
  padding: 12px;
  border-radius: 6px;
  background: #101828;
  color: #d1e7ff;
  font-size: 12px;
  line-height: 1.6;
}

@media (max-width: 1180px) {
  .query-grid,
  .architecture-grid,
  .analysis-card-grid,
  .trace-timeline {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .business-trace-center-page {
    padding: 16px;
  }

  .page-header,
  .card-header {
    flex-direction: column;
    align-items: stretch;
  }

  .query-grid,
  .architecture-grid,
  .analysis-card-grid,
  .trace-timeline {
    grid-template-columns: 1fr;
  }
}
</style>
