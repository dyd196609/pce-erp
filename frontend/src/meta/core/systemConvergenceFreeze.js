import { lockSystem } from '../freeze/systemLockManager.js'
import { standardizeModulesForProduction } from '../product/moduleStandardizationCore.js'

const experimentalLayerNames = [
  'aiSimulation',
  'civilization',
  'digitalCivilization',
  'economy',
  'globalEconomy',
  'worldEconomy',
  'autonomy',
  'fullAutonomy',
  'humanBehaviorSimulation',
  'hybridCognition',
]

export function unifyEngines(system = {}) {
  const schemas = system.schemas || []
  const modules = standardizeModulesForProduction(schemas, {
    runtimeState: system.runtimeState,
    tenantId: system.tenantId,
    tenant: system.tenant,
    plan: system.plan,
  })

  return {
    mode: 'PRODUCTION_ENGINE_UNIFICATION',
    coreEngines: ['api', 'ui', 'workflow', 'permission', 'tenant', 'billing', 'deployment'],
    unifiedModuleCount: modules.moduleCount,
    registry: modules,
    legacyEngines: experimentalLayerNames,
    legacyEnginePolicy: 'FROZEN_AND_HIDDEN',
  }
}

export function stabilizeRuntime(system = {}) {
  const lock = lockSystem(system.convergence || system.runtime || {})

  return {
    mode: 'PRODUCTION_RUNTIME_STABILIZATION',
    deterministic: true,
    runtimeLoops: 1,
    mutationPolicy: 'DISABLED',
    debugHooks: 'DISABLED',
    apiStrictMode: 'ENABLED',
    tenantScopedRuntime: 'ENFORCED',
    lock,
  }
}

export function removeExperimentalLayers(system = {}) {
  const disabled = experimentalLayerNames.map((name) => ({
    name,
    status: 'DISABLED',
    replacement: 'PRODUCTION_CONTRACT_LAYER',
  }))

  return {
    mode: 'PRODUCTION_EXPERIMENTAL_LAYER_REMOVAL',
    experimentalLayers: 'DISABLED',
    disabled,
    activeLayers: ['apiContract', 'uiContract', 'workflowContract', 'permissionContract', 'tenantIsolation', 'saasDeployment'],
    removedCount: disabled.length,
    sourceSystemVersionRange: system.versionRange || 'V12-V30',
  }
}

export function lockArchitecture(system = {}) {
  return {
    mode: 'PRODUCTION_ARCHITECTURE_LOCK',
    systemFrozen: true,
    architectureLocked: true,
    productionCut: 'ON',
    allowedChangeTypes: ['schema_contract_update', 'api_contract_update', 'tenant_config_update'],
    blockedChangeTypes: ['new_experimental_engine', 'runtime_mutation', 'civilization_simulation', 'economic_simulation'],
    deploymentTarget: system.deploymentTarget || 'enterprise_saas',
  }
}

export function freezeArchitecture(system = {}) {
  const engines = unifyEngines(system)
  const runtime = stabilizeRuntime(system)
  const layers = removeExperimentalLayers(system)
  const structure = lockArchitecture(system)

  return {
    mode: 'PRODUCTION_CUT_SYSTEM_CONVERGENCE_LAYER',
    engines,
    runtime,
    layers,
    structure,
    metrics: {
      moduleReadiness: engines.registry.moduleCount === 0 ? 100 : Math.round(engines.registry.apiContractCoverage * 100),
      disabledExperimentalLayers: layers.removedCount,
      runtimeStability: runtime.lock.productionReady ? 100 : 80,
      deployability: structure.architectureLocked && runtime.lock.status === 'FROZEN' ? 100 : 70,
    },
  }
}
