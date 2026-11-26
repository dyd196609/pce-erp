export const PRICE_APPROVAL_CREATION_ASSESSMENT_MAPPING_VERSION = 'V1.14.2.8.6.4'

const field = (runtimeField, sourceFields, fallback = '') => Object.freeze({
  runtimeField,
  sourceFields: Object.freeze(sourceFields),
  fallback,
  factAuthority: 'server',
})

export const PRICE_APPROVAL_CREATION_ASSESSMENT_RUNTIME_MAPPING = Object.freeze({
  mappingCode: 'SCM_PRICE_APPROVAL_CREATION_ASSESSMENT_RUNTIME_MAPPING',
  version: PRICE_APPROVAL_CREATION_ASSESSMENT_MAPPING_VERSION,
  sourceCollection: 'priceApprovalCreationAssessments',
  source: 'server_facts',
  fields: Object.freeze([
    field('creationAssessmentNo', ['creationAssessmentNo']),
    field('inquiryNo', ['inquiryNo']),
    field('entryAssessmentNo', ['entryAssessmentNo']),
    field('preparationNo', ['preparationNo']),
    field('entryAssessmentStatus', ['entryAssessmentStatus']),
    field('entryAssessmentStatusLabel', ['entryAssessmentStatusLabel']),
    field('preparationStatus', ['preparationStatus']),
    field('preparationStatusLabel', ['preparationStatusLabel']),
    field('quotationEvidenceStatus', ['quotationEvidenceStatus']),
    field('quotationEvidenceStatusLabel', ['quotationEvidenceStatusLabel']),
    field('creationAssessmentStatus', ['creationAssessmentStatus']),
    field('creationAssessmentStatusLabel', ['creationAssessmentStatusLabel']),
    field('manualReviewRequired', ['manualReviewRequired'], false),
    field('creationReadinessLabel', ['creationReadinessLabel']),
    field('blockedReasons', ['blockedReasons'], []),
  ]),
})

export function mapPriceApprovalCreationAssessmentFact(source = {}) {
  return Object.freeze(Object.fromEntries(PRICE_APPROVAL_CREATION_ASSESSMENT_RUNTIME_MAPPING.fields.map((item) => {
    const sourceField = item.sourceFields.find((name) => source?.[name] !== undefined && source[name] !== null)
    return [item.runtimeField, sourceField ? source[sourceField] : item.fallback]
  })))
}

export function validatePriceApprovalCreationAssessmentRuntimeMapping(mapping = PRICE_APPROVAL_CREATION_ASSESSMENT_RUNTIME_MAPPING) {
  const required = ['creationAssessmentNo', 'inquiryNo', 'entryAssessmentNo', 'preparationNo', 'entryAssessmentStatus', 'preparationStatus', 'quotationEvidenceStatus', 'creationAssessmentStatus', 'manualReviewRequired', 'blockedReasons']
  const fields = new Set(mapping.fields?.map((item) => item.runtimeField))
  const valid = required.every((name) => fields.has(name)) && mapping.source === 'server_facts'
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
