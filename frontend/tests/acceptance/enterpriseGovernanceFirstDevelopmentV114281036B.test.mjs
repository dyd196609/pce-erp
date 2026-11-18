import test from 'node:test'
import assert from 'node:assert/strict'
import {
  GOVERNANCE_FIRST_STAGES,
  GOVERNANCE_FIRST_STATUS,
  evaluateGovernanceFirstGate,
} from '../../src/meta/governance/governanceFirstDevelopment.js'

test('CODEX-COMMAND-003 blocks development before governance assessment', () => {
  const result = evaluateGovernanceFirstGate()
  assert.equal(result.status, GOVERNANCE_FIRST_STATUS.BLOCKED)
  assert.equal(result.governanceCheckPassed, false)
  assert.equal(result.developmentAllowed, false)
  assert.deepEqual(result.missingEvidence, ['existingStandardAssessed'])
})

test('CODEX-COMMAND-003 blocks development while required governance updates remain open', () => {
  const result = evaluateGovernanceFirstGate({
    existingStandardAssessed: true,
    standardUpdateRequired: true,
    caseUpdateRequired: true,
    matrixUpdateRequired: true,
  })
  assert.equal(result.status, GOVERNANCE_FIRST_STATUS.BLOCKED)
  assert.equal(result.developmentAllowed, false)
  assert.deepEqual(result.missingEvidence, [
    'standardUpdateCompleted',
    'caseUpdateCompleted',
    'matrixUpdateCompleted',
  ])
})

test('GOV-001 allows development only after all required governance evidence is complete', () => {
  const result = evaluateGovernanceFirstGate({
    existingStandardAssessed: true,
    standardUpdateRequired: true,
    standardUpdated: true,
    caseUpdateRequired: true,
    caseLibraryUpdated: true,
    matrixUpdateRequired: true,
    matrixUpdated: true,
  })
  assert.equal(result.status, GOVERNANCE_FIRST_STATUS.READY)
  assert.equal(result.developmentAllowed, true)
  assert.deepEqual(result.stages, GOVERNANCE_FIRST_STAGES)
  assert.deepEqual(result.stages, [
    'REQUIREMENT_OR_ISSUE',
    'GOVERNANCE_ASSESSMENT',
    'STANDARD_CHECK',
    'STANDARD_UPDATE',
    'CODEX_TASK_GENERATION',
    'DEVELOPMENT_IMPLEMENTATION',
    'AUTOMATIC_ACCEPTANCE',
    'HUMAN_ACCEPTANCE',
    'CASE_CLOSURE',
  ])
})
