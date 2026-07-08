import { analyzeExecutionPlans } from './traceExecutionPlanner.js'

function createPatch(plan) {
  const patches = []

  for (const p of plan.executionPlans || []) {
    if (p.type === 'performance_patch') {
      patches.push({
        target: p.target,
        type: 'CODE_OPTIMIZATION',
        diff: [
          '// OPTIMIZATION SUGGESTION',
          '// Add caching layer or memoization',
          '// Reduce API payload size',
          '// Split heavy schema fields',
        ],
      })
    }

    if (p.type === 'schema_fix') {
      patches.push({
        target: 'schema',
        type: 'SCHEMA_PATCH',
        diff: [
          '// SCHEMA FIX',
          'ensure api.module exists',
          'add fallback schema guard in schemaContract',
          'normalize missing ui.columns',
        ],
      })
    }

    if (p.type === 'architecture_fix') {
      patches.push({
        target: 'architecture',
        type: 'ARCH_REFACTOR',
        diff: [
          '// ARCHITECTURE FIX',
          'split large schema modules',
          'decouple API aggregation layer',
          'reduce nested UI rendering depth',
        ],
      })
    }
  }

  return patches
}

export function analyzePatch() {
  try {
    const plan = analyzeExecutionPlans()

    return {
      health: plan.health,
      executionPlans: plan.executionPlans,
      patches: createPatch(plan),
      mode: 'SUGGEST_ONLY',
    }
  } catch (error) {
    return {
      health: 0,
      executionPlans: [],
      patches: [
        {
          target: 'tracePatchEngine',
          type: 'PATCH_ANALYSIS_ERROR',
          diff: [`// Patch analysis failed: ${error?.message || String(error)}`],
        },
      ],
      mode: 'SUGGEST_ONLY',
    }
  }
}
