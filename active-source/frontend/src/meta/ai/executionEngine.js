import { evaluateDecision } from './decisionEngine.js'
import { runReviewControlLoop } from '../review/reviewControlEngine.js'
import { canPerformAction } from '../runtime/permissionEngine.js'
import { stateManager } from '../runtime/stateManager.js'

const executionHistory = []
let lastStatus = {
  status: 'IDLE',
  updatedAt: Date.now(),
}

const supportedActions = [
  'APPROVE',
  'REJECT',
  'SUBMIT',
  'CLOSE',
  'AUTO_UPDATE_STATE',
  'AUTO_MOVE_WORKFLOW',
]

function getWorkflowAction(context = {}) {
  return String(context.action || context.workflowAction || context.decision?.recommendation || '').toUpperCase()
}

function getStateField(schema = {}) {
  return schema.workflow?.stateField || 'workflow_state'
}

function getTransitions(schema = {}) {
  return schema.workflow?.transitions || []
}

function resolveNextState(context = {}) {
  const schema = context.schema || {}
  const record = context.record || {}
  const field = getStateField(schema)
  const current = record[field] || schema.workflow?.states?.[0] || 'DRAFT'
  const action = getWorkflowAction(context)
  const transitions = getTransitions(schema)
  const explicitTransition = transitions.find((transition) => transition.from === current)

  if (action === 'REJECT') return 'REJECTED'
  if (action === 'CLOSE') return 'CLOSED'
  if (context.nextState) return context.nextState

  return explicitTransition?.to || current
}

function buildLog(entry) {
  return {
    timestamp: Date.now(),
    ...entry,
  }
}

function saveHistory(entry) {
  const log = buildLog(entry)
  executionHistory.push(log)
  lastStatus = {
    status: log.status,
    updatedAt: log.timestamp,
    last: log,
  }
  return log
}

export function validateExecution(decisionContext = {}) {
  const runtimeState = decisionContext.runtimeState || stateManager.snapshot()
  const review = runReviewControlLoop(decisionContext.schema || {})
  const decision = decisionContext.decision || evaluateDecision(decisionContext)
  const roleAllowed = canPerformAction(runtimeState.role, 'EXECUTE')
  const riskLevel = decision.risk?.level || 'HIGH'
  const blocked = review.controlMode === 'BLOCKED'
  const restricted = review.controlMode === 'RESTRICTED'
  const manualConfirmed = decisionContext.manualConfirm === true

  if (blocked) {
    return {
      allowed: false,
      status: 'BLOCKED',
      reason: 'BLOCKED state cannot execute',
      review,
      decision,
    }
  }

  if (!roleAllowed) {
    return {
      allowed: false,
      status: 'BLOCKED',
      reason: 'permissionEngine denied EXECUTE',
      review,
      decision,
    }
  }

  if (restricted && !manualConfirmed) {
    return {
      allowed: false,
      status: 'MANUAL_CONFIRM_REQUIRED',
      reason: 'RESTRICTED state requires manual confirmation',
      review,
      decision,
    }
  }

  if (riskLevel !== 'LOW' && !manualConfirmed) {
    return {
      allowed: false,
      status: 'MANUAL_CONFIRM_REQUIRED',
      reason: `${riskLevel} risk requires manual confirmation`,
      review,
      decision,
    }
  }

  return {
    allowed: true,
    status: manualConfirmed ? 'MANUAL_EXECUTION_ALLOWED' : 'AUTO_EXECUTION_ALLOWED',
    reason: riskLevel === 'LOW' ? 'LOW risk execution allowed' : 'manual confirmation accepted',
    review,
    decision,
  }
}

export function resolveActions(decisionContext = {}) {
  const action = getWorkflowAction(decisionContext)
  const nextState = resolveNextState(decisionContext)
  const actions = []

  if (['APPROVE', 'REJECT', 'SUBMIT', 'CLOSE'].includes(action)) {
    actions.push({
      type: action,
      target: decisionContext.schema?.name || decisionContext.schema?.api?.module || 'module',
    })
  }

  actions.push({
    type: 'AUTO_MOVE_WORKFLOW',
    from: decisionContext.record?.[getStateField(decisionContext.schema)] || decisionContext.schema?.workflow?.states?.[0] || 'DRAFT',
    to: nextState,
  })

  actions.push({
    type: 'AUTO_UPDATE_STATE',
    field: getStateField(decisionContext.schema),
    value: nextState,
  })

  return actions
}

export function runActions(actions = [], context = {}) {
  const record = context.record || {}
  const mutation = {}

  actions.forEach((action) => {
    if (action.type === 'AUTO_UPDATE_STATE') {
      record[action.field] = action.value
      mutation[action.field] = action.value
    }
  })

  return {
    status: 'EXECUTED',
    mutation,
    record,
    actionsRun: actions.map((action) => action.type),
    parallel: actions.length > 1,
  }
}

export function executeDecision(decisionContext = {}) {
  const validated = validateExecution(decisionContext)

  if (!validated.allowed) {
    const blocked = {
      status: validated.status,
      executed: false,
      reason: validated.reason,
      decision: validated.decision,
      review: validated.review,
    }

    saveHistory(blocked)
    return blocked
  }

  const actions = resolveActions({
    ...decisionContext,
    decision: validated.decision,
  })
  const result = runActions(actions, decisionContext)
  const executed = {
    status: 'EXECUTED',
    executed: true,
    mode: validated.status,
    actions,
    result,
    decision: validated.decision,
    review: validated.review,
  }

  saveHistory(executed)
  return executed
}

export function getSupportedExecutionActions() {
  return supportedActions
}

export function getExecutionHistory() {
  return executionHistory
}

export function getExecutionStatus() {
  return lastStatus
}

export function clearExecutionHistory() {
  executionHistory.length = 0
  lastStatus = {
    status: 'IDLE',
    updatedAt: Date.now(),
  }
}
