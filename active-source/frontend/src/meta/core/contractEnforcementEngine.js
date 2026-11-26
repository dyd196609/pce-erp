import { calculateDriftScore } from './contractDriftEngine.js'

export function enforceContractRules() {
  const drift = calculateDriftScore()

  const status = {
    level: 'SAFE',
  }

  if (drift.driftScore > 0.3) {
    status.level = 'WARNING'
  }

  if (drift.driftScore > 0.6) {
    status.level = 'CRITICAL'
  }

  if (drift.driftScore > 0.8) {
    status.level = 'BLOCK'
  }

  return {
    drift,
    status,
  }
}
