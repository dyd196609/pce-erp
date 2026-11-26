import { analyzeRisk } from './traceRiskEngine.js'
import { approveAndExecute, runExecutionCycle } from './traceExecutionEngine.js'

function routeDecision(patch) {
  switch (patch.risk) {
    case 'LOW':
      return {
        action: 'AUTO_EXECUTE',
        reason: 'low risk auto approved',
        safe: true,
      }

    case 'MEDIUM':
      return {
        action: 'SUGGEST_EXECUTE',
        reason: 'manual confirmation required',
        safe: false,
      }

    case 'HIGH':
      return {
        action: 'BLOCK_TO_APPROVAL',
        reason: 'high risk requires human review',
        safe: false,
      }

    case 'CRITICAL':
      return {
        action: 'BLOCK',
        reason: 'critical risk - execution forbidden',
        safe: false,
      }

    default:
      return {
        action: 'BLOCK_TO_APPROVAL',
        reason: 'unknown risk requires human review',
        safe: false,
      }
  }
}

function executeIfAllowed(patch, index) {
  const decision = routeDecision(patch)

  if (decision.action === 'AUTO_EXECUTE') {
    return {
      status: 'AUTO_EXECUTED',
      decision,
      result: approveAndExecute(index),
    }
  }

  return {
    status: 'PENDING',
    decision,
    patch,
  }
}

export function runSafeExecution() {
  const risk = analyzeRisk()
  const cycle = runExecutionCycle()
  const simulated = cycle.simulated.map((patch, index) => ({
    ...patch,
    risk: risk.patches[index]?.risk || 'HIGH',
  }))
  const results = simulated.map((patch, index) => executeIfAllowed(patch, index))

  return {
    mode: 'SEMI_AUTONOMOUS',
    riskSummary: risk.summary,
    results,
    raw: {
      ...cycle,
      simulated,
    },
  }
}
