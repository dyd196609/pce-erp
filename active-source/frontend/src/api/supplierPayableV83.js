import request from './request'

export const supplierPayableV83Api = {
  payableConfirmations(params = {}) {
    return request({ method: 'GET', url: '/api/scm/supplier-payable-confirmations/', params, meta: { module: 'scm' } })
  },
  paymentRequests(params = {}) {
    return request({ method: 'GET', url: '/api/scm/supplier-payment-requests/', params, meta: { module: 'scm' } })
  },
  canaryActor(actor) {
    return request({
      method: 'GET',
      url: '/api/workflow/action-permissions/canary-session',
      params: { actor },
      meta: { module: 'scm' },
    })
  },
  executeWorkflowAction(data) {
    return request({
      method: 'POST',
      url: '/api/scm/supplier-settlement-workflow-actions/',
      data,
      meta: { module: 'scm' },
    })
  },
  inspectWorkflowAction(params) {
    return request({
      method: 'GET',
      url: '/api/scm/supplier-settlement-workflow-actions/',
      params,
      meta: { module: 'scm' },
    })
  },
}
