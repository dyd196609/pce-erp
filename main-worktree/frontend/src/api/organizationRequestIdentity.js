const IDEMPOTENT_ACTIONS = new Set([
  'SAVE_RESPONSIBILITY',
  'SAVE_POSITION_RESPONSIBILITY',
])

const pendingRequests = new Map()

function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize)
  if (value && typeof value === 'object') {
    return Object.keys(value).sort().reduce((result, key) => {
      result[key] = canonicalize(value[key])
      return result
    }, {})
  }
  return typeof value === 'string' ? value.trim() : value
}

function requestFingerprint(action, payload) {
  return JSON.stringify(canonicalize({ action, payload: payload || {} }))
}

export function createOrganizationRequestIdentity(action) {
  const uuid = globalThis.crypto?.randomUUID?.()
    || `${Date.now()}-${Math.random().toString(16).slice(2)}`
  return `organization-${String(action || '').toLowerCase()}-${uuid}`
}

export async function executeOrganizationWriteRequest({ action, payload, send }) {
  const normalizedAction = String(action || '').trim().toUpperCase()
  if (!IDEMPOTENT_ACTIONS.has(normalizedAction)) return send(null)

  const fingerprint = requestFingerprint(normalizedAction, payload)
  const requestIdentity = pendingRequests.get(fingerprint)
    || createOrganizationRequestIdentity(normalizedAction)
  pendingRequests.set(fingerprint, requestIdentity)
  try {
    const response = await send(requestIdentity)
    pendingRequests.delete(fingerprint)
    return response
  } catch (error) {
    // No HTTP response means the server commit outcome is unknown.  Keep the
    // same key so an identical user retry recovers from the formal ledger.
    // A server response is definitive (including 409), so a later user action
    // starts with a fresh request identity.
    if (error?.response) pendingRequests.delete(fingerprint)
    throw error
  }
}

export function resetOrganizationRequestIdentitiesForTests() {
  pendingRequests.clear()
}
