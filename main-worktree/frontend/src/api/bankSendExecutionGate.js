import request from './request'

export const bankSendExecutionGateApi = {
  list(params = {}) {
    return request({
      method: 'GET',
      url: '/api/finance/bank-send-execution-gates/',
      params,
      meta: { module: 'finance' },
    })
  },
  createFromTask(taskId, data) {
    return request({
      method: 'POST',
      url: `/api/finance/bank-send-execution-gates/from-task/${encodeURIComponent(taskId)}/create`,
      data,
      meta: { module: 'finance' },
    })
  },
  blockedCanaryAttempt(scenarioCode) {
    return request({
      method: 'POST',
      url: `/api/finance/bank-send-execution-gates/canary-pool/blocked/${encodeURIComponent(scenarioCode)}`,
      data: {},
      meta: { module: 'finance' },
    })
  },
}
