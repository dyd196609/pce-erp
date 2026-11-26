export const SUPPLIER_QUOTATION_RUNTIME_ACCEPTANCE_VERSION = 'V1.14.2.8.6.1'

export const SUPPLIER_QUOTATION_RUNTIME_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_PURCHASE_INQUIRY_QUOTATION_RUNTIME_ACCEPTANCE',
  version: SUPPLIER_QUOTATION_RUNTIME_ACCEPTANCE_VERSION,
  status: 'SCM_PURCHASE_INQUIRY_QUOTATION_RUNTIME_READY',
  pageCode: 'purchase-inquiry',
  route: '/scm/purchase-inquiry',
  objects: Object.freeze(['SCM_SUPPLIER_INQUIRY_TASK', 'SCM_SUPPLIER_QUOTATION']),
  requiredRegions: Object.freeze(['supplier-inquiry-task-list', 'supplier-quotation-list']),
  gates: Object.freeze(['Page', 'Router', 'Schema', 'Runtime', 'Guard', 'Acceptance', 'Build']),
  activationMode: 'read_only',
  automaticQuotationCreation: false,
  advancesPriceApproval: false,
  createsPurchaseOrder: false,
  modifiesPurchaseFlow: false,
  businessWriteCount: 0,
  databaseState: 'UNCHANGED',
  productionDataWritten: false,
})

export function validateSupplierQuotationRuntimeAcceptance(profile = SUPPLIER_QUOTATION_RUNTIME_ACCEPTANCE_PROFILE) {
  const gates = ['Page', 'Router', 'Schema', 'Runtime', 'Guard', 'Acceptance', 'Build']
  const valid = gates.every((gate) => profile.gates.includes(gate))
    && profile.objects.length === 2
    && profile.activationMode === 'read_only'
    && profile.automaticQuotationCreation === false
    && profile.advancesPriceApproval === false
    && profile.createsPurchaseOrder === false
    && profile.modifiesPurchaseFlow === false
    && profile.businessWriteCount === 0
    && profile.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
