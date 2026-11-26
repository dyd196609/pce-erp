export const businessActionTransactionStates = [
  'not_created', 'transaction_precheck_pending', 'transaction_blocked', 'transaction_ready',
  'lock_pending', 'lock_acquired', 'transaction_staging', 'commit_pending', 'commit_unknown',
  'committed', 'rollback_pending', 'rolled_back', 'rollback_failed', 'transaction_failed',
]

export const businessActionTransactionTerminalStates = [
  'transaction_blocked', 'committed', 'rolled_back', 'rollback_failed', 'transaction_failed',
]

export const businessActionTransactionStepStatuses = [
  'not_started', 'running', 'succeeded', 'blocked', 'failed', 'compensated',
  'compensation_failed', 'not_applicable',
]

export const businessActionIdempotencyStates = [
  'not_found', 'in_progress', 'committed', 'failed_retryable', 'failed_terminal', 'commit_unknown',
]

export const businessActionRecoveryClassifications = [
  'committed', 'not_committed_safe_to_retry', 'partial_commit_requires_intervention',
  'conflict', 'integrity_failed',
]

export const businessActionTransactionTransitions = Object.freeze({
  not_created: ['transaction_precheck_pending'],
  transaction_precheck_pending: ['transaction_blocked', 'transaction_ready'],
  transaction_ready: ['lock_pending'],
  lock_pending: ['lock_acquired', 'transaction_failed'],
  lock_acquired: ['transaction_staging'],
  transaction_staging: ['commit_pending', 'rollback_pending', 'transaction_failed'],
  commit_pending: ['committed', 'commit_unknown', 'rollback_pending'],
  rollback_pending: ['rolled_back', 'rollback_failed'],
})

export function isBusinessActionTransactionTerminal(state) {
  return businessActionTransactionTerminalStates.includes(state)
}

export function transitionBusinessActionTransactionState(currentState, nextState) {
  const allowed = businessActionTransactionTransitions[currentState] || []
  return allowed.includes(nextState)
    ? { allowed: true, currentState: nextState, errorCode: '' }
    : { allowed: false, currentState, errorCode: 'BUSINESS_ACTION_TRANSACTION_INVALID_TRANSITION' }
}
