import test from 'node:test'
import assert from 'node:assert/strict'
import {
  ACCEPTANCE_FACTS_VALIDATOR_RULES,
  AcceptanceFactsValidationError,
  validateAcceptanceFacts,
} from '../../src/meta/acceptance/AcceptanceFactsValidator.js'

const validFacts = {
  factLoadStatus: 'success',
  pageCode: 'FIN_TEST',
  factSource: 'server',
  recordCount: 8,
  selectedCount: 0,
  actionCount: 3,
  dangerActionCount: 0,
  businessProgressWriteCount: 0,
  downstreamObjectCount: 0,
}

for (const rule of ACCEPTANCE_FACTS_VALIDATOR_RULES) {
  test(`${rule.id} accepts complete server facts`, () => {
    assert.equal(rule.validate(validFacts), true)
  })
}

for (const rule of ACCEPTANCE_FACTS_VALIDATOR_RULES) {
  test(`${rule.id} rejects its missing field`, () => {
    const facts = { ...validFacts }
    delete facts[rule.field]
    assert.equal(rule.validate(facts), false)
  })
}

for (const field of [
  'recordCount',
  'actionCount',
  'dangerActionCount',
  'businessProgressWriteCount',
  'downstreamObjectCount',
]) {
  test(`${field} rejects negative count`, () => {
    assert.throws(
      () => validateAcceptanceFacts({ ...validFacts, [field]: -1 }),
      AcceptanceFactsValidationError,
    )
  })
}

test('complete success payload passes all six validator rules', () => {
  const result = validateAcceptanceFacts(validFacts)
  assert.equal(result.valid, true)
  assert.equal(result.checks.length, 6)
})

test('read_failed requires null record count and explicit error', () => {
  const result = validateAcceptanceFacts({
    ...validFacts,
    factLoadStatus: 'read_failed',
    recordCount: null,
    errorCode: 'NETWORK_READ_FAILED',
    errorMessage: 'network unavailable',
  })
  assert.equal(result.readFailed, true)
})

test('read_failed cannot masquerade as zero records', () => {
  assert.throws(
    () => validateAcceptanceFacts({
      ...validFacts,
      factLoadStatus: 'read_failed',
      recordCount: 0,
      errorCode: 'NETWORK_READ_FAILED',
      errorMessage: 'network unavailable',
    }),
    /READ_FAILED_CONTRACT/,
  )
})

test('client fact source is rejected', () => {
  assert.throws(
    () => validateAcceptanceFacts({ ...validFacts, factSource: 'client' }),
    /FACT-OBS-001/,
  )
})

test('successful load cannot omit record count', () => {
  assert.throws(
    () => validateAcceptanceFacts({ ...validFacts, recordCount: null }),
    /FACT-OBS-002/,
  )
})
