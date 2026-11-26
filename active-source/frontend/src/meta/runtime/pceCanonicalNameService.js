import {
  findPceBusinessModuleById,
  findPceBusinessModuleByRoute,
  listPceBusinessModules,
} from './pceBusinessModuleRegistry.js'

export const PCE_CANONICAL_NAME_SERVICE_VERSION = 'V1.14.2.8.4.6'

function normalizePath(value = '') {
  const raw = typeof value === 'string'
    ? value
    : value?.path || value?.fullPath || value?.routePath || ''
  const path = String(raw || '').split('?')[0].split('#')[0]
  if (!path) return '/'
  return path.startsWith('/') ? path : `/${path}`
}

export function resolvePceCanonicalName(input = {}) {
  const moduleId = typeof input === 'string' && !input.startsWith('/') ? input : input.moduleId
  const routePath = typeof input === 'string' && input.startsWith('/') ? input : input.routePath || input.path
  const moduleRecord = moduleId
    ? findPceBusinessModuleById(moduleId)
    : findPceBusinessModuleByRoute(normalizePath(routePath))

  if (!moduleRecord) {
    return {
      moduleId: moduleId || '',
      canonicalName: '',
      routePath: normalizePath(routePath),
      source: 'not_registered',
      exactMatched: false,
    }
  }

  return {
    moduleId: moduleRecord.moduleId,
    canonicalName: moduleRecord.canonicalName,
    routePath: moduleRecord.route,
    moduleName: moduleRecord.moduleName,
    moduleCode: moduleRecord.moduleCode,
    source: 'pceBusinessModuleRegistry',
    exactMatched: true,
  }
}

export function resolvePceCanonicalNameByRoute(routeOrPath = '') {
  return resolvePceCanonicalName({ routePath: normalizePath(routeOrPath) })
}

export function resolvePceCanonicalNameByModuleId(moduleId = '') {
  return resolvePceCanonicalName({ moduleId })
}

export function listPceCanonicalNameMatrix() {
  return listPceBusinessModules().map((item) => ({
    moduleId: item.moduleId,
    routePath: item.route,
    canonicalName: item.canonicalName,
    moduleName: item.moduleName,
    source: 'pceBusinessModuleRegistry',
  }))
}
