export const PAYMENT_INSTRUCTION_PREPARE_VERSION = 'V1.14.2.8.4.7.55'
export const PAYMENT_INSTRUCTION_PREPARE_CANONICAL_NAME = '付款指令准备'
export const PAYMENT_INSTRUCTION_PREPARE_SOURCE_DOCUMENT_TYPE = 'paymentRequest'
export const PAYMENT_INSTRUCTION_PREPARE_NEXT_MODULE = Object.freeze({
  code: 'payment_order_prepare',
  canonicalName: '正式付款单预备',
  route: '/finance/payment-prepares',
})
export const PAYMENT_INSTRUCTION_PREPARE_PRODUCTION_ROLLOUT_ENABLED = false
