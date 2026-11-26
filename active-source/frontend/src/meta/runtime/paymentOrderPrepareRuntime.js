export const PAYMENT_ORDER_PREPARE_VERSION = 'V1.14.2.8.4.7.55'
export const PAYMENT_ORDER_PREPARE_CANONICAL_NAME = '正式付款单预备'
export const PAYMENT_ORDER_PREPARE_SOURCE_DOCUMENT_TYPE = 'paymentInstructionPrepare'
export const PAYMENT_ORDER_PREPARE_NEXT_MODULE = Object.freeze({
  code: 'payment_order_draft',
  canonicalName: '正式付款单草稿',
  route: '/finance/payment-order-drafts',
})
export const PAYMENT_ORDER_PREPARE_PRODUCTION_ROLLOUT_ENABLED = false
