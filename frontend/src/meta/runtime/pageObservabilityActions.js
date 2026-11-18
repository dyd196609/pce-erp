export const PAGE_OBSERVABILITY_ACTIONS_KEY = Symbol('pce-page-observability-actions')

export function createEmptyPageObservabilityActions() {
  return {
    ready: false,
    refresh: null,
    buildDiagnostics: null,
  }
}

export function assertSafeDiagnosticPayload(payload) {
  const serialized = JSON.stringify(payload)
  const forbidden = [
    /"authorization"\s*:/i,
    /"cookie"\s*:/i,
    /"jwt"\s*:/i,
    /"databasePassword"\s*:/i,
    /"privateKey"\s*:/i,
    /"interfaceSecret"\s*:/i,
    /"userPassword"\s*:/i,
    /"identityDocument"\s*:/i,
  ]
  if (forbidden.some(pattern => pattern.test(serialized))) {
    throw new Error('diagnostic_payload_contains_forbidden_secret')
  }
  return serialized
}
