import { getPurchaseOrderNumber, inspectPurchaseOrderNumberPurity } from
  '../domain/scm/purchaseOrder/purchaseOrderCanonicalNumber.js'

export const PURCHASE_ORDER_NUMBER_RUNTIME_VERSION_V11428427212 =
  'V1.14.2.8.4.27.2.14'
export const PURCHASE_ORDER_NUMBER_CANONICAL_RULE_V11428427212 =
  'PURCHASE-ORDER-NUMBER-CANONICAL-002'
export const PURCHASE_ORDER_NUMBER_SOURCE_CHECK_RULE_V11428427213 =
  'PURCHASE-ORDER-NUMBER-SOURCE-CHECK-002'
export const PURCHASE_ORDER_CANONICAL_NUMBER_FIELD_V11428427213 = 'objectNo'

const digits = value => String(value ?? '').replace(/\D/g, '')

export function createCanonicalPurchaseOrderNumberV11428427212({
  issuedAt = new Date().toISOString(), sequence = 1,
} = {}) {
  const timestamp = digits(issuedAt).slice(0, 17).padEnd(17, '0')
  const ordinal = String(Math.max(1, Number(sequence) || 1)).padStart(3, '0')
  const objectNo = `PO${timestamp}${ordinal}`
  return Object.freeze({
    objectNo,
    poNo: objectNo,
    source: 'PurchaseOrderNumberRuntime',
    sourceBusinessKeyUsed: false,
    rule: PURCHASE_ORDER_NUMBER_CANONICAL_RULE_V11428427212,
    businessWriteCount: 0,
  })
}

export function assertCanonicalPurchaseOrderNumberV11428427212(purchaseOrder = {}) {
  const value = getPurchaseOrderNumber(purchaseOrder)
  const sourceValues = [purchaseOrder.sourceGateId, purchaseOrder.sourcePurchaseRequestId,
    purchaseOrder.sourceInquiryId, purchaseOrder.sourceQuoteComparisonId]
    .map(item => String(item || '').trim()).filter(Boolean)
  const purity = inspectPurchaseOrderNumberPurity(purchaseOrder)
  return Object.freeze({
    value,
    field: PURCHASE_ORDER_CANONICAL_NUMBER_FIELD_V11428427213,
    valid: /^PO[A-Z0-9-]+$/i.test(value) && purity.valid
      && !sourceValues.some(source => value.includes(source)),
    sourceValues: Object.freeze(sourceValues),
    forbiddenFragments: purity.matchedFragments,
    rule: PURCHASE_ORDER_NUMBER_SOURCE_CHECK_RULE_V11428427213,
  })
}
