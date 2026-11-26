import { defineProcess } from '../process/processDefinitionEngine.js'
import { runWorkflow } from '../process/workflowStateEngine.js'
import { trackTaskExecution } from '../process/taskEngine.js'
import { visualizeProcessHistory } from '../process/executionTimelineEngine.js'
import { runEndToEndProcessExecution } from './processExecutionEngine.js'

function normalizeProcess(process = 'purchase') {
  return typeof process === 'string' ? defineProcess(process) : process
}

export function executeWorkflow(process = 'purchase') {
  const normalized = normalizeProcess(process)
  return runWorkflow(normalized.type, normalized.transitions.map((transition) => transition.action))
}

export function executeTasks(process = 'purchase') {
  const normalized = normalizeProcess(process)
  return trackTaskExecution(normalized.type, normalized.steps)
}

export function updateState(process = 'purchase') {
  const workflow = executeWorkflow(process)

  return {
    currentState: workflow.currentState,
    consistent: workflow.consistency.consistent,
    rollbackProtection: workflow.rollbackProtection,
    dataState: workflow.blocked ? 'NOT_COMMITTED' : 'COMMITTED',
  }
}

export function recordTimeline(process = 'purchase') {
  const normalized = normalizeProcess(process)
  return visualizeProcessHistory(
    normalized.type,
    normalized.transitions.map((transition) => transition.action)
  )
}

export function runExecutionLoop(process = 'purchase') {
  const normalized = normalizeProcess(process)
  const execution = runEndToEndProcessExecution(normalized)

  return {
    mode: 'ENTERPRISE_EXECUTION_CLOSED_LOOP',
    executionLoop: 'ACTIVE',
    closedLoopMode: 'ON',
    processExecution: 'ENABLED',
    workflow: execution.workflow,
    tasks: execution.tasks,
    state: updateState(normalized),
    timeline: execution.timeline,
    persistence: execution.persistence,
    execution,
    completed: execution.completed,
    dataLanded: execution.persistence.dataLanded,
    breakpoints: execution.completed ? [] : ['EXECUTION_BLOCKED'],
  }
}
