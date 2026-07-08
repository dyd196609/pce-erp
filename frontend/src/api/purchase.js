import request from '@/api/request'

// =====================
// 采购订单 API（统一版本）
// =====================

// 获取列表
export const getPurchaseOrders = (params = {}) => {
  return request({
    url: '/api/purchase/orders/',
    method: 'get',
    params,
  })
}

// 创建
export const createPurchaseOrder = (data) => {
  return request({
    url: '/api/purchase/orders/',
    method: 'post',
    data,
  })
}

// 更新
export const updatePurchaseOrder = (id, data) => {
  return request({
    url: `/api/purchase/orders/${id}/`,
    method: 'put',
    data,
  })
}

// 删除
export const deletePurchaseOrder = (id) => {
  return request({
    url: `/api/purchase/orders/${id}/`,
    method: 'delete',
  })
}

// 批量删除
export const batchDeletePurchaseOrders = (ids) => {
  return request({
    url: '/api/purchase/orders/batch-delete/',
    method: 'post',
    data: { ids },
  })
}

// 下拉选项
export const getPurchaseBaseOptions = () => {
  return request({
    url: '/api/purchase/orders/base-options/',
    method: 'get',
  })
}
