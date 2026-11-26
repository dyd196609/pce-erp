import request from './request'

export const supplierSettlementV84Api = {
  paymentStatus(params = {}) {
    return request({
      method: 'GET',
      url: '/api/scm/supplier-payment-status/',
      params,
      meta: { module: 'scm' },
    })
  },
  settlementCompletions(params = {}) {
    return request({
      method: 'GET',
      url: '/api/scm/supplier-settlement-completions/',
      params,
      meta: { module: 'scm' },
    })
  },
}
