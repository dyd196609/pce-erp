const sandboxLog = []

function clone(value) {
  try {
    return JSON.parse(JSON.stringify(value || {}))
  } catch {
    return {}
  }
}

function normalizeLimits(limits = {}) {
  return {
    maxActions: limits.maxActions || 20,
    maxPayloadSize: limits.maxPayloadSize || 10000,
    maxRuntimeMs: limits.maxRuntimeMs || 50,
  }
}

export function createSandbox(plugin = {}, options = {}) {
  const limits = normalizeLimits(options.limits)

  return {
    id: plugin.id || plugin.module?.key || 'anonymousPlugin',
    mode: 'V20_PLUGIN_SANDBOX',
    isolated: true,
    mutationAllowed: false,
    workflowExecution: 'SECURE_SIMULATION',
    limits,
  }
}

export function runInSandbox(plugin = {}, task = {}, options = {}) {
  const sandbox = createSandbox(plugin, options)
  const startedAt = Date.now()
  const safeTask = clone(task)
  const payloadSize = JSON.stringify(safeTask).length
  const actionCount = Array.isArray(safeTask.actions) ? safeTask.actions.length : 1
  const violations = []

  if (payloadSize > sandbox.limits.maxPayloadSize) {
    violations.push('PAYLOAD_LIMIT_EXCEEDED')
  }

  if (actionCount > sandbox.limits.maxActions) {
    violations.push('ACTION_LIMIT_EXCEEDED')
  }

  const elapsed = Date.now() - startedAt
  if (elapsed > sandbox.limits.maxRuntimeMs) {
    violations.push('RUNTIME_LIMIT_EXCEEDED')
  }

  const result = {
    mode: 'SANDBOX_EXECUTION',
    sandbox: true,
    pluginId: sandbox.id,
    status: violations.length ? 'BLOCKED' : 'SANDBOX_EXECUTED',
    sideEffect: 'NONE',
    mutationAllowed: false,
    violations,
    resourceUsage: {
      actionCount,
      payloadSize,
      elapsed,
    },
  }

  sandboxLog.push({
    ...result,
    timestamp: Date.now(),
  })

  return result
}

export function getSandboxLog() {
  return sandboxLog
}

export function clearSandboxLog() {
  sandboxLog.length = 0
}
