export const SUPPLIER_QUOTE_SIMPLE_MODEL_VERSION = 'V1.14.2.8.18.12.1'

export const SUPPLIER_QUOTE_SIMPLE_FIELDS = Object.freeze([
  'quoteId', 'sourceInquiryId', 'supplierCode', 'supplierName',
  'materialCode', 'materialName', 'quantity', 'quotePrice', 'remark',
])

const text = value => String(value ?? '').trim()

export function createSupplierQuoteSimpleModel(source = {}, input = {}) {
  const quotePrice = Number(input.quotePrice)
  if (!text(source.inquiryNo || source.sourceInquiryId) || !text(source.supplierCode)
    || !text(source.materialCode) || !Number.isFinite(quotePrice) || quotePrice <= 0) {
    throw new Error('SUPPLIER_QUOTE_SIMPLE_INPUT_INVALID')
  }
  return Object.freeze({
    quoteId: text(source.quote?.quoteId || source.quote?.quoteNo)
      || `SQ-${text(source.inquiryNo || source.sourceInquiryId)}-${text(source.materialCode)}-${text(source.supplierCode)}`,
    sourceInquiryId: text(source.inquiryNo || source.sourceInquiryId),
    supplierCode: text(source.supplierCode),
    supplierName: text(source.supplierName),
    materialCode: text(source.materialCode),
    materialName: text(source.materialName),
    quantity: Number(source.quantity || 0),
    quotePrice,
    remark: text(input.remark),
  })
}

export function projectSupplierQuoteSimpleFields(quote = {}) {
  return Object.freeze(Object.fromEntries(SUPPLIER_QUOTE_SIMPLE_FIELDS.map(field => [field, quote[field] ?? ''])))
}
