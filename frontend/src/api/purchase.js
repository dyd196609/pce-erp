import request from './request'

export function getPurchaseOrders(params = {}) {
    return request.get('/api/purchase/orders/', { params })
}

export function createPurchaseOrder(data) {
    return request.post('/api/purchase/orders/', data)
}

export function updatePurchaseOrder(id, data) {
    return request.put(`/api/purchase/orders/${id}/`, data)
}

export function deletePurchaseOrder(id) {
    return request.delete(`/api/purchase/orders/${id}/`)
}

export function batchDeletePurchaseOrders(ids) {
    return request.post('/api/purchase/orders/batch-delete/', { ids })
}

export function getPurchaseBaseOptions() {
    return request.get('/api/purchase/orders/base-options/')
}