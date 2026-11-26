const STORAGE_KEY = 'business-flow-action-audit-state-v1142'

function clone(value) {
  return JSON.parse(JSON.stringify(value ?? null))
}

function defaultState() {
  return { audits: [] }
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

export function getBusinessFlowActionAuditState() {
  return clone(state)
}

export function saveBusinessFlowActionAuditState(nextState = defaultState()) {
  state = { audits: Array.isArray(nextState.audits) ? nextState.audits : [] }
  persist()
  return getBusinessFlowActionAuditState()
}

export function listBusinessFlowActionAudits() {
  return clone(state.audits)
}

export function addBusinessFlowActionAudit(payload = {}) {
  const audit = {
    id: payload.id || `flow-audit-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
    actionCode: payload.actionCode || '',
    actionName: payload.actionName || '',
    sourceObjectType: payload.sourceObjectType || '',
    sourceObjectNo: payload.sourceObjectNo || '',
    targetObjectType: payload.targetObjectType || '',
    targetObjectNo: payload.targetObjectNo || '',
    executionStatus: payload.executionStatus || 'completed',
    sourceWritebackStatus: payload.sourceWritebackStatus || '',
    flowLinkStatus: payload.flowLinkStatus || '',
    rollbackStatus: payload.rollbackStatus || 'not_required',
    cleanupRequired: Boolean(payload.cleanupRequired),
    operator: payload.operator || 'page-user',
    time: payload.time || new Date().toISOString(),
    remark: payload.remark || '',
  }
  state.audits.unshift(audit)
  persist()
  return { success: true, audit: clone(audit) }
}
