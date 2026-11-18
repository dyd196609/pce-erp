export const PRICE_APPROVAL_PREPARATION_CONTEXT_VERSION = 'V1.14.2.8.18.8'

export function createPriceApprovalPreparationContext(quotePreparation = {}) {
  if (quotePreparation.objectType !== 'QuotePreparationContext'
    || quotePreparation.preparationStatus !== 'quote_preparation_ready') {
    throw new Error('QUOTE_PREPARATION_READY_CONTEXT_REQUIRED')
  }
  const materialLines = Object.freeze([...(quotePreparation.materialLines || [])].map(Object.freeze))
  const materialSupplierCandidates = Object.freeze([...(quotePreparation.materialSupplierCandidates || [])]
    .map(Object.freeze))
  if (!quotePreparation.inquiryNo || !materialLines.length || !materialSupplierCandidates.length) {
    throw new Error('QUOTE_PREPARATION_CONTEXT_INCOMPLETE')
  }
  return Object.freeze({
    objectType: 'PriceApprovalPreparationContext',
    contextType: 'price_approval_preparation_context',
    priceApprovalPreparationNo: `PAP-${quotePreparation.inquiryNo}`,
    quotePreparationNo: quotePreparation.quotePreparationNo,
    inquiryNo: quotePreparation.inquiryNo,
    sourceRequestNo: quotePreparation.sourceRequestNo || '',
    materialLines,
    materialSupplierCandidates,
    preparationStatus: quotePreparation.preparationStatus,
    sourceFact: 'QuotePreparationContext',
    supplierQuoteCreated: false,
    quoteComparisonCreated: false,
    purchaseOrderCreated: false,
    financeCreated: false,
    supplierSent: false,
    productionDataWritten: false,
  })
}

export function validatePriceApprovalPreparationContext(context = {}) {
  const valid = context.objectType === 'PriceApprovalPreparationContext'
    && Boolean(context.inquiryNo && context.quotePreparationNo)
    && context.preparationStatus === 'quote_preparation_ready'
    && context.materialLines?.length > 0 && context.materialSupplierCandidates?.length > 0
    && ['supplierQuoteCreated', 'quoteComparisonCreated', 'purchaseOrderCreated', 'financeCreated',
      'supplierSent', 'productionDataWritten'].every(field => context[field] === false)
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
