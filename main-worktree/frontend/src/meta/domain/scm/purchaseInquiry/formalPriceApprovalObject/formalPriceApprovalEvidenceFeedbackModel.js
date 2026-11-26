export const FORMAL_PRICE_APPROVAL_EVIDENCE_FEEDBACK_VERSION = 'V1.14.2.8.6.23'

export const FORMAL_PRICE_APPROVAL_EVIDENCE_FEEDBACK_FIELDS = Object.freeze([
  'feedbackNo', 'sourceCommentNo', 'sourceEvidenceRefs', 'feedbackType', 'reviewRequired', 'feedbackStatus',
])

export const FORMAL_PRICE_APPROVAL_EVIDENCE_FEEDBACK_MODEL = Object.freeze({
  modelCode: 'SCM_FORMAL_PRICE_APPROVAL_EVIDENCE_FEEDBACK',
  version: FORMAL_PRICE_APPROVAL_EVIDENCE_FEEDBACK_VERSION,
  fields: FORMAL_PRICE_APPROVAL_EVIDENCE_FEEDBACK_FIELDS,
  statuses: Object.freeze(['definition_only', 'feedback_reference', 'review_reference', 'closed_reference']),
  currentStatus: 'definition_only',
  mode: 'definition_only',
  feedbackMeansBusinessChange: false,
  feedbackMeansTaskExecution: false,
  feedbackExecutionEnabled: false,
  feedbackInstanceCount: 0,
  persistenceConnected: false,
})

export function validateFormalPriceApprovalEvidenceFeedbackModel(model = FORMAL_PRICE_APPROVAL_EVIDENCE_FEEDBACK_MODEL) {
  const valid = model.modelCode === 'SCM_FORMAL_PRICE_APPROVAL_EVIDENCE_FEEDBACK'
    && model.fields.join(',') === FORMAL_PRICE_APPROVAL_EVIDENCE_FEEDBACK_FIELDS.join(',')
    && model.statuses.includes(model.currentStatus)
    && model.currentStatus === 'definition_only'
    && model.mode === 'definition_only'
    && model.feedbackMeansBusinessChange === false
    && model.feedbackMeansTaskExecution === false
    && model.feedbackExecutionEnabled === false
    && model.feedbackInstanceCount === 0
    && model.persistenceConnected === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
