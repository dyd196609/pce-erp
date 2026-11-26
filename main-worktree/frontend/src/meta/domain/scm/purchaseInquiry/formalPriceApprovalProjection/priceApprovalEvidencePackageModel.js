import { FORMAL_PRICE_APPROVAL_PROJECTION_STATES } from './formalPriceApprovalProjectionStateModel.js'

export const PRICE_APPROVAL_EVIDENCE_PACKAGE_MODEL_VERSION = 'V1.14.2.8.6.5'

const field = (name, type) => Object.freeze({ name, type, required: true, factAuthority: 'server' })

export const PRICE_APPROVAL_EVIDENCE_PACKAGE = Object.freeze({
  objectCode: 'SCM_PRICE_APPROVAL_EVIDENCE_PACKAGE',
  objectName: '价格审批前证据包',
  businessObject: 'PriceApprovalEvidencePackage',
  version: PRICE_APPROVAL_EVIDENCE_PACKAGE_MODEL_VERSION,
  fields: Object.freeze([
    field('evidencePackageNo', 'string'),
    field('inquiryNo', 'string'),
    field('quotationEvidenceRefs', 'array'),
    field('comparisonEvidenceRef', 'string'),
    field('preparationEvidenceRef', 'string'),
    field('entryAssessmentEvidenceRef', 'string'),
    field('creationFreezeEvidenceRef', 'string'),
    field('packageStatus', 'status'),
    field('missingEvidence', 'array'),
  ]),
  states: FORMAL_PRICE_APPROVAL_PROJECTION_STATES,
  persistenceMode: 'read_only_projection',
  archiveMode: 'server_fact_reference_only',
  archiveWriteAllowed: false,
  automaticAssembly: false,
  formalPriceApprovalObjectCreated: false,
  productionDataWritten: false,
})

export function validatePriceApprovalEvidencePackage(model = PRICE_APPROVAL_EVIDENCE_PACKAGE) {
  const required = ['evidencePackageNo', 'inquiryNo', 'quotationEvidenceRefs', 'comparisonEvidenceRef', 'preparationEvidenceRef', 'entryAssessmentEvidenceRef', 'creationFreezeEvidenceRef', 'packageStatus', 'missingEvidence']
  const fields = new Set(model.fields?.map((item) => item.name))
  const valid = required.every((name) => fields.has(name))
    && model.states.length === 4
    && model.persistenceMode === 'read_only_projection'
    && model.archiveMode === 'server_fact_reference_only'
    && model.archiveWriteAllowed === false
    && model.automaticAssembly === false
    && model.formalPriceApprovalObjectCreated === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
