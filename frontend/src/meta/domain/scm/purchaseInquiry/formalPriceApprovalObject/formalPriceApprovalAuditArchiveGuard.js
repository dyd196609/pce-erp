export const FORMAL_PRICE_APPROVAL_AUDIT_ARCHIVE_GUARD_VERSION = 'V1.14.2.8.6.24'

export const FORMAL_PRICE_APPROVAL_AUDIT_ARCHIVE_FORBIDDEN_ACTIONS = Object.freeze([
  'generateAuditBusinessRecord', 'persistEvidenceArchive', 'triggerApprovalFromAudit',
  'createApprovalInstance', 'createApprovalTask', 'executeApproval', 'createApprovalResult',
  'changePriceFromArchive', 'changeBusinessStateFromArchive', 'applyBusinessEffect', 'writeProductionDatabase',
])

export function evaluateFormalPriceApprovalAuditArchiveGuard({ action = '', mode = '' } = {}) {
  if (action === 'inspectAuditArchiveDefinition') {
    const designOnly = mode === 'design_only'
    return Object.freeze({ result: designOnly ? 'PASS' : 'FAIL', decision: designOnly ? 'allow_definition_inspection_only' : 'deny', auditPersisted: false, evidenceArchivePersisted: false, approvalInstanceCreated: false, approvalTaskCreated: false, approvalExecuted: false, approvalResultCreated: false, businessEffectApplied: false, priceChanged: false, businessStateChanged: false, databaseWritten: false, businessWriteCount: 0, productionDataWritten: false })
  }
  const protectedAction = FORMAL_PRICE_APPROVAL_AUDIT_ARCHIVE_FORBIDDEN_ACTIONS.includes(action)
  return Object.freeze({ result: protectedAction ? 'PASS' : 'FAIL', decision: 'deny', reason: protectedAction ? 'audit_archive_frozen' : 'audit_archive_default_deny', auditPersisted: false, evidenceArchivePersisted: false, approvalInstanceCreated: false, approvalTaskCreated: false, approvalExecuted: false, approvalResultCreated: false, businessEffectApplied: false, priceChanged: false, businessStateChanged: false, databaseWritten: false, businessWriteCount: 0, productionDataWritten: false })
}
