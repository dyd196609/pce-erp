export const PURCHASE_ORDER_CANONICAL_NUMBER_VERSION = 'V1.14.2.8.4.27.2.16'
export const PURCHASE_ORDER_CANONICAL_NUMBER_FIELD = 'objectNo'
export const PURCHASE_ORDER_NUMBER_PURITY_RULE = 'PURCHASE-ORDER-NUMBER-PURITY-001'
export const PURCHASE_ORDER_NUMBER_FORBIDDEN_FRAGMENTS = Object.freeze([
  'PAP-PI', 'PI-', 'QC-', 'PAP-', 'GATE', 'SOURCE', 'SRDB',
])

export const PurchaseOrderCanonicalNumber = Object.freeze({
  objectType: 'PurchaseOrder',
  field: PURCHASE_ORDER_CANONICAL_NUMBER_FIELD,
  reader: 'getPurchaseOrderNumber',
  fallbackAllowed: false,
  rule: 'NUMBER-LEGACY-BLOCK-001',
})

const text = value => String(value ?? '').trim()

export function getPurchaseOrderNumber(order = {}) {
  return text(order.objectNo)
}

export function inspectPurchaseOrderNumberPurity(order = {}) {
  const number = getPurchaseOrderNumber(order)
  const upperNumber = number.toUpperCase()
  const matchedFragments = PURCHASE_ORDER_NUMBER_FORBIDDEN_FRAGMENTS
    .filter(fragment => upperNumber.includes(fragment))
  return Object.freeze({
    number,
    canonicalField: PURCHASE_ORDER_CANONICAL_NUMBER_FIELD,
    matchedFragments: Object.freeze(matchedFragments),
    valid: Boolean(number) && matchedFragments.length === 0,
    rule: PURCHASE_ORDER_NUMBER_PURITY_RULE,
    sourceFallbackUsed: false,
    businessWriteCount: 0,
  })
}

export function assertPurePurchaseOrderNumber(order = {}) {
  const result = inspectPurchaseOrderNumberPurity(order)
  if (!result.valid) {
    throw new Error(`${PURCHASE_ORDER_NUMBER_PURITY_RULE}:${result.matchedFragments.join(',') || 'EMPTY'}`)
  }
  return result.number
}
