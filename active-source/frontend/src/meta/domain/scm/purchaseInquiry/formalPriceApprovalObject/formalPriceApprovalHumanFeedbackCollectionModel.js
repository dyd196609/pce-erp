export const FORMAL_PRICE_APPROVAL_HUMAN_FEEDBACK_COLLECTION_VERSION = 'V1.14.2.8.7.6.2'

export const FORMAL_PRICE_APPROVAL_HUMAN_FEEDBACK_TYPES = Object.freeze([
  'unclear_business_meaning', 'missing_information', 'too_much_information', 'navigation_problem', 'risk_warning_problem',
])

export function createFormalPriceApprovalHumanFeedbackCollection(input = {}) {
  return Object.freeze({
    feedbackNo: input.feedbackNo || 'SESSION-HUMAN-FEEDBACK',
    userRole: ['purchase_user', 'purchase_manager', 'acceptance_observer'].includes(input.userRole)
      ? input.userRole : 'purchase_user',
    pageSection: input.pageSection || 'formal_price_approval_business_view',
    feedbackType: FORMAL_PRICE_APPROVAL_HUMAN_FEEDBACK_TYPES.includes(input.feedbackType)
      ? input.feedbackType : 'unclear_business_meaning',
    description: String(input.description || ''),
    suggestion: String(input.suggestion || ''),
    status: input.status || 'not_collected',
    storageMode: 'memory_session_only',
    isErpData: false,
    persisted: false,
    businessStateChanged: false,
    approvalTriggered: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}

export const FORMAL_PRICE_APPROVAL_HUMAN_FEEDBACK_COLLECTION = createFormalPriceApprovalHumanFeedbackCollection()

export function validateFormalPriceApprovalHumanFeedbackCollection(model = FORMAL_PRICE_APPROVAL_HUMAN_FEEDBACK_COLLECTION) {
  const valid = Boolean(model.feedbackNo) && Boolean(model.userRole) && Boolean(model.pageSection)
    && FORMAL_PRICE_APPROVAL_HUMAN_FEEDBACK_TYPES.includes(model.feedbackType)
    && model.storageMode === 'memory_session_only' && model.isErpData === false
    && model.persisted === false && model.businessStateChanged === false
    && model.approvalTriggered === false && model.businessWriteCount === 0
    && model.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
