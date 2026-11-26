import request from './request'

export const bankSendExecutionFrameworkApi = {
  frameworks() {
    return request({
      method: 'GET',
      url: '/api/finance/bank-send-execution-framework-reviews/',
      meta: { module: 'finance' },
    })
  },
  adapters() {
    return request({
      method: 'GET',
      url: '/api/finance/bank-connector-adapter-reviews/',
      meta: { module: 'finance' },
    })
  },
}
