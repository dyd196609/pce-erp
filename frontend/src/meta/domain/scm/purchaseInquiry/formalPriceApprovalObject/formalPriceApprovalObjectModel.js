import { FORMAL_PRICE_APPROVAL_OBJECT_CURRENT_ALLOWED_STATES, FORMAL_PRICE_APPROVAL_OBJECT_LIFECYCLE } from './formalPriceApprovalObjectStateModel.js'

export const FORMAL_PRICE_APPROVAL_OBJECT_MODEL_VERSION = 'V1.14.2.8.6.6'

const field = (name, type) => Object.freeze({ name, type, required: true, factAuthority: 'future_server_object' })

export const FORMAL_PRICE_APPROVAL_OBJECT = Object.freeze({
  objectCode: 'SCM_FORMAL_PRICE_APPROVAL_OBJECT',
  objectName: '正式价格审批对象',
  businessObject: 'FormalPriceApprovalObject',
  version: FORMAL_PRICE_APPROVAL_OBJECT_MODEL_VERSION,
  fields: Object.freeze([
    field('priceApprovalNo', 'string'),
    field('inquiryNo', 'string'),
    field('projectionNo', 'string'),
    field('evidencePackageNo', 'string'),
    field('creationAssessmentNo', 'string'),
    field('supplierId', 'string'),
    field('quotationNo', 'string'),
    field('approvalAmount', 'money'),
    field('currency', 'currency'),
    field('approvalStatus', 'status'),
  ]),
  lifecycle: FORMAL_PRICE_APPROVAL_OBJECT_LIFECYCLE,
  currentAllowedStates: FORMAL_PRICE_APPROVAL_OBJECT_CURRENT_ALLOWED_STATES,
  persistenceMode: 'definition_only',
  instanceCreationAllowed: false,
  currentInstanceCount: 0,
  approvalWorkflowStartAllowed: false,
  approvalSubmissionAllowed: false,
  automaticApprovalAllowed: false,
  createsPurchaseOrder: false,
  productionDataWritten: false,
})

export function validateFormalPriceApprovalObject(model = FORMAL_PRICE_APPROVAL_OBJECT) {
  const required = ['priceApprovalNo', 'inquiryNo', 'projectionNo', 'evidencePackageNo', 'creationAssessmentNo', 'supplierId', 'quotationNo', 'approvalAmount', 'currency', 'approvalStatus']
  const fields = new Set(model.fields?.map((item) => item.name))
  const valid = required.every((name) => fields.has(name))
    && model.lifecycle.join(',') === 'definition_only,ready_for_creation,created,pending_approval,approved,rejected,cancelled'
    && model.currentAllowedStates.join(',') === 'definition_only,ready_for_creation'
    && model.persistenceMode === 'definition_only'
    && model.instanceCreationAllowed === false
    && model.currentInstanceCount === 0
    && model.approvalWorkflowStartAllowed === false
    && model.approvalSubmissionAllowed === false
    && model.automaticApprovalAllowed === false
    && model.createsPurchaseOrder === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
