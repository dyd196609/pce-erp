export const FORMAL_PRICE_APPROVAL_CREATION_AUDIT_TRAIL_MODEL_VERSION = 'V1.14.2.8.6.10'

export const FORMAL_PRICE_APPROVAL_CREATION_AUDIT_EVENT_TYPES = Object.freeze([
  'command_evaluated',
  'authorization_requested',
  'authorization_evaluated',
  'execution_blocked',
])

export const FORMAL_PRICE_APPROVAL_CREATION_AUDIT_TRAIL = Object.freeze({
  auditCode: 'SCM_FORMAL_PRICE_APPROVAL_CREATION_AUDIT_TRAIL',
  version: FORMAL_PRICE_APPROVAL_CREATION_AUDIT_TRAIL_MODEL_VERSION,
  artifactType: 'NON_PERSISTENT_AUDIT_DESCRIPTION',
  fields: Object.freeze(['eventType', 'actorId', 'occurredAt', 'outcome', 'reason']),
  supportedEventTypes: FORMAL_PRICE_APPROVAL_CREATION_AUDIT_EVENT_TYPES,
  businessObject: false,
  persistenceMode: 'none',
  auditRecordWritten: false,
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function buildFormalPriceApprovalCreationAuditTrail(events = []) {
  const entries = Object.freeze(events
    .filter((event) => FORMAL_PRICE_APPROVAL_CREATION_AUDIT_EVENT_TYPES.includes(event?.eventType))
    .map((event) => Object.freeze({
      eventType: event.eventType,
      actorId: String(event.actorId || ''),
      occurredAt: String(event.occurredAt || ''),
      outcome: String(event.outcome || ''),
      reason: String(event.reason || ''),
    })))
  return Object.freeze({
    auditCode: FORMAL_PRICE_APPROVAL_CREATION_AUDIT_TRAIL.auditCode,
    artifactType: FORMAL_PRICE_APPROVAL_CREATION_AUDIT_TRAIL.artifactType,
    entries,
    entryCount: entries.length,
    businessObject: false,
    persisted: false,
    auditRecordWritten: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}

export function validateFormalPriceApprovalCreationAuditTrail(model = FORMAL_PRICE_APPROVAL_CREATION_AUDIT_TRAIL) {
  const valid = model.auditCode === 'SCM_FORMAL_PRICE_APPROVAL_CREATION_AUDIT_TRAIL'
    && model.artifactType === 'NON_PERSISTENT_AUDIT_DESCRIPTION'
    && model.businessObject === false
    && model.persistenceMode === 'none'
    && model.auditRecordWritten === false
    && model.businessWriteCount === 0
    && model.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
