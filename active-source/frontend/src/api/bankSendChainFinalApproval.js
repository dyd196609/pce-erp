import request from './request'

export const bankSendChainFinalApprovalApi = {
  traces() {
    return request({
      method: 'GET',
      url: '/api/finance/bank-send-chain-traces/',
      meta: { module: 'finance' },
    })
  },
  approvals() {
    return request({
      method: 'GET',
      url: '/api/finance/bank-send-final-approvals/',
      meta: { module: 'finance' },
    })
  },
  firstApprove(id, reason) {
    return request({
      method: 'POST',
      url: `/api/finance/bank-send-final-approvals/${id}/first-approve/`,
      data: { reason },
      meta: { module: 'finance' },
    })
  },
  secondApprove(id, reason) {
    return request({
      method: 'POST',
      url: `/api/finance/bank-send-final-approvals/${id}/second-approve/`,
      data: { reason },
      meta: { module: 'finance' },
    })
  },
}
