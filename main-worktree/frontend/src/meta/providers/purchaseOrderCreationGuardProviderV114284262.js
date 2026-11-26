import { purchaseOrderAdmissionProviderV11428425 } from './purchaseOrderAdmissionProviderV11428425.js'
import { buildPurchaseOrderCreationEntryHandoffV11428425 } from
  '../process/scm/purchaseOrderCreationGate/purchaseOrderCreationEntryHandoffV11428425.js'
import { evaluatePurchaseOrderCreationGuardV114284262 } from
  '../domain/scm/purchaseOrder/gate/purchaseOrderCreationGuardV114284262.js'

export const PURCHASE_ORDER_CREATION_GUARD_PROVIDER_VERSION_V114284262 = 'V1.14.2.8.4.26.2'
const freeze = value => Object.freeze(value)

export function createPurchaseOrderCreationGuardProviderV114284262({
  admissionProvider = purchaseOrderAdmissionProviderV11428425,
} = {}) {
  return freeze({
    providerCode: 'PurchaseOrderCreationGuardProviderV114284262',
    load() {
      const admissionFacts = admissionProvider.load()
      const gate = admissionFacts.gate || null
      const admissionResult = admissionFacts.admissionResult || null
      let creationEntry = null
      if (admissionResult?.status === 'READY_FOR_PURCHASE_ORDER') {
        try { creationEntry = buildPurchaseOrderCreationEntryHandoffV11428425(admissionResult) }
        catch { creationEntry = null }
      }
      const guard = evaluatePurchaseOrderCreationGuardV114284262({
        gate: gate || {}, admissionResult: admissionResult || {}, creationEntry: creationEntry || {},
      })
      return freeze({ result: guard.result, factLoadStatus: admissionFacts.result === 'PASS'
        ? 'loaded' : 'read_failed', admissionFacts, gate, admissionResult, creationEntry, guard,
      checks: guard.checks, blockedReasons: guard.blockedReasons,
      businessWriteCount: 0, productionDataWritten: false, purchaseOrderCreated: false })
    },
  })
}

export const purchaseOrderCreationGuardProviderV114284262 =
  createPurchaseOrderCreationGuardProviderV114284262()
