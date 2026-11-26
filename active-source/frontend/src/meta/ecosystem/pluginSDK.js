import { registerPlatformModule } from '../platform/moduleHub.js'
import { runInSandbox } from './sandboxRuntime.js'

const pluginRegistry = new Map()
const workflowRegistry = new Map()
const apiRegistry = new Map()

function validateSchema(schema = {}) {
  if (!schema.name && !schema.api?.module) {
    throw new Error('[PLUGIN SDK] schema.name or schema.api.module is required')
  }

  if (!Array.isArray(schema?.ui?.list?.columns)) {
    throw new Error('[PLUGIN SDK] schema.ui.list.columns is required')
  }

  return {
    ...schema,
    api: {
      module: schema.api?.module || schema.name,
    },
  }
}

export function registerWorkflow(workflow = {}, pluginId = 'anonymousPlugin') {
  const key = workflow.entity || pluginId
  const normalized = {
    entity: key,
    states: workflow.states || ['DRAFT', 'ACTIVE', 'CLOSED'],
    transitions: workflow.transitions || [
      { from: 'DRAFT', to: 'ACTIVE' },
      { from: 'ACTIVE', to: 'CLOSED' },
    ],
    actions: workflow.actions || {
      ACTIVATE: ['DRAFT'],
      CLOSE: ['ACTIVE'],
    },
  }

  workflowRegistry.set(key, normalized)
  return normalized
}

export function exposeAPIs(api = {}, pluginId = 'anonymousPlugin') {
  const normalized = {
    list: api.list || `/api/execution/${pluginId}/list`,
    detail: api.detail || `/api/execution/${pluginId}/detail/:id`,
    create: api.create || `/api/execution/${pluginId}/create`,
    update: api.update || `/api/execution/${pluginId}/update/:id`,
    delete: api.delete || `/api/execution/${pluginId}/delete/:id`,
  }

  apiRegistry.set(pluginId, normalized)
  return normalized
}

export function registerPlugin(plugin = {}) {
  const pluginId = plugin.id || plugin.module?.key || plugin.schema?.api?.module || plugin.schema?.name
  const schema = validateSchema(plugin.schema || {})
  const workflow = registerWorkflow(plugin.workflow || schema.workflow || {}, pluginId)
  const api = exposeAPIs(plugin.api || {}, pluginId)
  const module = registerPlatformModule({
    key: plugin.module?.key || pluginId,
    name: plugin.module?.name || plugin.name || schema.meta?.title || pluginId,
    label: plugin.module?.label || plugin.name || schema.meta?.title || pluginId,
    route: plugin.module?.route || plugin.route || `/${plugin.module?.key || pluginId}`,
    icon: plugin.module?.icon || 'Box',
    layer: 'executionLayer',
    generated: true,
    pluginId,
    developerId: plugin.developerId || 'unknownDeveloper',
    apiNamespace: `/api/execution/${schema.api.module}`,
    permission: plugin.permission || {
      plans: ['pro', 'enterprise'],
      roles: ['admin', 'manager'],
    },
    schema: {
      ...schema,
      workflow,
    },
  })

  const registration = {
    id: pluginId,
    name: plugin.name || module.name,
    developerId: plugin.developerId || 'unknownDeveloper',
    status: 'REGISTERED',
    sandbox: true,
    module,
    workflow,
    api,
    registeredAt: Date.now(),
  }

  pluginRegistry.set(pluginId, registration)

  return registration
}

export function runPlugin(pluginId, task = {}) {
  const plugin = pluginRegistry.get(pluginId)

  if (!plugin) {
    return {
      status: 'PLUGIN_NOT_FOUND',
      pluginId,
    }
  }

  return runInSandbox(plugin, task)
}

export function getPluginRegistry() {
  return Array.from(pluginRegistry.values())
}

export function getPlugin(pluginId) {
  return pluginRegistry.get(pluginId)
}

export function getRegisteredWorkflows() {
  return Array.from(workflowRegistry.values())
}

export function getExposedAPIs() {
  return Array.from(apiRegistry.entries()).map(([pluginId, api]) => ({
    pluginId,
    api,
  }))
}
