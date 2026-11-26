const logs = []

export function recordEvent(event) {
  try {
    logs.push({
      ...event,
      timestamp: Date.now(),
    })
  } catch {
    // Monitoring must never affect runtime flow.
  }
}

export function triggerAutoHealingIfMonitor(governance, patchSet) {
  try {
    if (governance?.decision !== 'MONITOR') return null
    if (globalThis.__V71_AUTO_HEALING_RUNNING__) return null

    return window.__TRACE__?.system?.healAuto?.(patchSet)
  } catch (error) {
    recordEvent({
      type: 'AUTO_HEAL_TRIGGER_ERROR',
      status: 'FAILED',
      message: error?.message || String(error),
    })
    return null
  }
}

export function getSystemHealth() {
  return {
    totalEvents: logs.length,
    lastEvents: logs.slice(-10),
    errorCount: logs.filter((log) => log.type === 'ERROR').length,
  }
}

export function getLogs() {
  return logs
}
