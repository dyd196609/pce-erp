import request from './request'

export const formalExecutionApi = {
  inventoryFacts() {
    return request({ method: 'GET', url: '/api/procurement/formal-inventory-facts/', meta: { module: 'wms' } })
  },
  qualityFacts() {
    return request({ method: 'GET', url: '/api/procurement/formal-quality-facts/', meta: { module: 'qms' } })
  },
  purchaseReceiptFacts() {
    return request({ method: 'GET', url: '/api/procurement/formal-purchase-receipt-facts/', meta: { module: 'wms' } })
  },
  payableCheckFacts() {
    return request({ method: 'GET', url: '/api/procurement/formal-payable-check-facts/', meta: { module: 'finance' } })
  },
}
