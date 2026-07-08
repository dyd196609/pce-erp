export function approveLowRisk(context = {}) {
  const decision = context.decisionAutomationRuntime || context.automatedDecision || context.decision || {}
  const approval = decision.approvalDecision || {}

  return {
    autoApproveLowRisk: approval.action === 'AUTO_APPROVE',
    approvalStatus: approval.action === 'AUTO_APPROVE' ? 'APPROVED_WITHOUT_HUMAN' : 'NOT_LOW_RISK',
    approvalPath: approval.approvalPath || 'UNKNOWN',
  }
}

export function rerouteHighRisk(context = {}) {
  const decision = context.decisionAutomationRuntime || context.automatedDecision || context.decision || {}
  const riskDecision = decision.riskDecision || {}
  const shouldReroute = ['BLOCK_OPERATION', 'DOWNGRADE_FLOW'].includes(riskDecision.action)

  return {
    autoRerouteHighRisk: shouldReroute,
    route: shouldReroute ? riskDecision.executionPath : 'AUTO_EXECUTION_PATH',
    reason: riskDecision.reason || 'Low risk approval path',
  }
}

export function eliminateManualApproval(context = {}) {
  const lowRisk = approveLowRisk(context)
  const highRisk = rerouteHighRisk(context)

  return {
    zeroApproval: 'ENABLED',
    manualApproval: 'ELIMINATED',
    lowRisk,
    highRisk,
    finalApprovalPath: lowRisk.autoApproveLowRisk ? lowRisk.approvalPath : highRisk.route,
  }
}
