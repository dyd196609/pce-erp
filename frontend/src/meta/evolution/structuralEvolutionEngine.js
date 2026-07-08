import { getOrchestrationSnapshot } from '../orchestration/autoWorkflowConnector.js'
import { getIntelligenceSnapshot } from '../intelligence/decisionEngine.js'
import { getExecutionLayerSnapshot } from '../execution/executionEngine.js'
import { getEnterpriseAutopilotSnapshot } from '../autonomy/businessOrchestrator.js'
import { recombineModules } from './moduleRecompositionEngine.js'
import { mutateWorkflows } from './workflowMutationEngine.js'
import { adjustBehavior } from './behaviorAdaptationEngine.js'
import { optimizeEnterprisePerformance } from './performanceEvolutionAI.js'
import { checkEvolutionSafety, getStabilityBoundarySnapshot } from '../stability/evolutionBoundaryController.js'
import { isRuntimeLocked } from '../production/runtimeLock.js'

const evolutionTrace = []
const maxTrace = 80

function buildSystemState(systemState = {}) {
  return {
    orchestration: systemState.orchestration || getOrchestrationSnapshot(),
    intelligence: systemState.intelligence || getIntelligenceSnapshot(),
    execution: systemState.execution || getExecutionLayerSnapshot(),
    autopilot: systemState.autopilot || getEnterpriseAutopilotSnapshot(),
    schema: systemState.schema || null,
    record: systemState.record || null,
  }
}

export function adaptUI(systemState = {}) {
  const behavior = adjustBehavior(systemState)

  return {
    uiEvolution: 'ACTIVE',
    preferredPanel: behavior.uiAdaptation.focusPanel,
    layoutPolicy: 'enterprise_dense_readable',
    changes: behavior.uiAdaptation.changes,
    timestamp: Date.now(),
  }
}

export function evolveStructure(systemState = {}) {
  if (isRuntimeLocked() && evolutionTrace[0]) {
    return {
      ...evolutionTrace[0],
      evolutionStatus: 'FROZEN',
      applied: false,
      freezeReason: 'production_runtime_locked',
    }
  }

  const state = buildSystemState(systemState)
  const performance = optimizeEnterprisePerformance(state)
  const result = {
    evolutionMode: 'ON',
    structuralEvolution: 'ACTIVE',
    workflowMutation: 'ENABLED',
    moduleRecomposition: 'ACTIVE',
    moduleChanges: recombineModules(state),
    workflowChanges: mutateWorkflows(state),
    uiChanges: adaptUI(state),
    behaviorChanges: adjustBehavior(state),
    performance,
    timestamp: Date.now(),
  }
  const safety = checkEvolutionSafety(result)
  const controlledResult = {
    ...result,
    evolutionStatus: safety.allowed ? 'ALLOWED' : 'BLOCKED',
    stabilityBoundary: safety,
    applied: safety.allowed,
  }

  evolutionTrace.unshift(controlledResult)
  if (evolutionTrace.length > maxTrace) evolutionTrace.length = maxTrace

  return controlledResult
}

export function getEvolutionTrace() {
  return [...evolutionTrace]
}

export function getStructuralEvolutionSnapshot() {
  const latest = evolutionTrace[0] || evolveStructure()
  const trace = getEvolutionTrace()
  const performanceScore = latest.performance?.score ?? 0
  const workflowGrowth = latest.workflowChanges?.redundantStepRemoval?.redundantSteps?.length
    ? 82
    : 94
  const moduleFlexibility = Math.min(100, 70 + (latest.moduleChanges?.merges?.length || 0) * 10 + (latest.moduleChanges?.splits?.length || 0) * 8)
  const behaviorScore = latest.behaviorChanges?.workflowBehavior?.behaviorMode === 'STABLE_AUTONOMY' ? 96 : 84

  return {
    evolutionMode: 'ON',
    structuralEvolution: 'ACTIVE',
    workflowMutation: 'ENABLED',
    moduleRecomposition: 'ACTIVE',
    stabilityMode: 'ON',
    evolutionControl: 'ACTIVE',
    safeEvolutionGate: 'ENABLED',
    driftProtection: 'ACTIVE',
    latest,
    trace,
    stability: getStabilityBoundarySnapshot(),
    metrics: {
      systemEvolutionIndex: performanceScore,
      workflowEfficiencyGrowth: workflowGrowth,
      moduleStabilityFlexibility: moduleFlexibility,
      behavioralAdaptationScore: behaviorScore,
    },
  }
}
