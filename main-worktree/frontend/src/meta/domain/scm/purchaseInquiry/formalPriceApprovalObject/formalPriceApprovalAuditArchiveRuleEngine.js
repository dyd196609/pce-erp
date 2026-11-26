export const FORMAL_PRICE_APPROVAL_AUDIT_ARCHIVE_RULE_VERSION = 'V1.14.2.8.6.24'

const REQUIRED_SOURCES = Object.freeze(['node', 'rule', 'comment', 'evidence'])

export function evaluateFormalPriceApprovalAuditArchive(input = {}) {
  if (input.assessmentRequested !== true) {
    return Object.freeze({ result: 'PASS', decision: 'not_assessed', assessmentStatus: 'not_assessed', blockedReasons: Object.freeze([]), auditPersisted: false, evidenceArchivePersisted: false, approvalInstanceCreated: false, approvalTaskCreated: false, approvalExecuted: false, approvalResultCreated: false, businessEffectApplied: false, priceChanged: false, businessStateChanged: false, databaseWritten: false, businessWriteCount: 0, productionDataWritten: false })
  }
  const traceableSources = Array.isArray(input.traceableSources) ? input.traceableSources : []
  const blockedReasons = []
  if (!REQUIRED_SOURCES.every((source) => traceableSources.includes(source))) blockedReasons.push('Rule001_audit_source_incomplete')
  if (input.evidenceReferencePresent !== true) blockedReasons.push('Rule002_evidence_reference_missing')
  if (input.auditSeparatedFromPersistence !== true) blockedReasons.push('Rule003_audit_isolation_failed')
  if (input.archiveSeparatedFromBusinessData !== true) blockedReasons.push('Rule004_archive_isolation_failed')
  if (input.auditSeparatedFromApprovalExecution !== true) blockedReasons.push('Rule005_execution_isolation_failed')
  const forbiddenRequest = input.realAuditEventGenerationRequested === true
    || input.archivePersistenceRequested === true
    || input.approvalExecutionRequested === true
    || input.approvalInstanceCreationRequested === true
    || input.approvalTaskCreationRequested === true
    || input.approvalResultCreationRequested === true
    || input.priceChangeRequested === true
    || input.businessStateChangeRequested === true
    || input.databaseWriteRequested === true
    || Number(input.businessWriteCount || 0) > 0
  if (forbiddenRequest) blockedReasons.push('runtime_action_forbidden')
  const assessmentStatus = blockedReasons.length === 0 ? 'audit_archive_definition_ready' : 'blocked'
  return Object.freeze({
    result: assessmentStatus === 'audit_archive_definition_ready' ? 'PASS' : 'FAIL', decision: assessmentStatus, assessmentStatus,
    blockedReasons: Object.freeze(blockedReasons), auditPersisted: false, evidenceArchivePersisted: false,
    approvalInstanceCreated: false, approvalTaskCreated: false, approvalExecuted: false, approvalResultCreated: false,
    businessEffectApplied: false, priceChanged: false, businessStateChanged: false, databaseWritten: false,
    businessWriteCount: 0, productionDataWritten: false,
  })
}
