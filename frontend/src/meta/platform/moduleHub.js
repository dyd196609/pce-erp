import { getAllGlobalModules, registerGlobalModule } from '../registry/globalModuleRegistry.js'
import { registerModule } from '../registry/moduleRegistry.js'
import { registerSchema, schemaRegistry } from '../core/schemaRegistry.js'
import { buildMenuItem, buildPage, buildRouteItem } from './uiAutoBuilder.js'
import { bindAll, bindModule } from './selfBindingEngine.js'
import { initRuntimeSystem } from '../runtime/runtimeBootstrap.js'

let initialized = false
let moduleHubSystem = initRuntimeSystem()

function ensureModuleHubSystem(system = moduleHubSystem) {
  if (!system || !system.unifiedState) {
    moduleHubSystem = initRuntimeSystem()
    return moduleHubSystem
  }

  moduleHubSystem = system
  return moduleHubSystem
}

function safeModuleList(modules = []) {
  return Array.isArray(modules)
    ? modules.filter((module) => module && typeof module === 'object')
    : []
}

function moduleBaseRoute(module = {}) {
  return module.route || `/${module.key || module.schema?.api?.module || module.name || 'module'}`
}

export function generateDetailRoutes(module = {}) {
  const baseRoute = moduleBaseRoute(module)

  return [
    {
      key: `${module.key || module.name || baseRoute}:detail`,
      path: `${baseRoute}/:id`,
      mode: 'detail',
      schema: module.schema,
      module,
      component: module.detailView || 'DefaultDetailView',
    },
    {
      key: `${module.key || module.name || baseRoute}:edit`,
      path: `${baseRoute}/:id/edit`,
      mode: 'edit',
      schema: module.schema,
      module,
      component: module.editView || 'DefaultEditView',
    },
  ]
}

function generateModuleRoutes(module = {}) {
  const listRoute = module.routeBinding || buildRouteItem(module)
  const boundRoutes = Array.isArray(module.routes) && module.routes.length > 0
    ? module.routes
    : [
        {
          ...listRoute,
          mode: 'list',
        },
        ...generateDetailRoutes(module),
      ]

  return boundRoutes.map((route) => ({
    ...route,
    schema: route.schema || module.schema,
    module: route.module || module,
  }))
}

export function registerAllModules(system = moduleHubSystem) {
  ensureModuleHubSystem(system)
  const modules = safeModuleList(bindAll(safeModuleList(getAllGlobalModules())))

  modules.forEach((module) => {
    registerModule({
      key: module.key || module.schema?.api?.module || 'module',
      name: module.name || module.label || module.key || 'Module',
      responsibility: module.layer === 'decisionLayer' ? 'Decision Layer' : 'Execution Layer',
      apiNamespace: module.apiNamespace,
      layer: module.layer,
      generated: module.generated === true,
      permission: module.permission,
      data: module.data,
      bindingMode: module.bindingMode,
      schema: module.schema,
      route: module.route,
    })

    if (module.schema && module.route) {
      generateModuleRoutes(module).forEach((route) => {
        if (route.path && !schemaRegistry[route.path]) {
          registerSchema(route.path, module.schema)
        }
      })
    }
  })

  initialized = true
  return modules
}

export function generateMenuFromModules(modules = registerAllModules()) {
  ensureModuleHubSystem()
  return safeModuleList(modules)
    .filter((module) => module.route)
    .map((module) => module.ui?.menu || buildMenuItem(module))
}

export function generateRoutesFromModules(modules = registerAllModules()) {
  ensureModuleHubSystem()
  return safeModuleList(modules)
    .filter((module) => module.route && module.schema)
    .flatMap((module) => generateModuleRoutes(module))
}

export function generatePagesFromModules(modules = registerAllModules()) {
  ensureModuleHubSystem()
  return safeModuleList(modules)
    .filter((module) => module.route && module.schema)
    .map((module) => module.ui?.page || buildPage(module))
}

export function registerPlatformModule(module) {
  ensureModuleHubSystem()
  const registered = registerGlobalModule(bindModule(module || {}))
  initialized = false
  buildModuleHub()
  return registered
}

export function buildModuleHub(system = moduleHubSystem) {
  ensureModuleHubSystem(system)
  const modules = safeModuleList(initialized ? getAllGlobalModules() : registerAllModules(moduleHubSystem))

  return {
    mode: 'V19_PLATFORM_SELF_BINDING',
    safeMode: true,
    selfBindingMode: 'ON',
    platformAutonomy: 'ACTIVE',
    modules,
    menu: generateMenuFromModules(modules),
    routes: generateRoutesFromModules(modules),
    pages: generatePagesFromModules(modules),
  }
}
