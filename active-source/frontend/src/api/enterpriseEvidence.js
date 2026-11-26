import request from './request'

export function evidenceRead(url, params = {}) {
  return request({ url, params, timeout: 120000, meta: { readOnly: true } })
}

export function evidenceWrite(url, data) {
  return request({ url, method: 'POST', data })
}

export const followupRoot = '/api/sales/production-followup/'
export const bindingUrl = '/api/sales/customer-bindings/'
export const customerRoot = '/api/sales/customer-progress/orders/'
export const riskRoot = '/api/analytics/procurement-risks/'
export const orderUrl = (root, orderNo) => root + encodeURIComponent(orderNo) + '/'
