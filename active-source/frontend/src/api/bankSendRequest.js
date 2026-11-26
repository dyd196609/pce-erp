import request from './request'

export const bankSendRequestApi = {
  list(params = {}) {
    return request({ method: 'GET', url: '/api/finance/bank-send-requests/', params, meta: { module: 'finance' } })
  },
  createFromGate(gateId, data) {
    return request({
      method: 'POST',
      url: `/api/finance/bank-send-requests/from-gate/${encodeURIComponent(gateId)}/create`,
      data,
      meta: { module: 'finance' },
    })
  },
  revalidate(requestId) {
    return request({
      method: 'POST',
      url: `/api/finance/bank-send-requests/${encodeURIComponent(requestId)}/revalidate`,
      data: {},
      meta: { module: 'finance' },
    })
  },
  blockedCanaryAttempt(scenarioCode) {
    return request({
      method: 'POST',
      url: `/api/finance/bank-send-requests/canary-pool/blocked/${encodeURIComponent(scenarioCode)}/attempt`,
      data: {},
      meta: { module: 'finance' },
    })
  },
}
