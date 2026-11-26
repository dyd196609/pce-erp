import request from './request'

export const supplierPerformanceApi = {
  reconciliations(params = {}) {
    return request({ method: 'GET', url: '/api/scm/supplier-reconciliations/', params, meta: { module: 'scm' } })
  },
  buyers(params = {}) {
    return request({ method: 'GET', url: '/api/scm/buyer-performance/', params, meta: { module: 'scm' } })
  },
  suppliers(params = {}) {
    return request({ method: 'GET', url: '/api/scm/supplier-performance/', params, meta: { module: 'scm' } })
  },
}
