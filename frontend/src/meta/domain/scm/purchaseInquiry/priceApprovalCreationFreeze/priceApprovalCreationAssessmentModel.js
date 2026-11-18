import { PRICE_APPROVAL_CREATION_ASSESSMENT_STATES } from './priceApprovalCreationAssessmentStateModel.js'

export const PRICE_APPROVAL_CREATION_ASSESSMENT_MODEL_VERSION = 'V1.14.2.8.6.4'

const field = (name, type) => Object.freeze({ name, type, required: true, factAuthority: 'server' })

export const PRICE_APPROVAL_CREATION_ASSESSMENT = Object.freeze({
  objectCode: 'SCM_PRICE_APPROVAL_CREATION_ASSESSMENT',
  objectName: '正式价格审批对象创建前冻结评估',
  businessObject: 'PriceApprovalCreationAssessment',
  version: PRICE_APPROVAL_CREATION_ASSESSMENT_MODEL_VERSION,
  fields: Object.freeze([
    field('creationAssessmentNo', 'string'),
    field('inquiryNo', 'string'),
    field('entryAssessmentNo', 'string'),
    field('preparationNo', 'string'),
    field('entryAssessmentStatus', 'status'),
    field('preparationStatus', 'status'),
    field('quotationEvidenceStatus', 'status'),
    field('creationAssessmentStatus', 'status'),
    field('manualReviewRequired', 'boolean'),
    field('blockedReasons', 'array'),
  ]),
  states: PRICE_APPROVAL_CREATION_ASSESSMENT_STATES,
  purpose: 'formal_price_approval_creation_freeze_assessment_only',
  persistenceMode: 'read_only_projection',
  formalPriceApprovalObjectCreated: false,
  approvalWorkflowStarted: false,
  approvalSubmitted: false,
  priceApproved: false,
  createsPurchaseOrder: false,
  productionDataWritten: false,
})

export function validatePriceApprovalCreationAssessment(model = PRICE_APPROVAL_CREATION_ASSESSMENT) {
  const required = ['creationAssessmentNo', 'inquiryNo', 'entryAssessmentNo', 'preparationNo', 'entryAssessmentStatus', 'preparationStatus', 'quotationEvidenceStatus', 'creationAssessmentStatus', 'manualReviewRequired', 'blockedReasons']
  const fields = new Set(model.fields?.map((item) => item.name))
  const valid = required.every((name) => fields.has(name))
    && model.states.join(',') === 'not_assessed,ready,manual_review,blocked'
    && model.persistenceMode === 'read_only_projection'
    && model.formalPriceApprovalObjectCreated === false
    && model.approvalWorkflowStarted === false
    && model.approvalSubmitted === false
    && model.priceApproved === false
    && model.createsPurchaseOrder === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
