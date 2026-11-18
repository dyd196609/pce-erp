export const PURCHASE_ORDER_CREATION_GATE_DECISION_VERSION_V1142820 = 'V1.14.2.8.18.20'
export const PURCHASE_ORDER_GATE_ACTION_CLOSURE_VERSION_V11428201 = 'V1.14.2.8.18.20.1'
export const PURCHASE_ORDER_GATE_REOPEN_DATA_SYNC_VERSION_V11428203 = 'V1.14.2.8.18.20.3'
export const PURCHASE_ORDER_CREATION_GATE_DECISION_STORAGE_KEY_V1142820 =
  'pce.scm.purchase-order-creation-gate.decision.v1142820'

const text = value => String(value ?? '').trim()
const clone = value => JSON.parse(JSON.stringify(value))
const freeze = value => Object.freeze(value)
const frozen = value => freeze(clone(value))
const browserStorage = () => typeof window !== 'undefined' ? window.localStorage : null
const memoryDecisions = []

const hasHistoricalReference = evidence => evidence?.historyPrice != null
  || evidence?.historicalPurchasePrice != null
  || evidence?.priceReferenceContext
  || evidence?.priceChangeEvidence
  || /PurchaseOrderHistory|PriceReference/i.test(text(evidence?.evidenceSource))

function materialBlockedReasons(item = {}) {
  const reasons = []
  if (item.reviewStatus !== 'confirmed') reasons.push('物料推荐尚未确认')
  if (!item.selectedSupplierCode || !item.selectedSupplierName) reasons.push('推荐供应商信息不完整')
  if (!item.selectionReason) reasons.push('推荐理由未填写')
  if (!item.reviewer || !item.reviewedAt) reasons.push('人工确认记录不完整')
  if (!item.quoteComparisonEvidence?.length || !item.supplierQuoteEvidence?.length) {
    reasons.push('当前批次报价证据不完整')
  }
  return freeze(reasons)
}

function projectItem(resultItem = {}) {
  const selectedSupplierCode = text(resultItem.selectedSupplierCode
    || resultItem.decisionSupplier?.supplierCode)
  const selectedSupplierName = text(resultItem.selectedSupplierName
    || resultItem.decisionSupplier?.supplierName)
  const supplierCandidates = resultItem.supplierCandidates || []
  const priceEvidence = resultItem.priceEvidence || []
  const selectedCandidate = supplierCandidates.find(candidate =>
    text(candidate.supplierCode) === selectedSupplierCode) || null
  const selectedPriceEvidence = priceEvidence.filter(evidence =>
    !text(evidence.supplierCode) || text(evidence.supplierCode) === selectedSupplierCode)
  const quoteComparisonEvidence = selectedPriceEvidence.filter(evidence =>
    /QuoteComparison/i.test(text(evidence.evidenceSource))
      || evidence.currentPrice != null || evidence.priceRank != null)
  const historicalPriceEvidence = selectedPriceEvidence.filter(hasHistoricalReference)
  const item = {
    decisionItemId: text(resultItem.decisionItemId),
    materialCode: text(resultItem.materialCode),
    materialName: text(resultItem.materialName),
    quoteComparisonIds: frozen(resultItem.quoteComparisonIds || []),
    selectedSupplierCode,
    selectedSupplierName,
    selectionReason: text(resultItem.selectionReason || resultItem.decisionReason),
    reviewStatus: text(resultItem.reviewStatus || resultItem.status),
    reviewer: text(resultItem.reviewer),
    reviewedAt: text(resultItem.reviewedAt),
    supplierQuoteEvidence: selectedCandidate ? frozen([selectedCandidate]) : freeze([]),
    quoteComparisonEvidence: frozen(quoteComparisonEvidence),
    historicalPriceEvidence: frozen(historicalPriceEvidence),
  }
  return freeze({ ...item, blockedReasons: materialBlockedReasons(item),
    gateStatus: materialBlockedReasons(item).length ? 'blocked' : 'ready' })
}

export function createPurchaseOrderCreationGateDecisionV1142820({
  decisionBatchResult = {}, purchaseContext = {},
} = {}, now = new Date().toISOString()) {
  if (decisionBatchResult.objectType !== 'SupplierRecommendationDecisionBatchResult'
    || !text(decisionBatchResult.batchId) || !Array.isArray(decisionBatchResult.items)) {
    throw new Error('PURCHASE_ORDER_GATE_DECISION_BATCH_RESULT_REQUIRED')
  }
  const items = decisionBatchResult.items.map(item => projectItem(item))
  const completedItemCount = items.filter(item => item.selectedSupplierCode
    && item.selectedSupplierName && item.selectionReason && item.reviewStatus === 'confirmed').length
  const decisionRevision = Number(decisionBatchResult.decisionRevision) || 0
  const sourceDecisionSignature = [text(decisionBatchResult.batchId), decisionRevision,
    text(decisionBatchResult.status), text(decisionBatchResult.confirmedAt || decisionBatchResult.reopenedAt),
    items.map(item => `${item.materialCode}:${item.selectedSupplierCode}:${item.selectionReason}`).join('|')]
    .join('::')
  return freeze({
    objectType: 'PurchaseOrderCreationGateDecision',
    gateDecisionId: `POG-${text(decisionBatchResult.batchId)}`,
    sourceObjectType: decisionBatchResult.objectType,
    sourceBatchId: text(decisionBatchResult.batchId),
    sourceResultStatus: text(decisionBatchResult.status),
    sourceDecisionRevision: decisionRevision,
    sourceDecisionSignature,
    gateFactSource: 'SupplierRecommendationDecisionBatchResult',
    historicalPurchaseOrderReadCount: 0,
    purchaseContext: frozen(purchaseContext),
    items: frozen(items),
    batchCompleteness: freeze({
      totalItemCount: items.length,
      completedItemCount,
      pendingItemCount: items.length - completedItemCount,
      actionDisabled: items.length === 0 || completedItemCount !== items.length,
    }),
    checks: freeze([]),
    blockedReasons: freeze([]),
    status: 'pending_review',
    evaluatedAt: '',
    lastCheckedAt: '',
    checkedBy: '',
    createdAt: now,
    purchaseOrderCreationAllowed: false,
    purchaseOrderCreated: false,
    purchaseOrderSubmitted: false,
    purchaseOrderApproved: false,
    supplierAutoSelected: false,
    recommendationModified: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}

function gateCheck(checkCode, checkName, passed, blockedReason) {
  return freeze({ checkCode, checkName, passed, result: passed ? 'PASS' : 'BLOCKED',
    blockedReason: passed ? '' : blockedReason })
}

export function HistoricalPurchaseOrderIsolationCheck(decision = {}) {
  return freeze({ checkCode: 'HISTORICAL_PO_ISOLATION',
    checkName: 'HistoricalPurchaseOrderIsolationCheck（历史采购订单隔离）',
    passed: decision.gateFactSource === 'SupplierRecommendationDecisionBatchResult'
      && decision.historicalPurchaseOrderReadCount === 0 })
}

export function evaluatePurchaseOrderCreationGateDecisionV1142820(decision = {}, options = {}) {
  if (decision.objectType !== 'PurchaseOrderCreationGateDecision'
    || decision.status !== 'pending_review') {
    throw new Error('PURCHASE_ORDER_GATE_DECISION_NOT_PENDING_REVIEW')
  }
  const normalized = typeof options === 'string' ? { now: options } : options
  const now = normalized.now || new Date().toISOString()
  const checkedBy = text(normalized.checkedBy) || 'system-gate-reviewer'
  const items = (decision.items || []).map(item => freeze({ ...item,
    blockedReasons: materialBlockedReasons(item),
    gateStatus: materialBlockedReasons(item).length ? 'blocked' : 'ready' }))
  const checks = freeze([
    gateCheck('DECISION_REVISION', 'Decision版本',
      Number(decision.sourceDecisionRevision) > 0,
      'SupplierRecommendationDecisionBatchResult缺少有效DecisionRevision'),
    gateCheck('DECISION_RESULT_STATUS', 'DecisionBatchResult状态',
      decision.sourceResultStatus === 'confirmed',
      '供应商推荐修改后尚未重新确认'),
    gateCheck('BATCH_COMPLETENESS', '供应商推荐完整性',
      decision.batchCompleteness.totalItemCount > 0
        && decision.batchCompleteness.pendingItemCount === 0,
      '当前推荐批次仍有未完成物料决策'),
    gateCheck('DECISION_STATUS', 'Decision状态',
      items.length > 0 && items.every(item => item.reviewStatus === 'confirmed'),
      '存在未确认的DecisionItem'),
    gateCheck('SUPPLIER_COMPLETENESS', '供应商完整性',
      items.length > 0 && items.every(item => item.selectedSupplierCode && item.selectedSupplierName),
      '推荐供应商编码或名称不完整'),
    gateCheck('MANUAL_CONFIRMATION', '人工确认记录',
      items.length > 0 && items.every(item => item.reviewer && item.reviewedAt),
      '人工确认人或确认时间不完整'),
    gateCheck('BUSINESS_EVIDENCE', '业务证据', items.length > 0 && items.every(item =>
      item.selectionReason && item.quoteComparisonEvidence.length > 0
        && item.supplierQuoteEvidence.length > 0),
    '当前批次报价比较、供应商报价或推荐理由不完整'),
    gateCheck('HISTORICAL_PO_ISOLATION',
      'HistoricalPurchaseOrderIsolationCheck（历史采购订单隔离）',
      HistoricalPurchaseOrderIsolationCheck(decision).passed,
      'Gate读取了历史PurchaseOrder列表'),
  ])
  const blockedReasons = freeze(checks.filter(check => !check.passed)
    .map(check => check.blockedReason))
  const ready = blockedReasons.length === 0
  return freeze({
    ...decision,
    items: frozen(items),
    checks,
    blockedReasons,
    status: ready ? 'ready_for_purchase_order' : 'blocked',
    evaluatedAt: now,
    lastCheckedAt: now,
    checkedBy,
    purchaseOrderCreationAllowed: ready,
    purchaseOrderCreated: false,
    purchaseOrderSubmitted: false,
    purchaseOrderApproved: false,
    supplierAutoSelected: false,
    recommendationModified: false,
    businessWriteCount: 1,
    productionDataWritten: false,
  })
}

export function createPurchaseOrderCreationGateDecisionStoreV1142820({
  storage = browserStorage(), storageKey = PURCHASE_ORDER_CREATION_GATE_DECISION_STORAGE_KEY_V1142820,
} = {}) {
  const read = () => {
    if (!storage) return clone(memoryDecisions)
    try {
      const value = JSON.parse(storage.getItem(storageKey) || '[]')
      return Array.isArray(value) ? value : []
    } catch { return [] }
  }
  const write = values => {
    memoryDecisions.splice(0, memoryDecisions.length, ...clone(values))
    storage?.setItem(storageKey, JSON.stringify(values))
    return clone(values)
  }
  return freeze({
    list: read,
    findByBatchId: batchId => read().find(item => item.sourceBatchId === text(batchId)) || null,
    save(decision) {
      if (decision.objectType !== 'PurchaseOrderCreationGateDecision'
        || !['ready_for_purchase_order', 'blocked'].includes(decision.status)
        || decision.purchaseOrderCreated !== false) {
        throw new Error('PURCHASE_ORDER_GATE_DECISION_NOT_SAVABLE')
      }
      const values = read()
      const index = values.findIndex(item => item.sourceBatchId === decision.sourceBatchId)
      if (index < 0) values.push(clone(decision)); else values.splice(index, 1, clone(decision))
      return frozen(write(values).find(item => item.sourceBatchId === decision.sourceBatchId))
    },
    clear: () => write([]),
  })
}

export const purchaseOrderCreationGateDecisionStoreV1142820 =
  createPurchaseOrderCreationGateDecisionStoreV1142820()
