export const SUPPLIER_RECOMMENDATION_EVIDENCE_MODEL_VERSION = 'V1.14.2.8.5.4'

const field = (name, type) => Object.freeze({ name, type, required: true })

export const SUPPLIER_RECOMMENDATION_EVIDENCE_MODEL = Object.freeze({
  objectCode: 'SCM_SUPPLIER_RECOMMENDATION_EVIDENCE',
  objectName: '供应商推荐证据',
  businessObject: 'SupplierRecommendationEvidence',
  fields: Object.freeze([
    field('evidenceType', 'string'),
    field('sourceObjectType', 'string'),
    field('sourceObjectId', 'object_reference'),
    field('evidenceValue', 'evidence_value'),
  ]),
  parentObject: 'SCM_SUPPLIER_RECOMMENDATION_DECISION',
  relationshipType: 'evidence_reference',
  immutable: true,
  persistenceMode: 'definition_only',
  createdAutomatically: false,
  automaticCreation: false,
})

export function validateSupplierRecommendationEvidenceModel(model = SUPPLIER_RECOMMENDATION_EVIDENCE_MODEL) {
  const requiredFields = ['evidenceType', 'sourceObjectType', 'sourceObjectId', 'evidenceValue']
  const fields = new Set(model?.fields?.map(item => item.name) || [])
  const missing = requiredFields.filter(name => !fields.has(name))
  if (model?.parentObject !== 'SCM_SUPPLIER_RECOMMENDATION_DECISION') missing.push('parentObject')
  return Object.freeze({ result: missing.length ? 'FAIL' : 'PASS', missing: Object.freeze(missing) })
}
