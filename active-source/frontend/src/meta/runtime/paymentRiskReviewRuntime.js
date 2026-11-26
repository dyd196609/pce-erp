export const PAYMENT_RISK_REVIEW_VERSION = 'V1.14.2.8.4.7.52'

export const PAYMENT_RISK_REVIEW_MODULE = Object.freeze({
  pageCode: 'payment-risk-review',
  moduleCode: 'payment-risk-review',
  canonicalName: '真实付款风险评审',
  sourceDocumentType: 'paymentOrderDraft',
  route: '/finance/payment-risk-reviews',
  previousModuleCode: 'payment-order-draft',
  previousCanonicalName: '正式付款单草稿',
  nextModuleCode: 'formal-payment-order',
  nextCanonicalName: '正式付款单',
})

const labels = Object.freeze({
  draft: '草稿',
  reviewing: '评审中',
  passed: '已通过',
  blocked: '已阻断',
  rejected: '已拒绝',
  low: '低',
  medium: '中',
  high: '高',
  ready_for_formal_payment_order: '可进入正式付款单',
  committed: '已提交',
  not_started: '未开始',
  true: '是',
  false: '否',
})

export function paymentRiskReviewDisplayValue(value) {
  if (value === true) return labels.true
  if (value === false) return labels.false
  if (Array.isArray(value)) return value.length ? value.join('、') : '无'
  if (value === null || value === undefined || value === '') return '-'
  return labels[String(value)] || String(value)
}

export function createPaymentRiskReviewPageFacts(apiEnvelope = {}) {
  const data = apiEnvelope?.data || {}
  const rows = Array.isArray(data.results) ? data.results : []
  const capacity = {
    sourceDraftCount: Number(data.capacity?.sourceDraftCount || 0),
    riskReviewCount: Number(data.capacity?.riskReviewCount || rows.length),
    passedCount: Number(data.capacity?.passedCount || 0),
    blockedCount: Number(data.capacity?.blockedCount || 0),
    blockedScenarioCount: Number(data.capacity?.blockedScenarioCount || 0),
    nextStageConsumedCount: Number(data.capacity?.nextStageConsumedCount || 0),
  }
  const currentObject = rows[0] || null
  const sourceObjects = rows.map(row => ({
    id: row.sourcePaymentOrderDraftId,
    objectNo: row.sourcePaymentOrderDraftNo,
    sourceDocumentType: row.sourceDocumentType,
  }))
  const strictRows = rows.map(row => ({
    scenarioCode: row.scenarioCode || '',
    objectNo: row.reviewNo,
    sourceObjectNo: row.sourcePaymentOrderDraftNo,
    status: row.status,
    currentStateSource: 'server',
  }))
  return {
    version: PAYMENT_RISK_REVIEW_VERSION,
    canonicalName: PAYMENT_RISK_REVIEW_MODULE.canonicalName,
    currentStateSource: 'server',
    tenantId: 'tenant-canary-demo',
    canaryBatchId: 'PURCHASE-FLOW-DEMO-V1',
    rows,
    capacity,
    blockedScenarios: Array.isArray(data.blockedScenarios) ? data.blockedScenarios : [],
    downstreamCounts: data.downstreamCounts || {},
    currentObject,
    selectedObject: currentObject,
    sourceObjects,
    status: currentObject?.status || '',
    resultCount: rows.length,
    strictServerFacts: {
      currentStateSource: 'server',
      tenantId: 'tenant-canary-demo',
      batchId: 'PURCHASE-FLOW-DEMO-V1',
      pageCode: PAYMENT_RISK_REVIEW_MODULE.pageCode,
      resultCount: rows.length,
      currentObject: strictRows[0] || null,
      sourceObjects,
      status: currentObject?.status || '',
      rows: strictRows,
    },
  }
}
