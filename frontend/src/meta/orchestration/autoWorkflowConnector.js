import { emitEvent, getEventStream, subscribeEvent } from './eventBus.js'
import { runBusinessTriggers, getBusinessTriggerDashboard } from './businessTriggerEngine.js'
import { getDependencySummary } from './moduleDependencyGraph.js'
import { getCrossModuleState, syncCrossModuleState } from './crossModuleStateSync.js'
import { evaluateDecision, getIntelligenceSnapshot } from '../intelligence/decisionEngine.js'
import { executeActionPlan, getExecutionLayerSnapshot } from '../execution/executionEngine.js'

let connected = false
const connectorHistory = []
const maxDepth = 4

function moduleFromEventType(type = '') {
  const [module] = String(type).split('.')
  return module === 'purchaseOrder' ? 'purchase' : module
}

function targetFromTrigger(trigger = {}) {
  return trigger.targetModule || moduleFromEventType(trigger.action)
}

export function connectAutoWorkflows() {
  if (connected) return buildSnapshot()
  connected = true

  subscribeEvent('*', (event) => {
    if (event.depth > maxDepth) return
    const intelligence = evaluateDecision(event)
    if (String(event.type || '').endsWith('.executed') || event.payload?.executionEvent === true) {
      return
    }

    if (intelligence.decision?.action === 'BLOCK_AUTOMATION') {
      const execution = executeActionPlan(intelligence.actionPlan, {
        event,
        decision: intelligence.decision,
        risk: intelligence.risk,
      })
      connectorHistory.unshift({
        event: event.type,
        targetModule: 'review',
        action: 'blockedByIntelligence',
        intelligence,
        execution,
        timestamp: Date.now(),
      })
      return
    }

    const execution = executeActionPlan(intelligence.actionPlan, {
      event,
      decision: intelligence.decision,
      risk: intelligence.risk,
    })

    const triggers = runBusinessTriggers({
      ...event,
      payload: {
        ...(event.payload || {}),
        intelligence,
        execution,
      },
    })
    triggers.forEach((trigger) => {
      const sourceModule = moduleFromEventType(event.type)
      const targetModule = targetFromTrigger(trigger)
      const sync = syncCrossModuleState(sourceModule, targetModule, {
        ...trigger.payload,
        eventId: event.id,
      })
      connectorHistory.unshift({
        event: event.type,
        targetModule,
        action: trigger.action,
        sync,
        intelligence,
        execution,
        timestamp: Date.now(),
      })
    })
  })

  return buildSnapshot()
}

export function propagateStateTransition(module, action, record = {}, workflow = {}) {
  connectAutoWorkflows()
  const normalizedModule = module === 'purchaseOrder' ? 'purchase' : module
  const state = record.workflow_state || workflow.result?.record?.workflow_state
  const eventType = resolveEventType(normalizedModule, action, state, record)

  if (!eventType) return getOrchestrationSnapshot()

  emitEvent({
    type: eventType,
    source: normalizedModule,
    payload: {
      module: normalizedModule,
      action,
      state,
      record,
      workflow,
    },
  })

  return getOrchestrationSnapshot()
}

function resolveEventType(module, action, state, record = {}) {
  if (module === 'purchase' && (state === 'approved' || action === 'APPROVE')) return 'purchase.approved'
  if (module === 'crm' && (state === 'deal' || action === 'CLOSE_DEAL')) return 'crm.dealClosed'
  if (module === 'inventory' && Number(record.stockQuantity ?? 999999) <= Number(record.reorderLevel ?? -1)) return 'inventory.lowStock'
  if (module === 'scm' && (record.supplyStatus === 'Delay' || record.supplyStatus === 'Delayed' || action === 'DELAY')) return 'scm.delay'
  return null
}

export function getOrchestrationSnapshot() {
  connectAutoWorkflows()
  return buildSnapshot()
}

function buildSnapshot() {
  return {
    orchestrationMode: 'ON',
    eventBus: 'ACTIVE',
    crossModuleSync: 'ENABLED',
    dependencyGraph: getDependencySummary(),
    eventStream: getEventStream(),
    triggers: getBusinessTriggerDashboard(),
    stateSync: getCrossModuleState(),
    connectorHistory: [...connectorHistory],
    intelligence: getIntelligenceSnapshot(),
    execution: getExecutionLayerSnapshot(),
  }
}
