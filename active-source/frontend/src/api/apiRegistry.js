import request from '@/api/request'

export const apiRegistry = {
  purchase_order_list: () =>
    request({
      url: '/api/purchase/orders/',
      method: 'get',
      meta: { module: 'purchase' },
    }),

  purchase_order_detail: (id) =>
    request({
      url: `/api/purchase/orders/${id}/`,
      method: 'get',
      meta: { module: 'purchase' },
    }),
}
