import request from './request'

export const bankSendProductionReleaseApi = {
  isolationChecks() {
    return request({
      method: 'GET',
      url: '/api/finance/bank-send-dual-isolation-checks/',
      meta: { module: 'finance' },
    })
  },
  reviews() {
    return request({
      method: 'GET',
      url: '/api/finance/bank-send-production-release-reviews/',
      meta: { module: 'finance' },
    })
  },
  submitReview(id, stage, reason) {
    return request({
      method: 'POST',
      url: `/api/finance/bank-send-production-release-reviews/${id}/${stage}-review/`,
      data: { reason },
      meta: { module: 'finance' },
    })
  },
}
