import { analyzeActions } from './traceActionEngine.js'
import { analyzeIntelligence } from './traceIntelligence.js'

function buildExecutionPlans(actions) {
  const plans = []

  for (const action of actions.actions || []) {
    if (action.type === 'performance') {
      plans.push({
        type: 'performance_patch',
        target: action.target,
        plan: [
          'Step 1: Identify heavy computation or API call',
          'Step 2: Add caching or memoization layer',
          'Step 3: Reduce schema field complexity if applicable',
          'Step 4: Validate improvement via trace cost comparison',
        ],
        risk: 'medium',
        autoApplicable: false,
      })
    }

    if (action.type === 'error') {
      plans.push({
        type: 'schema_fix',
        plan: [
          'Step 1: Check missing schema fields',
          'Step 2: Validate api.module existence',
          'Step 3: Add fallback schema in schemaContract',
          'Step 4: Re-run validation trace',
        ],
        risk: 'high',
        autoApplicable: false,
      })
    }

    if (action.type === 'system') {
      plans.push({
        type: 'architecture_fix',
        plan: [
          'Step 1: Split large schema modules',
          'Step 2: Reduce nested UI structure',
          'Step 3: Decouple API aggregation layer',
          'Step 4: Re-run full trace validation',
        ],
        risk: 'critical',
        autoApplicable: false,
      })
    }
  }

  return plans
}

export function analyzeExecutionPlans() {
  try {
    const intel = analyzeIntelligence()
    const actions = analyzeActions()

    return {
      health: intel.health,
      bottlenecks: intel.bottlenecks,
      actions: actions.actions,
      executionPlans: buildExecutionPlans(actions),
    }
  } catch (error) {
    return {
      health: 0,
      bottlenecks: [],
      actions: [],
      executionPlans: [
        {
          type: 'planner_error',
          plan: [`Step 1: Inspect trace planner error: ${error?.message || String(error)}`],
          risk: 'high',
          autoApplicable: false,
        },
      ],
    }
  }
}
