export const ModuleRegistry = {
  decisionLayer: {
    owner: 'ProfitOS',
    modules: [
      {
        key: 'profitos',
        name: 'ProfitOS',
        responsibility: 'Decision Layer',
        apiNamespace: '/api/profit',
      },
    ],
  },

  executionLayer: {
    owner: 'PalmCloud',
    modules: [
      {
        key: 'process-center',
        name: 'Process Center',
        responsibility: 'Enterprise OS Process Layer',
        apiNamespace: '/api/execution/process',
      },
      {
        key: 'organization',
        name: 'Organization',
        responsibility: 'Enterprise OS Organization Layer',
        apiNamespace: '/api/execution/organization',
      },
      {
        key: 'work-center',
        name: 'Work Center',
        responsibility: 'Enterprise OS Role Work Layer',
        apiNamespace: '/api/execution/work-center',
      },
      {
        key: 'analytics',
        name: 'Analytics',
        responsibility: 'Enterprise OS Analytics Layer',
        apiNamespace: '/api/execution/analytics',
      },
    ],
  },
}

const runtimeModules = []

function normalizeModule(module) {
  return {
    key: module.key,
    name: module.name || module.key,
    responsibility: module.responsibility || 'Generated Runtime Module',
    apiNamespace: module.apiNamespace || '/api/execution/generated',
    layer: module.layer || 'executionLayer',
    generated: module.generated === true,
    schema: module.schema,
    route: module.route,
    permission: module.permission || module.permissions,
    data: module.data,
    bindingMode: module.bindingMode,
  }
}

export function registerModule(module) {
  const normalized = normalizeModule(module)
  const target = normalized.layer === 'decisionLayer'
    ? ModuleRegistry.decisionLayer.modules
    : ModuleRegistry.executionLayer.modules
  const existingIndex = target.findIndex((item) => item.key === normalized.key)

  if (existingIndex >= 0) {
    target.splice(existingIndex, 1, normalized)
  } else {
    target.push(normalized)
  }

  const runtimeIndex = runtimeModules.findIndex((item) => item.key === normalized.key)
  if (runtimeIndex >= 0) {
    runtimeModules.splice(runtimeIndex, 1, normalized)
  } else {
    runtimeModules.push(normalized)
  }

  return normalized
}

export function getModule(key) {
  return listModules().find((module) => module.key === key)
}

export function listModules() {
  return listRegisteredModules()
}

export function getModuleRegistry() {
  return ModuleRegistry
}

export function listRegisteredModules() {
  return [
    ...ModuleRegistry.decisionLayer.modules,
    ...ModuleRegistry.executionLayer.modules,
  ]
}

export function getModuleByKey(key) {
  return getModule(key)
}
