import {
  PCE_FILTER_DISPLAY_MAP,
  createPceAdvancedFilterSchema,
  displayPceFilterValue,
} from './pceAdvancedFilterContract.js'
import { assertStatusTransitionCountMatchesHistory } from './pceStateMachineFactContract.js'
import {
  factLoadPassed,
  factLoadResultCount,
  readPceFactLoadEnvelope,
} from './pceFactLoadContract.js'

export const FORMAL_PAYMENT_ORDER_VERSION = 'V1.14.2.8.4.7.54.3'

export const FORMAL_PAYMENT_ORDER_MODULE = Object.freeze({
  pageCode: 'formal-payment-order',
  moduleCode: 'formal-payment-order',
  canonicalName: '正式付款单',
  sourceDocumentType: 'paymentRiskReview',
  route: '/finance/formal-payment-orders',
  previousModuleCode: 'payment-risk-review',
  previousCanonicalName: '真实付款风险评审',
  nextModuleCode: 'bank-send-task',
  nextCanonicalName: '银行发送任务（后续版本）',
})

export const FORMAL_PAYMENT_ORDER_FILTER_SCHEMA = createPceAdvancedFilterSchema([
  { field: 'orderNo', label: '正式付款单编号', type: 'select' },
  { field: 'sourceRiskReviewNo', label: '来源风险评审编号', type: 'select' },
  {
    field: 'status',
    label: '业务状态',
    type: 'select',
    displayMap: PCE_FILTER_DISPLAY_MAP,
    options: [
      { value: 'prepared', label: '已准备' },
      { value: 'submitted', label: '已提交审批' },
      { value: 'approved', label: '已审批' },
      { value: 'frozen_for_execution', label: '已冻结待执行' },
    ],
  },
  {
    field: 'riskStatus',
    label: '风险状态',
    type: 'select',
    displayMap: PCE_FILTER_DISPLAY_MAP,
    options: [
      { value: 'passed', label: '已通过' },
      { value: 'blocked', label: '已阻断' },
    ],
  },
  {
    field: 'riskLevel',
    label: '风险等级',
    type: 'select',
    displayMap: PCE_FILTER_DISPLAY_MAP,
    options: [
      { value: 'low', label: '低' },
      { value: 'medium', label: '中' },
      { value: 'high', label: '高' },
    ],
  },
  { field: 'supplierName', label: '供应商', type: 'select' },
  { field: 'legalEntity', label: '法人', type: 'select' },
  { field: 'ledgerBook', label: '账簿', type: 'select' },
  { field: 'currency', label: '币种', type: 'select' },
  { field: 'amountMin', label: '金额下限', type: 'numberRange', sourceKey: 'amount' },
  { field: 'amountMax', label: '金额上限', type: 'numberRange', sourceKey: 'amount' },
  { field: 'executionDateFrom', label: '计划执行日期起', type: 'dateRange', sourceKey: 'plannedExecutionDate' },
  { field: 'executionDateTo', label: '计划执行日期止', type: 'dateRange', sourceKey: 'plannedExecutionDate' },
  { field: 'scenarioCode', label: '场景编码', type: 'select' },
])

const labels = Object.freeze({
  ...PCE_FILTER_DISPLAY_MAP,
  submitted: '已提交审批',
  approved: '已审批',
  frozen_for_execution: '已冻结待执行',
  pending: '审批中',
  frozen: '已冻结',
  not_frozen: '未冻结',
  ready_for_bank_send: '允许银行发送',
  payment_checker: '付款复核员',
  payment_authorizer: '付款授权人',
  server: '服务端',
})

export function formalPaymentOrderDisplayValue(value) {
  if (value === true) return '是'
  if (value === false) return '否'
  if (Array.isArray(value)) return value.length ? value.join('、') : '无'
  if (value === null || value === undefined || value === '') return '-'
  return labels[String(value)] || displayPceFilterValue(value) || String(value)
}

function serverCount(value, field) {
  if (!Number.isInteger(value) || value < 0) {
    throw new Error(
      `formal-payment-order:api:${field} must be a server-derived non-negative integer`,
    )
  }
  return value
}

export function createFormalPaymentOrderPageFacts(apiEnvelope = {}) {
  const { data, factLoadFacts } = readPceFactLoadEnvelope(
    apiEnvelope,
    '/api/finance/formal-payment-orders/',
    'formal-payment-order',
  )
  const rows = (Array.isArray(data.results) ? data.results : []).map(row => {
    assertStatusTransitionCountMatchesHistory(
      row,
      `formal-payment-order:api:${row.orderNo || row.id || 'unknown'}`,
    )
    assertStatusTransitionCountMatchesHistory(
      row.executionGateFacts,
      `formal-payment-order:execution-gate:${row.orderNo || row.id || 'unknown'}`,
    )
    return {
      ...row,
      riskStatus: row.riskStatus || row.evidence?.riskReview?.riskResult || '',
      riskLevel: row.riskLevel || row.evidence?.riskReview?.riskLevel || '',
      scenarioCode: row.sourceScenarioCode || '',
    }
  })
  const sources = Array.isArray(data.sources) ? data.sources : []
  const failed = factLoadFacts.factLoadStatus === 'read_failed'
  const capacity = {
    sourceRiskReviewCount: failed ? null : serverCount(
      data.capacity?.sourceRiskReviewCount,
      'sourceRiskReviewCount',
    ),
    formalPaymentOrderCount: failed ? null : serverCount(
      data.capacity?.formalPaymentOrderCount,
      'formalPaymentOrderCount',
    ),
    preparedCount: failed ? null : serverCount(
      data.capacity?.preparedCount,
      'preparedCount',
    ),
    approvedCount: failed ? null : serverCount(
      data.capacity?.approvedCount,
      'approvedCount',
    ),
    frozenCount: failed ? null : serverCount(
      data.capacity?.frozenCount,
      'frozenCount',
    ),
    bankSendEligibleCount: failed ? null : serverCount(
      data.capacity?.bankSendEligibleCount,
      'bankSendEligibleCount',
    ),
    blockedScenarioCount: failed ? null : serverCount(
      data.capacity?.blockedScenarioCount,
      'blockedScenarioCount',
    ),
    nextStageConsumedCount: failed ? null : serverCount(
      data.capacity?.nextStageConsumedCount,
      'nextStageConsumedCount',
    ),
  }
  const currentObject = rows[0] || null
  const sourceObjects = sources.map(row => ({
    id: row.id,
    objectNo: row.reviewNo,
    sourceDocumentType: 'paymentRiskReview',
    status: row.status,
    scenarioCode: row.scenarioCode || '',
  }))
  const strictRows = rows.map(row => ({
    scenarioCode: row.scenarioCode,
    objectNo: row.orderNo,
    sourceObjectNo: row.sourceRiskReviewNo,
    status: row.status,
    stateMachineConsistent: row.stateMachineConsistent === true,
    statusTransitionCount: row.statusTransitionCount,
    approvalStatus: row.approvalStatus,
    approvalNodeCount: row.approvalHistory?.length || 0,
    freezeStatus: row.freezeStatus,
    freezeHash: row.freezeHash,
    bankSendEligible: row.bankSendEligibility?.readyForBankSend === true,
    bankMessageCount: row.bankSendEligibility?.bankMessageCount || 0,
    currentStateSource: 'server',
  }))
  const strictServerFacts = {
    ...factLoadFacts,
    factLoadFacts,
    currentStateSource: 'server',
    tenantId: factLoadFacts.tenantId,
    batchId: factLoadFacts.batchId,
    pageCode: FORMAL_PAYMENT_ORDER_MODULE.pageCode,
    resultCount: factLoadResultCount(factLoadFacts, rows.length),
    passed: factLoadPassed(
      factLoadFacts,
      data.capacity?.passed === true,
    ),
    currentObject: strictRows[0] || null,
    sourceObjects,
    status: currentObject?.status || '',
    stateMachineConsistent: currentObject?.stateMachineConsistent === true,
    statusTransitionHistory: currentObject?.statusTransitionHistory,
    statusTransitionCount: currentObject?.statusTransitionCount,
    approvalStatus: currentObject?.approvalStatus || 'not_started',
    workflowInstance: currentObject?.workflowInstance || {},
    approvalHistory: currentObject?.approvalHistory || [],
    freezeStatus: currentObject?.freezeStatus || 'not_frozen',
    freezeHash: currentObject?.freezeHash || '',
    bankSendEligibility: currentObject?.bankSendEligibility || {},
    downstreamCounts: data.downstreamCounts || {},
    executionGateFacts: currentObject?.executionGateFacts || {},
    rows: strictRows,
  }
  if (currentObject) {
    assertStatusTransitionCountMatchesHistory(
      strictServerFacts,
      'formal-payment-order:strictServerFacts',
    )
  }
  return {
    version: FORMAL_PAYMENT_ORDER_VERSION,
    canonicalName: FORMAL_PAYMENT_ORDER_MODULE.canonicalName,
    currentStateSource: 'server',
    ...factLoadFacts,
    factLoadFacts,
    tenantId: factLoadFacts.tenantId,
    canaryBatchId: factLoadFacts.batchId,
    rows,
    sources,
    capacity,
    blockedScenarios: Array.isArray(data.blockedScenarios) ? data.blockedScenarios : [],
    downstreamCounts: data.downstreamCounts || {},
    currentObject,
    selectedObject: currentObject,
    sourceObjects,
    resultCount: factLoadResultCount(factLoadFacts, rows.length),
    passed: factLoadPassed(
      factLoadFacts,
      data.capacity?.passed === true,
    ),
    strictServerFacts,
  }
}
