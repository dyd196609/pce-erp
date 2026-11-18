export const FORMAL_PRICE_APPROVAL_USER_ACCEPTANCE_FEEDBACK_VERSION = 'V1.14.2.8.7.5'

export const FORMAL_PRICE_APPROVAL_USER_ACCEPTANCE_FEEDBACK_ISSUE_TYPES = Object.freeze([
  'unclear_business_meaning', 'missing_information', 'unnecessary_information', 'navigation_issue', 'risk_warning_issue',
])

export function createFormalPriceApprovalUserAcceptanceFeedback(input = {}) {
  const issueType = FORMAL_PRICE_APPROVAL_USER_ACCEPTANCE_FEEDBACK_ISSUE_TYPES.includes(input.issueType)
    ? input.issueType : 'unclear_business_meaning'
  return Object.freeze({
    feedbackNo: input.feedbackNo || 'SESSION-FEEDBACK-DRAFT',
    userRole: input.userRole || 'purchase_buyer',
    viewMode: ['business_view', 'acceptance_view'].includes(input.viewMode) ? input.viewMode : 'business_view',
    issueType,
    description: String(input.description || ''),
    suggestion: String(input.suggestion || ''),
    status: 'session_draft',
    isBusinessData: false,
    persisted: false,
    businessStateChanged: false,
    approvalActionTriggered: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}

export const FORMAL_PRICE_APPROVAL_USER_ACCEPTANCE_FEEDBACK = createFormalPriceApprovalUserAcceptanceFeedback()

export function validateFormalPriceApprovalUserAcceptanceFeedback(model = FORMAL_PRICE_APPROVAL_USER_ACCEPTANCE_FEEDBACK) {
  const valid = Boolean(model.feedbackNo) && Boolean(model.userRole)
    && ['business_view', 'acceptance_view'].includes(model.viewMode)
    && FORMAL_PRICE_APPROVAL_USER_ACCEPTANCE_FEEDBACK_ISSUE_TYPES.includes(model.issueType)
    && model.status === 'session_draft' && model.isBusinessData === false && model.persisted === false
    && model.businessStateChanged === false && model.approvalActionTriggered === false
    && model.businessWriteCount === 0 && model.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
