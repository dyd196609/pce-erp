export const PAYMENT_REQUEST_VERSION = 'V1.14.2.8.4.7.55'

export const PAYMENT_REQUEST_RUNTIME = Object.freeze({
  version: PAYMENT_REQUEST_VERSION,
  canonicalName: '付款申请',
  sourceDocumentType: 'paymentRequestPrepare',
  routePath: '/finance/payment-requests',
  currentModule: Object.freeze({ code: 'payment_request', name: '付款申请' }),
  previousModule: Object.freeze({ code: 'payment_request_prepare', name: '付款申请准备' }),
  nextModule: Object.freeze({ code: 'payment_instruction_prepare', name: '付款指令准备' }),
  productionRolloutEnabled: false,
})
