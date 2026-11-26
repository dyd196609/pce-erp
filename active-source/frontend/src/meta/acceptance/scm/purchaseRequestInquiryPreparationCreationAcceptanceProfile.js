import { createInquiryPreparationObject, validateInquiryPreparationObject } from '../../domain/scm/inquiryPreparation/inquiryPreparationObjectModel.js'
import { assessInquiryPreparationCreation } from '../../domain/scm/inquiryPreparation/inquiryPreparationRuleEngine.js'

export const PURCHASE_REQUEST_INQUIRY_PREPARATION_CREATION_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_PURCHASE_REQUEST_INQUIRY_PREPARATION_CREATION',
  version: 'V1.14.2.8.7.9',
  status: 'SCM_PURCHASE_REQUEST_INQUIRY_PREPARATION_CREATION_READY',
  sourceRoute: '/scm/purchase-request',
  targetRoute: '/scm/purchase-inquiry',
  allowedBusinessObject: 'InquiryPreparationObject',
  forbiddenObjects: Object.freeze(['PurchaseInquiry', 'SupplierInquiryTask', 'QuotationTask', 'SupplierQuotation']),
  productionDataWritten: false,
  database: 'UNCHANGED',
  gates: Object.freeze(['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']),
})

export function validatePurchaseRequestInquiryPreparationCreationAcceptance() {
  const request = { requestNo: 'PR202608020008', requestDate: '2026-08-02', requester: '验收采购员',
    purchaseDepartment: '采购部', statusCode: 'approved', approvalStatus: 'completed',
    inquiryEligibility: { eligible: true, items: [{ materialCode: 'MAT-001', quantity: 10, requiredDate: '2026-08-20' }] },
    items: [{ materialCode: 'MAT-001', quantity: 10, requiredDate: '2026-08-20', suggestedSupplierId: 'SUP-001' }] }
  const object = createInquiryPreparationObject(request)
  const valid = assessInquiryPreparationCreation(request).eligible && validateInquiryPreparationObject(object).valid
    && PURCHASE_REQUEST_INQUIRY_PREPARATION_CREATION_ACCEPTANCE_PROFILE.gates.length === 8
    && PURCHASE_REQUEST_INQUIRY_PREPARATION_CREATION_ACCEPTANCE_PROFILE.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
