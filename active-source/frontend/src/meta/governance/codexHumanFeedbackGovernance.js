export const CODEX_HUMAN_FEEDBACK_GOVERNANCE_VERSION = 'V1.14.2.8.18.10.3.6A'

export const CODEX_ACCEPTANCE_STATUS = Object.freeze({
  AUTO_FAIL: 'AUTOMATIC_ACCEPTANCE_FAIL',
  HUMAN_PENDING: 'HUMAN_ACCEPTANCE_PENDING',
  AUTO_PASS_HUMAN_FAIL: 'AUTO_PASS_HUMAN_FAIL',
  HUMAN_FEEDBACK_OPEN: 'HUMAN_FEEDBACK_OPEN',
  READY_ELIGIBLE: 'ACCEPTANCE_READY_ELIGIBLE',
})

export function evaluateCodexAcceptanceGate({
  automaticAcceptance,
  humanAcceptance,
  humanFeedbackRequired = false,
  humanFeedbackClosed = false,
} = {}) {
  if (automaticAcceptance !== 'PASS') return Object.freeze({
    status: CODEX_ACCEPTANCE_STATUS.AUTO_FAIL,
    readyEligible: false,
    publishAllowed: false,
    reason: 'automatic_acceptance_not_passed',
  })
  if (!humanAcceptance || humanAcceptance === 'PENDING' || humanAcceptance === 'BLOCKED') return Object.freeze({
    status: CODEX_ACCEPTANCE_STATUS.HUMAN_PENDING,
    readyEligible: false,
    publishAllowed: false,
    reason: 'human_acceptance_incomplete',
  })
  if (humanAcceptance === 'FAIL') return Object.freeze({
    status: CODEX_ACCEPTANCE_STATUS.AUTO_PASS_HUMAN_FAIL,
    readyEligible: false,
    publishAllowed: false,
    reason: 'human_acceptance_failed',
  })
  if (humanFeedbackRequired && !humanFeedbackClosed) return Object.freeze({
    status: CODEX_ACCEPTANCE_STATUS.HUMAN_FEEDBACK_OPEN,
    readyEligible: false,
    publishAllowed: false,
    reason: 'human_feedback_not_closed',
  })
  return Object.freeze({
    status: CODEX_ACCEPTANCE_STATUS.READY_ELIGIBLE,
    readyEligible: true,
    publishAllowed: true,
    reason: 'automatic_and_human_acceptance_passed',
  })
}
