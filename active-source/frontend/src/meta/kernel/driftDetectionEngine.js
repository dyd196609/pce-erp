import { getStructureState } from './structureMutationEngine.js'

export function detectStructuralDrift() {
  const state = getStructureState()

  const drift = {
    agentDrift: state.agents.length > 5,
    ruleDrift: state.rules.length > 3,
  }

  return {
    driftLevel: (drift.agentDrift ? 1 : 0) + (drift.ruleDrift ? 1 : 0),
    drift,
    state,
  }
}
