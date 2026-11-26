import { buildCivilizationState } from './unifiedCivilizationEngine.js'

const syncHistory = []

function resolveState(context = {}) {
  return context.civilizationState || buildCivilizationState(context)
}

export function synchronizeTenantWorlds(context = {}) {
  const state = resolveState(context)
  const tenantIds = state.enterpriseLayer.map((enterprise) => enterprise.tenantId)

  const result = {
    tenantIds,
    synchronized: true,
    sharedVersion: `civilization-${Date.now()}`,
  }

  syncHistory.push({
    ...result,
    timestamp: Date.now(),
  })

  return result
}

export function propagateSharedGlobalState(context = {}) {
  const state = resolveState(context)

  return state.enterpriseLayer.map((enterprise) => ({
    tenantId: enterprise.tenantId,
    globalHealth: state.globalLayer.health,
    macroStability: state.globalLayer.world.metrics.macroStability,
    status: 'PROPAGATED',
  }))
}

export function controlCrossWorldConsistency(context = {}) {
  const propagated = context.propagation || propagateSharedGlobalState(context)
  const inconsistent = propagated.filter((item) => item.globalHealth < 50)

  return {
    consistent: inconsistent.length === 0,
    inconsistent,
    consistencyScore: propagated.length === 0 ? 100 : Math.round(100 - (inconsistent.length / propagated.length) * 100),
  }
}

export function getWorldSyncHistory() {
  return syncHistory
}

export function runWorldStateSync(context = {}) {
  const tenantSync = synchronizeTenantWorlds(context)
  const propagation = propagateSharedGlobalState(context)

  return {
    mode: 'V27_WORLD_STATE_SYNC',
    tenantSync,
    propagation,
    consistency: controlCrossWorldConsistency({
      ...context,
      propagation,
    }),
  }
}
