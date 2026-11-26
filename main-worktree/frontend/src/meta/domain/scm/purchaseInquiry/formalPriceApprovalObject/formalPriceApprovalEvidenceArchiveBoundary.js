export const FORMAL_PRICE_APPROVAL_EVIDENCE_ARCHIVE_BOUNDARY_VERSION = 'V1.14.2.8.6.24'

export const FORMAL_PRICE_APPROVAL_EVIDENCE_ARCHIVE_FIELDS = Object.freeze([
  'archiveBoundaryNo', 'evidencePackageNo', 'sourceReferences', 'archiveMode', 'persisted',
])

export const FORMAL_PRICE_APPROVAL_EVIDENCE_ARCHIVE_BOUNDARY = Object.freeze({
  boundaryCode: 'SCM_FORMAL_PRICE_APPROVAL_EVIDENCE_ARCHIVE_BOUNDARY',
  version: FORMAL_PRICE_APPROVAL_EVIDENCE_ARCHIVE_BOUNDARY_VERSION,
  fields: FORMAL_PRICE_APPROVAL_EVIDENCE_ARCHIVE_FIELDS,
  archiveMode: 'design_only',
  persisted: false,
  evidenceArchiveMeansBusinessWrite: false,
  archiveBoundaryCount: 1,
  persistedRecordCount: 0,
  archiveWriterConnected: false,
  businessDataWriterConnected: false,
  approvalExecutorConnected: false,
  priceMutationExecutorConnected: false,
  businessStateManagerConnected: false,
  databaseWriterConnected: false,
  productionExecution: false,
})

export function validateFormalPriceApprovalEvidenceArchiveBoundary(model = FORMAL_PRICE_APPROVAL_EVIDENCE_ARCHIVE_BOUNDARY) {
  const valid = model.boundaryCode === 'SCM_FORMAL_PRICE_APPROVAL_EVIDENCE_ARCHIVE_BOUNDARY'
    && model.fields.join(',') === FORMAL_PRICE_APPROVAL_EVIDENCE_ARCHIVE_FIELDS.join(',')
    && model.archiveMode === 'design_only'
    && model.persisted === false
    && model.evidenceArchiveMeansBusinessWrite === false
    && model.archiveBoundaryCount === 1
    && model.persistedRecordCount === 0
    && model.archiveWriterConnected === false
    && model.businessDataWriterConnected === false
    && model.approvalExecutorConnected === false
    && model.priceMutationExecutorConnected === false
    && model.businessStateManagerConnected === false
    && model.databaseWriterConnected === false
    && model.productionExecution === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
