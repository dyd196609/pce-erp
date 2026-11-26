import { runExecutionCycle } from './traceExecutionEngine.js'

export function runShadowExecution(patchSet = {}) {
  const beforeState = patchSet.systemSnapshot || {}
  const before = JSON.stringify(beforeState)
  const simulated = runExecutionCycle()
  const futureState = {
    ...beforeState,
    execution: {
      mode: simulated.mode,
      count: simulated.simulated?.length || 0,
      patches: simulated.simulated || [],
    },
  }
  const after = JSON.stringify(futureState)

  return {
    mode: 'SHADOW_EXECUTION',
    before,
    after,
    simulated: {
      ...simulated,
      futureState,
    },
    timestamp: Date.now(),
  }
}
