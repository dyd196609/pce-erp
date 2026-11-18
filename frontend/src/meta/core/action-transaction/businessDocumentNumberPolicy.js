import { stableBusinessActionTransactionHash } from './businessActionTransactionIntegrity.js'

export const BUSINESS_DOCUMENT_NUMBER_POLICY_VERSION = 'business-document-number-policy-v1'

export function buildBusinessDocumentNumberReservationPlan({ documentType, legalEntityId, ledgerBookId, accountingPeriod, sequenceScope, idempotencyKey } = {}) {
  const numberScope = { documentType, legalEntityId, ledgerBookId, accountingPeriod, sequenceScope }
  const numberReservationKey = `BNR-${stableBusinessActionTransactionHash({ numberScope, idempotencyKey })}`
  return {
    numberPolicyVersion: BUSINESS_DOCUMENT_NUMBER_POLICY_VERSION,
    numberScope,
    numberReservationKey,
    allocationTiming: 'after_lock_recheck_and_idempotency',
    failedNumberReusable: false,
    sameIdempotencyReusesReservation: true,
    formalNumberAllocated: false,
    formalNumberAllocationCount: 0,
    simulatedReservationResult: `SIM-PRC-NUM-${numberReservationKey.slice(-8)}`,
  }
}

export function validateBusinessDocumentNumberReservation(plan = {}) {
  return {
    valid: Boolean(plan.numberReservationKey) && String(plan.simulatedReservationResult || '').startsWith('SIM-PRC-NUM-')
      && plan.formalNumberAllocated === false && Number(plan.formalNumberAllocationCount || 0) === 0,
    formalFormatAccepted: false,
    errorCode: String(plan.simulatedReservationResult || '').startsWith('SIM-PRC-NUM-') ? '' : 'BUSINESS_DOCUMENT_SIMULATED_NUMBER_PREFIX_REQUIRED',
  }
}
