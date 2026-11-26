import { getAutonomousStatus } from '../ai/selfDrivingEngine.js'
import { simulateCivilization } from '../civilization/civilizationSimulationEngine.js'
import { simulateGlobalEconomy } from '../global/globalEconomicBrain.js'
import { hybridDecision } from '../hybrid/hybridDecisionEngine.js'
import { runKernel } from '../kernel-core/index.js'
import { createDefaultEnterpriseNetwork } from '../network/enterpriseGraphEngine.js'

function clampScore(value) {
  return Math.max(0, Math.min(100, Math.round(value)))
}

function safeKernel(input, context) {
  if (context.kernel) return context.kernel

  try {
    return runKernel(input || { goal: 'unified civilization state' }, {
      ...(context.runtimeContext || {}),
      priority: 'HIGH',
    })
  } catch (error) {
    return {
      mode: 'PROFITOS_KERNEL',
      execution: {
        finalDecision: {
          decision: 'MONITOR',
          reason: error?.message || 'kernel fallback monitor',
        },
      },
      runtime: {
        mode: 'KERNEL_RUNTIME',
      },
    }
  }
}

export function mergeAllSystems(context = {}) {
  const enterprises = context.enterprises || createDefaultEnterpriseNetwork()
  const globalEconomy = context.globalEconomy || context.economy || simulateGlobalEconomy({
    enterprises,
    network: context.network,
    runtimeState: context.runtimeState,
  })
  const civilization = context.civilization || simulateCivilization({
    globalEconomy,
    economy: globalEconomy,
    runtimeState: context.runtimeState,
  })
  const hybrid = context.hybrid || hybridDecision({
    schema: context.schema || {},
    record: context.record || {},
    rows: context.rows || [],
    action: context.action || 'simulate',
    civilization,
    human: context.human,
    ai: context.decision || context.ai,
    runtimeState: context.runtimeState,
  })
  const autonomous = context.autonomous || context.autonomousStatus || getAutonomousStatus()
  const kernel = safeKernel(context.input || context.goal || { goal: 'unified civilization state' }, {
    ...context,
    globalEconomy,
    civilization,
    hybrid,
    autonomous,
  })

  return {
    mode: 'SINGLE_UNIFIED_MODEL',
    identity: 'FINAL_CIVILIZATION_AGENT',
    kernel,
    hybrid,
    autonomous,
    globalEconomy,
    civilization,
    singleState: {
      decision: hybrid.fused?.decision || kernel.execution?.finalDecision?.decision || 'MONITOR',
      control: kernel.execution?.finalDecision?.decision || 'ALLOW',
      economy: globalEconomy.macro?.interestRateImpact || 'STABLE',
      society: civilization.society?.stabilityIndex || 0,
      humanAiAgreement: hybrid.fused?.agreement === true,
    },
  }
}

export function computeGlobalIntelligence(unifiedState = {}) {
  const civilizationHealth = unifiedState.civilization?.economy?.civilizationKpi?.civilizationHealthIndex || 0
  const hybridConfidence = unifiedState.hybrid?.fused?.confidence || 0
  const networkEfficiency = unifiedState.globalEconomy?.market?.network?.globalOptimization?.networkEfficiency || 0
  const governanceStability = unifiedState.civilization?.governance?.stabilityControl || 0
  const coherence = unifiedState.singleState?.humanAiAgreement ? 12 : -8
  const systemStability = clampScore(
    civilizationHealth * 0.3 +
    hybridConfidence * 0.25 +
    networkEfficiency * 0.25 +
    governanceStability * 0.2 +
    coherence
  )

  return {
    mode: 'GLOBAL_INTELLIGENCE',
    civilizationUnityIndex: clampScore((civilizationHealth + hybridConfidence + governanceStability) / 3),
    systemCoherence: clampScore(systemStability + (unifiedState.singleState?.humanAiAgreement ? 6 : -6)),
    realityStability: systemStability,
    intelligenceLevel: systemStability >= 82 ? 'SELF_EVOLVING' : systemStability >= 65 ? 'ADAPTIVE' : 'STABILIZING',
  }
}

export function evolveSelfPolicy(unifiedState = {}) {
  const intelligence = computeGlobalIntelligence(unifiedState)
  const lowCoherence = intelligence.systemCoherence < 70
  const lowReality = intelligence.realityStability < 70

  return {
    mode: 'SELF_EVOLUTION_POLICY',
    autoSchemaEvolution: lowCoherence ? 'SIMPLIFY_SCHEMA' : 'KEEP_SCHEMA',
    autoWorkflowRestructuring: lowReality ? 'REDUCE_WORKFLOW_STEPS' : 'MONITOR_WORKFLOW',
    autoPermissionAdaptation: unifiedState.hybrid?.conflict?.detected ? 'REQUIRE_SHARED_APPROVAL' : 'ALLOW_NORMAL_FLOW',
    autoKpiRecalibration: 'SYSTEM_STABILITY',
    targetKpi: 'system stability',
  }
}

export function applyRealityControl(policy = {}, unifiedState = {}) {
  const intelligence = computeGlobalIntelligence(unifiedState)
  const corrections = []

  if (intelligence.systemCoherence < 70) {
    corrections.push({
      type: 'STRUCTURAL_CORRECTION',
      action: policy.autoSchemaEvolution,
    })
  }

  if (intelligence.realityStability < 70) {
    corrections.push({
      type: 'FLOW_OPTIMIZATION',
      action: policy.autoWorkflowRestructuring,
    })
  }

  if (policy.autoPermissionAdaptation === 'REQUIRE_SHARED_APPROVAL') {
    corrections.push({
      type: 'GOVERNANCE_ALIGNMENT',
      action: 'route high-conflict decisions to shared approval',
    })
  }

  return {
    mode: 'REALITY_CONTROL_SIMULATION',
    enabled: true,
    sideEffect: 'NONE',
    systemInefficiencyDetected: corrections.length > 0,
    corrections,
    stabilityIndicator: intelligence.realityStability,
  }
}

export function runCivilizationCore(context = {}) {
  const unifiedState = mergeAllSystems(context)
  const intelligence = computeGlobalIntelligence(unifiedState)
  const policy = evolveSelfPolicy(unifiedState)
  const reality = applyRealityControl(policy, unifiedState)

  return {
    mode: 'V13.10_FINAL_CIVILIZATION_OS',
    unifiedState,
    intelligence,
    policy,
    reality,
  }
}
