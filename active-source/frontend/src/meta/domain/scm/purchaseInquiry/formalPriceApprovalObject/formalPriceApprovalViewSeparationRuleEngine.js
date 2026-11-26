export const FORMAL_PRICE_APPROVAL_VIEW_SEPARATION_RULE_VERSION = 'V1.14.2.8.7.4'

const zeroEffect = Object.freeze({ viewSwitchMeansBusinessAction: false, hiddenMeansDeleted: false,
  businessActionTriggered: false, approvalObjectCreated: false, workflowStarted: false,
  governanceModelDeleted: false, persistencePerformed: false, businessWriteCount: 0, productionDataWritten: false })

export function evaluateFormalPriceApprovalViewSeparation(input = {}) {
  if (input.switchRequested !== true) return Object.freeze({ result: 'PASS', decision: 'business_view', activeMode: 'business_view', ...zeroEffect })
  const allowed = ['business_view', 'acceptance_view'].includes(input.targetMode)
  const forbiddenRequest = input.businessActionRequested === true || input.approvalObjectCreationRequested === true
    || input.workflowStartRequested === true || input.governanceModelDeletionRequested === true
    || input.persistenceRequested === true || Number(input.businessWriteCount || 0) > 0
  if (!allowed || forbiddenRequest) return Object.freeze({ result: 'FAIL', decision: 'blocked', activeMode: input.currentMode || 'business_view', ...zeroEffect })
  return Object.freeze({ result: 'PASS', decision: 'view_switched', activeMode: input.targetMode, ...zeroEffect })
}
