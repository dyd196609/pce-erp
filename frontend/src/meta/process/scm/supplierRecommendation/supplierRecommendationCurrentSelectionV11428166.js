export const SUPPLIER_RECOMMENDATION_CURRENT_SELECTION_VERSION_V11428166 = 'V1.14.2.8.18.16.6'

const text = value => String(value ?? '').trim()

export function createSupplierRecommendationCurrentSelectionV11428166({ runtimeContext, candidate } = {},
  selectedAt = new Date().toISOString()) {
  const runtimeContextId = text(runtimeContext?.runtimeContextNo)
  const materialCode = text(runtimeContext?.materialCode)
  const supplierCode = text(candidate?.supplierCode)
  if (!runtimeContextId || !materialCode || !supplierCode
    || text(candidate?.materialCode) !== materialCode) {
    throw new Error('SUPPLIER_RECOMMENDATION_CURRENT_SELECTION_INSTANCE_MISMATCH')
  }
  return Object.freeze({
    objectType: 'SupplierRecommendationCurrentSelection',
    runtimeContextId,
    priceApprovalId: text(runtimeContext.priceApprovalId),
    quoteComparisonId: text(runtimeContext.quoteComparisonId),
    materialCode,
    materialName: text(runtimeContext.materialName),
    supplierCode,
    supplierName: text(candidate.supplierName),
    supplierQuote: Number(candidate.quotePrice ?? 0),
    selectedAt,
    selectionMode: 'manual',
  })
}
