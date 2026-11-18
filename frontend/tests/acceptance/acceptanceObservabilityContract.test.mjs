import test from 'node:test'
import assert from 'node:assert/strict'
import {
  PCE_ACCEPTANCE_OBSERVABILITY_CONTRACT_VERSION,
  assertAcceptanceFacts,
  createAcceptanceFacts,
  summarizeAcceptanceActions,
} from '../../src/meta/acceptance/acceptanceObservabilityContract.js'

const baseFacts = {
  pageCode: 'FIN_TEST',
  factSource: 'server',
  recordCount: 8,
  selectedCount: 0,
  actionCount: 2,
  dangerActionCount: 0,
  businessProgressWriteCount: 0,
  downstreamObjectCount: 0,
}

test('observability contract version is V1.0', () => {
  assert.equal(PCE_ACCEPTANCE_OBSERVABILITY_CONTRACT_VERSION, 'PCE-ACCEPTANCE-OBSERVABILITY-CONTRACT-V1.0')
})

test('creates immutable server acceptance facts', () => {
  const facts = createAcceptanceFacts(baseFacts)
  assert.equal(facts.recordCount, 8)
  assert.ok(Object.isFrozen(facts))
})

test('rejects non-server fact source', () => {
  assert.throws(() => createAcceptanceFacts({ ...baseFacts, factSource: 'frontend' }), /factSource/)
})

test('requires every count field', () => {
  const facts = { ...baseFacts }
  delete facts.downstreamObjectCount
  assert.throws(() => createAcceptanceFacts(facts), /downstreamObjectCount/)
})

test('allows explicit unavailable server record count with reason', () => {
  const facts = createAcceptanceFacts({
    ...baseFacts,
    recordCount: null,
    recordCountUnavailableReason: 'legacy page has no server count contract',
  })
  assert.equal(facts.recordCount, null)
})

test('rejects unavailable record count without reason', () => {
  assert.throws(() => createAcceptanceFacts({ ...baseFacts, recordCount: null }), /UnavailableReason/)
})

test('action summary detects dangerous action codes', () => {
  assert.deepEqual(
    summarizeAcceptanceActions([{ actionCode: 'view-detail' }, { actionCode: 'bank-send-execution' }]),
    { actionCount: 2, dangerActionCount: 1 },
  )
})

test('assertion accepts a complete frozen fact payload', () => {
  const facts = createAcceptanceFacts(baseFacts)
  assert.equal(assertAcceptanceFacts(facts).pageCode, 'FIN_TEST')
})
