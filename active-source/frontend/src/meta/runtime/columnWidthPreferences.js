const STORAGE_PREFIX = 'pce:column-width:v1'
const STORAGE_VERSION = 1
const DEFAULT_MIN_WIDTH = 72
const DEFAULT_MAX_WIDTH = 960

function normalizePart(value) {
  return encodeURIComponent(String(value ?? '').trim() || 'unknown')
}

export function columnPreferenceKey(column) {
  const explicit = String(column?.columnKey || column?.rawColumnKey || '').trim()
  if (explicit) return `key:${explicit}`
  const property = String(column?.property || column?.prop || '').trim()
  if (property) return `prop:${property}`
  const label = String(column?.label || '').trim()
  if (label) return `label:${label}`
  const type = String(column?.type || '').trim()
  return type ? `type:${type}` : ''
}

export function columnWidthStorageKey({ userKey, pageId, tableId }) {
  return [STORAGE_PREFIX, normalizePart(userKey), normalizePart(pageId), normalizePart(tableId)].join(':')
}

function readNumber(value) {
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed > 0 ? Math.round(parsed) : 0
}

function clampWidth(width, column) {
  const minimum = Math.max(DEFAULT_MIN_WIDTH, readNumber(column?.minWidth) || 0)
  const maximum = Math.max(minimum, readNumber(column?.maxWidth) || DEFAULT_MAX_WIDTH)
  return Math.min(maximum, Math.max(minimum, readNumber(width) || minimum))
}

function parsePayload(raw) {
  if (!raw) return { version: STORAGE_VERSION, columns: {} }
  try {
    const payload = JSON.parse(raw)
    if (payload?.version !== STORAGE_VERSION || !payload.columns || Array.isArray(payload.columns)) {
      return { version: STORAGE_VERSION, columns: {} }
    }
    return { version: STORAGE_VERSION, columns: payload.columns }
  } catch {
    return { version: STORAGE_VERSION, columns: {} }
  }
}

export function createColumnWidthPreferenceRuntime({ storage, userKey, pageId, tableId }) {
  const persistent = Boolean(storage && String(userKey ?? '').trim() && pageId && tableId)
  const storageKey = columnWidthStorageKey({ userKey, pageId, tableId })
  const defaults = new Map()

  function columnsFrom(table) {
    const direct = table?.columns
    if (Array.isArray(direct)) return direct
    const stored = table?.store?.states?.columns?.value
    return Array.isArray(stored) ? stored : []
  }

  function capture(table) {
    for (const column of columnsFrom(table)) {
      const key = columnPreferenceKey(column)
      if (!key || defaults.has(key)) continue
      defaults.set(key, readNumber(column.width) || readNumber(column.realWidth) || readNumber(column.minWidth) || DEFAULT_MIN_WIDTH)
    }
  }

  function read() {
    if (!persistent) return { version: STORAGE_VERSION, columns: {} }
    try {
      return parsePayload(storage.getItem(storageKey))
    } catch {
      return { version: STORAGE_VERSION, columns: {} }
    }
  }

  function write(payload) {
    if (!persistent) return false
    try {
      storage.setItem(storageKey, JSON.stringify(payload))
      return true
    } catch {
      return false
    }
  }

  function setColumnWidth(column, width) {
    const resolved = clampWidth(width, column)
    column.width = resolved
    column.realWidth = resolved
    return resolved
  }

  function apply(table) {
    capture(table)
    const payload = read()
    let applied = 0
    for (const column of columnsFrom(table)) {
      const key = columnPreferenceKey(column)
      if (!key || !Object.prototype.hasOwnProperty.call(payload.columns, key)) continue
      setColumnWidth(column, payload.columns[key])
      applied += 1
    }
    table?.doLayout?.()
    return applied
  }

  function persist(width, column) {
    const key = columnPreferenceKey(column)
    if (!key) return false
    const payload = read()
    payload.columns[key] = setColumnWidth(column, width)
    return write(payload)
  }

  function reset(table) {
    capture(table)
    if (persistent) {
      try { storage.removeItem(storageKey) } catch { /* preference storage is best effort */ }
    }
    for (const column of columnsFrom(table)) {
      const key = columnPreferenceKey(column)
      if (!key || !defaults.has(key)) continue
      setColumnWidth(column, defaults.get(key))
    }
    table?.doLayout?.()
  }

  return { storageKey, persistent, capture, apply, persist, reset, read, columnsFrom }
}

