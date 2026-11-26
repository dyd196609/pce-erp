import { getPlugin, getPluginRegistry } from '../pluginSDK.js'
import { executePluginSandbox } from '../sandbox/sandboxEngine.js'

const pluginRuntimeHistory = []

export function isolateRuntimeContext(plugin = {}) {
  return {
    pluginId: plugin.id || plugin.pluginId || plugin.name,
    isolated: true,
    mutationAllowed: false,
    coreAccess: 'READ_ONLY',
  }
}

export function preventSystemMutation(plugin = {}) {
  return {
    pluginId: plugin.id || plugin.pluginId || plugin.name,
    systemMutationPrevented: true,
    blockedScopes: ['core', 'runtime', 'production', 'stability'],
  }
}

export function executePlugin(pluginId, task = {}, options = {}) {
  const plugin = getPlugin(pluginId)

  if (!plugin) {
    return {
      status: 'PLUGIN_NOT_FOUND',
      pluginId,
    }
  }

  const runtimeContext = isolateRuntimeContext(plugin)
  const mutationGuard = preventSystemMutation(plugin)
  const execution = executePluginSandbox(plugin, task, options)
  const result = {
    pluginSystem: 'ACTIVE',
    pluginId,
    runtimeContext,
    mutationGuard,
    execution,
    status: execution.status,
    timestamp: Date.now(),
  }

  pluginRuntimeHistory.unshift(result)
  if (pluginRuntimeHistory.length > 100) pluginRuntimeHistory.length = 100

  return result
}

export function getPluginRuntimeSnapshot() {
  return {
    pluginSystem: 'ACTIVE',
    sandboxMode: 'ENABLED',
    plugins: getPluginRegistry(),
    history: [...pluginRuntimeHistory],
  }
}
