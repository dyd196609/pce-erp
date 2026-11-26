import { defineProcess } from '../process/processDefinitionEngine.js'
import { runWorkflow } from '../process/workflowStateEngine.js'
import { trackTaskExecution } from '../process/taskEngine.js'
import { buildProcessRoutingMap } from '../process/processRouterEngine.js'
import { visualizeProcessHistory } from '../process/executionTimelineEngine.js'

const processExecutionLedger = []

function actionsForProcess(process = defineProcess('purchase')) {
  return process.transitions.map((transition) => transition.action)
}

function persistExecution(process = {}, execution = {}) {
  const record = {
    id: `${process.type || 'purchase'}:execution:${processExecutionLedger.length + 1}`,
    processType: process.type || 'purchase',
    finalState: execution.workflow.currentState,
    status: execution.completed ? 'COMMITTED' : 'BLOCKED',
    dataLanded: execution.completed,
    committedAt: new Date().toISOString(),
  }

  processExecutionLedger.unshift(record)
  return record
}

export function runEndToEndProcessExecution(processInput = 'purchase', context = {}) {
  const process = typeof processInput === 'string'
    ? defineProcess(processInput)
    : processInput
  const actions = context.actions || actionsForProcess(process)
  const workflow = runWorkflow(process.type, actions)
  const tasks = trackTaskExecution(process.type, process.steps)
  const routing = buildProcessRoutingMap(process.type)
  const timeline = visualizeProcessHistory(process.type, actions)
  const completed = !workflow.blocked
    && workflow.consistency.consistent
    && tasks.every((item) => item.validation.valid)
    && timeline.timeline.every((item) => item.status === 'COMPLETED')
  const execution = {
    process,
    workflow,
    tasks,
    routing,
    timeline,
    completed,
    crossModuleExecution: {
      supported: true,
      modules: ['purchase', 'finance', 'warehouse'],
      status: completed ? 'SYNCED' : 'BLOCKED',
    },
    transaction: {
      safe: completed,
      mode: 'TRANSACTION_SAFE_EXECUTION',
      rollbackProtection: workflow.rollbackProtection,
    },
  }

  return {
    ...execution,
    persistence: persistExecution(process, execution),
  }
}

export function getProcessExecutionLedger() {
  return [...processExecutionLedger]
}
