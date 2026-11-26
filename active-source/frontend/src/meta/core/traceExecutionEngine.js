import { analyzePatch } from './tracePatchEngine.js'

let executionLog = []

function buildExecutionQueue(patches) {
  return patches.map((patch) => ({
    ...patch,
    state: 'READY',
  }))
}

function simulateExecution(patch) {
  return {
    ...patch,
    state: 'SIMULATED',
    result: 'NO_SIDE_EFFECT',
  }
}

function approvePatch(patch) {
  return {
    ...patch,
    state: 'APPROVED',
  }
}

function executePatch(patch) {
  return {
    ...patch,
    state: 'EXECUTED',
    result: 'APPLIED',
  }
}

function rollback(patch) {
  return {
    ...patch,
    state: 'ROLLBACK',
    result: 'REVERTED',
  }
}

export function runExecutionCycle() {
  const patchData = analyzePatch()
  const queue = buildExecutionQueue(patchData.patches)
  const simulated = queue.map(simulateExecution)

  executionLog = simulated

  return {
    mode: 'HUMAN_APPROVAL_REQUIRED',
    queue,
    simulated,
    executionLog,
  }
}

export function approveAndExecute(index) {
  const patch = executionLog[index]

  if (!patch) {
    return {
      success: false,
      error: 'PATCH_NOT_FOUND',
    }
  }

  const approved = approvePatch(patch)
  const executed = executePatch(approved)

  executionLog[index] = executed

  return {
    success: true,
    executed,
  }
}

export function rollbackExecution(index) {
  const patch = executionLog[index]

  if (!patch) {
    return {
      success: false,
      error: 'PATCH_NOT_FOUND',
    }
  }

  const rolled = rollback(patch)

  executionLog[index] = rolled

  return rolled
}

export function getExecutionLog() {
  return executionLog
}
