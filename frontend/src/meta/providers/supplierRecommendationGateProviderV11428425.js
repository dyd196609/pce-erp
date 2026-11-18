import { createSupplierRecommendationGateV11428425,
  prepareSupplierRecommendationGateV11428425 } from '../domain/scm/purchaseOrder/gate/supplierRecommendationGateV11428425.js'
import { supplierRecommendationDecisionBatchStoreV11428169 } from '../process/scm/supplierRecommendation/supplierRecommendationDecisionBatchV11428169.js'
import { supplierRecommendationGateStoreV11428425 } from '../process/scm/purchaseOrderCreationGate/supplierRecommendationGateRuntimeV11428425.js'
import { supplierRecommendationDataHandoffProviderV1142818 } from './supplierRecommendationDataHandoffProviderV1142818.js'

export const SUPPLIER_RECOMMENDATION_GATE_PROVIDER_VERSION_V11428425 = 'V1.14.2.8.4.25'
const freeze = value => Object.freeze(value)

export function createSupplierRecommendationGateProviderV11428425({
  decisionBatchStore = supplierRecommendationDecisionBatchStoreV11428169,
  handoffProvider = supplierRecommendationDataHandoffProviderV1142818,
  gateStore = supplierRecommendationGateStoreV11428425,
} = {}) {
  const source = (explicitBatchId) => {
    const batchId = String(explicitBatchId || '').trim()
    if (!batchId) return freeze({ result: 'FAIL', error: 'EXPLICIT_DECISION_BATCH_REQUIRED',
      batchId: '', decisionBatchResult: null, handoff: null })
    const decisionBatchResult = batchId ? decisionBatchStore.findResult(batchId) : null
    const handoff = batchId ? decisionBatchStore.findHandoff(batchId) : null
    if (!batchId || decisionBatchResult?.objectType !== 'SupplierRecommendationDecisionBatchResult'
      || decisionBatchResult.status !== 'confirmed' || !handoff
      || handoff.status !== 'handoff_ready') {
      return freeze({ result: 'FAIL', error: 'CONFIRMED_RECOMMENDATION_HANDOFF_REQUIRED',
        batchId, decisionBatchResult: null, handoff: null })
    }
    const handoffFacts = handoffProvider.load({ taskId: batchId })
    if (handoffFacts.result !== 'PASS') return freeze({ result: 'FAIL',
      error: handoffFacts.error || 'RECOMMENDATION_SOURCE_CHAIN_INVALID', batchId,
      decisionBatchResult, handoff, handoffFacts })
    return freeze({ result: 'PASS', batchId, decisionBatchResult, handoff, handoffFacts })
  }
  return freeze({
    providerCode: 'SupplierRecommendationGateProviderV11428425',
    sourcePriority: freeze(['SupplierRecommendationDecisionBatchResult',
      'SupplierRecommendationDecisionBatchGateHandoff', 'PriceApprovalRuntimeContext']),
    load({ batchId } = {}) {
      const sourceFacts = source(batchId)
      if (sourceFacts.result !== 'PASS') return freeze({ ...sourceFacts, gate: null,
        factLoadStatus: 'read_failed', resultCount: 0, businessWriteCount: 0,
        productionDataWritten: false, purchaseOrderCreated: false })
      const projected = prepareSupplierRecommendationGateV11428425(
        createSupplierRecommendationGateV11428425({
          decisionBatchResult: sourceFacts.decisionBatchResult,
          purchaseContext: sourceFacts.handoffFacts.purchaseContext,
          handoff: sourceFacts.handoff,
        }))
      const persisted = gateStore.findBySourceBatchId(sourceFacts.batchId)
      const gate = persisted?.sourceSignature === projected.sourceSignature ? persisted : projected
      return freeze({ result: 'PASS', gate, source: sourceFacts,
        factSource: 'SupplierRecommendationDecisionBatchResult', factLoadStatus: 'loaded',
        resultCount: 1, businessWriteCount: 0, productionDataWritten: false,
        purchaseOrderCreated: false, automaticPurchaseOrderCreation: false })
    },
  })
}

export const supplierRecommendationGateProviderV11428425 =
  createSupplierRecommendationGateProviderV11428425()
