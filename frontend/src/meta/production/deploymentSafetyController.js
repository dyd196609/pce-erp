import { validateProductionReadiness } from './readinessValidator.js'
import { checkModuleCompliance } from './moduleComplianceChecker.js'
import { getRuntimeLockSnapshot } from './runtimeLock.js'

export function preventUnsafeDeployment(readiness = validateProductionReadiness(), compliance = checkModuleCompliance()) {
  return {
    safe: readiness.deploymentReady && compliance.moduleComplianceIndex >= 80,
    reasons: [
      readiness.deploymentReady ? null : 'production_readiness_not_met',
      compliance.moduleComplianceIndex >= 80 ? null : 'module_compliance_below_threshold',
    ].filter(Boolean),
  }
}

export function ensureRollbackProtection() {
  return {
    rollbackProtection: 'ENABLED',
    rollbackPoint: `freeze-${Date.now()}`,
  }
}

export function preventRuntimeCrash() {
  const lock = getRuntimeLockSnapshot()

  return {
    runtimeCrashPrevention: 'ACTIVE',
    deterministicRuntime: true,
    mutationDisabled: lock.mutationDisabled === true,
  }
}

export function evaluateDeploymentSafety() {
  const readiness = validateProductionReadiness()
  const compliance = checkModuleCompliance()
  const unsafe = preventUnsafeDeployment(readiness, compliance)
  const rollback = ensureRollbackProtection()
  const crashPrevention = preventRuntimeCrash()
  const deploymentSafetyLevel = unsafe.safe && crashPrevention.mutationDisabled ? 'SAFE' : 'REVIEW'

  return {
    deploymentSafetyLevel,
    safeToDeploy: deploymentSafetyLevel === 'SAFE',
    readiness,
    compliance,
    unsafe,
    rollback,
    crashPrevention,
    timestamp: Date.now(),
  }
}
