import { detectMaliciousPlugins, enforceSandboxRules } from './securityEngine.js'

export function restrictDangerousPlugins() {
  return detectMaliciousPlugins().map((plugin) => ({
    ...plugin,
    action: 'RESTRICT_PLUGIN',
  }))
}

export function enforceSandboxGovernance(pluginId) {
  return enforceSandboxRules(pluginId)
}

export function governApiAccess(plugin = {}) {
  const apiValues = Object.values(plugin.api || {})
  const unsafe = apiValues.some((url) => typeof url === 'string' && !url.startsWith('/api/execution/'))

  return {
    pluginId: plugin.id,
    apiAccess: unsafe ? 'RESTRICTED' : 'APPROVED',
    unsafe,
  }
}

export function runSecurityGovernance(plugins = []) {
  const restricted = restrictDangerousPlugins()

  return {
    securityGovernance: 'ACTIVE',
    threatCount: restricted.length,
    restricted,
    apiAccess: plugins.map(governApiAccess),
    status: restricted.length ? 'THREAT_DETECTED' : 'SECURE',
  }
}
