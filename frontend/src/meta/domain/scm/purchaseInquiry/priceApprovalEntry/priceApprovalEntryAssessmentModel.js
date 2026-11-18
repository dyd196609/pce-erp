import { PRICE_APPROVAL_ENTRY_ASSESSMENT_STATES } from './priceApprovalEntryAssessmentStateModel.js'

export const PRICE_APPROVAL_ENTRY_ASSESSMENT_MODEL_VERSION = 'V1.14.2.8.6.3'

const field = (name, type) => Object.freeze({ name, type, required: true, factAuthority: 'server' })

export const PRICE_APPROVAL_ENTRY_ASSESSMENT = Object.freeze({
  objectCode: 'SCM_PRICE_APPROVAL_ENTRY_ASSESSMENT',
  objectName: '价格审批入口准入评估',
  businessObject: 'PriceApprovalEntryAssessment',
  version: PRICE_APPROVAL_ENTRY_ASSESSMENT_MODEL_VERSION,
  fields: Object.freeze([
    field('assessmentNo', 'string'),
    field('inquiryNo', 'string'),
    field('comparisonNo', 'string'),
    field('preparationNo', 'string'),
    field('quotationEvidenceStatus', 'status'),
    field('comparisonStatus', 'status'),
    field('preparationStatus', 'status'),
    field('assessmentStatus', 'status'),
    field('manualReviewRequired', 'boolean'),
    field('blockedReasons', 'array'),
  ]),
  states: PRICE_APPROVAL_ENTRY_ASSESSMENT_STATES,
  purpose: 'future_price_approval_entry_condition_assessment_only',
  persistenceMode: 'read_only_projection',
  formalPriceApprovalObject: false,
  automaticCreation: false,
  automaticSubmission: false,
  automaticApproval: false,
  autoSupplierSelection: false,
  createsPurchaseOrder: false,
  productionDataWritten: false,
})

export function validatePriceApprovalEntryAssessment(model = PRICE_APPROVAL_ENTRY_ASSESSMENT) {
  const required = ['assessmentNo', 'inquiryNo', 'comparisonNo', 'preparationNo', 'quotationEvidenceStatus', 'comparisonStatus', 'preparationStatus', 'assessmentStatus', 'manualReviewRequired', 'blockedReasons']
  const fields = new Set(model.fields?.map((item) => item.name))
  const valid = required.every((name) => fields.has(name))
    && model.states.join(',') === 'not_assessed,eligible,not_eligible,manual_review,blocked'
    && model.persistenceMode === 'read_only_projection'
    && model.formalPriceApprovalObject === false
    && model.automaticCreation === false
    && model.automaticSubmission === false
    && model.automaticApproval === false
    && model.autoSupplierSelection === false
    && model.createsPurchaseOrder === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
