import request from './request'

export const bankSendPreparationApi = {
  list(params = {}) {
    return request({
      method: 'GET',
      url: '/api/finance/bank-send-prepares/',
      params,
      meta: { module: 'finance', factLoad: true },
    })
  },
  detail(id) {
    return request({
      method: 'GET',
      url: `/api/finance/bank-send-prepares/${encodeURIComponent(id)}`,
      meta: { module: 'finance' },
    })
  },
  eligibility(id) {
    return request({
      method: 'GET',
      url: `/api/finance/bank-send-prepares/${encodeURIComponent(id)}/eligibility`,
      meta: { module: 'finance' },
    })
  },
  gate(id) {
    return request({
      method: 'GET',
      url: `/api/finance/bank-send-prepares/${encodeURIComponent(id)}/gate`,
      meta: { module: 'finance' },
    })
  },
  preview(id) {
    return request({
      method: 'GET',
      url: `/api/finance/bank-send-prepares/${encodeURIComponent(id)}/preview`,
      meta: { module: 'finance' },
    })
  },
  generatePreview(id, data) {
    return request({
      method: 'POST',
      url: `/api/finance/bank-send-prepares/${encodeURIComponent(id)}/preview/generate`,
      data,
      meta: { module: 'finance' },
    })
  },
}
