export function initRuntimeSystem() {
  return {
    unifiedState: {},
    engines: {},
    runtime: {
      initialized: true,
      safeMode: true,
    },
  }
}

export function ensureRuntimeSystem(system) {
  const safeSystem = system && typeof system === 'object'
    ? system
    : initRuntimeSystem()

  if (!safeSystem.unifiedState || typeof safeSystem.unifiedState !== 'object') {
    safeSystem.unifiedState = {}
  }

  if (!safeSystem.engines || typeof safeSystem.engines !== 'object') {
    safeSystem.engines = {}
  }

  if (!safeSystem.runtime || typeof safeSystem.runtime !== 'object') {
    safeSystem.runtime = {}
  }

  safeSystem.runtime.initialized = safeSystem.runtime.initialized !== false
  safeSystem.runtime.safeMode = true

  return safeSystem
}
