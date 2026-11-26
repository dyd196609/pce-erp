import { runContinuousExecution, getContinuousExecutionSnapshot } from './continuousExecutionEngine.js'
import { runFullWorkflow } from './selfRunningWorkflowEngine.js'

const runtimeHistory = []

export function runInfiniteBusinessLoop(context = {}) {
  const continuous = runContinuousExecution({
    ...context,
    maxCycles: context.maxCycles || 5,
  })
  const workflow = runFullWorkflow(context)
  const result = {
    mode: 'V30_CONTINUOUS_RUNTIME_ENGINE',
    infiniteBusinessLoop: 'ACTIVE',
    autoWorkflowProgression: 'ENABLED',
    continuousExecution: 'ENABLED',
    continuous,
    workflow,
    timestamp: Date.now(),
  }

  runtimeHistory.unshift(result)
  if (runtimeHistory.length > 100) runtimeHistory.length = 100

  return result
}

export function runContinuousRuntime(context = {}) {
  return runInfiniteBusinessLoop(context)
}

export function getContinuousRuntimeSnapshot() {
  return {
    continuousRuntime: 'ENABLED',
    latest: runtimeHistory[0] || null,
    history: [...runtimeHistory],
    execution: getContinuousExecutionSnapshot(),
    metrics: {
      loopCount: runtimeHistory.length,
      workflowAutopilotRate: runtimeHistory[0]?.workflow?.metrics?.workflowAutopilotRate ?? 1,
      continuousExecutionRate: getContinuousExecutionSnapshot().metrics.continuousExecutionRate,
    },
  }
}

