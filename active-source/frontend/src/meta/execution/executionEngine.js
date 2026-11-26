import { validateRisk } from './riskGate.js'
import { runWorkflowAutopilot } from './workflowAutopilot.js'
import { runFinancialExecutor, getFinancialExecutionRecords } from './financialExecutor.js'
import { getCrossModuleExecutionGraph, runCrossModuleExecution } from './crossModuleExecutor.js'

const executionHistory = []
const executedPlans = new Set()
const maxHistory = 100

function planKey(actionPlan = {}, context = {}) {
  return context.event?.id || `${actionPlan.eventType || 'plan'}-${actionPlan.createdAt || Date.now()}`
}

function runActions(actionPlan = {}, context = {}) {
  const steps = actionPlan.steps || []

  return {
    status: steps.length ? 'EXECUTED' : 'NO_ACTION',
    actions: steps.map((step, index) => ({
      ...step,
      order: index + 1,
      executionStatus: 'DONE',
      executedAt: Date.now(),
    })),
  }
}

function updateBusinessState(actionPlan = {}, context = {}) {
  const workflow = runWorkflowAutopilot(actionPlan, context)
  const financial = runFinancialExecutor(actionPlan, context)

  return {
    workflow,
    financial,
    updatedAt: Date.now(),
  }
}

function emitNextEvents(actionPlan = {}, context = {}) {
  return runCrossModuleExecution(actionPlan, context)
}

function remember(entry = {}) {
  executionHistory.unshift(entry)
  if (executionHistory.length > maxHistory) {
    executionHistory.length = maxHistory
  }
  return entry
}

export function executeActionPlan(actionPlan = {}, context = {}) {
  const key = planKey(actionPlan, context)
  if (executedPlans.has(key)) {
    return executionHistory.find((item) => item.planKey === key) || { status: 'SKIPPED', reason: 'duplicate_plan' }
  }

  const validated = validateRisk(actionPlan, context)
  if (!validated.safe) {
    executedPlans.add(key)
    return remember({
      planKey: key,
      status: 'BLOCKED',
      validated,
      actionPlan,
      context,
      timestamp: Date.now(),
    })
  }

  const executionResult = runActions(actionPlan, context)
  const stateUpdates = updateBusinessState(actionPlan, context)
  const triggers = emitNextEvents(actionPlan, context)

  executedPlans.add(key)
  return remember({
    planKey: key,
    status: 'EXECUTED',
    validated,
    executionResult,
    stateUpdates,
    triggers,
    actionPlan,
    context,
    timestamp: Date.now(),
  })
}

export function getExecutionLayerSnapshot() {
  const total = executionHistory.length || 1
  const executed = executionHistory.filter((item) => item.status === 'EXECUTED').length
  const blocked = executionHistory.filter((item) => item.status === 'BLOCKED').length
  const financialRecords = getFinancialExecutionRecords()

  return {
    executionMode: 'ACTIVE',
    autopilotExecution: 'ON',
    businessExecutionLayer: 'ENABLED',
    latest: executionHistory[0] || null,
    history: [...executionHistory],
    financialRecords,
    crossModuleExecutionGraph: getCrossModuleExecutionGraph(),
    metrics: {
      executionSuccessRate: Math.round((executed / total) * 100),
      autopilotEfficiencyIndex: Math.max(0, Math.round(100 - blocked * 6)),
      financialAutomationScore: financialRecords.length ? 100 : 75,
      crossModuleExecutionCount: getCrossModuleExecutionGraph().length,
    },
  }
}
