export const FORMAL_PRICE_APPROVAL_HUMAN_BUSINESS_ACCEPTANCE_EXECUTION_VERSION = 'V1.14.2.8.7.6.2'

export const FORMAL_PRICE_APPROVAL_HUMAN_BUSINESS_ACCEPTANCE_EXECUTION_STATES = Object.freeze([
  'not_started', 'in_progress', 'completed', 'feedback_pending', 'closed',
])

export function createFormalPriceApprovalHumanBusinessAcceptanceExecution(input = {}) {
  return Object.freeze({
    acceptanceExecutionNo: input.acceptanceExecutionNo || 'SESSION-HUMAN-ACCEPTANCE',
    userRole: ['purchase_user', 'purchase_manager', 'acceptance_observer'].includes(input.userRole)
      ? input.userRole : 'purchase_user',
    viewMode: 'business_view',
    scenarioId: input.scenarioId || 'formal_price_approval_business_view',
    checklistResult: input.checklistResult || 'NOT_REVIEWED',
    feedbackStatus: input.feedbackStatus || 'not_collected',
    executionStatus: FORMAL_PRICE_APPROVAL_HUMAN_BUSINESS_ACCEPTANCE_EXECUTION_STATES.includes(input.executionStatus)
      ? input.executionStatus : 'not_started',
    isBusinessExecution: false,
    createsBusinessObject: false,
    createsApprovalObject: false,
    startsWorkflow: false,
    createsApprovalTask: false,
    persisted: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}

export const FORMAL_PRICE_APPROVAL_HUMAN_BUSINESS_ACCEPTANCE_EXECUTION = createFormalPriceApprovalHumanBusinessAcceptanceExecution()

export function validateFormalPriceApprovalHumanBusinessAcceptanceExecution(model = FORMAL_PRICE_APPROVAL_HUMAN_BUSINESS_ACCEPTANCE_EXECUTION) {
  const valid = Boolean(model.acceptanceExecutionNo) && model.viewMode === 'business_view'
    && FORMAL_PRICE_APPROVAL_HUMAN_BUSINESS_ACCEPTANCE_EXECUTION_STATES.includes(model.executionStatus)
    && ['PASS', 'FAIL', 'NOT_REVIEWED'].includes(model.checklistResult)
    && model.isBusinessExecution === false && model.createsBusinessObject === false
    && model.createsApprovalObject === false && model.startsWorkflow === false
    && model.createsApprovalTask === false && model.persisted === false
    && model.businessWriteCount === 0 && model.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
