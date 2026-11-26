import { writeAuditLog } from './auditEngine.js'
import { startNodeTimer, stopNodeTimer } from './timerEngine.js'
import { WorkflowSchema } from '../schema/core/workflowSchema.js'
import { buildWorkflowGraph, markWorkflowGraph } from '../bpm/workflowVisualizer.js'

const workflowListeners = new Set()
const runtime = {
  workflow: null,
  schema: null,
  version: 0,
  updatedAt: Date.now(),
}

function normalizeWorkflow(schema = {}) {
  const workflow = schema.workflow || {}

  if (workflow.states && workflow.transitions && workflow.actions) {
    return {
      ...WorkflowSchema,
      ...workflow,
      stateField: workflow.stateField || workflow.statusField || WorkflowSchema.stateField,
    }
  }

  if (schema?.api?.module === WorkflowSchema.entity || schema?.name === WorkflowSchema.entity) {
    return WorkflowSchema
  }

  return {
    ...WorkflowSchema,
    ...workflow,
    stateField: workflow.stateField || workflow.statusField || WorkflowSchema.stateField,
  }
}

function resolveCurrentState(workflow, record = {}) {
  const field = workflow.stateField || workflow.statusField || 'workflow_state'
  return record?.[field] || record?.workflowState || record?.state || workflow.states?.[0] || 'DRAFT'
}

function normalizeAction(action) {
  if (typeof action === 'string') return action
  return action?.workflowAction || action?.key || action?.action || action?.event
}

export function evaluate(schema = {}, record = {}) {
  const workflow = normalizeWorkflow(schema)
  const currentState = resolveCurrentState(workflow, record)
  const availableTransitions = (workflow.transitions || [])
    .filter((transition) => transition.from === currentState)
  const blockedTransitions = (workflow.transitions || [])
    .filter((transition) => transition.from !== currentState)
  const nextStates = availableTransitions.map((transition) => transition.to)
  const availableActions = Object.entries(workflow.actions || {})
    .filter(([, states]) => states.includes(currentState))
    .map(([action]) => action)
  const allActions = Object.keys(workflow.actions || {})
  const blockedActions = allActions.filter((action) => !availableActions.includes(action))
  const uiGraph = markWorkflowGraph(buildWorkflowGraph(workflow), currentState, availableTransitions)

  return {
    entity: workflow.entity,
    currentState,
    currentNode: uiGraph.nodes.find((node) => node.id === currentState) || null,
    availableActions,
    nextStates,
    nextPossibleStates: nextStates,
    blockedActions,
    availableTransitions,
    blockedTransitions,
    uiGraph,
    isActionAllowed(action) {
      const normalized = normalizeAction(action)
      return !allActions.includes(normalized) || availableActions.includes(normalized)
    },
  }
}

export function syncWorkflow(schema = {}, record = {}) {
  runtime.schema = schema
  runtime.workflow = evaluate(schema, record)
  runtime.version += 1
  runtime.updatedAt = Date.now()

  workflowListeners.forEach((listener) => listener(getWorkflowRuntime()))

  return getWorkflowRuntime()
}

export function getWorkflowRuntime() {
  return {
    ...runtime,
  }
}

export function subscribeWorkflowChanges(listener) {
  workflowListeners.add(listener)
  listener(getWorkflowRuntime())

  return () => workflowListeners.delete(listener)
}

export function runWorkflow({ action, row, meta, user }) {
  const workflow = meta?.workflow
  if (!workflow) return row

  if (workflow.nodes && workflow.edges) {
    return executeBPM(workflow, row, user)
  }

  return executeRuleMode(workflow, action, row, user)
}

function executeBPM(workflow, row, user) {
  const stateField = workflow.statusField || workflow.stateField || 'status'
  const currentState = row[stateField]
  const node = findNode(workflow, currentState)
  if (!node) return row

  const edges = findEdges(workflow, node.id)
  const nextEdge = edges.find((edge) => checkCondition(edge.condition, row))

  if (!nextEdge) {
    console.warn('[BPM] no valid edge')
    return row
  }

  const nextNode = findNodeById(workflow, nextEdge.to)
  if (!nextNode) return row

  const fromState = currentState
  const toState = nextNode.id

  row[stateField] = toState
  stopNodeTimer(row.id)

  if (nextNode?.sla) {
    startNodeTimer(row.id, nextNode)
  }

  writeAuditLog({
    orderId: row.id,
    action: 'bpm_transition',
    from: fromState,
    to: toState,
    user: user?.id || 'system',
    role: user?.role || 'system',
    time: new Date().toISOString(),
  })

  console.log('[BPM]', fromState, '->', toState)
  return row
}

function executeRuleMode(workflow, action, row, user) {
  const stateField = workflow.statusField || workflow.stateField || 'status'
  const currentState = row[stateField]
  const node = findNode(workflow, currentState)
  if (!node) return row

  const act = (node.actions || []).find((item) => item.action === action)
  if (!act) return row
  if (!checkCondition(act, row, user)) return row

  return executeAction(act, row, workflow, node, user)
}

function findNode(workflow, state) {
  return (workflow.nodes || []).find((node) => node.id === state || node.state === state)
}

function findNodeById(workflow, id) {
  return (workflow.nodes || []).find((node) => node.id === id)
}

function findEdges(workflow, fromId) {
  return (workflow.edges || []).filter((edge) => edge.from === fromId)
}

function checkCondition(condition, row) {
  if (!condition) return true

  const val = row[condition.field]

  switch (condition.op) {
    case '>':
      return val > condition.value
    case '<':
      return val < condition.value
    case '>=':
      return val >= condition.value
    case '<=':
      return val <= condition.value
    case '==':
      return val == condition.value
    case '!=':
      return val != condition.value
    default:
      return true
  }
}

function executeAction(action, row, workflow, node, user = {}) {
  const field = workflow.statusField || workflow.stateField || 'status'
  const fromState = row[field]
  let toState = fromState

  if (action.type === 'state') {
    toState = action.target
    row[field] = toState
    stopNodeTimer(row.id)

    const nextNode = findNode(workflow, toState)
    if (nextNode?.sla) {
      startNodeTimer(row.id, nextNode)
    }
  }

  if (action.type === 'api') {
    console.log('[workflow api]', action.api)
  }

  if (action.type === 'log') {
    console.log('[workflow log]', action.message)
  }

  writeAuditLog({
    orderId: row.id,
    action: action.action,
    from: fromState,
    to: toState,
    user: user.id || 'anonymous',
    role: user.role || 'unknown',
    time: new Date().toISOString(),
  })

  return row
}
