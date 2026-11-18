const STORAGE_KEY = 'business-flow-link-state-v1142'

function clone(value) {
  return JSON.parse(JSON.stringify(value ?? null))
}

function defaultState() {
  return { links: [] }
}

function loadState() {
  try {
    if (typeof localStorage === 'undefined') return defaultState()
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : defaultState()
  } catch (error) {
    return defaultState()
  }
}

let state = loadState()

function persist() {
  if (typeof localStorage !== 'undefined') localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

export function getBusinessFlowLinkState() {
  return clone(state)
}

export function saveBusinessFlowLinkState(nextState = defaultState()) {
  state = { links: Array.isArray(nextState.links) ? nextState.links : [] }
  persist()
  return getBusinessFlowLinkState()
}

export function listBusinessFlowLinks() {
  return clone(state.links)
}

export function findBusinessFlowLinkBySource(actionCode, sourceObjectType, sourceObjectId) {
  return clone(state.links.find((item) => (
    item.actionCode === actionCode
    && item.sourceObjectType === sourceObjectType
    && String(item.sourceObjectId) === String(sourceObjectId)
  )) || null)
}

export function addBusinessFlowLink(payload = {}) {
  const existed = findBusinessFlowLinkBySource(payload.actionCode, payload.sourceObjectType, payload.sourceObjectId)
  if (existed?.id) return { success: false, existed: true, link: existed }
  const link = {
    id: payload.id || `flow-link-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
    actionCode: payload.actionCode || '',
    sourceObjectType: payload.sourceObjectType || '',
    sourceObjectId: payload.sourceObjectId || '',
    sourceObjectNo: payload.sourceObjectNo || '',
    targetObjectType: payload.targetObjectType || '',
    targetObjectId: payload.targetObjectId || '',
    targetObjectNo: payload.targetObjectNo || '',
    linkStatus: 'linked',
    createdAt: payload.createdAt || new Date().toISOString(),
    createdBy: payload.createdBy || 'page-user',
  }
  state.links.unshift(link)
  persist()
  return { success: true, link: clone(link) }
}
