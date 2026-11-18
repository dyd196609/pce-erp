import request from './request'

export const supplierReconciliationV82Api = {
  differences(params = {}) {
    return request({ method: 'GET', url: '/api/scm/supplier-reconciliation-differences/', params, meta: { module: 'scm' } })
  },
  confirmations(params = {}) {
    return request({ method: 'GET', url: '/api/scm/supplier-reconciliation-confirmations/', params, meta: { module: 'scm' } })
  },
  buyerExceptions(params = {}) {
    return request({ method: 'GET', url: '/api/scm/buyer-exception-analysis/', params, meta: { module: 'scm' } })
  },
}
