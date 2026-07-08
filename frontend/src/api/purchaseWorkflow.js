import request from '@/api/request'

// 提交
export const submitOrder = (id, data = {}) => {
  return request.post(`/api/purchase/orders/${id}/submit/`, data)
}

// 审核
export const auditOrder = (id, data = {}) => {
  return request.post(`/api/purchase/orders/${id}/audit/`, data)
}

// 复核
export const reviewOrder = (id, data = {}) => {
  return request.post(`/api/purchase/orders/${id}/review/`, data)
}

// 审批
export const approveOrder = (id, data = {}) => {
  return request.post(`/api/purchase/orders/${id}/approve/`, data)
}

// 驳回
export const rejectOrder = (id, data = {}) => {
  return request.post(`/api/purchase/orders/${id}/reject/`, data)
}

// 作废
export const cancelOrder = (id, data = {}) => {
  return request.post(`/api/purchase/orders/${id}/cancel/`, data)
}
