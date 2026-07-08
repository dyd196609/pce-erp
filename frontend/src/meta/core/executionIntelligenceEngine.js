import { diffExecution } from './executionDiffEngine.js'
import { runShadowExecution } from './shadowExecutionEngine.js'

function detectAnomalies(diff) {
  const flags = []

  if (diff.removed.length > 5) {
    flags.push('LARGE_REMOVAL')
  }

  if (diff.added.length > 20) {
    flags.push('LARGE_INSERTION')
  }

  if (diff.modified.length > 10) {
    flags.push('HEAVY_MODIFICATION')
  }

  return {
    risky: flags.length > 0,
    flags,
  }
}

export function runExecutionIntelligence(patchSet = {}) {
  const shadow = runShadowExecution(patchSet)
  const diff = diffExecution(JSON.parse(shadow.before), JSON.parse(shadow.after))
  const anomaly = detectAnomalies(diff)

  return {
    mode: 'V6.2_INTELLIGENCE',
    shadow,
    diff,
    anomaly,
    decision: anomaly.risky ? 'BLOCK_OR_REVIEW' : 'SAFE_TO_PROCEED',
  }
}
