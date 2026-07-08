export function generateApprovalDecision(context = {}) {
  const prediction = context.predictionRuntime || context.predictiveDecision || context.prediction || {}
  const approval = prediction.approvalProbability || {}
  const risk = prediction.riskLevel || {}
  const probabilityScore = Number(approval.probabilityScore || 0)
  const riskLevel = risk.level || 'MEDIUM'

  if (riskLevel === 'LOW' && probabilityScore >= 75) {
    return {
      autoApproval: 'APPROVED',
      action: 'AUTO_APPROVE',
      probabilityScore,
      riskLevel,
      approvalPath: 'LOW_RISK_FAST_LANE',
      reason: 'Low risk and approval probability meets enterprise threshold',
    }
  }

  if (riskLevel === 'HIGH' || probabilityScore < 45) {
    return {
      autoApproval: 'REJECTED',
      action: 'AUTO_REJECT',
      probabilityScore,
      riskLevel,
      approvalPath: 'RISK_REJECTION_LANE',
      reason: 'Risk or approval probability violates enterprise threshold',
    }
  }

  return {
    autoApproval: 'ADJUSTED',
    action: 'ROUTE_TO_MANAGER_REVIEW',
    probabilityScore,
    riskLevel,
    approvalPath: 'MANAGER_REVIEW_LANE',
    reason: 'Decision requires human review before execution',
  }
}
