const STORAGE_KEY = 'p2p:risk:lifecycle:v1.13.26'

function createDefaultState() {
  return {
    records: {},
    riskLifecycleHistory: [],
  }
}

function clone(value) {
  return JSON.parse(JSON.stringify(value))
}

function loadState() {
  if (typeof localStorage === 'undefined') return createDefaultState()
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return createDefaultState()
    const parsed = JSON.parse(raw)
    return {
      records: parsed.records && typeof parsed.records === 'object' ? parsed.records : {},
      riskLifecycleHistory: Array.isArray(parsed.riskLifecycleHistory) ? parsed.riskLifecycleHistory : [],
    }
  } catch {
    return createDefaultState()
  }
}

function saveState(state) {
  if (typeof localStorage === 'undefined') return
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

let state = loadState()

export function processStatusForLifecycle(closureStatus = 'open') {
  return {
    open: 'not_started',
    confirmed: 'not_started',
    processing: 'processing',
    resolved: 'resolved',
    closed: 'closed',
    ignored: 'closed',
  }[closureStatus] || 'not_started'
}

function confirmStatusForLifecycle(closureStatus = 'open') {
  return ['confirmed', 'processing', 'resolved', 'closed'].includes(closureStatus) ? 'confirmed' : 'pending'
}

export function getP2PRiskLifecycleState() {
  return clone(state)
}

export function getP2PRiskLifecycleRecord(riskEventId) {
  return clone(state.records[riskEventId] || null)
}

export function transitionP2PRiskLifecycle({
  riskEventId,
  sourceDocument = '',
  beforeStatus = 'open',
  afterStatus = 'open',
  action = '',
  operator = '本地演示操作人',
  reason = '',
} = {}) {
  if (!riskEventId) return getP2PRiskLifecycleState()
  const previous = state.records[riskEventId] || {}
  const record = {
    riskEventId,
    sourceDocument: sourceDocument || previous.sourceDocument || '',
    confirmStatus: confirmStatusForLifecycle(afterStatus),
    processStatus: processStatusForLifecycle(afterStatus),
    closureStatus: afterStatus,
    riskHistory: Array.isArray(previous.riskHistory) ? [...previous.riskHistory] : [],
  }
  const historyItem = {
    riskEventId,
    sourceDocument: record.sourceDocument,
    beforeStatus,
    afterStatus,
    action,
    operator,
    time: new Date().toISOString(),
    reason,
  }
  record.riskHistory.push(historyItem)
  state = {
    records: {
      ...state.records,
      [riskEventId]: record,
    },
    riskLifecycleHistory: [
      ...state.riskLifecycleHistory,
      historyItem,
    ],
  }
  saveState(state)
  return getP2PRiskLifecycleState()
}
