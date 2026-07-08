import { dataGateway } from '../runtime/dataGateway.js'
import { getAllGlobalModules } from '../registry/globalModuleRegistry.js'

function kebab(value = '') {
  return String(value)
    .trim()
    .replace(/([a-z])([A-Z])/g, '$1-$2')
    .replace(/[^a-zA-Z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .toLowerCase()
}

export function autoGenerateRoute(module = {}) {
  if (module.route) return module.route
  const domain = module.domain || module.key || module.schema?.api?.module || module.schema?.name || 'module'
  return `/${kebab(domain)}`
}

export function autoGenerateRoutes(module = {}) {
  const listRoute = autoGenerateRoute(module)

  return [
    {
      key: `${module.key || module.schema?.api?.module || 'module'}:list`,
      path: listRoute,
      mode: 'list',
      schema: module.schema || {},
      module,
    },
    {
      key: `${module.key || module.schema?.api?.module || 'module'}:detail`,
      path: `${listRoute}/:id`,
      mode: 'detail',
      schema: module.schema || {},
      module,
    },
    {
      key: `${module.key || module.schema?.api?.module || 'module'}:edit`,
      path: `${listRoute}/:id/edit`,
      mode: 'edit',
      schema: module.schema || {},
      module,
    },
  ]
}

export function autoGenerateUI(module = {}) {
  const schema = module.schema || {}
  const route = autoGenerateRoute(module)

  return {
    menu: {
      key: module.key,
      label: module.label || module.name || module.key,
      path: route,
      icon: module.icon || 'DataBoard',
      generated: module.generated === true,
      domain: module.domain || module.key,
    },
    page: {
      key: module.key,
      route,
      schema,
      actions: schema?.ui?.list?.actions || [],
      workflow: schema.workflow || {},
      uiSource: 'schema',
    },
    schemaUI: schema.ui || {},
  }
}

export function autoGeneratePermissions(module = {}) {
  const permission = module.permission || module.permissions || {}

  return {
    module: module.key,
    plans: permission.plans || ['pro', 'enterprise'],
    roles: permission.roles || ['admin', 'manager'],
    actions: permission.actions || ['READ', 'ANALYZE', 'EXECUTE'],
    tenantScoped: permission.tenantScoped !== false,
    source: 'SELF_BINDING',
  }
}

export function autoBindDataSource(module = {}) {
  const schema = module.schema || {}
  const apiModule = schema.api?.module || module.apiModule || module.key

  return {
    module: apiModule,
    source: 'dataGateway',
    list: (params = {}) => dataGateway.list(apiModule, params),
    detail: (id) => dataGateway.detail(apiModule, id),
    execute: (action, payload = {}) => dataGateway.execute(action, {
      ...payload,
      module: apiModule,
    }),
  }
}

export function bindModule(module = {}) {
  const route = autoGenerateRoute(module)
  const normalized = {
    ...module,
    route,
    schema: {
      ...(module.schema || {}),
      api: {
        module: module.schema?.api?.module || module.apiModule || module.key,
        ...(module.schema?.api || {}),
      },
    },
  }
  const ui = autoGenerateUI(normalized)
  const permissions = autoGeneratePermissions(normalized)
  const data = autoBindDataSource(normalized)
  const routes = autoGenerateRoutes(normalized)

  return {
    ...normalized,
    bindingMode: 'SELF_BOUND',
    selfBindingMode: 'ON',
    route,
    routes,
    routeBinding: {
      key: normalized.key,
      path: route,
      mode: 'list',
      schema: normalized.schema,
      module: normalized,
    },
    detailRouteBinding: routes[1],
    editRouteBinding: routes[2],
    ui,
    permissions,
    permission: permissions,
    data,
  }
}

export function bindAll(modules = getAllGlobalModules()) {
  return modules.map(bindModule)
}
