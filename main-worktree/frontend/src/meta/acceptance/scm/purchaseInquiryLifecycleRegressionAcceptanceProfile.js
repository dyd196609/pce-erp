import { createPurchaseInquiryLifecycleProvider } from '../../providers/purchaseInquiryLifecycleProvider.js'
import { evaluatePurchaseInquiryBatchPreparation } from '../../domain/scm/purchaseInquiry/lifecycle/purchaseInquiryBatchPreparationRule.js'

const preparations = Object.freeze(['001', '002', '003'].map(code => Object.freeze({
  inquiryPreparationNo: `IPR-${code}`, sourceRequestNo: `PR-${code}`, status: 'prepared',
  statusLabel: '询价准备完成', inquiryLines: Object.freeze([{ materialCode: `MAT-${code}`, quantity: 1 }]),
  supplierCandidates: Object.freeze([]),
})))
const preparationProvider = Object.freeze({ load: () => Object.freeze({ providerCode: 'TEST_PREPARATION_PROVIDER',
  recordCount: preparations.length, objects: preparations, selected: null }) })

export const PURCHASE_INQUIRY_LIFECYCLE_REGRESSION_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_PURCHASE_INQUIRY_LIFECYCLE_REGRESSION', version: 'V1.14.2.8.7.13.1',
  status: 'SCM_PURCHASE_INQUIRY_LIFECYCLE_REGRESSION_READY', route: '/scm/purchase-inquiry',
  requiredRegions: Object.freeze(['business_context', 'pending_preparations', 'existing_inquiries', 'current_detail', 'next_action']),
  singleBusinessPage: true, automaticBatchActivation: false, businessWriteMode: 'explicit_manual_only',
})

export function validatePurchaseInquiryLifecycleRegressionAcceptance() {
  const existing = Object.freeze({ id: 'PI-001', inquiryNo: 'PI-001', sourceRequestNo: 'PR-001',
    inquiryDate: '2026-08-03', statusCode: 'draft', statusLabel: '草稿' })
  const facts = createPurchaseInquiryLifecycleProvider({ preparationProvider }).load({ serverFacts: { objects: [existing] } })
  const batch = evaluatePurchaseInquiryBatchPreparation({ preparations: facts.pendingPreparations, existingInquiries: facts.inquiries })
  const valid = facts.inquiries.some(item => item.inquiryNo === existing.inquiryNo) && facts.preparations.length === 3
    && facts.pendingPreparationCount === 2 && batch.batchInputCount === 2 && batch.batchOutputCount === 2
    && batch.automaticActivation === false && batch.onePreparationOneInquiry === true
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid, existingInquiryListCount: facts.existingInquiryCount,
    preparationCount: facts.preparations.length, batchInputCount: batch.batchInputCount, batchOutputCount: batch.batchOutputCount })
}
