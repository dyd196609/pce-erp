import { stableBusinessActionGateHash } from '../action-gate/businessActionGateIntegrity.js'

export const cloneBusinessActionTransactionValue = (value) => JSON.parse(JSON.stringify(value ?? null))

export function stableBusinessActionTransactionHash(value) {
  return stableBusinessActionGateHash(value)
}

export function buildBusinessActionTransactionIntegrityPayload(result = {}) {
  const {
    transactionResultHash, resultSource, infrastructureMetadata, recoveryAttemptCount,
    runnerPath, screenshotPath, tracePath, artifactClassification, displayText, ...payload
  } = result
  return payload
}

export function sealBusinessActionTransactionResult(result = {}) {
  const payload = buildBusinessActionTransactionIntegrityPayload(result)
  return { ...result, transactionResultHash: stableBusinessActionTransactionHash(payload) }
}

export function validateBusinessActionTransactionIntegrity(result = {}) {
  const expectedTransactionResultHash = stableBusinessActionTransactionHash(buildBusinessActionTransactionIntegrityPayload(result))
  const integrityValid = Boolean(result.transactionResultHash) && result.transactionResultHash === expectedTransactionResultHash
  return {
    integrityValid, expectedTransactionResultHash, actualTransactionResultHash: result.transactionResultHash || '',
    errorCode: integrityValid ? '' : 'BUSINESS_ACTION_TRANSACTION_INTEGRITY_FAILED',
  }
}
