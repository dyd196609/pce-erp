import { createPriceReferenceContext } from './priceReferenceContext.js'

export const MATERIAL_PRICE_CONTEXT_VERSION = 'V1.14.2.8.18.15'
export const MATERIAL_PRICE_CONTEXT_TYPES = Object.freeze({
  NEW_MATERIAL: 'new_material',
  EXISTING_MATERIAL: 'existing_material',
})

const isHistoricalPurchase = record => record && Number.isFinite(Number(record.purchasePrice))
  && Number(record.purchasePrice) > 0

export function detectMaterialPriceContextType(historicalPurchases = []) {
  return historicalPurchases.some(isHistoricalPurchase)
    ? MATERIAL_PRICE_CONTEXT_TYPES.EXISTING_MATERIAL
    : MATERIAL_PRICE_CONTEXT_TYPES.NEW_MATERIAL
}

export function createNewMaterialPriceAssessmentContext(input = {}) {
  if (!input.materialCode) throw new Error('NEW_MATERIAL_IDENTITY_REQUIRED')
  return Object.freeze({
    objectType: 'NewMaterialPriceAssessmentContext',
    materialCode: input.materialCode,
    materialName: input.materialName || '',
    supplierQuote: input.supplierQuote ?? null,
    comparisonResult: input.comparisonResult ?? null,
    supplierInfo: Object.freeze({
      supplierCode: input.supplierCode || '',
      supplierName: input.supplierName || '',
    }),
    manualAssessment: input.manualAssessment || '',
    historyReferenceAvailable: false,
    automaticDecision: false,
    businessWriteCount: 0,
  })
}

export function createMaterialPriceContext(input = {}) {
  if (!input.materialCode || !input.inquiryNo) throw new Error('MATERIAL_PRICE_CONTEXT_IDENTITY_REQUIRED')
  const historicalPurchases = (input.historicalPurchases || []).filter(isHistoricalPurchase)
  const contextType = detectMaterialPriceContextType(historicalPurchases)
  const common = {
    objectType: 'MaterialPriceContext',
    contextType,
    inquiryNo: input.inquiryNo,
    materialCode: input.materialCode,
    materialName: input.materialName || '',
    supplierCode: input.supplierCode || '',
    supplierName: input.supplierName || '',
    readOnly: true,
    automaticQuoteRejection: false,
    automaticQuoteApproval: false,
    automaticSupplierRecommendation: false,
    purchaseOrderCreated: false,
    businessStateAdvanced: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  }
  if (contextType === MATERIAL_PRICE_CONTEXT_TYPES.NEW_MATERIAL) {
    return Object.freeze({ ...common,
      newMaterialPriceAssessmentContext: createNewMaterialPriceAssessmentContext(input),
      priceReferenceContext: null,
    })
  }
  return Object.freeze({ ...common,
    newMaterialPriceAssessmentContext: null,
    priceReferenceContext: createPriceReferenceContext({ ...input, historicalPurchases }),
  })
}
