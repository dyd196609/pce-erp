export const PCE_STATE_MACHINE_FACT_CONTRACT_VERSION = 'V1.14.2.8.4.7.55'

export class PceStateMachineFactContractError extends Error {
  constructor(message, surface) {
    super(`${surface}: ${message}`)
    this.name = 'PceStateMachineFactContractError'
    this.surface = surface
  }
}

export function assertStatusTransitionCountMatchesHistory(
  facts,
  surface = 'state-machine-facts',
) {
  if (!facts || typeof facts !== 'object') {
    throw new PceStateMachineFactContractError(
      'server facts are required',
      surface,
    )
  }
  if (!Array.isArray(facts.statusTransitionHistory)) {
    throw new PceStateMachineFactContractError(
      'statusTransitionHistory must be a server-derived array',
      surface,
    )
  }
  if (
    !Number.isInteger(facts.statusTransitionCount)
    || facts.statusTransitionCount < 0
  ) {
    throw new PceStateMachineFactContractError(
      'statusTransitionCount must be a non-negative server-derived integer',
      surface,
    )
  }
  if (
    facts.statusTransitionCount
    !== facts.statusTransitionHistory.length
  ) {
    throw new PceStateMachineFactContractError(
      'statusTransitionCount must equal statusTransitionHistory.length',
      surface,
    )
  }
  return facts
}

export function stateMachineFactsFromServer(
  facts,
  surface = 'state-machine-facts',
) {
  const verified = assertStatusTransitionCountMatchesHistory(facts, surface)
  return Object.freeze({
    statusTransitionHistory: verified.statusTransitionHistory,
    statusTransitionCount: verified.statusTransitionCount,
    stateMachineConsistent: verified.stateMachineConsistent === true,
  })
}
