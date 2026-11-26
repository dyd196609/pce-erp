import request from './request'

export const supplierSettlementFormalApi = {
  inspect(params) {
    return request({
      method: 'GET',
      url: '/api/scm/supplier-settlement-formal-actions/',
      params,
      meta: { module: 'scm' },
    })
  },
  execute(data) {
    return request({
      method: 'POST',
      url: '/api/scm/supplier-settlement-formal-actions/',
      data,
      meta: { module: 'scm' },
    })
  },
  chain(orderId) {
    return request({
      method: 'GET',
      url: `/api/scm/supplier-settlement-formal-chain/${orderId}/`,
      meta: { module: 'scm' },
    })
  },
}
