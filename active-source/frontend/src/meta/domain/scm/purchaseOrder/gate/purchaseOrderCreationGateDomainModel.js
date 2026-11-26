export const PURCHASE_ORDER_CREATION_GATE_DOMAIN_MODEL_VERSION = 'V1.14.2.8.5.5'

const field = (name, type, required = true) => Object.freeze({ name, type, required })

export const PURCHASE_ORDER_CREATION_GATE_DOMAIN_MODEL = Object.freeze({
  objectCode: 'SCM_PURCHASE_ORDER_CREATION_GATE',
  objectName: '采购订单创建准入门',
  businessObject: 'PurchaseOrderCreationGate',
  fields: Object.freeze([
    field('recommendationDecisionId', 'object_reference'),
    field('inquiryId', 'object_reference'),
    field('supplierId', 'object_reference'),
    field('gateStatus', 'status'),
    field('eligibilityResult', 'enum'),
    field('blockingReasons', 'array'),
    field('riskWarnings', 'array'),
    field('evaluatedConditions', 'array'),
  ]),
  relationships: Object.freeze([
    Object.freeze({ relationshipCode: 'RECOMMENDATION_DECISION_TO_PO_CREATION_GATE', sourceObject: 'SCM_SUPPLIER_RECOMMENDATION_DECISION', targetObject: 'SCM_PURCHASE_ORDER_CREATION_GATE', relationshipType: 'business_reference', direction: 'forward' }),
    Object.freeze({ relationshipCode: 'PO_CREATION_GATE_TO_PURCHASE_ORDER_BOUNDARY', sourceObject: 'SCM_PURCHASE_ORDER_CREATION_GATE', targetBoundary: 'SCM_PURCHASE_ORDER', relationshipType: 'eligibility_reference', direction: 'forward', automaticCreation: false }),
  ]),
  traceFields: Object.freeze(['recommendationDecisionId', 'inquiryId', 'supplierId']),
  statusField: 'gateStatus',
  actionRules: Object.freeze({ ruleCode: 'SCM_PURCHASE_ORDER_CREATION_GATE_ACTION_GUARD', mode: 'explicit_whitelist_default_deny' }),
  persistenceMode: 'definition_only',
  createdAutomatically: false,
  automaticCreation: false,
  createsPurchaseOrder: false,
  executesBusinessAction: false,
})

export function validatePurchaseOrderCreationGateDomainModel(model = PURCHASE_ORDER_CREATION_GATE_DOMAIN_MODEL) {
  const requiredFields = ['recommendationDecisionId', 'inquiryId', 'supplierId', 'gateStatus', 'eligibilityResult', 'blockingReasons', 'riskWarnings', 'evaluatedConditions']
  const fields = new Set(model?.fields?.map(item => item.name) || [])
  const missing = requiredFields.filter(name => !fields.has(name))
  if (model?.createdAutomatically !== false) missing.push('createdAutomatically')
  if (model?.createsPurchaseOrder !== false) missing.push('createsPurchaseOrder')
  if (model?.persistenceMode !== 'definition_only') missing.push('persistenceMode')
  return Object.freeze({ result: missing.length ? 'FAIL' : 'PASS', missing: Object.freeze(missing) })
}
