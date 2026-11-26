export const FORMAL_PRICE_APPROVAL_AUDIT_TRAIL_VERSION = 'V1.14.2.8.6.24'

export const FORMAL_PRICE_APPROVAL_AUDIT_FIELDS = Object.freeze([
  'auditNo', 'sourceType', 'sourceReference', 'eventType', 'operatorRole', 'evidenceReference', 'auditStatus',
])

export const FORMAL_PRICE_APPROVAL_AUDIT_EVENT_TYPES = Object.freeze([
  'NODE_DEFINED', 'RULE_DEFINED', 'COMMENT_DEFINED', 'EVIDENCE_REFERENCED', 'REVIEW_CHECKED', 'DECISION_PREPARED',
])

export const FORMAL_PRICE_APPROVAL_AUDIT_DEFINITIONS = Object.freeze(
  FORMAL_PRICE_APPROVAL_AUDIT_EVENT_TYPES.map((eventType) => Object.freeze({ eventType, auditStatus: 'definition_only', realEventGenerated: false })),
)

export const FORMAL_PRICE_APPROVAL_AUDIT_TRAIL = Object.freeze({
  auditCode: 'SCM_FORMAL_PRICE_APPROVAL_AUDIT_TRAIL',
  version: FORMAL_PRICE_APPROVAL_AUDIT_TRAIL_VERSION,
  fields: FORMAL_PRICE_APPROVAL_AUDIT_FIELDS,
  eventTypes: FORMAL_PRICE_APPROVAL_AUDIT_EVENT_TYPES,
  definitions: FORMAL_PRICE_APPROVAL_AUDIT_DEFINITIONS,
  currentStatus: 'definition_only',
  auditMeansPersistence: false,
  auditMeansApprovalExecution: false,
  realEventGenerationEnabled: false,
  auditDefinitionCount: 6,
  persistedRecordCount: 0,
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function validateFormalPriceApprovalAuditTrail(model = FORMAL_PRICE_APPROVAL_AUDIT_TRAIL) {
  const valid = model.auditCode === 'SCM_FORMAL_PRICE_APPROVAL_AUDIT_TRAIL'
    && model.fields.join(',') === FORMAL_PRICE_APPROVAL_AUDIT_FIELDS.join(',')
    && model.eventTypes.join(',') === FORMAL_PRICE_APPROVAL_AUDIT_EVENT_TYPES.join(',')
    && model.definitions.length === 6
    && model.definitions.every((item) => item.auditStatus === 'definition_only' && item.realEventGenerated === false)
    && model.currentStatus === 'definition_only'
    && model.auditMeansPersistence === false
    && model.auditMeansApprovalExecution === false
    && model.realEventGenerationEnabled === false
    && model.auditDefinitionCount === 6
    && model.persistedRecordCount === 0
    && model.businessWriteCount === 0
    && model.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
