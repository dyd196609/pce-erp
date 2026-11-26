export const FORMAL_PRICE_APPROVAL_SCENARIO_RULE_VERSION = 'V1.14.2.8.7.3'

const zeroEffect = Object.freeze({ scenarioDataMeansProductionData: false, expectedResultMeansAutoDecision: false,
  businessObjectCreated: false, approvalObjectCreated: false, workflowStarted: false,
  autoDecisionPerformed: false, persistencePerformed: false, businessWriteCount: 0, productionDataWritten: false })

export function evaluateFormalPriceApprovalScenario(input = {}) {
  if (input.simulationRequested !== true) {
    return Object.freeze({ result: 'PASS', decision: 'not_started', scenarioResult: 'not_started', ...zeroEffect })
  }
  const forbiddenRequest = input.productionDataRequested === true || input.autoDecisionRequested === true
    || input.businessObjectCreationRequested === true || input.approvalObjectCreationRequested === true
    || input.workflowStartRequested === true || input.persistenceRequested === true
    || Number(input.businessWriteCount || 0) > 0
  if (forbiddenRequest) return Object.freeze({ result: 'FAIL', decision: 'blocked', scenarioResult: 'blocked', ...zeroEffect })
  if (input.scenarioType === 'normal' && input.evidenceComplete === true && Number(input.supplierCount) >= 2)
    return Object.freeze({ result: 'PASS', decision: 'ready_for_manual_review', scenarioResult: 'ready_for_manual_review', ...zeroEffect })
  if (input.scenarioType === 'special' && input.specialPurchase === true && Number(input.supplierCount) === 1)
    return Object.freeze({ result: 'PASS', decision: 'manual_confirmation_required', scenarioResult: 'manual_confirmation_required', ...zeroEffect })
  if (input.scenarioType === 'exception' && input.evidenceComplete === false)
    return Object.freeze({ result: 'PASS', decision: 'blocked', scenarioResult: 'blocked', ...zeroEffect })
  return Object.freeze({ result: 'FAIL', decision: 'blocked', scenarioResult: 'blocked', ...zeroEffect })
}
