export const LEGACY_FOUNDATION_KEYS = Object.freeze([
  'manufacturing-foundation-state-v1',
  'enterprise-operation-state-v1',
])

function countRecords(value) {
  if (!value || typeof value !== 'object') return 0
  return Object.values(value).reduce((total, item) => total + (Array.isArray(item) ? item.length : 0), 0)
}

export function inspectLegacyFoundationStorage(storage) {
  return LEGACY_FOUNDATION_KEYS.map((key) => {
    const raw = storage.getItem(key)
    if (raw === null) return Object.freeze({ key, exists: false, parseable: false, recordCount: 0, classification: 'NOT_PRESENT' })
    try {
      const parsed = JSON.parse(raw)
      return Object.freeze({ key, exists: true, parseable: true, recordCount: countRecords(parsed), classification: 'UNKNOWN' })
    } catch (_) {
      return Object.freeze({ key, exists: true, parseable: false, recordCount: null, classification: 'UNKNOWN' })
    }
  })
}
