import { ApiContract } from './apiContract.js'
import { executionGateway } from '../gateway/executionGateway.js'

function buildAutoApiTemplate(module, action) {
  if (!module || !action) {
    throw new Error(`[API CONTRACT] Missing: ${module}.${action}`)
  }

  if (['detail', 'update', 'delete'].includes(action)) {
    return `/api/execution/${module}/${action}/:id`
  }

  return `/api/execution/${module}/${action}`
}

export function getApiTemplate(module, action) {
  return ApiContract?.[module]?.[action] || buildAutoApiTemplate(module, action)
}

export function resolveApi(module, action, params = {}) {
  let url = getApiTemplate(module, action)

  Object.keys(params).forEach((key) => {
    url = url.replace(`:${key}`, encodeURIComponent(params[key]))
  })

  return url
}

export function parsePath(path = '') {
  const normalized = String(path || '').split('?')[0]
  const parts = normalized.split('/').filter(Boolean)
  const executionIndex = parts.findIndex((part) => part === 'execution')
  const module = executionIndex >= 0 ? parts[executionIndex + 1] : parts[0]
  const action = executionIndex >= 0 ? parts[executionIndex + 2] : parts[1]
  const id = parts.includes('detail') || parts.includes('update') || parts.includes('delete')
    ? parts[parts.length - 1]
    : null

  return {
    module,
    action: action || 'list',
    id: id && !['detail', 'update', 'delete'].includes(id) ? id : null,
  }
}

export function resolveAPI(path, params = {}) {
  const parsed = parsePath(path)

  return executionGateway.executeRequest({
    module: parsed.module,
    action: parsed.action,
    tenantId: params.tenantId,
    params: {
      ...params,
      id: params.id || parsed.id,
    },
  })
}
