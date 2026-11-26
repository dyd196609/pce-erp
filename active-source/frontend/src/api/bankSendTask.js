import request from './request'

export const bankSendTaskApi = {
  list(params = {}) {
    return request({
      method: 'GET',
      url: '/api/finance/bank-send-tasks/',
      params,
      meta: { module: 'finance' },
    })
  },
  detail(id) {
    return request({
      method: 'GET',
      url: `/api/finance/bank-send-tasks/${encodeURIComponent(id)}`,
      meta: { module: 'finance' },
    })
  },
  createFromPreparation(preparationId, data) {
    return request({
      method: 'POST',
      url: `/api/finance/bank-send-tasks/from-preparation/${encodeURIComponent(preparationId)}/create`,
      data,
      meta: { module: 'finance' },
    })
  },
  replenishCanaryPool(count = 8) {
    return request({
      method: 'POST',
      url: '/api/finance/bank-send-tasks/canary-pool/replenish',
      data: { count },
      meta: { module: 'finance' },
    })
  },
}
