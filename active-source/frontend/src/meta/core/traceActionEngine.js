import { analyzeIntelligence } from './traceIntelligence.js'

function buildActions(intel) {
  const actions = []

  intel.bottlenecks.forEach((bottleneck) => {
    if (bottleneck.avgCost > 500) {
      actions.push({
        type: 'performance',
        target: bottleneck.step,
        severity: 'high',
        suggestion: ['Add cache layer', 'Split heavy API or schema', 'Reduce field complexity'],
      })
    } else if (bottleneck.avgCost > 200) {
      actions.push({
        type: 'performance',
        target: bottleneck.step,
        severity: 'medium',
        suggestion: ['Optimize query shape', 'Reduce unnecessary fields'],
      })
    }
  })

  if (intel.errors.length > 0) {
    actions.push({
      type: 'error',
      severity: 'high',
      suggestion: ['Check required schema fields', 'Check api.module', 'Review schema contract handling'],
    })
  }

  if (intel.health < 60) {
    actions.push({
      type: 'system',
      severity: 'critical',
      suggestion: ['Reduce system load', 'Split large modules', 'Reduce schema nesting'],
    })
  }

  return actions
}

export function analyzeActions() {
  try {
    const intel = analyzeIntelligence()

    return {
      health: intel.health,
      bottlenecks: intel.bottlenecks,
      actions: buildActions(intel),
    }
  } catch (error) {
    return {
      health: 0,
      bottlenecks: [],
      actions: [
        {
          type: 'trace',
          severity: 'high',
          suggestion: [`Trace action analysis failed: ${error?.message || String(error)}`],
        },
      ],
    }
  }
}