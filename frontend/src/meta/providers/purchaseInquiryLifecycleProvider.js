import { inquiryPreparationProvider } from './inquiryPreparationProvider.js'
import { purchaseInquiryProvider } from './purchaseInquiryProvider.js'
import { resolvePurchaseInquiryBusinessContext } from '../domain/scm/purchaseInquiry/entry/purchaseInquiryBusinessContext.js'
import { createPurchaseInquiryLifecycleContext } from '../domain/scm/purchaseInquiry/lifecycle/purchaseInquiryLifecycleContext.js'

export const PURCHASE_INQUIRY_LIFECYCLE_PROVIDER_VERSION = 'V1.14.2.8.7.13.1'
export const PURCHASE_INQUIRY_ENTRY_CODES = Object.freeze({
  purchaseRequest: 'purchase_request_handoff',
  processCenter: 'process_center',
  directUrl: 'direct_url',
})

export function createPurchaseInquiryLifecycleProvider({ preparationProvider = inquiryPreparationProvider } = {}) {
  return Object.freeze({
    providerCode: 'SCM_PURCHASE_INQUIRY_LIFECYCLE_PROVIDER', version: PURCHASE_INQUIRY_LIFECYCLE_PROVIDER_VERSION,
    factOwner: 'purchase-inquiry-lifecycle', sourceMode: 'provider_composed',
    load({ query = {}, serverFacts = {}, entryCode = PURCHASE_INQUIRY_ENTRY_CODES.directUrl } = {}) {
      const preparationFacts = preparationProvider.load(query)
      const inquiryFacts = purchaseInquiryProvider.load({ serverFacts })
      const runtimeView = inquiryFacts.runtimeView
      const allInquiries = inquiryFacts.existingInquiryList
      const entryContext = resolvePurchaseInquiryBusinessContext({ query, preparations: preparationFacts.objects, inquiries: allInquiries })
      const preparation = preparationFacts.objects.find(item => item.inquiryPreparationNo === entryContext.preparationNo) || null
      const inquiry = allInquiries.find(item => item.inquiryNo === entryContext.currentInquiryNo) || null
      const inquiryPreparationNos = new Set(allInquiries.map(item => item.sourcePreparationNo).filter(Boolean))
      const inquirySourceNos = new Set(allInquiries.map(item => item.sourceRequestNo).filter(Boolean))
      const pendingPreparations = Object.freeze(preparationFacts.objects.filter(item =>
        !inquiryPreparationNos.has(item.inquiryPreparationNo) && !inquirySourceNos.has(item.sourceRequestNo)))
      const lifecycleContext = createPurchaseInquiryLifecycleContext({ entryContext, preparation, inquiry,
        quotationCount: runtimeView.quotationRuntime.supplierQuotations.length })
      return Object.freeze({ providerCode: this.providerCode, version: this.version, factOwner: this.factOwner,
        entryCode, factSnapshotId: preparationFacts.snapshotId,
        factChain: Object.freeze(['Page', this.providerCode, 'PurchaseInquiryRuntimeContext', 'InquiryPreparationObject']),
        entryContext, lifecycleContext, preparationFacts, runtimeView,
        currentPreparation: preparation, currentInquiry: inquiry, preparations: preparationFacts.objects,
        pendingPreparations, pendingPreparationCount: pendingPreparations.length,
        inquiryFacts, existingInquiryList: allInquiries,
        inquiries: allInquiries, existingInquiryCount: allInquiries.length,
        evidence: lifecycleContext.evidence, protections: lifecycleContext.protections })
    },
    loadForEntry(entryCode, options = {}) {
      if (!Object.values(PURCHASE_INQUIRY_ENTRY_CODES).includes(entryCode)) throw new Error('PURCHASE_INQUIRY_ENTRY_CODE_INVALID')
      return this.load({ ...options, entryCode })
    },
  })
}

export const purchaseInquiryLifecycleProvider = createPurchaseInquiryLifecycleProvider()
