import { getPluginRegistry, getRegisteredWorkflows } from '../pluginSDK.js'
import { getSandboxLog } from '../sandboxRuntime.js'

function isUnsafeApi(api = {}) {
  return Object.values(api).some((url) => typeof url === 'string' && !url.startsWith('/api/execution/'))
}

export function detectMaliciousPlugins() {
  return getPluginRegistry().filter((plugin) => {
    const sandboxEvents = getSandboxLog().filter((item) => item.pluginId === plugin.id)
    const hasViolations = sandboxEvents.some((item) => item.violations?.length)
    return isUnsafeApi(plugin.api) || hasViolations
  }).map((plugin) => ({
    pluginId: plugin.id,
    name: plugin.name,
    reason: isUnsafeApi(plugin.api) ? 'UNSAFE_API_SCOPE' : 'SANDBOX_VIOLATION',
  }))
}

export function isolateUnsafeWorkflows() {
  const unsafePlugins = new Set(detectMaliciousPlugins().map((plugin) => plugin.pluginId))

  return getRegisteredWorkflows()
    .filter((workflow) => unsafePlugins.has(workflow.entity))
    .map((workflow) => ({
      entity: workflow.entity,
      status: 'ISOLATED',
      reason: 'PLUGIN_SECURITY_RISK',
    }))
}

export function enforceSandboxRules(pluginId) {
  const threats = detectMaliciousPlugins()
  const threat = threats.find((item) => item.pluginId === pluginId)

  return {
    pluginId,
    allowed: !threat,
    action: threat ? 'ISOLATE' : 'ALLOW_SANDBOX_EXECUTION',
    reason: threat?.reason || 'SANDBOX_RULES_PASSED',
  }
}

export function evaluateSecurity() {
  const threats = detectMaliciousPlugins()

  return {
    mode: 'V21_ECOSYSTEM_SECURITY',
    threatCount: threats.length,
    threats,
    isolatedWorkflows: isolateUnsafeWorkflows(),
    status: threats.length ? 'ATTENTION' : 'SECURE',
  }
}
