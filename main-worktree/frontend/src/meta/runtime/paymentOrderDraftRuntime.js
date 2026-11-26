import { stateMachineFactsFromServer } from './pceStateMachineFactContract.js'
import {
  factLoadPassed,
  factLoadResultCount,
  readPceFactLoadEnvelope,
} from './pceFactLoadContract.js'

export const PAYMENT_ORDER_DRAFT_VERSION = 'V1.14.2.8.4.7.55'
export const PAYMENT_ORDER_DRAFT_CANONICAL_NAME = '正式付款单草稿'
export const PAYMENT_ORDER_DRAFT_SOURCE_DOCUMENT_TYPE = 'paymentOrderPrepare'
export const PAYMENT_ORDER_DRAFT_NEXT_MODULE = Object.freeze({
  code: 'payment-risk-review',
  canonicalName: '真实付款风险评审',
  route: '/finance/payment-risk-reviews',
})
export const PAYMENT_ORDER_DRAFT_PRODUCTION_ROLLOUT_ENABLED = false

export const PAYMENT_ORDER_DRAFT_RULE_CLASSIFICATION = Object.freeze({
  generationAndSourceGateRuleCount: 11,
  dataCompletenessRuleCount: 3,
  finalReviewRuleCount: 27,
  totalRuleCount: 41,
})

const displayMap = Object.freeze({
  created: '已创建',
  reviewed: '已复核',
  prepared: '已准备',
  submitted: '已提交',
  complete: '完整',
  passed: '已通过',
  validated: '已校验',
  committed: '已提交',
  consumed: '已使用',
  available: '可用',
  ready: '就绪',
  ready_for_payment_risk_review: '可进入真实付款风险评审',
  true: '是',
  false: '否',
})

export function paymentOrderDraftDisplayValue(value) {
  if (Array.isArray(value)) return value.length ? value.map(paymentOrderDraftDisplayValue).join('、') : '无'
  if (value === null || value === undefined || value === '') return '无'
  return displayMap[String(value)] || String(value)
}

function serverCount(value, field) {
  if (!Number.isInteger(value) || value < 0) {
    throw new Error(
      `payment-order-draft:api:${field} must be a server-derived non-negative integer`,
    )
  }
  return value
}

function strictRow(row) {
  const stateFacts = stateMachineFactsFromServer(
    row,
    `payment-order-draft:${row.draftNo}`,
  )
  return {
    scenarioCode: row.scenarioCode || '',
    objectNo: row.draftNo,
    sourceObjectNo: row.sourcePaymentOrderPrepareNo,
    status: row.status,
    ...stateFacts,
    currentStateSource: 'server',
  }
}

export function createPaymentOrderDraftPageFacts(apiEnvelope = {}) {
  const { data, factLoadFacts } = readPceFactLoadEnvelope(
    apiEnvelope,
    '/api/finance/payment-order-drafts/',
    'payment-order-draft',
  )
  const rows = Array.isArray(data?.results) ? data.results : []
  const failed = factLoadFacts.factLoadStatus === 'read_failed'
  const capacity = {
    ...(data?.capacity || {}),
    formalPaymentOrderDraftCount: failed ? null : rows.length,
    reviewedPaymentOrderDraftCount: failed ? null : rows.filter(row => row.status === 'reviewed').length,
    downstreamEligibleSourceCount: failed ? null : rows.filter(row => row.eligibility?.eligible).length,
    nextStageConsumedCount: failed ? null : serverCount(
      data?.capacity?.nextStageConsumedCount,
      'nextStageConsumedCount',
    ),
  }
  const currentObject = rows[0] || null
  if (currentObject) {
    stateMachineFactsFromServer(
      currentObject,
      `payment-order-draft-current:${currentObject.draftNo}`,
    )
  }
  const sourceObjects = rows.map(row => ({
    objectNo: row.sourcePaymentOrderPrepareNo,
    sourcePaymentOrderPrepareNo: row.sourcePaymentOrderPrepareNo,
  }))
  const strictRows = rows.map(strictRow)
  return {
    version: PAYMENT_ORDER_DRAFT_VERSION,
    currentStateSource: 'server',
    ...factLoadFacts,
    factLoadFacts,
    tenantId: factLoadFacts.tenantId,
    canaryBatchId: factLoadFacts.batchId,
    formalListApiCount: failed ? null : rows.length,
    moduleCapacityCount: capacity.formalPaymentOrderDraftCount,
    resultCount: factLoadResultCount(factLoadFacts, rows.length),
    passed: factLoadPassed(
      factLoadFacts,
      data?.capacity?.passed === true,
    ),
    rows,
    capacity,
    downstreamCounts: { ...(data?.downstreamCounts || {}) },
    currentObject,
    selectedObject: currentObject,
    sourceObjects,
    status: currentObject?.status || '',
    strictServerFacts: {
      ...factLoadFacts,
      factLoadFacts,
      currentStateSource: 'server',
      tenantId: factLoadFacts.tenantId,
      batchId: factLoadFacts.batchId,
      pageCode: 'payment-order-draft',
      resultCount: factLoadResultCount(
        factLoadFacts,
        strictRows.length,
      ),
      passed: factLoadPassed(
        factLoadFacts,
        data?.capacity?.passed === true,
      ),
      currentObject: strictRows[0] || null,
      sourceObjects,
      status: currentObject?.status || '',
      ...(strictRows[0]
        ? {
            statusTransitionHistory: strictRows[0].statusTransitionHistory,
            statusTransitionCount: strictRows[0].statusTransitionCount,
            stateMachineConsistent: strictRows[0].stateMachineConsistent,
          }
        : {}),
      rows: strictRows,
    },
    ruleClassification: { ...PAYMENT_ORDER_DRAFT_RULE_CLASSIFICATION },
  }
}
