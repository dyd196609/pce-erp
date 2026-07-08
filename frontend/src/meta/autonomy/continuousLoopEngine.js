import { runContinuousExecution } from './continuousExecutionEngine.js'

export function runInfiniteERPLoop(context = {}) {
  const continuous = runContinuousExecution({
    ...context,
    maxCycles: context.maxCycles || 3,
  })

  return {
    infiniteERPLoop: 'CONTROLLED_ON',
    status: 'RUNNING',
    cycles: continuous.cycles,
    events: continuous.events,
  }
}

export function restartWorkflow(context = {}) {
  const execution = context.executionClosedLoop || context.execution || {}
  const needsRestart = execution.completed === false || (execution.breakpoints || []).length > 0

  return {
    autoWorkflowRestart: needsRestart ? 'RESTARTED' : 'NOT_REQUIRED',
    restartReason: needsRestart ? 'Execution breakpoint detected' : 'Workflow completed normally',
    targetState: needsRestart ? 'draft' : execution.workflow?.currentState || 'approved',
  }
}

export function runBusinessCycle(context = {}) {
  const loop = runInfiniteERPLoop(context)
  const restart = restartWorkflow(context)

  return {
    autoBusinessCycle: 'ACTIVE',
    loop,
    restart,
    cyclePolicy: 'CONTINUOUS_BUSINESS_OPERATION',
  }
}

export function continuousRun(context = {}) {
  return {
    continuousLoop: 'ON',
    infiniteERP: runInfiniteERPLoop(context),
    workflowRestart: restartWorkflow(context),
    businessCycle: runBusinessCycle(context),
  }
}
