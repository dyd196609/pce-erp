export const PRICE_APPROVAL_ENTRY_ASSESSMENT_MAPPING_VERSION = 'V1.14.2.8.6.3'

const field = (runtimeField, sourceFields, fallback = '') => Object.freeze({
  runtimeField,
  sourceFields: Object.freeze(sourceFields),
  fallback,
  factAuthority: 'server',
})

export const PRICE_APPROVAL_ENTRY_ASSESSMENT_RUNTIME_MAPPING = Object.freeze({
  mappingCode: 'SCM_PRICE_APPROVAL_ENTRY_ASSESSMENT_RUNTIME_MAPPING',
  version: PRICE_APPROVAL_ENTRY_ASSESSMENT_MAPPING_VERSION,
  sourceCollection: 'priceApprovalEntryAssessments',
  source: 'server_facts',
  fields: Object.freeze([
    field('assessmentNo', ['assessmentNo']),
    field('inquiryNo', ['inquiryNo']),
    field('comparisonNo', ['comparisonNo']),
    field('preparationNo', ['preparationNo']),
    field('quotationEvidenceStatus', ['quotationEvidenceStatus']),
    field('quotationEvidenceStatusLabel', ['quotationEvidenceStatusLabel']),
    field('comparisonStatus', ['comparisonStatus']),
    field('comparisonStatusLabel', ['comparisonStatusLabel']),
    field('preparationStatus', ['preparationStatus']),
    field('preparationStatusLabel', ['preparationStatusLabel']),
    field('assessmentStatus', ['assessmentStatus']),
    field('assessmentStatusLabel', ['assessmentStatusLabel']),
    field('manualReviewRequired', ['manualReviewRequired'], false),
    field('entryConditionLabel', ['entryConditionLabel']),
    field('blockedReasons', ['blockedReasons'], []),
  ]),
})

export function mapPriceApprovalEntryAssessmentFact(source = {}) {
  return Object.freeze(Object.fromEntries(PRICE_APPROVAL_ENTRY_ASSESSMENT_RUNTIME_MAPPING.fields.map((item) => {
    const sourceField = item.sourceFields.find((name) => source?.[name] !== undefined && source[name] !== null)
    return [item.runtimeField, sourceField ? source[sourceField] : item.fallback]
  })))
}

export function validatePriceApprovalEntryAssessmentRuntimeMapping(mapping = PRICE_APPROVAL_ENTRY_ASSESSMENT_RUNTIME_MAPPING) {
  const required = ['assessmentNo', 'inquiryNo', 'comparisonNo', 'preparationNo', 'quotationEvidenceStatus', 'comparisonStatus', 'preparationStatus', 'assessmentStatus', 'manualReviewRequired', 'blockedReasons']
  const fields = new Set(mapping.fields?.map((item) => item.runtimeField))
  const valid = required.every((name) => fields.has(name)) && mapping.source === 'server_facts'
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
