const REQUIRED_COUNT_FIELDS = Object.freeze([
  'recordCount',
  'actionCount',
  'dangerActionCount',
  'businessProgressWriteCount',
  'downstreamObjectCount',
])

const rule = (id, field, validate) => Object.freeze({ id, field, validate })

export const ACCEPTANCE_FACTS_VALIDATOR_RULES = Object.freeze([
  rule('FACT-OBS-001', 'factSource', facts => facts?.factSource === 'server'),
  rule('FACT-OBS-002', 'recordCount', facts => Number.isInteger(facts?.recordCount)),
  rule('FACT-OBS-003', 'actionCount', facts => Number.isInteger(facts?.actionCount)),
  rule('FACT-OBS-004', 'dangerActionCount', facts => Number.isInteger(facts?.dangerActionCount)),
  rule(
    'FACT-OBS-005',
    'businessProgressWriteCount',
    facts => Number.isInteger(facts?.businessProgressWriteCount),
  ),
  rule(
    'FACT-OBS-006',
    'downstreamObjectCount',
    facts => Number.isInteger(facts?.downstreamObjectCount),
  ),
])

export class AcceptanceFactsValidationError extends Error {
  constructor(violations) {
    super(`AcceptanceFacts validation failed: ${violations.join(', ')}`)
    this.name = 'AcceptanceFactsValidationError'
    this.violations = violations
  }
}

export function validateAcceptanceFacts(facts) {
  if (facts?.factLoadStatus === 'read_failed') {
    const validFailure = facts.recordCount === null
      && Boolean(facts.errorCode)
      && Boolean(facts.errorMessage)
    if (!validFailure) {
      throw new AcceptanceFactsValidationError(['READ_FAILED_CONTRACT'])
    }
    return Object.freeze({ valid: true, readFailed: true, checks: [] })
  }
  const violations = ACCEPTANCE_FACTS_VALIDATOR_RULES
    .filter(item => !item.validate(facts))
    .map(item => item.id)
  if (violations.length) throw new AcceptanceFactsValidationError(violations)
  for (const field of REQUIRED_COUNT_FIELDS) {
    if (facts[field] < 0) {
      throw new AcceptanceFactsValidationError([`${field}:NEGATIVE`])
    }
  }
  return Object.freeze({
    valid: true,
    readFailed: false,
    checks: ACCEPTANCE_FACTS_VALIDATOR_RULES.map(item => item.id),
  })
}
