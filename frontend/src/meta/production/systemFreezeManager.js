import { getStabilityBoundarySnapshot } from '../stability/evolutionBoundaryController.js'
import { getStructuralEvolutionSnapshot } from '../evolution/structuralEvolutionEngine.js'
import { validateProductionReadiness } from './readinessValidator.js'
import { checkModuleCompliance } from './moduleComplianceChecker.js'
import { evaluateDeploymentSafety } from './deploymentSafetyController.js'
import { lockRuntime } from './runtimeLock.js'

let frozenSnapshot = null

export function captureSnapshot(systemState = {}) {
  return {
    capturedAt: Date.now(),
    systemState,
    stability: getStabilityBoundarySnapshot(),
    evolution: getStructuralEvolutionSnapshot(),
  }
}

export function freezeSystem(systemState = {}) {
  if (frozenSnapshot) return frozenSnapshot

  const stabilitySnapshot = captureSnapshot(systemState)
  const runtimeLock = lockRuntime(stabilitySnapshot)
  const readiness = validateProductionReadiness()
  const compliance = checkModuleCompliance()
  const deployment = evaluateDeploymentSafety()

  frozenSnapshot = {
    productionFinalizationMode: 'ON',
    frozen: true,
    allowedChanges: false,
    systemFrozen: true,
    mutationDisabled: true,
    deploymentReady: deployment.safeToDeploy ? 'ACTIVE' : 'REVIEW',
    stabilitySnapshot,
    runtimeLock,
    readiness,
    compliance,
    deployment,
    timestamp: Date.now(),
  }

  return frozenSnapshot
}

export function getProductionFinalizationSnapshot(systemState = {}) {
  return frozenSnapshot || freezeSystem(systemState)
}
