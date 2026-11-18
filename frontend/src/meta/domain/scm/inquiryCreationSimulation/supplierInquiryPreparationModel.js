export const SUPPLIER_INQUIRY_PREPARATION_VERSION = 'V1.14.2.8.7.8'

export function createSupplierInquiryPreparation(input = {}) {
  const candidates = Array.isArray(input.supplierCandidates) ? input.supplierCandidates.map((candidate, index) => Object.freeze({
    candidateNo: `CANDIDATE-${String(index + 1).padStart(3, '0')}`,
    supplierId: String(candidate.supplierId || ''),
    evidenceReference: String(candidate.evidenceReference || ''),
    candidateStatus: candidate.supplierId ? 'candidate_ready' : 'blocked',
    isSupplierInquiryTask: false,
    sendStatus: 'not_sent',
  })) : []
  const ready = Boolean(input.simulationNo) && candidates.length > 0
    && candidates.every(candidate => candidate.candidateStatus === 'candidate_ready')
  return Object.freeze({
    modelCode: 'SCM_SUPPLIER_INQUIRY_PREPARATION',
    version: SUPPLIER_INQUIRY_PREPARATION_VERSION,
    preparationNo: `PREP-${String(input.simulationNo || 'UNRESOLVED')}`,
    simulationNo: String(input.simulationNo || ''),
    preparationStatus: ready ? 'prepared' : 'blocked',
    supplierCandidates: Object.freeze(candidates),
    candidateCount: candidates.length,
    responseDeadlineReference: input.responseDeadlineReference || null,
    isSupplierInquiryTask: false,
    supplierInquiryTaskCreated: false,
    supplierSent: false,
    quotationTaskCreated: false,
    persistenceMode: 'none',
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}

export function validateSupplierInquiryPreparation(model) {
  const valid = model?.modelCode === 'SCM_SUPPLIER_INQUIRY_PREPARATION'
    && ['prepared', 'blocked'].includes(model.preparationStatus)
    && model.supplierCandidates.every(candidate => candidate.isSupplierInquiryTask === false
      && candidate.sendStatus === 'not_sent')
    && model.isSupplierInquiryTask === false && model.supplierInquiryTaskCreated === false
    && model.supplierSent === false && model.quotationTaskCreated === false
    && model.persistenceMode === 'none' && model.businessWriteCount === 0
    && model.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
