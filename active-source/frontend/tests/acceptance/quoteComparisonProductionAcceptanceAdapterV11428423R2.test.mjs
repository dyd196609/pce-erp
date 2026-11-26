import test from 'node:test'
import assert from 'node:assert/strict'
import { adaptQuoteComparisonProductionFacts } from '../../src/meta/acceptance/quoteComparisonProductionAcceptanceAdapterV11428423R2.js'

const productionFacts = count => ({
  rows: Array.from({ length: count }, (_, index) => ({ quoteComparisonId: `QC-${index + 1}` })),
  resultCount: count,
  source: 'production',
  dataMode: 'production',
  factLoadStatus: 'loaded',
})

test('13 production rows satisfy the unified contract', () => {
  const result = adaptQuoteComparisonProductionFacts(productionFacts(13))
  assert.equal(result.contractAligned, true)
  assert.equal(result.productionDataConsistent, true)
  assert.equal(result.productionUserDataWritten, false)
})

test('a session with five rows remains visible but cannot pass the 13-row gate', () => {
  const result = adaptQuoteComparisonProductionFacts(productionFacts(5))
  assert.equal(result.contractAligned, true)
  assert.equal(result.productionDataConsistent, false)
})

test('canary facts cannot satisfy the production contract', () => {
  const result = adaptQuoteComparisonProductionFacts({
    ...productionFacts(13), source: 'canary', dataMode: 'canary_acceptance',
  })
  assert.equal(result.contractAligned, false)
  assert.equal(result.productionDataConsistent, false)
})
