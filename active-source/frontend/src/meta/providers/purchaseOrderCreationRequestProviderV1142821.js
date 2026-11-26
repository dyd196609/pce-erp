import { canPerformAction } from '../runtime/permissionEngine.js'
import { purchaseOrderGateRuntimeProviderV1142820 } from './purchaseOrderGateRuntimeProviderV1142820.js'
import { createPurchaseOrderCreationRequestsV1142821,
  purchaseOrderCreationRequestStoreV1142821,
  transitionPurchaseOrderCreationRequestV1142821,
} from '../process/scm/purchaseOrderCreationRequest/purchaseOrderCreationRequestV1142821.js'

export const PURCHASE_ORDER_CREATION_REQUEST_PROVIDER_VERSION_V1142821 = 'V1.14.2.8.18.21'
const freeze = value => Object.freeze(value)
const text = value => String(value ?? '').trim()

export function createPurchaseOrderCreationRequestProviderV1142821({
  gateProvider = purchaseOrderGateRuntimeProviderV1142820,
  requestStore = purchaseOrderCreationRequestStoreV1142821,
} = {}) {
  const facts = () => {
    const gateFacts = gateProvider.load()
    const batchId = text(gateFacts.current?.sourceBatchId || gateFacts.source?.batchId)
    const requests = batchId ? requestStore.listByBatchId(batchId) : freeze([])
    return freeze({ gateFacts, batchId, requests })
  }
  return freeze({
    providerCode: 'PurchaseOrderCreationRequestProviderV1142821',
    sourcePriority: freeze(['SupplierRecommendationDecisionBatchResult']),
    load() {
      const current = facts()
      if (current.gateFacts.result !== 'PASS') return freeze({
        result: 'FAIL', error: current.gateFacts.error || 'PURCHASE_ORDER_GATE_INPUT_NOT_FOUND',
        currentGate: current.gateFacts.current || null, requests: current.requests,
        requestCount: current.requests.length, sourceTrace: null,
        businessWriteCount: 0, productionDataWritten: false, purchaseOrderCreated: false,
      })
      const result = current.gateFacts.source?.decisionBatchResult
      const validSource = result?.objectType === 'SupplierRecommendationDecisionBatchResult'
        && result.batchId === current.batchId
        && current.gateFacts.current?.sourceBatchId === current.batchId
      return freeze({ result: validSource ? 'PASS' : 'FAIL',
        error: validSource ? '' : 'DECISION_BATCH_RESULT_SOURCE_MISMATCH',
        currentGate: current.gateFacts.current, decisionBatchResult: result || null,
        purchaseContext: current.gateFacts.source?.handoffFacts?.purchaseContext || {},
        requests: current.requests, requestCount: current.requests.length,
        sourceTrace: validSource ? freeze({
          factSource: 'SupplierRecommendationDecisionBatchResult',
          batchId: result.batchId, decisionRevision: result.decisionRevision,
          gateId: current.gateFacts.current.gateDecisionId,
          gateStatus: current.gateFacts.current.status,
        }) : null,
        businessWriteCount: 0, productionDataWritten: false, purchaseOrderCreated: false })
    },
    createActive({ permissionContext = {}, now } = {}) {
      if (!canPerformAction(permissionContext.role, 'EXECUTE')) return freeze({
        result: 'FAIL', error: 'ACTION_PERMISSION_DENIED', requests: freeze([]),
        productionDataWritten: false, purchaseOrderCreated: false })
      const current = this.load()
      if (current.result !== 'PASS') return freeze({ ...current,
        productionDataWritten: false, purchaseOrderCreated: false })
      const createdBy = text(permissionContext.userName || permissionContext.user?.name
        || permissionContext.userId || permissionContext.role)
      try {
        const requests = createPurchaseOrderCreationRequestsV1142821({
          decisionBatchResult: current.decisionBatchResult,
          gateDecision: current.currentGate,
          purchaseContext: current.purchaseContext,
          createdBy,
          now,
        })
        const saved = requestStore.saveAll(requests)
        return freeze({ result: 'PASS', requests: saved, requestCount: saved.length,
          materialItemCount: saved.reduce((count, request) => count + request.materialItems.length, 0),
          sourceTrace: current.sourceTrace, businessWriteCount: saved.length,
          productionDataWritten: true, purchaseOrderCreated: false,
          purchaseOrderSubmitted: false, purchaseOrderApproved: false })
      } catch (error) {
        return freeze({ result: 'FAIL', error: error.message, requests: freeze([]),
          productionDataWritten: false, purchaseOrderCreated: false })
      }
    },
    transition(requestId, nextStatus, { permissionContext = {}, now } = {}) {
      const request = requestStore.findById(requestId)
      if (!request) return freeze({ result: 'FAIL', error: 'CREATION_REQUEST_NOT_FOUND',
        purchaseOrderCreated: false })
      try {
        const updated = transitionPurchaseOrderCreationRequestV1142821(request, nextStatus,
          { permissionContext, now })
        requestStore.save(updated)
        return freeze({ result: 'PASS', request: updated, businessWriteCount: 1,
          productionDataWritten: true, purchaseOrderCreated: false,
          purchaseOrderSubmitted: false, purchaseOrderApproved: false })
      } catch (error) {
        return freeze({ result: 'FAIL', error: error.message,
          productionDataWritten: false, purchaseOrderCreated: false })
      }
    },
  })
}

export const purchaseOrderCreationRequestProviderV1142821 =
  createPurchaseOrderCreationRequestProviderV1142821()
