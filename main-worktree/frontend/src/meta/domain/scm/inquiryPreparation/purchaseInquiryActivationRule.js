export const PURCHASE_INQUIRY_ACTIVATION_RULE_VERSION = 'V1.14.2.8.7.11'

export function assessPurchaseInquiryActivation(preparation = {}, existingInquiry = null) {
  const checks = Object.freeze({
    preparationExists: preparation?.modelCode === 'SCM_INQUIRY_PREPARATION_OBJECT'
      || Boolean(preparation?.inquiryPreparationNo),
    preparationReady: preparation?.status === 'prepared',
    sourceRequestTraceable: Boolean(preparation?.sourceRequestNo),
    inquiryLinesPresent: Array.isArray(preparation?.inquiryLines) && preparation.inquiryLines.length > 0,
    notPreviouslyActivated: !existingInquiry,
  })
  const idempotent = Boolean(existingInquiry)
  const eligible = Object.entries(checks).filter(([code]) => code !== 'notPreviouslyActivated').every(([, passed]) => passed)
    && checks.notPreviouslyActivated
  return Object.freeze({ ruleCode: 'SCM_PURCHASE_INQUIRY_ACTIVATION_RULE', result: eligible || idempotent ? 'PASS' : 'FAIL',
    decision: eligible ? 'allow_create_draft' : idempotent ? 'return_existing' : 'blocked', eligible, idempotent,
    checks, quotationCount: 0, supplierSent: false, purchaseOrderCreated: false })
}
