import request from './request'

export const bankSendSimulationIsolationApi = {
  audits() {
    return request({
      method: 'GET',
      url: '/api/finance/bank-send-simulation-audits/',
      meta: { module: 'finance' },
    })
  },
  gates() {
    return request({
      method: 'GET',
      url: '/api/finance/bank-send-isolation-gates/',
      meta: { module: 'finance' },
    })
  },
}
