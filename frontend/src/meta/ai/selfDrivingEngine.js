import { evaluateDecision } from './decisionEngine.js'
import { evolveERP } from './erpEvolutionEngine.js'
import { executeDecision, getExecutionHistory, getExecutionStatus } from './executionEngine.js'
import { collectRuntimeFeedback } from './runtimeFeedbackCollector.js'
import { simulateEnterpriseState } from '../digitalTwin/enterpriseDigitalTwinEngine.js'

const autonomousHistory = []
let loopHandle = null
let autonomousStatus = {
  running: false,
  mode: 'IDLE',
  autonomyLevel: 4,
  updatedAt: Date.now(),
}

function recordCycle(entry) {
  const log = {
    timestamp: Date.now(),
    ...entry,
  }
  autonomousHistory.push(log)
  autonomousStatus = {
    running: autonomousStatus.running,
    mode: entry.execution?.executed ? 'EXECUTING' : 'MONITORING',
    autonomyLevel: 4,
    updatedAt: log.timestamp,
    last: log,
  }
  return log
}

function inferAutonomousAction(context = {}) {
  if (context.action) return context.action

  const record = context.record || context.rows?.[0] || {}
  const workflow = context.schema?.workflow || {}
  const field = workflow.stateField || 'workflow_state'
  const currentState = record[field] || workflow.states?.[0]
  const action = Object.entries(workflow.actions || {}).find(([, states]) => states.includes(currentState))

  if (action) return action[0]

  const transition = (workflow.transitions || []).find((item) => item.from === currentState)
  if (transition?.to === 'APPROVED') return 'APPROVE'
  if (transition?.to === 'SUBMITTED') return 'SUBMIT'
  if (transition?.to === 'CLOSED') return 'CLOSE'

  return 'APPROVE'
}

export function senseEnterpriseState(context = {}) {
  const simulation = simulateEnterpriseState(context)
  const feedback = collectRuntimeFeedback({
    schema: context.schema,
    module: context.schema?.api?.module || context.schema?.name,
  })

  return {
    mode: 'SENSE_LAYER',
    workflow: {
      currentState: simulation.state.order.currentState,
      bottleneck: simulation.workflowSimulation.workflowBottleneck,
      failureRisk: simulation.workflowSimulation.transitionFailureRisk,
    },
    kpi: {
      forecast: simulation.kpiForecast,
      anomalies: simulation.kpiForecast.anomalies,
    },
    orders: simulation.state.order,
    cashFlow: simulation.state.cashFlow,
    risks: simulation.riskProfile,
    execution: {
      status: getExecutionStatus(),
      history: getExecutionHistory(),
    },
    feedback,
    simulation,
  }
}

export function optimizeSystem(state = {}, execution = {}) {
  const evolution = evolveERP({
    schema: state.schema || state.simulation?.schema,
    module: state.simulation?.state?.module,
  })
  const tightenControl = state.risks?.riskLevel === 'HIGH' || execution.status === 'BLOCKED'

  return {
    mode: 'AUTONOMOUS_OPTIMIZATION',
    schemaOptimization: evolution.schema,
    workflowRestructuring: evolution.workflow,
    uiSimplification: evolution.ui,
    controlPolicy: {
      ...evolution.control,
      autonomousAdjustment: tightenControl ? 'TIGHTEN' : 'RELAX_OR_MONITOR',
    },
    systemScoreDelta: execution.executed ? 4 : 1,
  }
}

export function runAutonomousCycle(context = {}) {
  const action = inferAutonomousAction(context)
  const state = {
    ...senseEnterpriseState({
      ...context,
      action,
    }),
    schema: context.schema,
  }
  const decision = evaluateDecision({
    ...context,
    action,
  })
  const execution = executeDecision({
    ...context,
    action,
    decision,
    manualConfirm: false,
  })
  const optimization = optimizeSystem(state, execution)
  const cycle = {
    mode: 'V13.4_SELF_DRIVING_ENTERPRISE_OS',
    autonomousMode: 'ON',
    selfDriving: 'ENABLED',
    systemAutonomyLevel: 4,
    state,
    decision,
    execution,
    optimization,
  }

  recordCycle(cycle)
  return cycle
}

export function startAutonomousLoop(context = {}, options = {}) {
  if (loopHandle) return autonomousStatus

  const interval = Math.max(Number(options.interval || 5000), 1000)
  autonomousStatus = {
    running: true,
    mode: 'RUNNING',
    autonomyLevel: 4,
    updatedAt: Date.now(),
  }
  runAutonomousCycle(context)
  loopHandle = setInterval(() => {
    runAutonomousCycle(context)
  }, interval)

  return autonomousStatus
}

export function stopAutonomousLoop() {
  if (loopHandle) {
    clearInterval(loopHandle)
    loopHandle = null
  }

  autonomousStatus = {
    ...autonomousStatus,
    running: false,
    mode: 'STOPPED',
    updatedAt: Date.now(),
  }

  return autonomousStatus
}

export function getAutonomousStatus() {
  return autonomousStatus
}

export function getAutonomousHistory() {
  return autonomousHistory
}

export function clearAutonomousHistory() {
  autonomousHistory.length = 0
  autonomousStatus = {
    running: false,
    mode: 'IDLE',
    autonomyLevel: 4,
    updatedAt: Date.now(),
  }
}
