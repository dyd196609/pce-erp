import { listPurchaseOrderCreationGateContexts,
  listPurchaseOrderCreationGateDecisions } from '../runtime/purchaseOrderCreationGateRuntime.js'
import { supplierRecommendationRuntimeStoreV1142811 } from '../runtime/supplierRecommendationRuntimeStoreV1142811.js'

export const PURCHASE_ORDER_GATE_HANDOFF_PROVIDER_VERSION_V11428161 = 'V1.14.2.8.18.16.1'
const freeze = value => Object.freeze(value)
const text = value => String(value ?? '').trim()

function legacyRecords(contexts, decisions) {
  return contexts.map(context => {
    const decision = decisions.find(item => item.contextCode === context.contextCode)
    const statusCode = decision?.status || context.status
    return freeze({
      gateNo: decision?.gateDecisionNo || context.contextCode,
      recommendedSupplierName: context.recommendedSupplier?.supplierName || '',
      currency: context.costReference?.currency || '-', totalCost: context.costReference?.totalCost ?? '-',
      purchaseDetailCount: context.purchaseDetails?.length || 0,
      sourceInquiryNo: context.sourceChain?.inquiryNo || '', statusCode,
      statusLabel: ({ gate_context_created: '准入上下文已建立', evaluating: '正在检查准入',
        eligible: '准入通过', blocked: '准入阻断' })[statusCode] || '状态待确认',
      blockedReasonLabel: (decision?.blockedReasons || []).join('、') || '无',
      recommendationEvidenceCount: context.recommendationEvidence?.length || 0,
      recommendationEvidence: freeze([...(context.recommendationEvidence || [])]),
      recommendationBasis: decision?.decisionReason || context.decisionReason || '-',
      confirmedBy: decision?.manualReviewer || context.manualReviewer || '-',
      confirmedAt: decision?.manualReviewedAt || context.manualReviewedAt || '-',
      comparisonEvidencePresent: Boolean(context.comparisonEvidence?.comparisonResult),
      purchaseOrderCreated: false, factScope: 'purchase_order_gate_runtime',
    })
  })
}

function handoffRecord(handoff) {
  const suppliers = handoff.payload?.recommendedSuppliers || []
  return freeze({
    gateNo: `POG-${text(handoff.sourceObjectId)}`,
    recommendedSupplierName: suppliers.map(item => text(item.supplierName || item.supplierCode)).join('、'),
    currency: '-', totalCost: '-', purchaseDetailCount: suppliers.length,
    sourceInquiryNo: text(handoff.payload?.sourceInquiryNo),
    statusCode: 'handoff_ready', statusLabel: '推荐交接已就绪', blockedReasonLabel: '无',
    recommendationEvidenceCount: handoff.payload?.recommendationEvidence?.length || 0,
    recommendationEvidence: freeze([...(handoff.payload?.recommendationEvidence || [])]),
    recommendationBasis: text(handoff.payload?.decisionReason) || '-',
    confirmedBy: text(handoff.payload?.manualReviewer) || '-',
    confirmedAt: text(handoff.payload?.manualReviewedAt) || '-',
    comparisonEvidencePresent: Boolean(handoff.payload?.sourceQuoteComparisonId),
    priceApprovalId: text(handoff.payload?.priceApprovalId),
    priceApprovalNo: text(handoff.payload?.priceApprovalNo || handoff.payload?.priceApprovalId),
    quoteComparisonId: text(handoff.payload?.quoteComparisonId || handoff.payload?.sourceQuoteComparisonId),
    purchaseOrderCreated: false, factScope: 'supplier_recommendation_handoff',
  })
}

export function createPurchaseOrderGateHandoffProviderV11428161({
  gateContextLoader = listPurchaseOrderCreationGateContexts,
  gateDecisionLoader = listPurchaseOrderCreationGateDecisions,
  recommendationStore = supplierRecommendationRuntimeStoreV1142811,
} = {}) {
  return freeze({ providerCode: 'PurchaseOrderGateHandoffProvider', load() {
    const runtimeRecords = legacyRecords(gateContextLoader(), gateDecisionLoader())
    const handoffRecords = recommendationStore.listHandoffs()
      .filter(item => item.objectType === 'SupplierRecommendationPurchaseOrderGateHandoff'
        && item.handoffReady === true && item.purchaseOrderCreated === false).map(handoffRecord)
    const runtimeIds = new Set(runtimeRecords.map(item => item.gateNo))
    const records = freeze([...runtimeRecords, ...handoffRecords.filter(item => !runtimeIds.has(item.gateNo))])
    return freeze({ providerCode: this.providerCode, records, current: records.at(-1) || null,
      recordCount: records.length, businessWriteCount: 0, productionDataWritten: false,
      purchaseOrderCreated: false })
  } })
}

export const purchaseOrderGateHandoffProviderV11428161 =
  createPurchaseOrderGateHandoffProviderV11428161()
