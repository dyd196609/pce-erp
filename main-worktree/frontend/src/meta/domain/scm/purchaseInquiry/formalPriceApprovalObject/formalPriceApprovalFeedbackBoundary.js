export const FORMAL_PRICE_APPROVAL_FEEDBACK_BOUNDARY_VERSION = 'V1.14.2.8.6.23'

export const FORMAL_PRICE_APPROVAL_FEEDBACK_BOUNDARY = Object.freeze({
  boundaryCode: 'SCM_FORMAL_PRICE_APPROVAL_FEEDBACK_BOUNDARY',
  version: FORMAL_PRICE_APPROVAL_FEEDBACK_BOUNDARY_VERSION,
  mode: 'feedback_definition_only',
  commentMeansApprovalResult: false,
  feedbackMeansBusinessChange: false,
  feedbackMeansTaskExecution: false,
  commentFactoryConnected: false,
  feedbackExecutorConnected: false,
  taskExecutorConnected: false,
  resultFactoryConnected: false,
  businessChangeExecutorConnected: false,
  persistenceAdapterConnected: false,
  productionExecution: false,
})

export function validateFormalPriceApprovalFeedbackBoundary(model = FORMAL_PRICE_APPROVAL_FEEDBACK_BOUNDARY) {
  const valid = model.boundaryCode === 'SCM_FORMAL_PRICE_APPROVAL_FEEDBACK_BOUNDARY'
    && model.mode === 'feedback_definition_only'
    && model.commentMeansApprovalResult === false
    && model.feedbackMeansBusinessChange === false
    && model.feedbackMeansTaskExecution === false
    && model.commentFactoryConnected === false
    && model.feedbackExecutorConnected === false
    && model.taskExecutorConnected === false
    && model.resultFactoryConnected === false
    && model.businessChangeExecutorConnected === false
    && model.persistenceAdapterConnected === false
    && model.productionExecution === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
