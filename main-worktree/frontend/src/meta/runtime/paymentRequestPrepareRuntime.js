export const PAYMENT_REQUEST_PREPARE_RUNTIME = Object.freeze({
  version: 'V1.14.2.8.4.7.55',
  canonicalName: '付款申请准备',
  route: '/finance/payment-applications',
  previousModule: Object.freeze({
    code: 'payable_confirmation_prepare',
    name: '应付确认准备',
  }),
  currentModule: Object.freeze({
    code: 'payment_request_prepare',
    name: '付款申请准备',
  }),
  nextModule: Object.freeze({
    code: 'payment_request',
    name: '付款申请',
  }),
})

export const PAYMENT_REQUEST_PREPARE_VERSION = PAYMENT_REQUEST_PREPARE_RUNTIME.version
