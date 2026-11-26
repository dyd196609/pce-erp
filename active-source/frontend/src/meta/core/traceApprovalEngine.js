import { analyzeRisk } from './traceRiskEngine.js'

function decide(risk) {
  switch (risk) {
    case 'LOW':
      return 'AUTO_APPROVE_SUGGESTED'
    case 'MEDIUM':
      return 'MANUAL_APPROVAL_REQUIRED'
    case 'HIGH':
      return 'HARD_REVIEW_REQUIRED'
    case 'CRITICAL':
      return 'BLOCK_EXECUTION'
    default:
      return 'HARD_REVIEW_REQUIRED'
  }
}

export function analyzeApproval() {
  const risk = analyzeRisk()
  const decisions = risk.patches.map((patch) => ({
    ...patch,
    decision: decide(patch.risk),
  }))

  return {
    decisions,
    policy: {
      auto: decisions.filter((decision) => decision.decision === 'AUTO_APPROVE_SUGGESTED')
        .length,
      manual: decisions.filter((decision) => decision.decision === 'MANUAL_APPROVAL_REQUIRED')
        .length,
      review: decisions.filter((decision) => decision.decision === 'HARD_REVIEW_REQUIRED')
        .length,
      blocked: decisions.filter((decision) => decision.decision === 'BLOCK_EXECUTION').length,
    },
  }
}
