import { evaluatePurchaseOrderCreationFinalCheckV114284271146 } from
  '../domain/scm/purchaseOrder/domain/purchaseOrderCreationFinalCheckV114284271146.js'

export const PURCHASE_ORDER_CREATION_FINAL_CHECK_PROVIDER_VERSION_V114284271146 =
  'V1.14.2.8.4.27.1.4.6'

const freeze = value => Object.freeze(value)

export function createPurchaseOrderCreationFinalCheckProviderV114284271146() {
  return freeze({
    providerCode: 'PurchaseOrderCreationFinalCheckProviderV114284271146',
    sourcePriority: freeze(['PurchaseOrderCreationGuard', 'PurchaseOrderCreationContext',
      'PurchaseOrderDraft', 'PurchaseOrderMaterialEligibilityGuard']),
    load({ facts = {}, draft = {} } = {}) {
      return evaluatePurchaseOrderCreationFinalCheckV114284271146({
        gate: facts.gate || {}, creationContext: draft.creationContext || {},
        draft, entryGuard: facts.guard || {},
      })
    },
  })
}

export const purchaseOrderCreationFinalCheckProviderV114284271146 =
  createPurchaseOrderCreationFinalCheckProviderV114284271146()
