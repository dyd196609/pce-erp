export const GOVERNANCE_FIRST_VERSION = 'V1.14.2.8.18.10.3.6B'

export const GOVERNANCE_FIRST_STAGES = Object.freeze([
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

export const GOVERNANCE_FIRST_STATUS = Object.freeze({
  READY: 'GOVERNANCE_FIRST_READY',
  BLOCKED: 'GOVERNANCE_FIRST_BLOCKED',
})

export function evaluateGovernanceFirstGate({
  existingStandardAssessed = false,
  standardUpdateRequired = false,
  standardUpdated = false,
  caseUpdateRequired = false,
  caseLibraryUpdated = false,
  matrixUpdateRequired = false,
  matrixUpdated = false,
} = {}) {
  const evidence = Object.freeze({
    existingStandardAssessed,
    standardUpdateCompleted: !standardUpdateRequired || standardUpdated,
    caseUpdateCompleted: !caseUpdateRequired || caseLibraryUpdated,
    matrixUpdateCompleted: !matrixUpdateRequired || matrixUpdated,
  })
  const missingEvidence = Object.freeze(Object.entries(evidence)
    .filter(([, completed]) => !completed)
    .map(([name]) => name))
  const governanceCheckPassed = missingEvidence.length === 0

  return Object.freeze({
    status: governanceCheckPassed
      ? GOVERNANCE_FIRST_STATUS.READY
      : GOVERNANCE_FIRST_STATUS.BLOCKED,
    governanceCheckPassed,
    designAllowed: governanceCheckPassed,
    developmentAllowed: governanceCheckPassed,
    evidence,
    missingEvidence,
    stages: GOVERNANCE_FIRST_STAGES,
  })
}
