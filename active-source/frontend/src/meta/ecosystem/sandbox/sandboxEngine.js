import { createSandbox, runInSandbox } from '../sandboxRuntime.js'

export function isolateMemory(plugin = {}) {
  return {
    pluginId: plugin.id || plugin.pluginId || plugin.name || 'anonymousPlugin',
    isolatedMemory: true,
    sharedStateAccess: false,
  }
}

export function restrictApiAccess(plugin = {}) {
  const allowedApis = plugin.allowedApis || plugin.permissions?.apis || ['read:tenant', 'read:module']

  return {
    apiAccess: 'RESTRICTED',
    allowedApis,
    blockedApis: ['write:core', 'mutate:runtime', 'disable:freeze'],
  }
}

export function preventCoreSystemModification(plugin = {}) {
  return {
    pluginId: plugin.id || plugin.pluginId || plugin.name || 'anonymousPlugin',
    coreMutationAllowed: false,
    runtimeMutationAllowed: false,
    productionFreezeBypass: false,
  }
}

export function sandboxDeploy(plugin = {}, options = {}) {
  const sandbox = createSandbox(plugin, options)
  return {
    sandboxMode: 'ENABLED',
    sandbox: true,
    sandboxProfile: sandbox,
    memory: isolateMemory(plugin),
    api: restrictApiAccess(plugin),
    mutationGuard: preventCoreSystemModification(plugin),
    deployedAt: Date.now(),
  }
}

export function executePluginSandbox(plugin = {}, task = {}, options = {}) {
  const deployment = sandboxDeploy(plugin, options)
  const execution = runInSandbox(plugin, task, options)

  return {
    ...execution,
    deployment,
    isolatedRuntimeContext: true,
  }
}
