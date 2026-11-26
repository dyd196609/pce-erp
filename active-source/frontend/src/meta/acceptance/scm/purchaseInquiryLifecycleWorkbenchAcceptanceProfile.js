import { createPurchaseInquiryLifecycleContext, validatePurchaseInquiryLifecycleContext } from '../../domain/scm/purchaseInquiry/lifecycle/purchaseInquiryLifecycleContext.js'
import { resolvePurchaseInquiryLifecycleStage, validatePurchaseInquiryLifecycleStage } from '../../domain/scm/purchaseInquiry/lifecycle/purchaseInquiryLifecycleStage.js'
import { createPurchaseInquiryLifecycleProvider } from '../../providers/purchaseInquiryLifecycleProvider.js'

const preparation = Object.freeze({ inquiryPreparationNo: 'IPR-PR202608020008', sourceRequestNo: 'PR202608020008',
  status: 'prepared', statusLabel: '询价准备完成', materialLineCount: 2, materialQuantity: 514,
  supplierCandidateCount: 1, inquiryLines: Object.freeze([]), supplierCandidates: Object.freeze([]) })
const preparationProvider = Object.freeze({ load: () => Object.freeze({ providerCode: 'TEST_PREPARATION_PROVIDER',
  recordCount: 1, objects: Object.freeze([preparation]), selected: preparation }) })

export const PURCHASE_INQUIRY_LIFECYCLE_WORKBENCH_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_PURCHASE_INQUIRY_LIFECYCLE_WORKBENCH', version: 'V1.14.2.8.7.13',
  status: 'SCM_PURCHASE_INQUIRY_LIFECYCLE_WORKBENCH_READY', route: '/scm/purchase-inquiry',
  providerCode: 'SCM_PURCHASE_INQUIRY_LIFECYCLE_PROVIDER', singleBusinessPage: true,
  directPageFactComposition: false, allowedActions: Object.freeze(['startInquiry', 'editInquiry', 'viewInquiry']),
  forbiddenActions: Object.freeze(['sendSupplier', 'createQuotation', 'createPurchaseOrder', 'payment']),
})

export function validatePurchaseInquiryLifecycleWorkbenchAcceptance() {
  const providerFacts = createPurchaseInquiryLifecycleProvider({ preparationProvider }).load({
    query: { inquiryPreparationNo: preparation.inquiryPreparationNo }, serverFacts: { objects: [] } })
  const stage = resolvePurchaseInquiryLifecycleStage({ entryContext: providerFacts.entryContext })
  const context = createPurchaseInquiryLifecycleContext({ entryContext: providerFacts.entryContext, preparation })
  const valid = providerFacts.providerCode === 'SCM_PURCHASE_INQUIRY_LIFECYCLE_PROVIDER'
    && providerFacts.factOwner === 'purchase-inquiry-lifecycle' && stage.code === 'preparation_ready'
    && validatePurchaseInquiryLifecycleStage(stage).valid && validatePurchaseInquiryLifecycleContext(context).valid
    && context.allowedActions.join(',') === 'startInquiry'
    && Object.values(context.protections).every(value => value === false)
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
