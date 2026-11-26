export const TAB_AUTH_TOKEN_KEY = 'pce_tab_auth_token_v1'
export const TAB_AUTH_IDENTITY_KEY = 'pce_current_identity_v1'
export const TAB_AUTH_EPOCH_KEY = 'pce_tab_auth_epoch_v1'

function tabStorage() {
  return typeof window === 'undefined' ? null : window.sessionStorage
}

function sharedStorage() {
  return typeof window === 'undefined' ? null : window.localStorage
}

function isUsableServerJwt(token) {
  try {
    const [, encodedPayload] = String(token || '').split('.')
    if (!encodedPayload) return false
    const normalized = encodedPayload.replace(/-/g, '+').replace(/_/g, '/')
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=')
    const payload = JSON.parse(globalThis.atob(padded))
    return !payload.exp || Number(payload.exp) * 1000 > Date.now() + 5000
  } catch { return false }
}

function bumpEpoch(storage = tabStorage()) {
  if (!storage) return 0
  const next = Number(storage.getItem(TAB_AUTH_EPOCH_KEY) || 0) + 1
  storage.setItem(TAB_AUTH_EPOCH_KEY, String(next))
  return next
}

// Compatibility is deliberately a one-time claim. The first already-open tab
// can keep the former login, while the shared copy is removed so another tab
// cannot silently inherit that actor.
export function claimLegacySharedAuthentication(
  session = tabStorage(), local = sharedStorage(),
) {
  if (!session || !local || session.getItem(TAB_AUTH_TOKEN_KEY)) return false
  const token = String(local.getItem('token') || '').trim()
  if (!isUsableServerJwt(token)) {
    local.removeItem('token')
    local.removeItem(TAB_AUTH_IDENTITY_KEY)
    return false
  }
  session.setItem(TAB_AUTH_TOKEN_KEY, token)
  const identity = local.getItem(TAB_AUTH_IDENTITY_KEY)
  if (identity) session.setItem(TAB_AUTH_IDENTITY_KEY, identity)
  local.removeItem('token')
  local.removeItem(TAB_AUTH_IDENTITY_KEY)
  bumpEpoch(session)
  return true
}

export function getTabAuthToken(storage = tabStorage()) {
  claimLegacySharedAuthentication(storage, sharedStorage())
  const token = String(storage?.getItem(TAB_AUTH_TOKEN_KEY) || '').trim()
  return isUsableServerJwt(token) ? token : ''
}

export function getTabAuthEpoch(storage = tabStorage()) {
  return Number(storage?.getItem(TAB_AUTH_EPOCH_KEY) || 0)
}

export function setTabAuthToken(token, storage = tabStorage()) {
  if (!storage) return 0
  const normalized = String(token || '').trim()
  if (normalized) storage.setItem(TAB_AUTH_TOKEN_KEY, normalized)
  else storage.removeItem(TAB_AUTH_TOKEN_KEY)
  return bumpEpoch(storage)
}

export function rememberTabIdentity(user, storage = tabStorage()) {
  const identity = user ? {
    userId: user.id ?? user.userId ?? user.identity?.userId ?? null,
    username: String(user.username ?? user.identity?.username ?? ''),
    realName: String(user.real_name ?? user.realName ?? user.identity?.realName ?? ''),
    companyId: user.company_id ?? user.companyId ?? user.organization?.id ?? null,
  } : null
  if (!storage || !identity?.username) return null
  storage.setItem(TAB_AUTH_IDENTITY_KEY, JSON.stringify(identity))
  return identity
}

export function readTabIdentity(storage = tabStorage()) {
  try { return JSON.parse(storage?.getItem(TAB_AUTH_IDENTITY_KEY) || 'null') }
  catch { return null }
}

export function clearTabAuthentication(storage = tabStorage()) {
  if (!storage) return 0
  storage.removeItem(TAB_AUTH_TOKEN_KEY)
  storage.removeItem(TAB_AUTH_IDENTITY_KEY)
  return bumpEpoch(storage)
}

export function authenticationContextChanged(requestEpoch, storage = tabStorage()) {
  return Number(requestEpoch) !== getTabAuthEpoch(storage)
}
