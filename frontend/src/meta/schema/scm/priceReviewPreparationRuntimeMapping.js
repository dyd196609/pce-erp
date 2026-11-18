export const PRICE_REVIEW_PREPARATION_RUNTIME_MAPPING_VERSION = 'V1.14.2.8.6.2'

const field = (runtimeField, sourceFields, fallback = '') => Object.freeze({
  runtimeField,
  sourceFields: Object.freeze(sourceFields),
  fallback,
  factAuthority: 'server',
})

export const QUOTATION_COMPARISON_RUNTIME_MAPPING = Object.freeze({
  mappingCode: 'SCM_QUOTATION_COMPARISON_RUNTIME_MAPPING',
  version: PRICE_REVIEW_PREPARATION_RUNTIME_MAPPING_VERSION,
  sourceCollection: 'quotationComparisons',
  source: 'server_facts',
  fields: Object.freeze([
    field('comparisonNo', ['comparisonNo']),
    field('inquiryNo', ['inquiryNo']),
    field('quotationCount', ['quotationCount'], 0),
    field('supplierCount', ['supplierCount'], 0),
    field('lowestPriceSupplier', ['lowestPriceSupplier']),
    field('highestPriceSupplier', ['highestPriceSupplier']),
    field('priceVariance', ['priceVariance'], 0),
    field('deliveryComparison', ['deliveryComparison'], []),
    field('comparisonStatus', ['comparisonStatus']),
    field('comparisonStatusLabel', ['comparisonStatusLabel']),
    field('comparisonConclusion', ['comparisonConclusion']),
  ]),
})

export const PRICE_REVIEW_PREPARATION_RUNTIME_MAPPING = Object.freeze({
  mappingCode: 'SCM_PRICE_REVIEW_PREPARATION_RUNTIME_MAPPING',
  version: PRICE_REVIEW_PREPARATION_RUNTIME_MAPPING_VERSION,
  sourceCollection: 'priceReviewPreparations',
  source: 'server_facts',
  fields: Object.freeze([
    field('preparationNo', ['preparationNo']),
    field('inquiryNo', ['inquiryNo']),
    field('comparisonNo', ['comparisonNo']),
    field('sourceQuotationCount', ['sourceQuotationCount'], 0),
    field('reviewStatus', ['reviewStatus']),
    field('reviewStatusLabel', ['reviewStatusLabel']),
    field('blockedReasons', ['blockedReasons'], []),
    field('priceReviewEntryAllowed', ['priceReviewEntryAllowed'], false),
    field('priceReviewEntryAllowedLabel', ['priceReviewEntryAllowedLabel']),
  ]),
})

function project(source, mapping) {
  return Object.freeze(Object.fromEntries(mapping.fields.map((item) => {
    const key = item.sourceFields.find((sourceField) => source?.[sourceField] !== undefined && source[sourceField] !== null)
    return [item.runtimeField, key ? source[key] : item.fallback]
  })))
}

export const mapQuotationComparisonFact = (source = {}) => project(source, QUOTATION_COMPARISON_RUNTIME_MAPPING)
export const mapPriceReviewPreparationFact = (source = {}) => project(source, PRICE_REVIEW_PREPARATION_RUNTIME_MAPPING)

export function validatePriceReviewPreparationRuntimeMappings() {
  const comparisonFields = new Set(QUOTATION_COMPARISON_RUNTIME_MAPPING.fields.map((item) => item.runtimeField))
  const preparationFields = new Set(PRICE_REVIEW_PREPARATION_RUNTIME_MAPPING.fields.map((item) => item.runtimeField))
  const valid = ['comparisonNo', 'inquiryNo', 'quotationCount', 'supplierCount', 'lowestPriceSupplier', 'highestPriceSupplier', 'priceVariance', 'deliveryComparison', 'comparisonStatus'].every((name) => comparisonFields.has(name))
    && ['preparationNo', 'inquiryNo', 'comparisonNo', 'sourceQuotationCount', 'reviewStatus', 'blockedReasons'].every((name) => preparationFields.has(name))
    && [QUOTATION_COMPARISON_RUNTIME_MAPPING, PRICE_REVIEW_PREPARATION_RUNTIME_MAPPING].every((item) => item.source === 'server_facts')
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
