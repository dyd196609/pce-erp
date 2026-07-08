import { ensureRuntimeSystem } from '../runtime/runtimeBootstrap.js'

const MAX_WORKFLOW_DEPTH = 8
const MAX_ENGINE_COUNT = 16
const MAX_RECURSION_LOOP = 1

function stableStringify(value) {
  if (value == null || typeof value !== 'object') return JSON.stringify(value)
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(',')}]`

  return `{${Object.keys(value)
    .sort()
    .map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`)
    .join(',')}}`
}

function stableHash(value) {
  const source = stableStringify(value)
  let hash = 0

  for (let i = 0; i < source.length; i++) {
    hash = ((hash << 5) - hash + source.charCodeAt(i)) | 0
  }

  return Math.abs(hash).toString(16).padStart(8, '0')
}

export function preventNewEngines(v13Core = {}) {
  const safeCore = ensureRuntimeSystem(v13Core)
  const sourceSystems = safeCore.unifiedState?.unifiedState?.sourceSystems
    || safeCore.unifiedState?.sourceSystems
    || []

  return {
    newEngineAllowed: false,
    dynamicEngineInjection: 'DISABLED',
    engineCount: Math.min(sourceSystems.length || 0, MAX_ENGINE_COUNT),
    maxEngineCount: MAX_ENGINE_COUNT,
    policy: 'NO_NEW_V13_STRUCTURES',
  }
}

export function freezeExecutionLayers(v13Core = {}) {
  const safeCore = ensureRuntimeSystem(v13Core)
  const activeLoops = safeCore.unifiedState?.executionControl?.activeLoops || 1
  const frozenLoops = safeCore.unifiedState?.executionControl?.frozenLoops || 0

  return {
    activeLoops: Math.min(activeLoops, MAX_RECURSION_LOOP),
    frozenLoops,
    maxRecursionLoop: MAX_RECURSION_LOOP,
    blockedRule: 'HARD_STOP',
    restrictedRule: 'HUMAN_GATE_ONLY',
    autoRule: 'POLICY_CONTROLLED',
  }
}

export function enforceDeterministicRuntime(v13Core = {}) {
  const safeCore = ensureRuntimeSystem(v13Core)

  return {
    deterministic: true,
    sameInputSameOutput: true,
    adaptiveStructuralMutation: 'DISABLED',
    dynamicEngineInjection: 'DISABLED',
    runtimeSignature: stableHash({
      mode: safeCore.mode,
      stabilityScore: safeCore.stabilityScore,
      complexity: safeCore.unifiedState?.complexity?.level,
      decision: safeCore.unifiedState?.unifiedState?.decision,
      conflicts: safeCore.unifiedState?.conflictHeatmap,
    }),
  }
}

export function capComplexity(v13Core = {}) {
  const safeCore = ensureRuntimeSystem(v13Core)
  const complexity = safeCore.unifiedState?.complexity || {}
  const workflowDepth = Math.min(Number(safeCore.workflowDepth || complexity.workflowDepth || 3), MAX_WORKFLOW_DEPTH)

  return {
    bounded: true,
    level: complexity.level || 'BOUNDED',
    score: Math.min(Number(complexity.score || 0), 100),
    maxWorkflowDepth: MAX_WORKFLOW_DEPTH,
    workflowDepth,
    maxEngineCount: MAX_ENGINE_COUNT,
    maxRecursionLoop: MAX_RECURSION_LOOP,
    expansionAllowed: false,
  }
}

export function lockSystem(v13Core = {}) {
  const safeCore = ensureRuntimeSystem(v13Core)
  const engineLock = preventNewEngines(safeCore)
  const executionLock = freezeExecutionLayers(safeCore)
  const deterministicRuntime = enforceDeterministicRuntime(safeCore)
  const complexityCap = capComplexity(safeCore)
  const productionReady = deterministicRuntime.deterministic
    && executionLock.activeLoops === 1
    && engineLock.newEngineAllowed === false
    && complexityCap.bounded

  return {
    ...safeCore,
    status: 'FROZEN',
    mode: 'PRODUCTION_LOCK',
    productionReady,
    freezeMode: 'ON',
    safeMode: true,
    productionLock: 'ACTIVE',
    systemMutability: 'DISABLED',
    engineLock,
    executionLock,
    deterministicRuntime,
    complexityCap,
    cockpitStatus: productionReady ? 'PRODUCTION READY' : 'LOCK REVIEW REQUIRED',
  }
}
