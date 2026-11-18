import test from 'node:test'
import assert from 'node:assert/strict'
import {
  CODEX_ACCEPTANCE_STATUS,
  evaluateCodexAcceptanceGate,
} from '../../src/meta/governance/codexHumanFeedbackGovernance.js'

test('CODEX-COMMAND-002 blocks READY when automatic acceptance passes but human acceptance fails', () => {
  const result = evaluateCodexAcceptanceGate({
    automaticAcceptance: 'PASS',
    humanAcceptance: 'FAIL',
  })
  assert.equal(result.status, CODEX_ACCEPTANCE_STATUS.AUTO_PASS_HUMAN_FAIL)
  assert.equal(result.readyEligible, false)
  assert.equal(result.publishAllowed, false)
})

test('CODEX-COMMAND-002 keeps READY blocked while human feedback remains open', () => {
  const result = evaluateCodexAcceptanceGate({
    automaticAcceptance: 'PASS',
    humanAcceptance: 'PASS',
    humanFeedbackRequired: true,
    humanFeedbackClosed: false,
  })
  assert.equal(result.status, CODEX_ACCEPTANCE_STATUS.HUMAN_FEEDBACK_OPEN)
  assert.equal(result.readyEligible, false)
})

test('READY eligibility requires automatic PASS, human PASS and closed feedback', () => {
  const result = evaluateCodexAcceptanceGate({
    automaticAcceptance: 'PASS',
    humanAcceptance: 'PASS',
    humanFeedbackRequired: true,
    humanFeedbackClosed: true,
  })
  assert.equal(result.status, CODEX_ACCEPTANCE_STATUS.READY_ELIGIBLE)
  assert.equal(result.readyEligible, true)
})
