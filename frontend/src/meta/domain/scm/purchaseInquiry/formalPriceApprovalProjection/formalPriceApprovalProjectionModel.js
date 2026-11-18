import { FORMAL_PRICE_APPROVAL_PROJECTION_STATES } from './formalPriceApprovalProjectionStateModel.js'

export const FORMAL_PRICE_APPROVAL_PROJECTION_MODEL_VERSION = 'V1.14.2.8.6.5'

const field = (name, type) => Object.freeze({ name, type, required: true, factAuthority: 'server' })

export const FORMAL_PRICE_APPROVAL_PROJECTION = Object.freeze({
  objectCode: 'SCM_FORMAL_PRICE_APPROVAL_PROJECTION',
  objectName: '正式价格审批对象只读投影',
  businessObject: 'FormalPriceApprovalProjection',
  version: FORMAL_PRICE_APPROVAL_PROJECTION_MODEL_VERSION,
  fields: Object.freeze([
    field('projectionNo', 'string'),
    field('inquiryNo', 'string'),
    field('creationAssessmentNo', 'string'),
    field('preparationNo', 'string'),
    field('comparisonNo', 'string'),
    field('evidencePackageNo', 'string'),
    field('projectionStatus', 'status'),
    field('missingEvidence', 'array'),
  ]),
  states: FORMAL_PRICE_APPROVAL_PROJECTION_STATES,
  purpose: 'pre_creation_read_only_projection',
  persistenceMode: 'read_only_projection',
  formalPriceApprovalObject: false,
  objectCreationAllowed: false,
  approvalWorkflowStartAllowed: false,
  approvalTaskCreationAllowed: false,
  approvalSubmissionAllowed: false,
  priceApprovalAllowed: false,
  createsPurchaseOrder: false,
  productionDataWritten: false,
})

export function validateFormalPriceApprovalProjection(model = FORMAL_PRICE_APPROVAL_PROJECTION) {
  const required = ['projectionNo', 'inquiryNo', 'creationAssessmentNo', 'preparationNo', 'comparisonNo', 'evidencePackageNo', 'projectionStatus', 'missingEvidence']
  const fields = new Set(model.fields?.map((item) => item.name))
  const valid = required.every((name) => fields.has(name))
    && model.states.join(',') === 'not_created,available,incomplete,blocked'
    && model.persistenceMode === 'read_only_projection'
    && model.formalPriceApprovalObject === false
    && model.objectCreationAllowed === false
    && model.approvalWorkflowStartAllowed === false
    && model.approvalTaskCreationAllowed === false
    && model.approvalSubmissionAllowed === false
    && model.priceApprovalAllowed === false
    && model.createsPurchaseOrder === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
