import { deployProduction, deployStaging, rollbackDeployment } from './deploymentRuntime.js'
import { getProductionFinalizationSnapshot } from '../production/systemFreezeManager.js'

const deploymentHistory = []

export function deployToStaging(context = {}) {
  return {
    stage: 'staging',
    status: 'READY',
    result: deployStaging(context),
    timestamp: Date.now(),
  }
}

export function deployToProduction(context = {}) {
  const finalization = getProductionFinalizationSnapshot()
  if (finalization.deployment?.deploymentSafetyLevel !== 'SAFE') {
    return {
      stage: 'production',
      status: 'BLOCKED',
      reason: 'deployment_safety_not_met',
      finalization,
      timestamp: Date.now(),
    }
  }

  return {
    stage: 'production',
    status: 'DEPLOYED',
    result: deployProduction(context),
    finalization,
    timestamp: Date.now(),
  }
}

export function runRollback(context = {}) {
  return {
    stage: 'rollback',
    status: 'ROLLBACK_READY',
    result: rollbackDeployment(context),
    timestamp: Date.now(),
  }
}

export function runSafeReleaseFlow(context = {}) {
  const staging = deployToStaging(context)
  const production = deployToProduction(context)
  const rollback = runRollback(context)
  const result = {
    deployment: 'ACTIVE',
    status: production.status === 'DEPLOYED' ? 'STABLE' : 'REVIEW',
    staging,
    production,
    rollback,
    deploymentStabilityScore: production.status === 'DEPLOYED' && rollback.status === 'ROLLBACK_READY' ? 100 : 75,
    timestamp: Date.now(),
  }

  deploymentHistory.unshift(result)
  if (deploymentHistory.length > 80) deploymentHistory.length = 80

  return result
}

export function getDeploymentPipelineSnapshot() {
  const latest = deploymentHistory[0] || null

  return {
    deployment: 'ACTIVE',
    latest,
    history: [...deploymentHistory],
    metrics: {
      deploymentStabilityScore: latest?.deploymentStabilityScore ?? 90,
      deployments: deploymentHistory.length,
    },
  }
}
