import { runCivilizationCore } from '../final/unifiedCivilizationCore.js'

const canonicalDecisionLayers = ['final', 'hybrid', 'decision']
const canonicalExecutionLayers = ['final', 'autonomousStatus', 'executionStatus']

function asArray(value) {
  return Array.isArray(value) ? value : []
}

function countPresent(systems = {}, keys = []) {
  return keys.filter((key) => systems[key] != null).length
}

export function pruneRedundantCapabilities(v13Systems = {}) {
  const final = v13Systems.final || runCivilizationCore(v13Systems)
  const pruned = {
    final,
    unifiedState: final.unifiedState,
    intelligence: final.intelligence,
    policy: final.policy,
    reality: final.reality,
    hybrid: v13Systems.hybrid || final.unifiedState?.hybrid,
    autonomousStatus: v13Systems.autonomousStatus || final.unifiedState?.autonomous,
    executionStatus: v13Systems.executionStatus,
    network: v13Systems.network || final.unifiedState?.globalEconomy?.market?.network,
    globalEconomy: v13Systems.globalEconomy || final.unifiedState?.globalEconomy,
    civilization: v13Systems.civilization || final.unifiedState?.civilization,
  }
  const duplicateDecisionLayers = Math.max(0, countPresent(v13Systems, canonicalDecisionLayers) - 1)
  const duplicateExecutionLayers = Math.max(0, countPresent(v13Systems, canonicalExecutionLayers) - 1)

  return {
    mode: 'PRUNED_CAPABILITIES',
    systems: pruned,
    prunedCapabilities: [
      duplicateDecisionLayers > 0 ? 'duplicate decision layers merged into final.unifiedState' : null,
      duplicateExecutionLayers > 0 ? 'duplicate execution loops frozen under convergence governance' : null,
      'dimension systems collapsed into single governance runtime',
    ].filter(Boolean),
    duplicateDecisionLayers,
    duplicateExecutionLayers,
  }
}

export function unifyRuntime(pruned = {}) {
  const final = pruned.systems?.final || {}
  const unifiedState = final.unifiedState || pruned.systems?.unifiedState || {}

  return {
    mode: 'UNIFIED_RUNTIME',
    unifiedState: {
      identity: unifiedState.identity || 'FINAL_CIVILIZATION_AGENT',
      runtimeModel: 'SINGLE_AGENT_STRUCTURE',
      decision: unifiedState.singleState?.decision || 'MONITOR',
      control: unifiedState.singleState?.control || 'ALLOW',
      systemStability: final.intelligence?.realityStability || pruned.systems?.intelligence?.realityStability || 0,
      economy: unifiedState.singleState?.economy || 'STABLE',
      society: unifiedState.singleState?.society || 0,
      humanAiAgreement: unifiedState.singleState?.humanAiAgreement === true,
      sourceSystems: [
        'hybridDecisionEngine',
        'selfDrivingEngine',
        'globalEconomicBrain',
        'civilizationSimulationEngine',
        'enterpriseOSKernel',
      ],
    },
    prunedCapabilities: pruned.prunedCapabilities || [],
    duplicateDecisionLayers: pruned.duplicateDecisionLayers || 0,
    duplicateExecutionLayers: pruned.duplicateExecutionLayers || 0,
  }
}

export function stabilizeExecution(unified = {}) {
  const loopBudget = 1
  const conflictBudget = 1
  const executionLoops = Math.max(1, unified.duplicateExecutionLayers + 1)
  const recursiveRisk = executionLoops > loopBudget

  return {
    ...unified,
    mode: 'STABILIZED_EXECUTION',
    executionControl: {
      loopBudget,
      activeLoops: Math.min(loopBudget, executionLoops),
      frozenLoops: Math.max(0, executionLoops - loopBudget),
      recursiveDecisionGuard: recursiveRisk ? 'ACTIVE' : 'READY',
      multiEngineInterference: recursiveRisk ? 'CONTAINED' : 'LOW',
      conflictBudget,
    },
  }
}

export function resolveConflicts(stabilized = {}) {
  const conflicts = []

  if (stabilized.duplicateDecisionLayers > 0) {
    conflicts.push({
      type: 'DUPLICATE_DECISION_LAYER',
      resolution: 'route all decisions through final.unifiedState',
    })
  }

  if (stabilized.executionControl?.frozenLoops > 0) {
    conflicts.push({
      type: 'DUPLICATE_EXECUTION_LOOP',
      resolution: 'freeze secondary loops and keep single active runtime loop',
    })
  }

  if (stabilized.unifiedState?.humanAiAgreement === false) {
    conflicts.push({
      type: 'HUMAN_AI_DECISION_CONFLICT',
      resolution: 'use hybrid trust engine before execution',
    })
  }

  return {
    ...stabilized,
    mode: 'CONFLICT_RESOLVED_RUNTIME',
    conflicts,
    conflictHeatmap: {
      decision: conflicts.filter((item) => item.type.includes('DECISION')).length,
      execution: conflicts.filter((item) => item.type.includes('EXECUTION')).length,
      humanAi: conflicts.filter((item) => item.type.includes('HUMAN_AI')).length,
    },
  }
}

export function calculateComplexity(resolved = {}) {
  const sourceCount = resolved.unifiedState?.sourceSystems?.length || 0
  const conflictCount = asArray(resolved.conflicts).length
  const frozenLoops = resolved.executionControl?.frozenLoops || 0
  const raw = sourceCount + conflictCount * 2 + frozenLoops * 3

  return {
    score: Math.min(100, raw * 8),
    level: raw <= 6 ? 'BOUNDED' : raw <= 10 ? 'WATCH' : 'HIGH',
    maxRuntimeLoops: resolved.executionControl?.loopBudget || 1,
    expansionAllowed: false,
  }
}

export function calculateStability(resolved = {}) {
  const base = Number(resolved.unifiedState?.systemStability || 75)
  const conflictPenalty = asArray(resolved.conflicts).length * 6
  const loopPenalty = (resolved.executionControl?.frozenLoops || 0) * 4
  const boundedBonus = calculateComplexity(resolved).level === 'BOUNDED' ? 8 : 0

  return Math.max(0, Math.min(100, Math.round(base - conflictPenalty - loopPenalty + boundedBonus)))
}

export function convergeSystem(v13Systems = {}) {
  const pruned = pruneRedundantCapabilities(v13Systems)
  const unified = unifyRuntime(pruned)
  const stabilized = stabilizeExecution(unified)
  const resolved = resolveConflicts(stabilized)
  const complexity = calculateComplexity(resolved)

  return {
    mode: 'V13.11_SYSTEM_CONVERGENCE',
    unifiedState: {
      ...resolved,
      complexity,
    },
    stabilityScore: calculateStability(resolved),
    convergenceRules: {
      noNewCoreLayers: true,
      singleDecisionFlow: true,
      singleExecutionLoop: true,
      boundedComplexity: complexity.level,
    },
  }
}
