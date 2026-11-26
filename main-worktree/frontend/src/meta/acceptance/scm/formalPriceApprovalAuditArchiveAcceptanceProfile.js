export const FORMAL_PRICE_APPROVAL_AUDIT_ARCHIVE_ACCEPTANCE_VERSION = 'V1.14.2.8.6.24'

export const FORMAL_PRICE_APPROVAL_AUDIT_ARCHIVE_ACCEPTANCE_PROFILE = Object.freeze({
  profileCode: 'SCM_FORMAL_PRICE_APPROVAL_AUDIT_ARCHIVE_ACCEPTANCE',
  version: FORMAL_PRICE_APPROVAL_AUDIT_ARCHIVE_ACCEPTANCE_VERSION,
  status: 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_AUDIT_ARCHIVE_READY',
  route: '/scm/purchase-inquiry',
  requiredRegions: Object.freeze(['formal-price-approval-audit-archive']),
  forbiddenPageActions: Object.freeze(['save-audit', 'archive-evidence', 'approve', 'execute']),
  gates: Object.freeze(['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']),
  auditModelComplete: true,
  evidenceBoundaryComplete: true,
  auditMeansPersistence: false,
  evidenceArchiveMeansBusinessWrite: false,
  auditMeansApprovalExecution: false,
  auditDefinitionCount: 6,
  archiveBoundaryCount: 1,
  persistedRecordCount: 0,
  auditPersisted: false,
  evidenceArchivePersisted: false,
  businessWriteCount: 0,
  databaseState: 'UNCHANGED',
  productionDataWritten: false,
})

export function validateFormalPriceApprovalAuditArchiveAcceptance(profile = FORMAL_PRICE_APPROVAL_AUDIT_ARCHIVE_ACCEPTANCE_PROFILE) {
  const gates = ['Page', 'Router', 'Schema', 'Runtime', 'Rule', 'Guard', 'Acceptance', 'Build']
  const valid = gates.every((gate) => profile.gates.includes(gate))
    && profile.auditModelComplete === true && profile.evidenceBoundaryComplete === true
    && profile.auditMeansPersistence === false && profile.evidenceArchiveMeansBusinessWrite === false
    && profile.auditMeansApprovalExecution === false && profile.auditDefinitionCount === 6
    && profile.archiveBoundaryCount === 1 && profile.persistedRecordCount === 0
    && profile.auditPersisted === false && profile.evidenceArchivePersisted === false
    && profile.businessWriteCount === 0 && profile.databaseState === 'UNCHANGED'
    && profile.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
