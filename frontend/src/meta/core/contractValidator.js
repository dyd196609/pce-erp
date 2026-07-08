import { ApiContract } from './apiContract.js'
import { recordEvent, triggerAutoHealingIfMonitor } from './monitoringLayer.js'
import { getAllSchemaEntries } from './schemaRegistry.js'

const methodByAction = {
  list: 'GET',
  detail: 'GET',
  create: 'POST',
  update: 'PUT',
  delete: 'DELETE',
}

function hasPathLikeValue(value) {
  return typeof value === 'string' && value.includes('/api/')
}

function resolveProbeUrl(template, params = {}) {
  return Object.entries(params).reduce(
    (url, [key, value]) => url.replace(`:${key}`, encodeURIComponent(value)),
    template
  )
}

function joinUrl(baseUrl, path) {
  if (!baseUrl) return path
  return `${baseUrl.replace(/\/$/, '')}/${path.replace(/^\//, '')}`
}

export function validateContracts() {
  const issues = []
  const schemaEntries = getAllSchemaEntries()

  schemaEntries.forEach(({ route, schema }) => {
    const module = schema.api?.module

    if (!module || !ApiContract[module]) {
      issues.push({
        type: 'MISSING_CONTRACT',
        route,
        module,
      })
      return
    }

    const contract = ApiContract[module]

    if (!contract?.list || !contract?.detail) {
      issues.push({
        type: 'INCOMPLETE_CONTRACT',
        route,
        module,
      })
    }

    Object.entries(schema.api || {}).forEach(([key, value]) => {
      if (key !== 'module' && hasPathLikeValue(value)) {
        issues.push({
          type: 'SCHEMA_API_PATH_FORBIDDEN',
          route,
          module,
          key,
        })
      }
    })
  })

  const result = {
    valid: issues.length === 0,
    issues,
  }

  recordEvent({
    type: result.valid ? 'CONTRACT' : 'ERROR',
    module: 'contract',
    status: result.valid ? 'SUCCESS' : 'FAILED',
    issues: issues.length,
  })

  triggerAutoHealingIfMonitor(
    {
      decision: result.valid ? 'ALLOW' : 'MONITOR',
      suggestions: issues,
    },
    {
      source: 'contractValidator',
      issues,
    }
  )

  return result
}

export async function validateBackendContracts(options = {}) {
  const baseUrl = options.baseUrl || 'http://127.0.0.1:8000'
  const probeId = options.probeId ?? 999999
  const checks = []

  for (const [module, contract] of Object.entries(ApiContract)) {
    for (const [action, template] of Object.entries(contract)) {
      const method = methodByAction[action]

      if (!method || !template) continue

      const url = joinUrl(baseUrl, resolveProbeUrl(template, { id: probeId }))

      try {
        const res = await fetch(url, {
          method: 'OPTIONS',
        })

        checks.push({
          module,
          action,
          method,
          url,
          exists: res.status !== 404,
          status: res.status,
        })
      } catch (error) {
        checks.push({
          module,
          action,
          method,
          url,
          exists: false,
          error: error?.message || String(error),
        })
      }
    }
  }

  const missing = checks.filter((check) => !check.exists)

  const result = {
    valid: missing.length === 0,
    missing,
    checks,
  }

  recordEvent({
    type: result.valid ? 'CONTRACT' : 'ERROR',
    module: 'backend-contract',
    status: result.valid ? 'SUCCESS' : 'FAILED',
    issues: missing.length,
  })

  return result
}
