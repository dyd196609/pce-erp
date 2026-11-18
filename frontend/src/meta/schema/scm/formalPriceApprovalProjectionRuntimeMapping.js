export const FORMAL_PRICE_APPROVAL_PROJECTION_MAPPING_VERSION = 'V1.14.2.8.6.5'

const field = (runtimeField, sourceFields, fallback = '') => Object.freeze({
  runtimeField,
  sourceFields: Object.freeze(sourceFields),
  fallback,
  factAuthority: 'server',
})

export const FORMAL_PRICE_APPROVAL_PROJECTION_RUNTIME_MAPPING = Object.freeze({
  mappingCode: 'SCM_FORMAL_PRICE_APPROVAL_PROJECTION_RUNTIME_MAPPING',
  version: FORMAL_PRICE_APPROVAL_PROJECTION_MAPPING_VERSION,
  sourceCollection: 'formalPriceApprovalProjections',
  source: 'server_facts',
  fields: Object.freeze([
    field('projectionNo', ['projectionNo']),
    field('inquiryNo', ['inquiryNo']),
    field('creationAssessmentNo', ['creationAssessmentNo']),
    field('preparationNo', ['preparationNo']),
    field('comparisonNo', ['comparisonNo']),
    field('evidencePackageNo', ['evidencePackageNo']),
    field('projectionStatus', ['projectionStatus']),
    field('projectionStatusLabel', ['projectionStatusLabel']),
    field('projectionAvailabilityLabel', ['projectionAvailabilityLabel']),
    field('missingEvidence', ['missingEvidence'], []),
  ]),
})

export const PRICE_APPROVAL_EVIDENCE_PACKAGE_RUNTIME_MAPPING = Object.freeze({
  mappingCode: 'SCM_PRICE_APPROVAL_EVIDENCE_PACKAGE_RUNTIME_MAPPING',
  version: FORMAL_PRICE_APPROVAL_PROJECTION_MAPPING_VERSION,
  sourceCollection: 'priceApprovalEvidencePackages',
  source: 'server_facts',
  fields: Object.freeze([
    field('evidencePackageNo', ['evidencePackageNo']),
    field('inquiryNo', ['inquiryNo']),
    field('quotationEvidenceRefs', ['quotationEvidenceRefs'], []),
    field('comparisonEvidenceRef', ['comparisonEvidenceRef']),
    field('preparationEvidenceRef', ['preparationEvidenceRef']),
    field('entryAssessmentEvidenceRef', ['entryAssessmentEvidenceRef']),
    field('creationFreezeEvidenceRef', ['creationFreezeEvidenceRef']),
    field('packageStatus', ['packageStatus']),
    field('packageStatusLabel', ['packageStatusLabel']),
    field('evidenceCount', ['evidenceCount'], 0),
    field('missingEvidence', ['missingEvidence'], []),
  ]),
})

function project(source, mapping) {
  return Object.freeze(Object.fromEntries(mapping.fields.map((item) => {
    const sourceField = item.sourceFields.find((name) => source?.[name] !== undefined && source[name] !== null)
    return [item.runtimeField, sourceField ? source[sourceField] : item.fallback]
  })))
}

export const mapFormalPriceApprovalProjectionFact = (source = {}) => project(source, FORMAL_PRICE_APPROVAL_PROJECTION_RUNTIME_MAPPING)
export const mapPriceApprovalEvidencePackageFact = (source = {}) => project(source, PRICE_APPROVAL_EVIDENCE_PACKAGE_RUNTIME_MAPPING)

export function validateFormalPriceApprovalProjectionRuntimeMappings() {
  const projectionFields = new Set(FORMAL_PRICE_APPROVAL_PROJECTION_RUNTIME_MAPPING.fields.map((item) => item.runtimeField))
  const packageFields = new Set(PRICE_APPROVAL_EVIDENCE_PACKAGE_RUNTIME_MAPPING.fields.map((item) => item.runtimeField))
  const valid = ['projectionNo', 'inquiryNo', 'creationAssessmentNo', 'preparationNo', 'comparisonNo', 'evidencePackageNo', 'projectionStatus', 'missingEvidence'].every((name) => projectionFields.has(name))
    && ['evidencePackageNo', 'inquiryNo', 'quotationEvidenceRefs', 'comparisonEvidenceRef', 'preparationEvidenceRef', 'entryAssessmentEvidenceRef', 'creationFreezeEvidenceRef', 'packageStatus', 'missingEvidence'].every((name) => packageFields.has(name))
    && [FORMAL_PRICE_APPROVAL_PROJECTION_RUNTIME_MAPPING, PRICE_APPROVAL_EVIDENCE_PACKAGE_RUNTIME_MAPPING].every((item) => item.source === 'server_facts')
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
