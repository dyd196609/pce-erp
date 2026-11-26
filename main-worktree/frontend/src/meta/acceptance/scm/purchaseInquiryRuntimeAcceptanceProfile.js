export const PURCHASE_INQUIRY_RUNTIME_ACCEPTANCE_VERSION = 'V1.14.2.8.6.0'

export const PURCHASE_INQUIRY_RUNTIME_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_PURCHASE_INQUIRY_RUNTIME_ACCEPTANCE',
  version: PURCHASE_INQUIRY_RUNTIME_ACCEPTANCE_VERSION,
  status: 'SCM_PURCHASE_INQUIRY_RUNTIME_READY',
  routes: Object.freeze(['/scm/purchase-inquiry', '/scm/purchase-inquiry/create']),
  requiredRegions: Object.freeze({
    workbench: Object.freeze(['business-summary', 'status-statistics', 'inquiry-list']),
    create: Object.freeze(['basic-information', 'supplier-selection', 'inquiry-lines']),
  }),
  gates: Object.freeze(['Page', 'Router', 'Schema', 'Runtime', 'Guard', 'Acceptance', 'Build']),
  allowedActions: Object.freeze(['createInquiryObject']),
  forbiddenActions: Object.freeze(['createPurchaseOrder', 'sendSupplier', 'payment', 'inventoryAction']),
  businessWriteCount: 0,
  databaseState: 'UNCHANGED',
  productionDataWritten: false,
})

export function validatePurchaseInquiryRuntimeAcceptance(profile = PURCHASE_INQUIRY_RUNTIME_ACCEPTANCE_PROFILE) {
  const requiredGates = ['Page', 'Router', 'Schema', 'Runtime', 'Guard', 'Acceptance', 'Build']
  const valid = requiredGates.every((gate) => profile.gates.includes(gate))
    && profile.routes.length === 2
    && profile.businessWriteCount === 0
    && profile.databaseState === 'UNCHANGED'
    && profile.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
