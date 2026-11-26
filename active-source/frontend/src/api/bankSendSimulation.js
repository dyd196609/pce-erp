import request from './request'

export const bankSendSimulationApi = {
  list() {
    return request({
      method: 'GET',
      url: '/api/finance/bank-send-simulations/',
      meta: { module: 'finance' },
    })
  },
  create(requestId, data) {
    return request({
      method: 'POST',
      url: `/api/finance/bank-send-simulations/from-request/${encodeURIComponent(requestId)}/create`,
      data,
      meta: { module: 'finance' },
    })
  },
  resolveRecovery(recoveryId, data) {
    return request({
      method: 'POST',
      url: `/api/finance/bank-send-simulations/recoveries/${encodeURIComponent(recoveryId)}/resolve`,
      data,
      meta: { module: 'finance' },
    })
  },
}

