import { createPurchaseOrderAdmissionContextV11428425 } from '../domain/scm/purchaseOrder/gate/supplierRecommendationGateV11428425.js'
import { purchaseOrderAdmissionResultStoreV11428425 } from '../process/scm/purchaseOrderCreationGate/supplierRecommendationGateRuntimeV11428425.js'
import { supplierRecommendationGateProviderV11428425 } from './supplierRecommendationGateProviderV11428425.js'

export const PURCHASE_ORDER_ADMISSION_PROVIDER_VERSION_V11428425 = 'V1.14.2.8.4.25'
const freeze = value => Object.freeze(value)

export function createPurchaseOrderAdmissionProviderV11428425({
  gateProvider = supplierRecommendationGateProviderV11428425,
  resultStore = purchaseOrderAdmissionResultStoreV11428425,
} = {}) {
  return freeze({
    providerCode: 'PurchaseOrderAdmissionProviderV11428425',
    load({ batchId } = {}) {
      const gateFacts = gateProvider.load({ batchId })
      if (gateFacts.result !== 'PASS') return freeze({ result: 'FAIL',
        error: gateFacts.error, gateFacts, context: null, admissionResult: null,
        factLoadStatus: 'read_failed', resultCount: 0, businessWriteCount: 0,
        productionDataWritten: false, purchaseOrderCreated: false })
      const gate = gateFacts.gate
      const context = gate.status === 'CONFIRMED'
        ? createPurchaseOrderAdmissionContextV11428425(gate) : null
      const stored = resultStore.findByGateId(gate.gateId)
      const admissionResult = stored?.sourceSignature === gate.sourceSignature ? stored : null
      return freeze({ result: 'PASS', gateFacts, gate, context, admissionResult,
        factSource: 'SupplierRecommendationGate', factLoadStatus: 'loaded', resultCount: 1,
        businessWriteCount: 0, productionDataWritten: false, purchaseOrderCreated: false,
        automaticPurchaseOrderCreation: false })
    },
  })
}

export const purchaseOrderAdmissionProviderV11428425 =
  createPurchaseOrderAdmissionProviderV11428425()
