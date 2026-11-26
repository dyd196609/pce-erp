let runtimeLocked = false
let lockSnapshot = null

export function lockRuntime(systemState = {}) {
  runtimeLocked = true
  lockSnapshot = {
    runtimeLocked,
    mutationDisabled: true,
    lockedAt: Date.now(),
    systemState,
    freezeRuntimeEvolution: true,
    preventStructuralMutation: true,
    productionSafetyMode: 'ENFORCED',
  }

  return {
    runtimeLocked,
    mutationDisabled: true,
    ...lockSnapshot,
  }
}

export function isRuntimeLocked() {
  return runtimeLocked
}

export function getRuntimeLockSnapshot() {
  return lockSnapshot || {
    runtimeLocked,
    mutationDisabled: runtimeLocked,
    freezeRuntimeEvolution: runtimeLocked,
    preventStructuralMutation: runtimeLocked,
    productionSafetyMode: runtimeLocked ? 'ENFORCED' : 'READY',
  }
}

export function enforceProductionSafetyMode(systemState = {}) {
  if (runtimeLocked) return getRuntimeLockSnapshot()
  return lockRuntime(systemState)
}
